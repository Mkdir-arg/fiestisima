"""List/search, create, read, and patch the product catalogue.

No owner mode anywhere in this file: every endpoint runs as_user, and
products_select/products_write (see migrations/0002_rls.sql) decide who may
read or write, never current_user.role or .business_id in Python (see
db.py's as_user() and the module comment in routers/auth.py for the same
rule). There is no DELETE endpoint - products are deactivated with
PATCH {"active": false}, and the default list only shows active = true.

v2-15 asymmetry, worth calling out explicitly because the two write
endpoints answer the same "you may not do that" fact with different status
codes: products_write is a single FOR ALL policy scoped to
app_role() in ('titolare', 'responsabile'). An operatore's INSERT fails its
WITH CHECK - an INSERT has no pre-existing row for Postgres to just filter
out, so the WITH CHECK failure is a genuine error (psycopg.errors.
InsufficientPrivilege, uncaught here, mapped to 403 by main.py's handler).
An operatore's UPDATE fails the same policy's USING clause instead - and a
USING mismatch is not an error, Postgres simply excludes the row from the
statement's target set (see the CREATE POLICY docs: "rows for which the
expression returns false or null will not be visible" - no exception,
rowcount/RETURNING-empty exactly as if the id did not exist). So:
POST /products as operatore -> 403, PATCH /products/{id} as operatore ->
404. Same rule, same policy, different SQL command, different failure
shape - not a bug.

Two 409 shapes with a non-string detail, both a deliberate departure from
the "detail is always a machine code string" rule documented at the top of
api-contract-for-client.md (that file's Task 5 section notes the exception
too):
  - barcode_taken: {"code": "barcode_taken", "name": "<existing product's
    name>"} - raised when a UniqueViolation on (business_id, barcode) is
    caught inside the same block that attempted the write, on both POST and
    PATCH. The existing row's name is looked up by barcode alone
    (products_select scopes that read to the caller's own business, which
    is exactly the uniqueness constraint's scope - a barcode collision can
    only ever be with a product in the same tenant). The client maps this
    straight to t.products.duplicateBarcode(name).
  - barcode_locked: "barcode_locked" (a plain string, unlike barcode_taken)
    - PATCH only, when the caller may write the product (see below) but its
    barcode cannot change because it already has lots. Kept as a string
    since there is no extra payload to carry, unlike barcode_taken's name.

A category_id from another business fails the composite foreign key
(category_id, business_id) -> ForeignKeyViolation -> main.py's generic
409 {"detail": "conflict"}. Not distinguished from any other 23503/23505
here - acceptable, documented in the contract file.

PATCH's barcode-locked check (spec: a product that already has lots keeps
its barcode) uses the same "for update" trick as routers/users.py's last-
titolare guard, not a plain SELECT, and this is not cosmetic: a plain
"select 1 from products where id = %s" would be visible to *any* role in
the business (products_select's USING is business-scoped only, no role
check), so an operatore's PATCH that happens to include "barcode" would
wrongly read as "the product exists" and answer 409 barcode_locked instead
of the 404 every other operatore PATCH gets. "select 1 from products where
id = %s for update", by contrast, is additionally gated by the applicable
UPDATE policy's USING clause (products_write requires
app_role() in ('titolare', 'responsabile')) - so it resolves to a row only
for a caller who could otherwise write this product, letting the barcode-
locked check answer 409 without ever reading current_user.role.
"""
from decimal import Decimal
from typing import Literal
from uuid import UUID
from datetime import datetime

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from ..db import as_user
from ..security import CurrentUser, require_user

router = APIRouter(prefix="/products", tags=["products"])

Unit = Literal["pz", "kg", "l", "g", "ml"]
Storage = Literal["frigo", "freezer", "dispensa"]

_PRODUCT_COLUMNS = (
    "id, name, barcode, brand, unit, storage, min_stock, has_expiry, "
    "active, category_id, created_at, updated_at"
)

# The columns PATCH is allowed to touch, and the only source of the SET
# clause's column *names* - the request body only ever supplies values,
# never names, so a client can never steer which column gets written.
_PATCH_COLUMNS = (
    "name", "barcode", "brand", "unit", "storage",
    "min_stock", "has_expiry", "category_id", "active",
)


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


def _normalize_barcode(value: object) -> object:
    # "" is treated the same as omitting the field: a barcode scanner or a
    # form left empty should not create a spurious empty-string value that
    # (unlike NULL) *would* collide with a second empty-string barcode.
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


# --------------------------------------------------------------- schemas

class ProductOut(BaseModel):
    id: UUID
    name: str
    barcode: str | None
    brand: str | None
    unit: str
    storage: str
    # Decimal, not float: pydantic serialises Decimal to a JSON *string*
    # (checked against this pydantic version - model_dump_json() produces
    # {"min_stock": "3.50"}, not a bare number), which avoids the float
    # rounding a numeric column's exact value would otherwise pick up on
    # the wire. The client parses it as a string, not a JSON number.
    min_stock: Decimal
    has_expiry: bool
    active: bool
    category_id: UUID | None
    created_at: datetime
    updated_at: datetime


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    barcode: str | None = Field(default=None, max_length=64)
    brand: str | None = Field(default=None, max_length=120)
    unit: Unit
    storage: Storage
    min_stock: Decimal = Field(default=Decimal("0"), ge=0)
    has_expiry: bool = True
    category_id: UUID | None = None

    _strip_name = field_validator("name", mode="before")(_strip)
    _normalize_barcode_v = field_validator("barcode", mode="before")(_normalize_barcode)


class ProductPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    barcode: str | None = Field(default=None, max_length=64)
    brand: str | None = Field(default=None, max_length=120)
    unit: Unit | None = None
    storage: Storage | None = None
    min_stock: Decimal | None = Field(default=None, ge=0)
    has_expiry: bool | None = None
    category_id: UUID | None = None
    active: bool | None = None

    _strip_name = field_validator("name", mode="before")(_strip)
    _normalize_barcode_v = field_validator("barcode", mode="before")(_normalize_barcode)


def _product_out(row) -> ProductOut:
    return ProductOut(
        id=row[0], name=row[1], barcode=row[2], brand=row[3], unit=row[4],
        storage=row[5], min_stock=row[6], has_expiry=row[7], active=row[8],
        category_id=row[9], created_at=row[10], updated_at=row[11],
    )


def _barcode_taken(existing_row) -> HTTPException:
    name = existing_row[0] if existing_row is not None else None
    return HTTPException(status_code=409, detail={"code": "barcode_taken", "name": name})


# ------------------------------------------------------------------- list

@router.get("", response_model=list[ProductOut])
async def list_products(
    search: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    current_user: CurrentUser = Depends(require_user),
):
    # Read-only: raising inside is fine (see the exemption noted in
    # routers/auth.py's module comment). Every role may read the catalog -
    # products_select has no role condition, only products_write does.
    like_term = f"%{search}%" if search else None
    async with as_user(current_user.id) as conn:
        cur = await conn.execute(
            f"""
            select {_PRODUCT_COLUMNS}
            from products
            where (%s or active) and (%s::text is null or name ilike %s or barcode ilike %s)
            order by name
            """,
            (include_inactive, like_term, like_term, like_term),
        )
        rows = await cur.fetchall()
        return [_product_out(row) for row in rows]


# ----------------------------------------------------------------- create

@router.post("", response_model=ProductOut, status_code=201)
async def create_product(body: ProductIn, current_user: CurrentUser = Depends(require_user)):
    # products_write's WITH CHECK restricts this INSERT to a titolare or
    # responsabile of the caller's own business - an operatore's insert
    # raises psycopg.errors.InsufficientPrivilege here, uncaught, and
    # main.py's handler turns it into 403 (see the module comment for why
    # this differs from PATCH's 404). Nothing in this function checks
    # current_user.role.
    error: HTTPException | None = None
    created: ProductOut | None = None

    async with as_user(current_user.id) as conn:
        try:
            # A nested conn.transaction() issues a SAVEPOINT: on
            # UniqueViolation only this INSERT is rolled back, not the
            # whole as_user() transaction - the lookup below still needs to
            # run in the same (still-good) transaction, and Postgres
            # refuses any further statement on an already-aborted one.
            async with conn.transaction():
                cur = await conn.execute(
                    f"""
                    insert into products
                      (business_id, name, barcode, brand, unit, storage, min_stock, has_expiry, category_id)
                    values (app_business_id(), %s, %s, %s, %s, %s, %s, %s, %s)
                    returning {_PRODUCT_COLUMNS}
                    """,
                    (
                        body.name, body.barcode, body.brand, body.unit, body.storage,
                        body.min_stock, body.has_expiry, body.category_id,
                    ),
                )
                row = await cur.fetchone()
        except psycopg.errors.UniqueViolation:
            # (business_id, barcode) already has a row with this barcode.
            # The insert already failed and aborted this transaction;
            # letting the block exit normally below just rolls it back, no
            # second connection needed for the lookup below.
            cur = await conn.execute(
                "select name from products where barcode = %s", (body.barcode,)
            )
            existing = await cur.fetchone()
            error = _barcode_taken(existing)
        else:
            created = _product_out(row)

    if error is not None:
        raise error
    return created


# --------------------------------------------------------------------- get

@router.get("/{product_id}", response_model=ProductOut)
async def get_product(product_id: UUID, current_user: CurrentUser = Depends(require_user)):
    # Read-only: raising inside is fine (see the exemption noted in
    # routers/auth.py's module comment). products_select scopes this to the
    # caller's own business - a different business's product id (or one
    # that never existed) is indistinguishable, both 404.
    async with as_user(current_user.id) as conn:
        cur = await conn.execute(
            f"select {_PRODUCT_COLUMNS} from products where id = %s", (product_id,)
        )
        row = await cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="not_found")
        return _product_out(row)


# ------------------------------------------------------------------- patch

@router.patch("/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: UUID, body: ProductPatch, current_user: CurrentUser = Depends(require_user)
):
    # exclude_unset, not a dict of coalesce() params: unlike businesses.py's
    # PATCH /me, some of these columns (barcode, brand, category_id) are
    # nullable and clearing one of them to NULL is a legitimate patch -
    # coalesce(new, old) could never tell "clear it" apart from "leave it
    # alone". Only fields the client actually sent end up in the SET list.
    provided = body.model_dump(exclude_unset=True)
    if not provided:
        raise HTTPException(status_code=422, detail="empty_patch")

    set_parts: list[str] = []
    params: list = []
    for column in _PATCH_COLUMNS:
        if column in provided:
            set_parts.append(f"{column} = %s")
            params.append(provided[column])

    barcode_changing = "barcode" in provided
    # Spec rule (docs/05): a product that already has lots keeps its
    # barcode. Only added to the WHERE clause when barcode is actually
    # being changed - every other patch (min_stock, active, ...) is
    # unaffected by whether lots exist.
    lots_guard = (
        " and not exists (select 1 from lots where product_id = products.id)"
        if barcode_changing else ""
    )

    error: HTTPException | None = None
    updated: ProductOut | None = None

    async with as_user(current_user.id) as conn:
        write_visible = None
        if barcode_changing:
            # See the module comment: this lock is only visible to a caller
            # whose role also satisfies products_write's USING clause, not
            # merely products_select's business-only one - the only way to
            # tell "no write access at all" (operatore, 404) apart from
            # "write access, but the lots guard below filtered the row"
            # (409 barcode_locked) without reading current_user.role.
            cur = await conn.execute(
                "select 1 from products where id = %s for update", (product_id,)
            )
            write_visible = await cur.fetchone()

        sql = (
            f"update products set {', '.join(set_parts)}, "
            f"updated_at = now(), updated_by = app_user_id() "
            f"where id = %s{lots_guard} "
            f"returning {_PRODUCT_COLUMNS}"
        )
        try:
            # See create_product's comment: a nested conn.transaction() is
            # a SAVEPOINT, so a UniqueViolation here only rolls back this
            # UPDATE, leaving the outer transaction usable for the lookup
            # below.
            async with conn.transaction():
                cur = await conn.execute(sql, (*params, product_id))
                row = await cur.fetchone()
        except psycopg.errors.UniqueViolation:
            cur = await conn.execute(
                "select name from products where barcode = %s", (provided["barcode"],)
            )
            existing = await cur.fetchone()
            error = _barcode_taken(existing)
        else:
            if row is None:
                if barcode_changing and write_visible is not None:
                    # The row exists and this caller could otherwise write
                    # it (the for-update lock above proves both), so only
                    # the lots guard can have filtered it out.
                    error = HTTPException(status_code=409, detail="barcode_locked")
                else:
                    # Covers: no such id, a different business, and an
                    # operatore (products_write's USING clause filters all
                    # three the same way, with no error to tell them apart
                    # - see the module comment).
                    error = HTTPException(status_code=404, detail="not_found")
            else:
                updated = _product_out(row)

    if error is not None:
        raise error
    return updated
