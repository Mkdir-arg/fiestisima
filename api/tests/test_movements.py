"""POST /movements (all four types, idempotent retries), GET the ledger
(pagination, lot/product filters), and POST .../reverse (the sign
convention, the 24h/role gate, double-reversal rejection).
"""
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
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
    """Same rationale as test_lots.py's fixture of the same name: nothing
    but this fixture cleans up the lots/movements these tests create."""
    lot_ids: list[uuid.UUID] = []
    yield lot_ids
    async with as_owner() as conn:
        for lot_id in lot_ids:
            await conn.execute("delete from movements where lot_id = %s", (lot_id,))
            await conn.execute("delete from lots where id = %s", (lot_id,))


async def _stock_of(client, token, lot_id) -> str:
    resp = await client.get("/stock/lots", headers=_auth(token), params={"lot_id": lot_id})
    return resp.json()[0]["stock"]


# ----------------------------------------------------------------- create

@pytest.mark.parametrize(
    "type_,extra",
    [
        ("scarico_uso", {}),
        ("scarico_vendita", {}),
        ("scarto", {"reason": "Danneggiato"}),
    ],
)
async def test_create_each_movement_type(client, business, cleanup_lots, type_, extra):
    token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, token)
    lot = await _create_lot(client, token, product_id, quantity="10")
    cleanup_lots.append(uuid.UUID(lot["id"]))

    payload = {"lot_id": lot["id"], "type": type_, "quantity": "3"}
    payload.update(extra)
    resp = await client.post("/movements", headers=_auth(token), json=payload)
    assert resp.status_code == 201, resp.text
    assert resp.json()["type"] == type_

    assert await _stock_of(client, token, lot["id"]) == "7"


async def test_scarto_without_reason_is_422(client, business, cleanup_lots):
    token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, token)
    lot = await _create_lot(client, token, product_id)
    cleanup_lots.append(uuid.UUID(lot["id"]))

    resp = await client.post(
        "/movements", headers=_auth(token),
        json={"lot_id": lot["id"], "type": "scarto", "quantity": "1"},
    )
    assert resp.status_code == 422


async def test_zero_quantity_is_422(client, business, cleanup_lots):
    token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, token)
    lot = await _create_lot(client, token, product_id)
    cleanup_lots.append(uuid.UUID(lot["id"]))

    resp = await client.post(
        "/movements", headers=_auth(token),
        json={"lot_id": lot["id"], "type": "scarico_uso", "quantity": "0"},
    )
    assert resp.status_code == 422


async def test_cross_tenant_lot_id_is_409(client, business, other_business, cleanup_lots):
    other_token = await _access_token(client, other_business.titolare_email, other_business.password)
    other_product = await _create_product(client, other_token)
    other_lot = await _create_lot(client, other_token, other_product)
    try:
        token = await _access_token(client, business.titolare_email, business.password)
        resp = await client.post(
            "/movements", headers=_auth(token),
            json={"lot_id": other_lot["id"], "type": "scarico_uso", "quantity": "1"},
        )
        assert resp.status_code == 409
    finally:
        async with as_owner() as conn:
            await conn.execute("delete from movements where lot_id = %s", (other_lot["id"],))
            await conn.execute("delete from lots where id = %s", (other_lot["id"],))


async def test_duplicate_client_id_is_idempotent(client, business, cleanup_lots):
    token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, token)
    lot = await _create_lot(client, token, product_id, quantity="10")
    cleanup_lots.append(uuid.UUID(lot["id"]))
    client_id = str(uuid.uuid4())

    payload = {"lot_id": lot["id"], "type": "scarico_uso", "quantity": "4", "client_id": client_id}
    first = await client.post("/movements", headers=_auth(token), json=payload)
    assert first.status_code == 201, first.text

    retry = await client.post("/movements", headers=_auth(token), json=payload)
    assert retry.status_code == 201, retry.text
    assert retry.json()["id"] == first.json()["id"]
    assert await _stock_of(client, token, lot["id"]) == "6"  # not 2 - only one scarico applied


# ------------------------------------------------------------------- list

async def test_ledger_requires_lot_or_product(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    resp = await client.get("/movements", headers=_auth(token))
    assert resp.status_code == 422


async def test_ledger_by_lot_and_pagination(client, business, cleanup_lots):
    token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, token)
    lot = await _create_lot(client, token, product_id, quantity="20")
    cleanup_lots.append(uuid.UUID(lot["id"]))

    for _ in range(3):
        resp = await client.post(
            "/movements", headers=_auth(token),
            json={"lot_id": lot["id"], "type": "scarico_uso", "quantity": "1"},
        )
        assert resp.status_code == 201, resp.text

    full = await client.get("/movements", headers=_auth(token), params={"lot_id": lot["id"]})
    assert full.status_code == 200
    # The opening carico plus the 3 scarichi.
    assert len(full.json()) == 4

    page = await client.get(
        "/movements", headers=_auth(token), params={"lot_id": lot["id"], "limit": 2, "offset": 0}
    )
    assert len(page.json()) == 2

    by_type = await client.get(
        "/movements", headers=_auth(token),
        params={"lot_id": lot["id"], "type": "scarico_uso"},
    )
    assert len(by_type.json()) == 3


async def test_ledger_by_product_spans_multiple_lots(client, business, cleanup_lots):
    token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, token)
    lot_a = await _create_lot(client, token, product_id, quantity="1")
    cleanup_lots.append(uuid.UUID(lot_a["id"]))
    lot_b = await _create_lot(client, token, product_id, quantity="1")
    cleanup_lots.append(uuid.UUID(lot_b["id"]))

    resp = await client.get(
        "/movements", headers=_auth(token), params={"product_id": product_id}
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_ledger_tenant_isolation(client, business, other_business, cleanup_lots):
    other_token = await _access_token(client, other_business.titolare_email, other_business.password)
    other_product = await _create_product(client, other_token)
    other_lot = await _create_lot(client, other_token, other_product)
    try:
        token = await _access_token(client, business.titolare_email, business.password)
        resp = await client.get(
            "/movements", headers=_auth(token), params={"lot_id": other_lot["id"]}
        )
        assert resp.status_code == 200
        assert resp.json() == []
    finally:
        async with as_owner() as conn:
            await conn.execute("delete from movements where lot_id = %s", (other_lot["id"],))
            await conn.execute("delete from lots where id = %s", (other_lot["id"],))


# ---------------------------------------------------------------- reverse

async def test_reverse_carico_returns_stock_to_zero(client, business, cleanup_lots):
    token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, token)
    lot = await _create_lot(client, token, product_id, quantity="10")
    cleanup_lots.append(uuid.UUID(lot["id"]))

    resp = await client.post(
        f"/movements/{lot['movement_id']}/reverse", headers=_auth(token), json={}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["type"] == "carico"
    assert body["reverses_id"] == lot["movement_id"]
    assert await _stock_of(client, token, lot["id"]) == "0"


async def test_reverse_scarto_preserves_reason(client, business, cleanup_lots):
    token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, token)
    lot = await _create_lot(client, token, product_id, quantity="10")
    cleanup_lots.append(uuid.UUID(lot["id"]))

    scarto = await client.post(
        "/movements", headers=_auth(token),
        json={"lot_id": lot["id"], "type": "scarto", "quantity": "2", "reason": "Danneggiato"},
    )
    assert scarto.status_code == 201, scarto.text

    reversed_resp = await client.post(
        f"/movements/{scarto.json()['id']}/reverse", headers=_auth(token), json={}
    )
    assert reversed_resp.status_code == 201, reversed_resp.text
    assert reversed_resp.json()["reason"] == "Danneggiato"
    assert reversed_resp.json()["type"] == "scarto"


async def test_reverse_twice_is_409(client, business, cleanup_lots):
    token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, token)
    lot = await _create_lot(client, token, product_id, quantity="10")
    cleanup_lots.append(uuid.UUID(lot["id"]))

    first = await client.post(
        f"/movements/{lot['movement_id']}/reverse", headers=_auth(token), json={}
    )
    assert first.status_code == 201, first.text

    second = await client.post(
        f"/movements/{lot['movement_id']}/reverse", headers=_auth(token), json={}
    )
    assert second.status_code == 409
    assert second.json()["detail"] == "already_reversed"


async def test_reverse_nonexistent_movement_is_404(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    resp = await client.post(
        f"/movements/{uuid.uuid4()}/reverse", headers=_auth(token), json={}
    )
    assert resp.status_code == 404


async def test_operatore_reverses_own_recent_movement(client, business, cleanup_lots):
    titolare_token = await _access_token(client, business.titolare_email, business.password)
    operatore_token = await _access_token(client, business.operatore_email, business.password)
    product_id = await _create_product(client, titolare_token)
    lot = await _create_lot(client, operatore_token, product_id, quantity="10")
    cleanup_lots.append(uuid.UUID(lot["id"]))

    resp = await client.post(
        f"/movements/{lot['movement_id']}/reverse", headers=_auth(operatore_token), json={}
    )
    assert resp.status_code == 201, resp.text


async def test_operatore_cannot_reverse_colleagues_movement(client, business, cleanup_lots):
    titolare_token = await _access_token(client, business.titolare_email, business.password)
    operatore_token = await _access_token(client, business.operatore_email, business.password)
    product_id = await _create_product(client, titolare_token)
    lot = await _create_lot(client, titolare_token, product_id, quantity="10")
    cleanup_lots.append(uuid.UUID(lot["id"]))

    resp = await client.post(
        f"/movements/{lot['movement_id']}/reverse", headers=_auth(operatore_token), json={}
    )
    assert resp.status_code == 404


async def test_operatore_cannot_reverse_own_movement_after_24h(client, business, cleanup_lots):
    token = await _access_token(client, business.operatore_email, business.password)
    titolare_token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, titolare_token)
    lot = await _create_lot(client, token, product_id, quantity="10")
    cleanup_lots.append(uuid.UUID(lot["id"]))

    old = datetime.now(timezone.utc) - timedelta(hours=25)
    async with as_owner() as conn:
        await conn.execute(
            "update movements set created_at = %s where id = %s", (old, lot["movement_id"])
        )

    resp = await client.post(
        f"/movements/{lot['movement_id']}/reverse", headers=_auth(token), json={}
    )
    assert resp.status_code == 404


async def test_concurrent_reversal_race_is_blocked_by_unique_index(client, business, cleanup_lots):
    # The router's own "select 1 from movements where reverses_id = %s"
    # pre-check (see reverse_movement) closes the sequential case but
    # cannot serialise two truly concurrent reversal attempts of the same
    # movement - movements has no UPDATE policy, so a "for update" lock
    # is not an option here (see 0007's own migration comment). This
    # proves the real backstop directly: 0007's partial unique index on
    # (reverses_id) rejects a second reversal row even when nothing
    # stopped the pre-check from passing twice.
    token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, token)
    lot = await _create_lot(client, token, product_id, quantity="10")
    cleanup_lots.append(uuid.UUID(lot["id"]))

    async with as_owner() as conn:
        await conn.execute(
            """
            insert into movements (business_id, lot_id, type, quantity, created_by, reverses_id)
            values (%s, %s, 'carico', 10, %s, %s)
            """,
            (business.business_id, lot["id"], business.titolare_id, lot["movement_id"]),
        )
        with pytest.raises(psycopg.errors.UniqueViolation):
            await conn.execute(
                """
                insert into movements (business_id, lot_id, type, quantity, created_by, reverses_id)
                values (%s, %s, 'carico', 10, %s, %s)
                """,
                (business.business_id, lot["id"], business.titolare_id, lot["movement_id"]),
            )


async def test_titolare_reverses_colleagues_old_movement(client, business, cleanup_lots):
    operatore_token = await _access_token(client, business.operatore_email, business.password)
    titolare_token = await _access_token(client, business.titolare_email, business.password)
    product_id = await _create_product(client, titolare_token)
    lot = await _create_lot(client, operatore_token, product_id, quantity="10")
    cleanup_lots.append(uuid.UUID(lot["id"]))

    old = datetime.now(timezone.utc) - timedelta(hours=25)
    async with as_owner() as conn:
        await conn.execute(
            "update movements set created_at = %s where id = %s", (old, lot["movement_id"])
        )

    resp = await client.post(
        f"/movements/{lot['movement_id']}/reverse", headers=_auth(titolare_token), json={}
    )
    assert resp.status_code == 201, resp.text
