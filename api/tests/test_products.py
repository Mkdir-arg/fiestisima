"""GET/POST /products, GET/PATCH /products/{id}: catalog listing, search,
creation, the barcode_taken/barcode_locked 409 shapes, the v2-15 asymmetry
(operatore POST -> 403, operatore PATCH -> 404), and that an explicit null
on a required column is rejected as 422, never reaches Postgres as a 500.
"""
import uuid

import psycopg

from app.db import as_owner
from app.main import app


async def _login(client, email: str, password: str):
    return await client.post("/auth/login", json={"email": email, "password": password})


async def _access_token(client, email: str, password: str) -> str:
    resp = await _login(client, email, password)
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create_product(client, token: str, **overrides):
    payload = {"name": "Farina 00", "unit": "kg", "storage": "dispensa"}
    payload.update(overrides)
    return await client.post("/products", headers=_auth(token), json=payload)


# ------------------------------------------------------------------- list

async def test_operatore_lists_but_cannot_create(client, business):
    operatore_token = await _access_token(client, business.operatore_email, business.password)

    list_resp = await client.get("/products", headers=_auth(operatore_token))
    assert list_resp.status_code == 200
    assert list_resp.json() == []

    create_resp = await _create_product(client, operatore_token, name="Zucchero")
    assert create_resp.status_code == 403


async def test_search_by_name_and_barcode_fragment(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    await _create_product(client, token, name="Farina 00", barcode="8001112223334")
    await _create_product(client, token, name="Zucchero semolato")

    by_name = await client.get("/products", headers=_auth(token), params={"search": "farina"})
    assert by_name.status_code == 200
    assert {p["name"] for p in by_name.json()} == {"Farina 00"}

    by_barcode = await client.get(
        "/products", headers=_auth(token), params={"search": "1112223"}
    )
    assert by_barcode.status_code == 200
    assert {p["name"] for p in by_barcode.json()} == {"Farina 00"}


# ----------------------------------------------------------------- create

async def test_responsabile_creates_with_barcode(client, business):
    token = await _access_token(client, business.responsabile_email, business.password)
    resp = await _create_product(client, token, name="Farina 00", barcode="8001234567890")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["barcode"] == "8001234567890"
    assert body["active"] is True
    assert body["min_stock"] == "0"


async def test_titolare_creates_without_barcode(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    resp = await _create_product(client, token, name="Zucchero")
    assert resp.status_code == 201, resp.text
    assert resp.json()["barcode"] is None


async def test_two_null_barcodes_both_succeed(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    first = await _create_product(client, token, name="Prodotto Uno")
    second = await _create_product(client, token, name="Prodotto Due")
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text


async def test_duplicate_barcode_is_409_with_existing_name(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    first = await _create_product(client, token, name="Farina 00", barcode="8009999999999")
    assert first.status_code == 201, first.text

    second = await _create_product(
        client, token, name="Farina 00 bis", barcode="8009999999999"
    )
    assert second.status_code == 409, second.text
    detail = second.json()["detail"]
    assert detail["code"] == "barcode_taken"
    assert detail["name"] == "Farina 00"


async def test_invalid_unit_is_422(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    resp = await _create_product(client, token, name="Prodotto Invalido", unit="cajas")
    assert resp.status_code == 422


# --------------------------------------------------------------------- get

async def test_get_other_business_product_is_404(client, business, other_business):
    other_token = await _access_token(
        client, other_business.titolare_email, other_business.password
    )
    other_create = await _create_product(client, other_token, name="Solo Altro")
    assert other_create.status_code == 201, other_create.text
    other_product_id = other_create.json()["id"]

    token = await _access_token(client, business.titolare_email, business.password)
    resp = await client.get(f"/products/{other_product_id}", headers=_auth(token))
    assert resp.status_code == 404


# ------------------------------------------------------------------- patch

async def test_operatore_patch_is_404(client, business):
    titolare_token = await _access_token(client, business.titolare_email, business.password)
    create_resp = await _create_product(client, titolare_token, name="Farina 00")
    product_id = create_resp.json()["id"]

    operatore_token = await _access_token(client, business.operatore_email, business.password)
    resp = await client.patch(
        f"/products/{product_id}", headers=_auth(operatore_token), json={"min_stock": "5"}
    )
    assert resp.status_code == 404


async def test_titolare_patch_min_stock(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    create_resp = await _create_product(client, token, name="Farina 00")
    product_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/products/{product_id}", headers=_auth(token), json={"min_stock": "12.5"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["min_stock"] == "12.5"


async def test_patch_active_false_hides_from_default_list(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    create_resp = await _create_product(client, token, name="Prodotto Da Disattivare")
    product_id = create_resp.json()["id"]

    patch_resp = await client.patch(
        f"/products/{product_id}", headers=_auth(token), json={"active": False}
    )
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["active"] is False

    default_list = await client.get("/products", headers=_auth(token))
    assert product_id not in {p["id"] for p in default_list.json()}

    full_list = await client.get(
        "/products", headers=_auth(token), params={"include_inactive": "true"}
    )
    assert product_id in {p["id"] for p in full_list.json()}


async def test_empty_patch_is_422(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    create_resp = await _create_product(client, token, name="Farina 00")
    product_id = create_resp.json()["id"]

    resp = await client.patch(f"/products/{product_id}", headers=_auth(token), json={})
    assert resp.status_code == 422
    assert resp.json()["detail"] == "empty_patch"


async def test_barcode_change_blocked_when_lot_exists(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    create_resp = await _create_product(
        client, token, name="Farina 00", barcode="8005554443332"
    )
    assert create_resp.status_code == 201, create_resp.text
    product_id = uuid.UUID(create_resp.json()["id"])

    async with as_owner() as conn:
        await conn.execute(
            "insert into lots (business_id, product_id, lot_code, created_by) "
            "values (%s, %s, %s, %s)",
            (business.business_id, product_id, "LOTTO-1", business.titolare_id),
        )

    resp = await client.patch(
        f"/products/{product_id}", headers=_auth(token), json={"barcode": "8009998887776"}
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == "barcode_locked"

    # Dedicated cleanup, lots before products - the `business` fixture's own
    # teardown asserts zero lots for this business before it ever touches
    # products (see conftest.py's _teardown_business), and lots' foreign key
    # to products is "on delete restrict".
    async with as_owner() as conn:
        result = await conn.execute("delete from lots where product_id = %s", (product_id,))
        assert result.rowcount == 1
        result = await conn.execute("delete from products where id = %s", (product_id,))
        assert result.rowcount == 1


# -------------------------------------------------------- explicit nulls

async def test_patch_null_on_required_column_is_422(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    create_resp = await _create_product(client, token, name="Farina 00")
    product_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/products/{product_id}", headers=_auth(token), json={"unit": None}
    )
    assert resp.status_code == 422, resp.text
    # pydantic's own shape here, not the machine-code string the rest of
    # this router's errors use - ProductPatch's model validator rejects
    # this before the request ever reaches SQL.
    assert isinstance(resp.json()["detail"], list)


async def test_patch_null_on_nullable_column_clears_it(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    create_resp = await _create_product(client, token, name="Farina 00", brand="Barilla")
    product_id = create_resp.json()["id"]
    assert create_resp.json()["brand"] == "Barilla"

    resp = await client.patch(
        f"/products/{product_id}", headers=_auth(token), json={"brand": None}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["brand"] is None


async def test_not_null_violation_maps_to_422():
    # A router-agnostic check of main.py's own error map, not a route: no
    # current input to any endpoint in this codebase can actually get an
    # explicit null past its Pydantic model onto a NOT NULL column (see the
    # module docstring), so there is no live HTTP path left to provoke a
    # genuine psycopg.errors.NotNullViolation from client input - this
    # calls the registered handler directly instead, the same object
    # main.py's @app.exception_handler(...) decorator put in
    # app.exception_handlers.
    handler = app.exception_handlers[psycopg.errors.NotNullViolation]
    response = await handler(None, psycopg.errors.NotNullViolation("column x"))
    assert response.status_code == 422
    assert response.body == b'{"detail":"invalid"}'
