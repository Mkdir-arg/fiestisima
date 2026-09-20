"""View and edit the caller's own business.

Both endpoints run as_user; businesses_select/businesses_update decide who
may read or write, never current_user.role or .business_id in this file
(see db.py's as_user() and the module comment in routers/auth.py).

PATCH is gated by businesses_update's USING clause (id = app_business_id()
and app_role() = 'titolare'), the same shape as invitations_all: a
non-titolare's UPDATE matches 0 rows (Postgres filters, no error - see
routers/invitations.py's module comment for the same reasoning) and this
file reports that as 404, not 403.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..db import as_user
from ..security import CurrentUser, require_user

router = APIRouter(prefix="/businesses", tags=["businesses"])


class BusinessOut(BaseModel):
    id: UUID
    name: str
    address: str | None
    vat_number: str | None
    expiry_threshold_days: int


class UpdateBusinessRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    address: str | None = None
    vat_number: str | None = None
    expiry_threshold_days: int | None = Field(default=None, ge=1, le=60)


def _business_out(row) -> BusinessOut:
    return BusinessOut(id=row[0], name=row[1], address=row[2], vat_number=row[3], expiry_threshold_days=row[4])


@router.get("/me", response_model=BusinessOut)
async def get_my_business(current_user: CurrentUser = Depends(require_user)):
    # Read-only: raising inside is fine (see the exemption noted in
    # routers/auth.py's module comment).
    async with as_user(current_user.id) as conn:
        cur = await conn.execute(
            "select id, name, address, vat_number, expiry_threshold_days "
            "from businesses where id = app_business_id()"
        )
        row = await cur.fetchone()
        if row is None:
            # A deactivated caller's app_business_id() resolves to NULL
            # (see 0001's function), leaving nothing to select - same as an
            # unusable credential elsewhere in this codebase, 401 not 404.
            raise HTTPException(status_code=401, detail="invalid_token")
        return _business_out(row)


@router.patch("/me", response_model=BusinessOut)
async def update_my_business(
    body: UpdateBusinessRequest, current_user: CurrentUser = Depends(require_user)
):
    error: HTTPException | None = None
    updated_row = None

    async with as_user(current_user.id) as conn:
        cur = await conn.execute(
            """
            update businesses set
              name = coalesce(%s, name),
              address = coalesce(%s, address),
              vat_number = coalesce(%s, vat_number),
              expiry_threshold_days = coalesce(%s, expiry_threshold_days)
            where id = app_business_id()
            returning id, name, address, vat_number, expiry_threshold_days
            """,
            (body.name, body.address, body.vat_number, body.expiry_threshold_days),
        )
        row = await cur.fetchone()
        if row is None:
            error = HTTPException(status_code=404, detail="not_found")
        else:
            updated_row = row

    if error is not None:
        raise error
    return _business_out(updated_row)
