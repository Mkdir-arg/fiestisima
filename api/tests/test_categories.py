"""GET/POST/PATCH/DELETE /categories: catalog labels, the v2-15 asymmetry
(operatore POST -> 403, operatore PATCH/DELETE -> 404), tenant isolation
and duplicate-name handling.
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


async def _create_category(client, token: str, name: str):
    return await client.post("/categories", headers=_auth(token), json={"name": name})


# ------------------------------------------------------------------- list

@pytest.mark.parametrize("email_attr", ["titolare_email", "responsabile_email", "operatore_email"])
async def test_every_role_lists_categories(client, business, email_attr):
    titolare_token = await _access_token(client, business.titolare_email, business.password)
    create_resp = await _create_category(client, titolare_token, f"Latticini-{uuid.uuid4().hex[:6]}")
    assert create_resp.status_code == 201, create_resp.text

    token = await _access_token(client, getattr(business, email_attr), business.password)
    resp = await client.get("/categories", headers=_auth(token))
    assert resp.status_code == 200
    assert create_resp.json()["id"] in {c["id"] for c in resp.json()}


async def test_tenant_isolation_on_list(client, business, other_business):
    other_token = await _access_token(client, other_business.titolare_email, other_business.password)
    other_create = await _create_category(client, other_token, f"OnlyOther-{uuid.uuid4().hex[:6]}")
    assert other_create.status_code == 201, other_create.text

    token = await _access_token(client, business.titolare_email, business.password)
    resp = await client.get("/categories", headers=_auth(token))
    assert resp.status_code == 200
    assert other_create.json()["id"] not in {c["id"] for c in resp.json()}


# ----------------------------------------------------------------- create

async def test_operatore_cannot_create_category(client, business):
    token = await _access_token(client, business.operatore_email, business.password)
    resp = await _create_category(client, token, "Should Not Exist")
    assert resp.status_code == 403


async def test_responsabile_creates_category(client, business):
    token = await _access_token(client, business.responsabile_email, business.password)
    resp = await _create_category(client, token, f"Bevande-{uuid.uuid4().hex[:6]}")
    assert resp.status_code == 201, resp.text
    assert "id" in resp.json()


async def test_duplicate_name_is_409(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    name = f"Duplicata-{uuid.uuid4().hex[:6]}"
    first = await _create_category(client, token, name)
    assert first.status_code == 201, first.text

    second = await _create_category(client, token, name)
    assert second.status_code == 409, second.text
    assert second.json()["detail"] == "name_taken"


async def test_empty_name_is_422(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    resp = await _create_category(client, token, "   ")
    assert resp.status_code == 422


# ------------------------------------------------------------------- patch

async def test_titolare_renames_category(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    create_resp = await _create_category(client, token, f"Original-{uuid.uuid4().hex[:6]}")
    category_id = create_resp.json()["id"]

    new_name = f"Rinominata-{uuid.uuid4().hex[:6]}"
    resp = await client.patch(
        f"/categories/{category_id}", headers=_auth(token), json={"name": new_name}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == new_name


async def test_operatore_patch_is_404(client, business):
    titolare_token = await _access_token(client, business.titolare_email, business.password)
    create_resp = await _create_category(client, titolare_token, f"Fixed-{uuid.uuid4().hex[:6]}")
    category_id = create_resp.json()["id"]

    operatore_token = await _access_token(client, business.operatore_email, business.password)
    resp = await client.patch(
        f"/categories/{category_id}", headers=_auth(operatore_token), json={"name": "Nope"}
    )
    assert resp.status_code == 404


async def test_patch_other_business_category_is_404(client, business, other_business):
    other_token = await _access_token(client, other_business.titolare_email, other_business.password)
    other_create = await _create_category(client, other_token, f"OtherOnly-{uuid.uuid4().hex[:6]}")
    other_id = other_create.json()["id"]

    token = await _access_token(client, business.titolare_email, business.password)
    resp = await client.patch(
        f"/categories/{other_id}", headers=_auth(token), json={"name": "Stolen"}
    )
    assert resp.status_code == 404


# ------------------------------------------------------------------ delete

async def test_titolare_deletes_category(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    create_resp = await _create_category(client, token, f"ToDelete-{uuid.uuid4().hex[:6]}")
    category_id = create_resp.json()["id"]

    resp = await client.delete(f"/categories/{category_id}", headers=_auth(token))
    assert resp.status_code == 204

    list_resp = await client.get("/categories", headers=_auth(token))
    assert category_id not in {c["id"] for c in list_resp.json()}


async def test_operatore_delete_is_404(client, business):
    titolare_token = await _access_token(client, business.titolare_email, business.password)
    create_resp = await _create_category(client, titolare_token, f"Protected-{uuid.uuid4().hex[:6]}")
    category_id = create_resp.json()["id"]

    operatore_token = await _access_token(client, business.operatore_email, business.password)
    resp = await client.delete(f"/categories/{category_id}", headers=_auth(operatore_token))
    assert resp.status_code == 404


async def test_delete_nonexistent_category_is_404(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    resp = await client.delete(f"/categories/{uuid.uuid4()}", headers=_auth(token))
    assert resp.status_code == 404


async def test_delete_category_used_by_product_sets_null(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    create_cat = await _create_category(client, token, f"Linked-{uuid.uuid4().hex[:6]}")
    category_id = create_cat.json()["id"]

    create_product = await client.post(
        "/products",
        headers=_auth(token),
        json={"name": "Prodotto Con Categoria", "unit": "pz", "storage": "dispensa",
              "category_id": category_id},
    )
    assert create_product.status_code == 201, create_product.text
    product_id = create_product.json()["id"]

    resp = await client.delete(f"/categories/{category_id}", headers=_auth(token))
    assert resp.status_code == 204

    get_product = await client.get(f"/products/{product_id}", headers=_auth(token))
    assert get_product.json()["category_id"] is None
