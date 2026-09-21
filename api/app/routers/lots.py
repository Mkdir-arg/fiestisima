"""List/filter, read, register (carico) and correct lots; the scadenze
list.

No owner mode anywhere in this file: every endpoint runs as_user, and
lots_select/lots_insert/lots_update (see migrations/0002_rls.sql) decide
who may read or write, never current_user.role or .business_id in Python.

Reads never touch the `lots` table directly: they go through `lots_view`
(and `lot_stock` for the computed quantity), the same view products/movements
never bypass either - lots_view's own case expression is what hides
unit_price/document_url from an operatore (see 0001's comment on the view
and 0002's column-level revoke on the base table). This matters for writes
too: POST and PATCH below RETURNING only the columns app_user actually has
SELECT on at the table level (id, business_id, product_id, supplier_id,
lot_code, expires_on, received_on, created_by, created_at - see 0002's
column grants) and then do a second read from lots_view to build the
response body, because RETURNING a column requires SELECT privilege on it
just like an ordinary query would - RETURNING unit_price straight off the
base table would fail privilege checks for every role, titolare included,
since that column is only ever exposed through the view's case expression,
never granted directly. _fetch_lot_out() is that second read.

POST is a carico (docs/07): it creates a lot and its opening movement in
one transaction - concretely, one as_user() transaction, the same one
db.py always opens per request; nothing here starts a second one. If the
same product + lot_code + expires_on + supplier already has a lot (the
"unique nulls not distinct" constraint from 0001), no second lot is
created - the movement is added to the existing one instead, the same
"two identical caricos don't create two lots" rule 0001 documents. This
follows the exact SAVEPOINT-then-fallback-lookup shape products.py's
create_product uses for barcode_taken: a nested conn.transaction() rolls
back only the failed INSERT, the outer transaction (and the lookup +
movement insert that follow, on the same connection) stays usable. There
is no role check anywhere in this path: lots_insert's WITH CHECK only
requires business_id/created_by to match the caller (docs/02: carico is
an all-roles action - "goods-in is everyone's job on the floor", per
0002's own comment on lots_insert). Notably this means INSERT is *not*
column-restricted the way UPDATE is: an operatore's carico request may
freely carry unit_price/document_url (the app's UI simply does not show
those fields to them, per docs/07 - "oculto per operatore" is a client
concern, not a privilege one) - they just never see the value again,
because every read of it goes back through lots_view's case expression.

PATCH corrects an existing lot's fields (docs/07: "solo titolare e
responsabile correggono"). lots_update's USING clause enforces that role
gate entirely in Postgres: an operatore's PATCH matches 0 rows (Postgres
filters, no error) and is reported here as 404 - the same v2-15 asymmetry
documented at length in products.py's module comment, which applies here
without a POST-side counterpart (lots_insert allows anyone through, unlike
products_write).

GET /lots/expiring is the scadenze list (docs/08). It must be declared
before GET /{lot_id} in this file: FastAPI/Starlette match path operations
in registration order, and "/expiring" would otherwise be parsed as
lot_id="expiring" (a UUID validation 422) before ever reaching the
handler below.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator

from ..db import as_user
from ..security import CurrentUser, require_user
from .movements import _insert_movement_or_existing

router = APIRouter(prefix="/lots", tags=["lots"])

Storage = Literal["frigo", "freezer", "dispensa"]

# The columns PATCH is allowed to touch - matches lots_update's granted
# UPDATE columns exactly (see 0002's "grant update (...) on lots").
_PATCH_COLUMNS = (
    "product_id", "supplier_id", "lot_code", "expires_on",
    "unit_price", "document_url", "received_on",
)
# Of _PATCH_COLUMNS, these are NOT NULL in the lots table.
_REQUIRED_PATCH_COLUMNS = ("product_id", "lot_code", "received_on")

# lots_view's own columns, plus the computed stock from lot_stock - the
# read path every endpoint in this file uses to build a response body
# (see the module comment for why the base table's RETURNING cannot carry
# unit_price/document_url).
_LOT_VIEW_SELECT = """
    select lv.id, lv.business_id, lv.product_id, lv.supplier_id, lv.lot_code, lv.expires_on,
           lv.document_url, lv.received_on, lv.created_by, lv.created_at, lv.unit_price,
           coalesce(ls.stock, 0) as stock
    from lots_view lv
    left join lot_stock ls on ls.lot_id = lv.id
    where lv.id = %s
"""


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


# --------------------------------------------------------------- schemas

class LotOut(BaseModel):
    id: UUID
    business_id: UUID
    product_id: UUID
    supplier_id: UUID | None
    lot_code: str
    expires_on: date | None
    # None for an operatore regardless of what is actually stored - see the
    # module comment: this is lots_view's own case expression, not
    # something decided here.
    document_url: str | None
    received_on: date
    created_by: UUID
    created_at: datetime
    unit_price: Decimal | None
    stock: Decimal


class LotExpiringOut(LotOut):
    # Negative once expires_on is in the past - the client's StatusPill
    # renders straight off the sign, no extra parsing.
    days_left: int
    status: Literal["scaduto", "in_scadenza", "ok"]


class LotCaricoOut(LotOut):
    movement_id: UUID


class LotCaricoIn(BaseModel):
    product_id: UUID
    supplier_id: UUID | None = None
    lot_code: str = Field(min_length=1, max_length=120)
    expires_on: date | None = None
    # Hidden from an operatore client-side (docs/07); nothing stops it from
    # being sent - see the module comment.
    unit_price: Decimal | None = Field(default=None, ge=0)
    document_url: str | None = None
    # Left out, the column default (today in Europe/Rome) applies - see
    # 0001's comment on lots.received_on.
    received_on: date | None = None
    quantity: Decimal = Field(gt=0)
    reason: str | None = Field(default=None, max_length=500)
    event_id: UUID | None = None
    occurred_at: datetime | None = None
    client_id: UUID | None = None

    _strip_lot_code = field_validator("lot_code", mode="before")(_strip)


class LotPatch(BaseModel):
    """All fields optional (only those actually sent end up in the SET
    list), except that a field in _REQUIRED_PATCH_COLUMNS may not be *sent*
    as null - see products.py's ProductPatch for the identical shape."""
    product_id: UUID | None = None
    supplier_id: UUID | None = None
    lot_code: str | None = Field(default=None, min_length=1, max_length=120)
    expires_on: date | None = None
    unit_price: Decimal | None = Field(default=None, ge=0)
    document_url: str | None = None
    received_on: date | None = None

    _strip_lot_code = field_validator("lot_code", mode="before")(_strip)

    @model_validator(mode="after")
    def _reject_null_on_required_columns(self) -> "LotPatch":
        for column in _REQUIRED_PATCH_COLUMNS:
            if column in self.model_fields_set and getattr(self, column) is None:
                raise ValueError(f"{column} cannot be null")
        return self


def _lot_out(row) -> LotOut:
    return LotOut(
        id=row[0], business_id=row[1], product_id=row[2], supplier_id=row[3],
        lot_code=row[4], expires_on=row[5], document_url=row[6], received_on=row[7],
        created_by=row[8], created_at=row[9], unit_price=row[10], stock=row[11],
    )


async def _fetch_lot_out(conn, lot_id: UUID) -> LotOut | None:
    cur = await conn.execute(_LOT_VIEW_SELECT, (lot_id,))
    row = await cur.fetchone()
    return _lot_out(row) if row is not None else None


# ------------------------------------------------------------------- list

@router.get("", response_model=list[LotOut])
async def list_lots(
    product_id: UUID | None = Query(default=None),
    supplier_id: UUID | None = Query(default=None),
    storage: Storage | None = Query(default=None),
    active_only: bool = Query(default=False, description="only lots with stock != 0"),
    expired: bool | None = Query(default=None, description="true: only expired, false: only not expired"),
    expiring_within_days: int | None = Query(default=None, ge=0),
    current_user: CurrentUser = Depends(require_user),
):
    # Read-only: every role may read lots (lots_select has no role
    # condition) - price/document visibility is decided by lots_view's own
    # case expression, not here.
    async with as_user(current_user.id) as conn:
        cur = await conn.execute(
            """
            select lv.id, lv.business_id, lv.product_id, lv.supplier_id, lv.lot_code, lv.expires_on,
                   lv.document_url, lv.received_on, lv.created_by, lv.created_at, lv.unit_price,
                   coalesce(ls.stock, 0) as stock
            from lots_view lv
            join products p on p.id = lv.product_id
            left join lot_stock ls on ls.lot_id = lv.id
            where (%s::uuid is null or lv.product_id = %s)
              and (%s::uuid is null or lv.supplier_id = %s)
              and (%s::storage_place is null or p.storage = %s)
              and (%s = false or coalesce(ls.stock, 0) <> 0)
              and (
                    %s::boolean is null
                    or (%s and lv.expires_on < current_date)
                    or (not %s and (lv.expires_on is null or lv.expires_on >= current_date))
                  )
              and (
                    %s::int is null
                    or (lv.expires_on is not null and lv.expires_on >= current_date
                        and lv.expires_on <= current_date + %s::int)
                  )
            order by lv.expires_on nulls last, lv.lot_code
            """,
            (
                product_id, product_id,
                supplier_id, supplier_id,
                storage, storage,
                active_only,
                expired, expired, expired,
                expiring_within_days, expiring_within_days,
            ),
        )
        rows = await cur.fetchall()
        return [_lot_out(row) for row in rows]


# --------------------------------------------------------------- expiring

@router.get("/expiring", response_model=list[LotExpiringOut])
async def list_expiring_lots(
    within_days: int | None = Query(
        default=None, ge=0,
        description="overrides the business's own expiry_threshold_days for both "
                    "the status threshold and (unless horizon_days is also given) the cutoff",
    ),
    horizon_days: int | None = Query(
        default=None, ge=0, description="upper bound of days-until-expiry to include"
    ),
    include_all: bool = Query(
        default=False, description="ignore the cutoff entirely (docs/08's 'Tutti' filter)"
    ),
    current_user: CurrentUser = Depends(require_user),
):
    # docs/08: lots with stock > 0 and a vencimiento set, already-expired
    # ones included, ordered soonest first, each carrying the days-left
    # number the client's StatusPill renders directly.
    async with as_user(current_user.id) as conn:
        cur = await conn.execute(
            "select expiry_threshold_days from businesses where id = app_business_id()"
        )
        business_row = await cur.fetchone()
        if business_row is None:
            # A deactivated caller's app_business_id() resolves to NULL
            # (0001) - same treatment as businesses.py's GET /me.
            raise HTTPException(status_code=401, detail="invalid_token")

        threshold_days = within_days if within_days is not None else business_row[0]
        cutoff_days = horizon_days if horizon_days is not None else threshold_days

        cur = await conn.execute(
            """
            select lv.id, lv.business_id, lv.product_id, lv.supplier_id, lv.lot_code, lv.expires_on,
                   lv.document_url, lv.received_on, lv.created_by, lv.created_at, lv.unit_price,
                   coalesce(ls.stock, 0) as stock,
                   (lv.expires_on - current_date) as days_left
            from lots_view lv
            left join lot_stock ls on ls.lot_id = lv.id
            where lv.expires_on is not null
              and coalesce(ls.stock, 0) > 0
              and (%s or lv.expires_on <= current_date + %s::int)
            order by lv.expires_on asc, lv.lot_code
            """,
            (include_all, cutoff_days),
        )
        rows = await cur.fetchall()

    result: list[LotExpiringOut] = []
    for row in rows:
        days_left = row[-1]
        if days_left < 0:
            status: Literal["scaduto", "in_scadenza", "ok"] = "scaduto"
        elif days_left <= threshold_days:
            status = "in_scadenza"
        else:
            status = "ok"
        result.append(
            LotExpiringOut(**_lot_out(row[:-1]).model_dump(), days_left=days_left, status=status)
        )
    return result


# ----------------------------------------------------------------- create

@router.post("", response_model=LotCaricoOut, status_code=201)
async def create_lot(body: LotCaricoIn, current_user: CurrentUser = Depends(require_user)):
    async with as_user(current_user.id) as conn:
        lot_id: UUID | None = None
        try:
            # SAVEPOINT: on UniqueViolation only this INSERT rolls back,
            # not the whole as_user() transaction - the lookup below still
            # needs to run in the same (still-good) transaction. See
            # products.py's create_product for the identical shape.
            async with conn.transaction():
                cur = await conn.execute(
                    """
                    insert into lots
                      (business_id, product_id, supplier_id, lot_code, expires_on,
                       unit_price, document_url, received_on, created_by)
                    values
                      (app_business_id(), %s, %s, %s, %s, %s, %s,
                       coalesce(%s, (now() at time zone 'Europe/Rome')::date), app_user_id())
                    returning id
                    """,
                    (
                        body.product_id, body.supplier_id, body.lot_code, body.expires_on,
                        body.unit_price, body.document_url, body.received_on,
                    ),
                )
                row = await cur.fetchone()
                lot_id = row[0]
        except psycopg.errors.UniqueViolation:
            # Same product + lot_code + expires_on + supplier already has a
            # lot ("unique nulls not distinct", 0001) - the carico adds a
            # movement to it instead of creating a duplicate. "is not
            # distinct from" (not "=") because expires_on/supplier_id are
            # nullable and the constraint itself treats two nulls as equal.
            cur = await conn.execute(
                """
                select id from lots
                where business_id = app_business_id() and product_id = %s and lot_code = %s
                  and expires_on is not distinct from %s
                  and supplier_id is not distinct from %s
                """,
                (body.product_id, body.lot_code, body.expires_on, body.supplier_id),
            )
            existing = await cur.fetchone()
            if existing is None:
                raise
            lot_id = existing[0]

        movement_row, _replayed = await _insert_movement_or_existing(
            conn,
            lot_id=lot_id, event_id=body.event_id, type_="carico", quantity=body.quantity,
            reason=body.reason, occurred_at=body.occurred_at, client_id=body.client_id,
        )
        lot = await _fetch_lot_out(conn, lot_id)

    return LotCaricoOut(**lot.model_dump(), movement_id=movement_row[0])


# --------------------------------------------------------------------- get

@router.get("/{lot_id}", response_model=LotOut)
async def get_lot(lot_id: UUID, current_user: CurrentUser = Depends(require_user)):
    async with as_user(current_user.id) as conn:
        lot = await _fetch_lot_out(conn, lot_id)
        if lot is None:
            raise HTTPException(status_code=404, detail="not_found")
        return lot


# ------------------------------------------------------------------- patch

@router.patch("/{lot_id}", response_model=LotOut)
async def update_lot(
    lot_id: UUID, body: LotPatch, current_user: CurrentUser = Depends(require_user)
):
    provided = body.model_dump(exclude_unset=True)
    if not provided:
        raise HTTPException(status_code=422, detail="empty_patch")

    set_parts: list[str] = []
    params: list = []
    for column in _PATCH_COLUMNS:
        if column in provided:
            set_parts.append(f"{column} = %s")
            params.append(provided[column])

    error: HTTPException | None = None
    lot: LotOut | None = None

    async with as_user(current_user.id) as conn:
        # A UniqueViolation here (a corrected lot_code/expires_on/supplier
        # colliding with another lot) is left uncaught: nothing further
        # needs this connection on that path, so it propagates straight to
        # main.py's generic UniqueViolation -> 409 handler, same as a
        # cross-tenant product_id/supplier_id propagates as a generic
        # ForeignKeyViolation -> 409 (see products.py's module comment for
        # the identical acceptance on category_id).
        cur = await conn.execute(
            f"update lots set {', '.join(set_parts)} where id = %s returning id",
            (*params, lot_id),
        )
        row = await cur.fetchone()
        if row is None:
            # Covers: no such id, a different business, and an operatore
            # (lots_update's USING clause filters all three the same way -
            # see the module comment).
            error = HTTPException(status_code=404, detail="not_found")
        else:
            lot = await _fetch_lot_out(conn, lot_id)

    if error is not None:
        raise error
    return lot
