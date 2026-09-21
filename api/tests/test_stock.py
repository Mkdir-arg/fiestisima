"""GET /stock/products and GET /stock/lots: read-only views over
product_stock/lot_stock, the min_stock shortfall flag, and tenant
isolation. No role gate on either endpoint (docs/02: consulting stock is
an all-roles action), so the role matrix here is "everyone can read".
"""
import uuid

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


async def _create_lot(client, token: str, product_id: str, **overrides) -> dict:
    payload = {
        "product_id": product_id,
        "lot_code": f"LOT-{uuid.uuid4().hex[:8]}",
        "quantity": "10",
    }
    payload.update(overrides)
    resp = await client.post("/lots", headers=_auth(token), json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
async def cleanup_lots():
    lot_ids: list[uuid.UUID] = []
    yield lot_ids
    async with as_owner() as conn:
        for lot_id in lot_ids:
            await conn.execute("delete from movements where lot_id = %s", (lot_id,))
            await conn.execute("delete from lots where id = %s", (lot_id,))


# ---------------------------------------------------------------- products

async def test_product_with_no_lots_shows_zero_stock_and_below_min(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, token, min_stock="5")

    resp = await client.get("/stock/products", headers=_auth(token))
    assert resp.status_code == 200
    row = next(r for r in resp.json() if r["product_id"] == product_id)
    assert row["stock"] == "0"
    assert row["min_stock"] == "5"
    assert row["below_min"] is True


async def test_below_min_only_filter(client, business, cleanup_lots):
    token = await _access_token(client, business.titolare_email, business.password)
    short_product = await _create_product(client, token, min_stock="10")
    plenty_product = await _create_product(client, token, min_stock="1")

    lot = await _create_lot(client, token, plenty_product, quantity="5")
    cleanup_lots.append(uuid.UUID(lot["id"]))

    resp = await client.get(
        "/stock/products", headers=_auth(token), params={"below_min_only": "true"}
    )
    ids = {r["product_id"] for r in resp.json()}
    assert short_product in ids
    assert plenty_product not in ids


@pytest.mark.parametrize("email_attr", ["titolare_email", "responsabile_email", "operatore_email"])
async def test_every_role_reads_product_stock(client, business, cleanup_lots, email_attr):
    titolare_token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, titolare_token)
    lot = await _create_lot(client, titolare_token, product_id, quantity="6")
    cleanup_lots.append(uuid.UUID(lot["id"]))

    token = await _access_token(client, getattr(business, email_attr), business.password)
    resp = await client.get("/stock/products", headers=_auth(token))
    assert resp.status_code == 200
    row = next(r for r in resp.json() if r["product_id"] == product_id)
    assert row["stock"] == "6"


async def test_product_stock_tenant_isolation(client, business, other_business, cleanup_lots):
    other_token = await _access_token(client, other_business.titolare_email, other_business.password)
    other_product = await _create_product(client, other_token)
    other_lot = await _create_lot(client, other_token, other_product, quantity="9")
    try:
        token = await _access_token(client, business.titolare_email, business.password)
        resp = await client.get("/stock/products", headers=_auth(token))
        assert other_product not in {r["product_id"] for r in resp.json()}
    finally:
        async with as_owner() as conn:
            await conn.execute("delete from movements where lot_id = %s", (other_lot["id"],))
            await conn.execute("delete from lots where id = %s", (other_lot["id"],))


# -------------------------------------------------------------------- lots

async def test_lot_stock_matches_lot_view_stock(client, business, cleanup_lots):
    token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, token)
    lot = await _create_lot(client, token, product_id, quantity="8")
    cleanup_lots.append(uuid.UUID(lot["id"]))

    resp = await client.get("/stock/lots", headers=_auth(token), params={"lot_id": lot["id"]})
    assert resp.status_code == 200
    assert resp.json() == [{"lot_id": lot["id"], "product_id": product_id, "stock": "8"}]


async def test_lot_stock_by_product_spans_lots(client, business, cleanup_lots):
    token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, token)
    lot_a = await _create_lot(client, token, product_id, quantity="1")
    cleanup_lots.append(uuid.UUID(lot_a["id"]))
    lot_b = await _create_lot(client, token, product_id, quantity="2")
    cleanup_lots.append(uuid.UUID(lot_b["id"]))

    resp = await client.get(
        "/stock/lots", headers=_auth(token), params={"product_id": product_id}
    )
    assert resp.status_code == 200
    assert {row["lot_id"] for row in resp.json()} == {lot_a["id"], lot_b["id"]}


async def test_lot_stock_tenant_isolation(client, business, other_business, cleanup_lots):
    other_token = await _access_token(client, other_business.titolare_email, other_business.password)
    other_product = await _create_product(client, other_token)
    other_lot = await _create_lot(client, other_token, other_product, quantity="4")
    try:
        token = await _access_token(client, business.titolare_email, business.password)
        resp = await client.get(
            "/stock/lots", headers=_auth(token), params={"lot_id": other_lot["id"]}
        )
        assert resp.json() == []
    finally:
        async with as_owner() as conn:
            await conn.execute("delete from movements where lot_id = %s", (other_lot["id"],))
            await conn.execute("delete from lots where id = %s", (other_lot["id"],))
