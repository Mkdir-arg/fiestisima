"""GET/POST/PATCH /suppliers: directory search, the v2-15 asymmetry
(operatore POST -> 403, operatore PATCH -> 404), no DELETE endpoint,
tenant isolation and duplicate-name handling.
"""
import uuid

import pytest


async def _login(client, email: str, password: str):
    return await client.post("/auth/login", json={"email": email, "password": password})


async def _access_token(client, email: str, password: str) -> str:
    resp = await _login(client, email, password)
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create_supplier(client, token: str, **overrides):
    payload = {"name": f"Fornitore {uuid.uuid4().hex[:8]}"}
    payload.update(overrides)
    return await client.post("/suppliers", headers=_auth(token), json=payload)


# ------------------------------------------------------------------- list

async def test_operatore_lists_but_cannot_create(client, business):
    operatore_token = await _access_token(client, business.operatore_email, business.password)

    list_resp = await client.get("/suppliers", headers=_auth(operatore_token))
    assert list_resp.status_code == 200

    create_resp = await _create_supplier(client, operatore_token)
    assert create_resp.status_code == 403


async def test_search_by_name(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    await _create_supplier(client, token, name="Metro Ingrosso")
    await _create_supplier(client, token, name="Bofrost")

    resp = await client.get("/suppliers", headers=_auth(token), params={"search": "metro"})
    assert resp.status_code == 200
    assert {s["name"] for s in resp.json()} == {"Metro Ingrosso"}


async def test_tenant_isolation_on_list(client, business, other_business):
    other_token = await _access_token(client, other_business.titolare_email, other_business.password)
    other_create = await _create_supplier(client, other_token, name="Solo Altro Fornitore")
    assert other_create.status_code == 201, other_create.text

    token = await _access_token(client, business.titolare_email, business.password)
    resp = await client.get("/suppliers", headers=_auth(token))
    assert resp.status_code == 200
    assert other_create.json()["id"] not in {s["id"] for s in resp.json()}


# ----------------------------------------------------------------- create

async def test_responsabile_creates_supplier_with_full_details(client, business):
    token = await _access_token(client, business.responsabile_email, business.password)
    resp = await _create_supplier(
        client, token, name="Fresh Market", phone="+391234567890",
        email="ordini@freshmarket.invalid", vat_number="IT12345678901",
        address="Via Roma 1", notes="Consegna il martedi",
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["phone"] == "+391234567890"
    assert body["active"] is True


async def test_titolare_creates_supplier_with_name_only(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    resp = await _create_supplier(client, token)
    assert resp.status_code == 201, resp.text
    assert resp.json()["phone"] is None


async def test_duplicate_name_is_409(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    name = f"Duplicato-{uuid.uuid4().hex[:6]}"
    first = await _create_supplier(client, token, name=name)
    assert first.status_code == 201, first.text

    second = await _create_supplier(client, token, name=name)
    assert second.status_code == 409, second.text
    assert second.json()["detail"] == "name_taken"


# --------------------------------------------------------------------- get

async def test_get_other_business_supplier_is_404(client, business, other_business):
    other_token = await _access_token(client, other_business.titolare_email, other_business.password)
    other_create = await _create_supplier(client, other_token)
    other_id = other_create.json()["id"]

    token = await _access_token(client, business.titolare_email, business.password)
    resp = await client.get(f"/suppliers/{other_id}", headers=_auth(token))
    assert resp.status_code == 404


async def test_get_supplier_visible_to_operatore(client, business):
    titolare_token = await _access_token(client, business.titolare_email, business.password)
    create_resp = await _create_supplier(client, titolare_token)
    supplier_id = create_resp.json()["id"]

    operatore_token = await _access_token(client, business.operatore_email, business.password)
    resp = await client.get(f"/suppliers/{supplier_id}", headers=_auth(operatore_token))
    assert resp.status_code == 200


# ------------------------------------------------------------------- patch

async def test_operatore_patch_is_404(client, business):
    titolare_token = await _access_token(client, business.titolare_email, business.password)
    create_resp = await _create_supplier(client, titolare_token)
    supplier_id = create_resp.json()["id"]

    operatore_token = await _access_token(client, business.operatore_email, business.password)
    resp = await client.patch(
        f"/suppliers/{supplier_id}", headers=_auth(operatore_token), json={"phone": "123"}
    )
    assert resp.status_code == 404


async def test_titolare_patches_phone(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    create_resp = await _create_supplier(client, token)
    supplier_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/suppliers/{supplier_id}", headers=_auth(token), json={"phone": "+390000000"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["phone"] == "+390000000"


async def test_deactivate_hides_from_default_list(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    create_resp = await _create_supplier(client, token)
    supplier_id = create_resp.json()["id"]

    patch_resp = await client.patch(
        f"/suppliers/{supplier_id}", headers=_auth(token), json={"active": False}
    )
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["active"] is False

    default_list = await client.get("/suppliers", headers=_auth(token))
    assert supplier_id not in {s["id"] for s in default_list.json()}

    full_list = await client.get(
        "/suppliers", headers=_auth(token), params={"include_inactive": "true"}
    )
    assert supplier_id in {s["id"] for s in full_list.json()}


async def test_empty_patch_is_422(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    create_resp = await _create_supplier(client, token)
    supplier_id = create_resp.json()["id"]

    resp = await client.patch(f"/suppliers/{supplier_id}", headers=_auth(token), json={})
    assert resp.status_code == 422
    assert resp.json()["detail"] == "empty_patch"


async def test_patch_null_on_required_column_is_422(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    create_resp = await _create_supplier(client, token)
    supplier_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/suppliers/{supplier_id}", headers=_auth(token), json={"name": None}
    )
    assert resp.status_code == 422, resp.text
    assert isinstance(resp.json()["detail"], list)


async def test_no_delete_endpoint(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    create_resp = await _create_supplier(client, token)
    supplier_id = create_resp.json()["id"]

    resp = await client.delete(f"/suppliers/{supplier_id}", headers=_auth(token))
    assert resp.status_code == 405
