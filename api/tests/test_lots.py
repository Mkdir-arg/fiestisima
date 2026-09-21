"""POST/GET/PATCH /lots, GET /lots/expiring: the carico transaction (lot +
opening movement), the price/document masking every role gets from
lots_view, filters, PATCH's titolare/responsabile-only gate, and the
scadenze list's status/days-left computation.
"""
import uuid
from datetime import date, timedelta

import pytest

from app.db import as_owner


async def _login(client, email: str, password: str):
    return await client.post("/auth/login", json={"email": email, "password": password})


async def _access_token(client, email: str, password: str) -> str:
    resp = await _login(client, email, password)
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create_product(client, token: str, **overrides) -> str:
    payload = {"name": f"Prodotto {uuid.uuid4().hex[:8]}", "unit": "kg", "storage": "dispensa"}
    payload.update(overrides)
    resp = await client.post("/products", headers=_auth(token), json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_lot(client, token: str, product_id: str, **overrides):
    payload = {
        "product_id": product_id,
        "lot_code": f"LOT-{uuid.uuid4().hex[:8]}",
        "quantity": "10",
    }
    payload.update(overrides)
    return await client.post("/lots", headers=_auth(token), json=payload)


@pytest.fixture
async def cleanup_lots():
    """lots/movements created through the API in these tests are never
    covered by the `business` fixture's own teardown - that teardown
    asserts 0 leftover lots/movements before it ever touches profiles
    (see conftest.py), so every test here must clean up its own rows."""
    lot_ids: list[uuid.UUID] = []
    yield lot_ids
    async with as_owner() as conn:
        for lot_id in lot_ids:
            await conn.execute("delete from movements where lot_id = %s", (lot_id,))
            await conn.execute("delete from lots where id = %s", (lot_id,))


# ----------------------------------------------------------------- create

async def test_carico_creates_lot_and_movement(client, business, cleanup_lots):
    token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, token)

    resp = await _create_lot(client, token, product_id, quantity="24")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    cleanup_lots.append(uuid.UUID(body["id"]))
    assert body["stock"] == "24"
    assert "movement_id" in body

    stock_resp = await client.get(
        "/stock/lots", headers=_auth(token), params={"lot_id": body["id"]}
    )
    assert stock_resp.json()[0]["stock"] == "24"


async def test_operatore_can_register_carico(client, business, cleanup_lots):
    titolare_token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, titolare_token)

    operatore_token = await _access_token(client, business.operatore_email, business.password)
    resp = await _create_lot(client, operatore_token, product_id, quantity="5")
    assert resp.status_code == 201, resp.text
    cleanup_lots.append(uuid.UUID(resp.json()["id"]))
    # docs/07: goods-in is everyone's job - lots_insert has no role gate.
    assert resp.json()["unit_price"] is None  # never sent, and hidden anyway


async def test_repeated_carico_merges_into_existing_lot(client, business, cleanup_lots):
    token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, token)
    lot_code = f"LOT-{uuid.uuid4().hex[:8]}"

    first = await _create_lot(client, token, product_id, lot_code=lot_code, quantity="10")
    assert first.status_code == 201, first.text
    cleanup_lots.append(uuid.UUID(first.json()["id"]))

    second = await _create_lot(client, token, product_id, lot_code=lot_code, quantity="5")
    assert second.status_code == 201, second.text
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["stock"] == "15"

    list_resp = await client.get("/lots", headers=_auth(token), params={"product_id": product_id})
    assert len(list_resp.json()) == 1


async def test_carico_duplicate_client_id_is_idempotent(client, business, cleanup_lots):
    token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, token)
    client_id = str(uuid.uuid4())

    first = await _create_lot(client, token, product_id, quantity="3", client_id=client_id)
    assert first.status_code == 201, first.text
    cleanup_lots.append(uuid.UUID(first.json()["id"]))

    retry = await _create_lot(
        client, token, product_id, quantity="3", client_id=client_id,
        lot_code=first.json()["lot_code"],
    )
    assert retry.status_code == 201, retry.text
    assert retry.json()["movement_id"] == first.json()["movement_id"]
    # No duplicate movement: the stock is still 3, not 6.
    assert retry.json()["stock"] == "3"


# ---------------------------------------------------------- price masking

async def test_operatore_never_sees_price_or_document(client, business, cleanup_lots):
    token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, token)

    resp = await _create_lot(
        client, token, product_id, unit_price="9.50",
        document_url="https://example.invalid/ddt.pdf",
    )
    lot_id = resp.json()["id"]
    cleanup_lots.append(uuid.UUID(lot_id))

    operatore_token = await _access_token(client, business.operatore_email, business.password)

    get_resp = await client.get(f"/lots/{lot_id}", headers=_auth(operatore_token))
    assert get_resp.status_code == 200
    assert get_resp.json()["unit_price"] is None
    assert get_resp.json()["document_url"] is None

    list_resp = await client.get(
        "/lots", headers=_auth(operatore_token), params={"product_id": product_id}
    )
    assert list_resp.json()[0]["unit_price"] is None
    assert list_resp.json()[0]["document_url"] is None


async def test_titolare_and_responsabile_see_price(client, business, cleanup_lots):
    token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, token)
    resp = await _create_lot(
        client, token, product_id, unit_price="9.50",
        document_url="https://example.invalid/ddt.pdf",
    )
    lot_id = resp.json()["id"]
    cleanup_lots.append(uuid.UUID(lot_id))

    for email_attr in ("titolare_email", "responsabile_email"):
        t = await _access_token(client, getattr(business, email_attr), business.password)
        get_resp = await client.get(f"/lots/{lot_id}", headers=_auth(t))
        assert get_resp.json()["unit_price"] == "9.50"
        assert get_resp.json()["document_url"] == "https://example.invalid/ddt.pdf"


# --------------------------------------------------------------------- get

async def test_get_other_business_lot_is_404(client, business, other_business, cleanup_lots):
    other_token = await _access_token(client, other_business.titolare_email, other_business.password)
    other_product = await _create_product(client, other_token)
    other_lot_resp = await _create_lot(client, other_token, other_product)
    other_lot_id = other_lot_resp.json()["id"]
    try:
        token = await _access_token(client, business.titolare_email, business.password)
        resp = await client.get(f"/lots/{other_lot_id}", headers=_auth(token))
        assert resp.status_code == 404
    finally:
        async with as_owner() as conn:
            await conn.execute("delete from movements where lot_id = %s", (other_lot_id,))
            await conn.execute("delete from lots where id = %s", (other_lot_id,))


# ------------------------------------------------------------------- patch

async def test_operatore_patch_is_404(client, business, cleanup_lots):
    titolare_token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, titolare_token)
    lot_resp = await _create_lot(client, titolare_token, product_id)
    lot_id = lot_resp.json()["id"]
    cleanup_lots.append(uuid.UUID(lot_id))

    operatore_token = await _access_token(client, business.operatore_email, business.password)
    resp = await client.patch(
        f"/lots/{lot_id}", headers=_auth(operatore_token), json={"lot_code": "NUOVO"}
    )
    assert resp.status_code == 404


async def test_titolare_corrects_lot_code(client, business, cleanup_lots):
    token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, token)
    lot_resp = await _create_lot(client, token, product_id)
    lot_id = lot_resp.json()["id"]
    cleanup_lots.append(uuid.UUID(lot_id))

    resp = await client.patch(
        f"/lots/{lot_id}", headers=_auth(token), json={"lot_code": "CORRETTO"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["lot_code"] == "CORRETTO"


async def test_responsabile_corrects_price(client, business, cleanup_lots):
    token = await _access_token(client, business.responsabile_email, business.password)
    product_id = await _create_product(client, token)
    lot_resp = await _create_lot(client, token, product_id, unit_price="1.00")
    lot_id = lot_resp.json()["id"]
    cleanup_lots.append(uuid.UUID(lot_id))

    resp = await client.patch(
        f"/lots/{lot_id}", headers=_auth(token), json={"unit_price": "2.50"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["unit_price"] == "2.50"


async def test_empty_patch_is_422(client, business, cleanup_lots):
    token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, token)
    lot_resp = await _create_lot(client, token, product_id)
    lot_id = lot_resp.json()["id"]
    cleanup_lots.append(uuid.UUID(lot_id))

    resp = await client.patch(f"/lots/{lot_id}", headers=_auth(token), json={})
    assert resp.status_code == 422
    assert resp.json()["detail"] == "empty_patch"


async def test_patch_null_on_required_column_is_422(client, business, cleanup_lots):
    token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, token)
    lot_resp = await _create_lot(client, token, product_id)
    lot_id = lot_resp.json()["id"]
    cleanup_lots.append(uuid.UUID(lot_id))

    resp = await client.patch(f"/lots/{lot_id}", headers=_auth(token), json={"lot_code": None})
    assert resp.status_code == 422, resp.text
    assert isinstance(resp.json()["detail"], list)


# ------------------------------------------------------------------- list

async def test_list_filters_by_storage_and_active_only(client, business, cleanup_lots):
    token = await _access_token(client, business.titolare_email, business.password)
    frigo_product = await _create_product(client, token, storage="frigo")
    dispensa_product = await _create_product(client, token, storage="dispensa")

    frigo_lot = await _create_lot(client, token, frigo_product, quantity="1")
    cleanup_lots.append(uuid.UUID(frigo_lot.json()["id"]))
    dispensa_lot = await _create_lot(client, token, dispensa_product, quantity="1")
    cleanup_lots.append(uuid.UUID(dispensa_lot.json()["id"]))

    resp = await client.get("/lots", headers=_auth(token), params={"storage": "frigo"})
    ids = {row["id"] for row in resp.json()}
    assert frigo_lot.json()["id"] in ids
    assert dispensa_lot.json()["id"] not in ids

    # Exhaust the frigo lot, then active_only should hide it.
    scarico = await client.post(
        "/movements", headers=_auth(token),
        json={"lot_id": frigo_lot.json()["id"], "type": "scarico_uso", "quantity": "1"},
    )
    assert scarico.status_code == 201, scarico.text

    resp = await client.get(
        "/lots", headers=_auth(token), params={"product_id": frigo_product, "active_only": "true"}
    )
    assert resp.json() == []


async def test_list_filters_by_expired(client, business, cleanup_lots):
    token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, token)

    past = (date.today() - timedelta(days=2)).isoformat()
    future = (date.today() + timedelta(days=20)).isoformat()
    expired_lot = await _create_lot(client, token, product_id, expires_on=past)
    cleanup_lots.append(uuid.UUID(expired_lot.json()["id"]))
    future_lot = await _create_lot(client, token, product_id, expires_on=future)
    cleanup_lots.append(uuid.UUID(future_lot.json()["id"]))

    resp = await client.get(
        "/lots", headers=_auth(token), params={"product_id": product_id, "expired": "true"}
    )
    ids = {row["id"] for row in resp.json()}
    assert expired_lot.json()["id"] in ids
    assert future_lot.json()["id"] not in ids


# --------------------------------------------------------------- expiring

async def test_expiring_endpoint_statuses(client, business, cleanup_lots):
    token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, token)

    expired = await _create_lot(
        client, token, product_id, expires_on=(date.today() - timedelta(days=1)).isoformat()
    )
    cleanup_lots.append(uuid.UUID(expired.json()["id"]))
    soon = await _create_lot(
        client, token, product_id, expires_on=(date.today() + timedelta(days=3)).isoformat()
    )
    cleanup_lots.append(uuid.UUID(soon.json()["id"]))
    far = await _create_lot(
        client, token, product_id, expires_on=(date.today() + timedelta(days=60)).isoformat()
    )
    cleanup_lots.append(uuid.UUID(far.json()["id"]))
    no_expiry = await _create_lot(client, token, product_id, expires_on=None)
    cleanup_lots.append(uuid.UUID(no_expiry.json()["id"]))

    # Default threshold (business.expiry_threshold_days == 7): expired + soon,
    # not far, not no_expiry.
    resp = await client.get(
        "/lots/expiring", headers=_auth(token), params={"product_id": product_id}
    )
    by_id = {row["id"]: row for row in resp.json() if row["product_id"] == product_id}
    assert expired.json()["id"] in by_id
    assert soon.json()["id"] in by_id
    assert far.json()["id"] not in by_id
    assert no_expiry.json()["id"] not in by_id
    assert by_id[expired.json()["id"]]["status"] == "scaduto"
    assert by_id[expired.json()["id"]]["days_left"] < 0
    assert by_id[soon.json()["id"]]["status"] == "in_scadenza"

    # include_all lifts the cutoff entirely, so `far` shows up as "ok".
    all_resp = await client.get(
        "/lots/expiring", headers=_auth(token), params={"include_all": "true"}
    )
    all_by_id = {row["id"]: row for row in all_resp.json()}
    assert all_by_id[far.json()["id"]]["status"] == "ok"


async def test_expiring_endpoint_excludes_zero_stock_lot(client, business, cleanup_lots):
    token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, token)
    lot_resp = await _create_lot(
        client, token, product_id, quantity="2",
        expires_on=(date.today() - timedelta(days=1)).isoformat(),
    )
    lot_id = lot_resp.json()["id"]
    cleanup_lots.append(uuid.UUID(lot_id))

    scarto = await client.post(
        "/movements", headers=_auth(token),
        json={"lot_id": lot_id, "type": "scarto", "quantity": "2", "reason": "Scaduto"},
    )
    assert scarto.status_code == 201, scarto.text

    resp = await client.get(
        "/lots/expiring", headers=_auth(token), params={"include_all": "true"}
    )
    assert lot_id not in {row["id"] for row in resp.json()}
