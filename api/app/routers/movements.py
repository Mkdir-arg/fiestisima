"""The traceability ledger: POST a movement, GET it filtered by lot or
product, and reverse one.

No owner mode anywhere in this file: every endpoint runs as_user, and
movements_select/movements_insert (see migrations/0002_rls.sql) decide who
may read or write, never current_user.role or .business_id in Python (see
db.py's as_user() and the module comment in routers/auth.py for the same
rule). movements_insert's WITH CHECK only requires business_id/created_by
to match the caller - every role may record every movement type (docs/02:
carico/scarico/scarto are all-roles actions), so there is no role branch to
document here the way products.py has one for its write endpoints.

Idempotency for the offline queue (docs/07's "se registran hasta días
después"): movements.client_id is unique. _insert_movement_or_existing
below is the single place that inserts a movement; a retry that repeats a
client_id gets back the row that already exists instead of a 409, so a
client that never heard back from a first attempt can safely replay it.
lots.py's carico endpoint (creating a lot's opening movement) calls this
same helper rather than duplicating the insert.

Cross-tenant lot_id/event_id: the composite foreign keys
(lot_id, business_id) / (event_id, business_id) reject a reference into
another business the same way products.py's category_id does - a plain
psycopg.errors.ForeignKeyViolation, uncaught here, mapped to a generic 409
by main.py. Not distinguished from a lot_id that never existed at all:
both fail the same FK lookup the same way. Documented, not fixed, matching
the precedent set in products.py's module comment.

Reversal permissions (docs/07: "anulable dentro de las 24 h por quien lo
hizo, y en cualquier momento por titolare/responsabile") are not encoded
as a migrations/0002 policy - movements has no UPDATE/DELETE policy at
all (the ledger is immutable; "undoing" a movement is inserting a new
row, never touching the old one), and this rule is about which *existing*
row a new INSERT may reference, not which rows the caller's own INSERT
touches - RLS's WITH CHECK on movements_insert already governs that part
(business_id/created_by) and says nothing about reverses_id. So the rule
is expressed as an ordinary SQL predicate in reverse_movement() below,
using app_role()/app_user_id() - the same session-scoped functions every
RLS policy in this codebase reads - never current_user.role from the JWT.
It is not a CREATE POLICY only because "may reference row X" has no
natural home in a policy that governs "may write row Y"; the intent (ask
the database, not the token) is the same. If a target row does not match
that predicate, this looks exactly like v2-15's RLS-filtered UPDATE: 404,
not 403 - the row exists but this caller cannot act on it, and that is the
same "hide the button" case the UI already avoids showing.
"""
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator

from ..db import as_user
from ..security import CurrentUser, require_user

router = APIRouter(prefix="/movements", tags=["movements"])

MovementType = Literal["carico", "scarico_uso", "scarico_vendita", "scarto"]

_MOVEMENT_COLUMNS = (
    "id, business_id, lot_id, event_id, type, quantity, reason, "
    "reverses_id, client_id, created_by, occurred_at, created_at"
)


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


# --------------------------------------------------------------- schemas

class MovementOut(BaseModel):
    id: UUID
    business_id: UUID
    lot_id: UUID
    event_id: UUID | None
    type: MovementType
    # Decimal, not float: same reasoning as products.py's min_stock -
    # serialises to a JSON string, never a float-rounded number.
    quantity: Decimal
    reason: str | None
    reverses_id: UUID | None
    client_id: UUID | None
    created_by: UUID
    occurred_at: datetime
    created_at: datetime


class MovementIn(BaseModel):
    lot_id: UUID
    type: MovementType
    quantity: Decimal = Field(gt=0)
    reason: str | None = Field(default=None, max_length=500)
    event_id: UUID | None = None
    # When the movement actually happened on the floor - see
    # movements.occurred_at in 0001. Left out, the database default (now())
    # applies; the offline queue sends this explicitly for a backdated sync.
    occurred_at: datetime | None = None
    client_id: UUID | None = None

    _strip_reason = field_validator("reason", mode="before")(_strip)

    @model_validator(mode="after")
    def _scarto_needs_reason(self) -> "MovementIn":
        # The database's own scarto_needs_reason check (23514) is the real
        # backstop (see main.py's CheckViolation handler); this just gives
        # the same rule a friendlier, uniform 422 before the request ever
        # reaches SQL, the same philosophy as ProductPatch's null-column
        # guard in products.py.
        if self.type == "scarto" and not self.reason:
            raise ValueError("reason is required for scarto")
        return self


class ReverseIn(BaseModel):
    # Optional override of the reversed movement's own reason. Left unset,
    # the reversal copies the original's reason (needed unconditionally for
    # a scarto reversal, which is itself subject to scarto_needs_reason).
    reason: str | None = Field(default=None, max_length=500)
    client_id: UUID | None = None

    _strip_reason = field_validator("reason", mode="before")(_strip)


def _movement_out(row) -> MovementOut:
    return MovementOut(
        id=row[0], business_id=row[1], lot_id=row[2], event_id=row[3], type=row[4],
        quantity=row[5], reason=row[6], reverses_id=row[7], client_id=row[8],
        created_by=row[9], occurred_at=row[10], created_at=row[11],
    )


# ---------------------------------------------------------------- shared

async def _insert_movement_or_existing(
    conn,
    *,
    lot_id: UUID,
    event_id: UUID | None,
    type_: str,
    quantity: Decimal,
    reason: str | None,
    occurred_at: datetime | None,
    client_id: UUID | None,
    reverses_id: UUID | None = None,
) -> tuple[tuple, bool]:
    """Inserts a movement, or - if client_id repeats one already recorded
    (the offline queue's idempotency key: movements.client_id is the only
    unique constraint on this table besides its primary key, so any
    UniqueViolation here is that one) - returns the original row instead of
    raising. Runs on a SAVEPOINT (conn.transaction() nested inside the
    caller's already-open as_user() transaction), the same shape as
    products.py's create_product: only this INSERT rolls back on the
    UniqueViolation, the caller's own transaction stays usable afterwards
    (lots.py's carico endpoint still needs to read the lot back on this
    same connection). Returns (row, was_idempotent_replay).
    """
    try:
        async with conn.transaction():
            cur = await conn.execute(
                f"""
                insert into movements
                  (business_id, lot_id, event_id, type, quantity, reason,
                   reverses_id, created_by, occurred_at, client_id)
                values
                  (app_business_id(), %s, %s, %s, %s, %s, %s, app_user_id(),
                   coalesce(%s, now()), %s)
                returning {_MOVEMENT_COLUMNS}
                """,
                (lot_id, event_id, type_, quantity, reason, reverses_id, occurred_at, client_id),
            )
            row = await cur.fetchone()
        return row, False
    except psycopg.errors.UniqueViolation:
        if client_id is None:
            # Cannot be the idempotency key (there is none) - some other
            # constraint this table does not currently have. Re-raise for
            # main.py's generic UniqueViolation -> 409 handler.
            raise
        cur = await conn.execute(
            f"select {_MOVEMENT_COLUMNS} from movements where client_id = %s", (client_id,)
        )
        existing = await cur.fetchone()
        if existing is None:
            raise
        return existing, True


# ----------------------------------------------------------------- create

@router.post("", response_model=MovementOut, status_code=201)
async def create_movement(body: MovementIn, current_user: CurrentUser = Depends(require_user)):
    async with as_user(current_user.id) as conn:
        row, _replayed = await _insert_movement_or_existing(
            conn,
            lot_id=body.lot_id, event_id=body.event_id, type_=body.type,
            quantity=body.quantity, reason=body.reason, occurred_at=body.occurred_at,
            client_id=body.client_id,
        )
    return _movement_out(row)


# ------------------------------------------------------------------- list

@router.get("", response_model=list[MovementOut])
async def list_movements(
    lot_id: UUID | None = Query(default=None),
    product_id: UUID | None = Query(default=None),
    type: MovementType | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(require_user),
):
    # The ledger for a single lot or a single product, never the whole
    # business at once - one of the two is required so a client cannot
    # accidentally page through every movement the tenant has ever made.
    if lot_id is None and product_id is None:
        raise HTTPException(status_code=422, detail="lot_id_or_product_id_required")

    async with as_user(current_user.id) as conn:
        cur = await conn.execute(
            """
            select m.id, m.business_id, m.lot_id, m.event_id, m.type, m.quantity, m.reason,
                   m.reverses_id, m.client_id, m.created_by, m.occurred_at, m.created_at
            from movements m
            join lots l on l.id = m.lot_id
            where (%s::uuid is null or m.lot_id = %s)
              and (%s::uuid is null or l.product_id = %s)
              and (%s::movement_type is null or m.type = %s)
            order by m.occurred_at desc, m.created_at desc
            limit %s offset %s
            """,
            (lot_id, lot_id, product_id, product_id, type, type, limit, offset),
        )
        rows = await cur.fetchall()
        return [_movement_out(row) for row in rows]


# --------------------------------------------------------------- reverse

@router.post("/{movement_id}/reverse", response_model=MovementOut, status_code=201)
async def reverse_movement(
    movement_id: UUID, body: ReverseIn, current_user: CurrentUser = Depends(require_user)
):
    error: HTTPException | None = None
    result_row = None

    async with as_user(current_user.id) as conn:
        # See the module comment: this predicate is the reversal
        # permission rule, expressed in SQL against app_role()/
        # app_user_id() - never against current_user from the JWT. created_at,
        # not occurred_at: the 24h grace period is about how recently the
        # user actually performed the action, not about the (possibly
        # backdated, offline-synced) business date the movement carries.
        cur = await conn.execute(
            """
            select lot_id, event_id, type, quantity, reason
            from movements
            where id = %s
              and business_id = app_business_id()
              and (
                    app_role() in ('titolare', 'responsabile')
                    or (created_by = app_user_id() and created_at >= now() - interval '24 hours')
                  )
            """,
            (movement_id,),
        )
        target = await cur.fetchone()
        if target is None:
            error = HTTPException(status_code=404, detail="not_found")
        else:
            lot_id, event_id, type_, quantity, original_reason = target
            # A movement may be reversed at most once: reverses_id points
            # from the reversal back to what it undoes (see 0001's
            # comment), so "already reversed" is "some row already points
            # here".
            cur = await conn.execute(
                "select 1 from movements where reverses_id = %s", (movement_id,)
            )
            if await cur.fetchone() is not None:
                error = HTTPException(status_code=409, detail="already_reversed")
            else:
                # Same type as the original (0001/docs-07: a reversed
                # carico is still type carico), same quantity (a full
                # undo, no partial reversal), same lot and event. reason
                # defaults to the original's own reason - load-bearing for
                # a scarto reversal, itself subject to scarto_needs_reason.
                reason = body.reason if body.reason is not None else original_reason
                try:
                    row, _replayed = await _insert_movement_or_existing(
                        conn,
                        lot_id=lot_id, event_id=event_id, type_=type_, quantity=quantity,
                        reason=reason, occurred_at=None, client_id=body.client_id,
                        reverses_id=movement_id,
                    )
                except psycopg.errors.UniqueViolation:
                    # The pre-check above narrows the common sequential
                    # case, but cannot serialise two *concurrent*
                    # reversals of the same movement - movements has no
                    # UPDATE policy at all (see the module comment), so
                    # "select ... for update" would lock nothing here the
                    # way it does on profiles. 0007's partial unique index
                    # on (reverses_id) is what actually closes the race;
                    # this is that constraint's violation, translated to
                    # the same detail code the pre-check already uses.
                    error = HTTPException(status_code=409, detail="already_reversed")
                else:
                    result_row = row

    if error is not None:
        raise error
    return _movement_out(result_row)
