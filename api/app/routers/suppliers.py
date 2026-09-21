"""List/search, create, read and patch the supplier directory.

Follows products.py's pattern exactly: every endpoint runs as_user, and
suppliers_select/suppliers_write (see migrations/0002_rls.sql) decide who
may read or write, never current_user.role or .business_id in Python.
suppliers_write is a single FOR ALL policy scoped to
app_role() in ('titolare', 'responsabile') - the same v2-15 asymmetry as
products.py's products_write: an operatore's POST fails the WITH CHECK
(psycopg.errors.InsufficientPrivilege, uncaught here, mapped to 403 by
main.py) while an operatore's PATCH fails the USING clause instead
(rowcount 0, reported here as 404). See products.py's module comment for
the full reasoning.

There is no DELETE endpoint: 0002/0004 never grant DELETE on suppliers at
all (unlike categories), matching docs/10's own rule ("Un fornitore con
lotes no puede borrarse") - a supplier is deactivated with
PATCH {"active": false}, never removed. A deactivated supplier disappears
from the default list (and from the carico form's selector, per docs/10)
but its historical lots keep showing it - lots.supplier_id is "on delete
restrict" specifically so this never becomes a dangling reference.

Duplicate name (unique(business_id, name)) answers a plain 409 "name_taken"
string, the same shape categories.py uses and for the same reason: unlike
products.py's barcode_taken, the caller already knows which name collided
(they just typed it), so there is nothing extra worth carrying in the body.
"""
from datetime import datetime
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator

from ..db import as_user
from ..security import CurrentUser, require_user

router = APIRouter(prefix="/suppliers", tags=["suppliers"])

_SUPPLIER_COLUMNS = (
    "id, name, phone, email, vat_number, address, notes, active, created_at"
)

# The columns PATCH is allowed to touch - see products.py's _PATCH_COLUMNS
# for why the SET clause's column *names* only ever come from this
# constant, never from the request body.
_PATCH_COLUMNS = ("name", "phone", "email", "vat_number", "address", "notes", "active")

# Of _PATCH_COLUMNS, only these are NOT NULL in the suppliers table - see
# products.py's _REQUIRED_PATCH_COLUMNS for why an explicit null on one of
# these is rejected by pydantic (422) rather than reaching Postgres's own
# NOT NULL constraint.
_REQUIRED_PATCH_COLUMNS = ("name", "active")


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


def _blank_to_none(value: object) -> object:
    # An empty string from a form field left untouched should behave like
    # the field was never sent, not like an explicit "" value - matches
    # products.py's _normalize_barcode.
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


# --------------------------------------------------------------- schemas

class SupplierOut(BaseModel):
    id: UUID
    name: str
    phone: str | None
    email: str | None
    vat_number: str | None
    address: str | None
    notes: str | None
    active: bool
    created_at: datetime


class SupplierIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=254)
    vat_number: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=2000)

    _strip_name = field_validator("name", mode="before")(_strip)
    _blank_phone = field_validator("phone", mode="before")(_blank_to_none)
    _blank_email = field_validator("email", mode="before")(_blank_to_none)
    _blank_vat = field_validator("vat_number", mode="before")(_blank_to_none)
    _blank_address = field_validator("address", mode="before")(_blank_to_none)
    _blank_notes = field_validator("notes", mode="before")(_blank_to_none)


class SupplierPatch(BaseModel):
    """All fields optional (only those actually sent end up in the SET
    list - see update_supplier's use of model_dump(exclude_unset=True)),
    except that name/active may not be *sent* as null - see
    _reject_null_on_required_columns below."""
    name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=254)
    vat_number: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=2000)
    active: bool | None = None

    _strip_name = field_validator("name", mode="before")(_strip)
    _blank_phone = field_validator("phone", mode="before")(_blank_to_none)
    _blank_email = field_validator("email", mode="before")(_blank_to_none)
    _blank_vat = field_validator("vat_number", mode="before")(_blank_to_none)
    _blank_address = field_validator("address", mode="before")(_blank_to_none)
    _blank_notes = field_validator("notes", mode="before")(_blank_to_none)

    @model_validator(mode="after")
    def _reject_null_on_required_columns(self) -> "SupplierPatch":
        # model_fields_set (not "is the value None") is what tells "sent as
        # null" apart from "not sent at all" - see products.py's
        # ProductPatch for the identical reasoning.
        for column in _REQUIRED_PATCH_COLUMNS:
            if column in self.model_fields_set and getattr(self, column) is None:
                raise ValueError(f"{column} cannot be null")
        return self


def _supplier_out(row) -> SupplierOut:
    return SupplierOut(
        id=row[0], name=row[1], phone=row[2], email=row[3], vat_number=row[4],
        address=row[5], notes=row[6], active=row[7], created_at=row[8],
    )


# ------------------------------------------------------------------- list

@router.get("", response_model=list[SupplierOut])
async def list_suppliers(
    search: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    current_user: CurrentUser = Depends(require_user),
):
    # Read-only: every role may read the directory - suppliers_select has
    # no role condition, only suppliers_write does.
    like_term = f"%{search}%" if search else None
    async with as_user(current_user.id) as conn:
        cur = await conn.execute(
            f"""
            select {_SUPPLIER_COLUMNS}
            from suppliers
            where (%s or active) and (%s::text is null or name ilike %s)
            order by name
            """,
            (include_inactive, like_term, like_term),
        )
        rows = await cur.fetchall()
        return [_supplier_out(row) for row in rows]


# ----------------------------------------------------------------- create

@router.post("", response_model=SupplierOut, status_code=201)
async def create_supplier(body: SupplierIn, current_user: CurrentUser = Depends(require_user)):
    error: HTTPException | None = None
    created: SupplierOut | None = None

    async with as_user(current_user.id) as conn:
        try:
            cur = await conn.execute(
                f"""
                insert into suppliers (business_id, name, phone, email, vat_number, address, notes)
                values (app_business_id(), %s, %s, %s, %s, %s, %s)
                returning {_SUPPLIER_COLUMNS}
                """,
                (body.name, body.phone, body.email, body.vat_number, body.address, body.notes),
            )
            row = await cur.fetchone()
        except psycopg.errors.UniqueViolation:
            error = HTTPException(status_code=409, detail="name_taken")
        else:
            created = _supplier_out(row)

    if error is not None:
        raise error
    return created


# --------------------------------------------------------------------- get

@router.get("/{supplier_id}", response_model=SupplierOut)
async def get_supplier(supplier_id: UUID, current_user: CurrentUser = Depends(require_user)):
    # Read-only: suppliers_select scopes this to the caller's own business -
    # a different business's supplier id (or one that never existed) is
    # indistinguishable, both 404.
    async with as_user(current_user.id) as conn:
        cur = await conn.execute(
            f"select {_SUPPLIER_COLUMNS} from suppliers where id = %s", (supplier_id,)
        )
        row = await cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="not_found")
        return _supplier_out(row)


# ------------------------------------------------------------------- patch

@router.patch("/{supplier_id}", response_model=SupplierOut)
async def update_supplier(
    supplier_id: UUID, body: SupplierPatch, current_user: CurrentUser = Depends(require_user)
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
    updated: SupplierOut | None = None

    async with as_user(current_user.id) as conn:
        sql = (
            f"update suppliers set {', '.join(set_parts)} "
            f"where id = %s returning {_SUPPLIER_COLUMNS}"
        )
        try:
            cur = await conn.execute(sql, (*params, supplier_id))
            row = await cur.fetchone()
        except psycopg.errors.UniqueViolation:
            error = HTTPException(status_code=409, detail="name_taken")
        else:
            if row is None:
                # Covers: no such id, a different business, and an
                # operatore (suppliers_write's USING clause filters all
                # three the same way, with no error to tell them apart -
                # see the module comment).
                error = HTTPException(status_code=404, detail="not_found")
            else:
                updated = _supplier_out(row)

    if error is not None:
        raise error
    return updated
