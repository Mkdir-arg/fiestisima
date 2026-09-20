"""List colleagues, change role/active.

Everything here runs as_user - RLS and the profiles_block_self_role_change
trigger decide who may change what; this module never inspects
current_user.role or .business_id (see db.py's as_user() and the module
comment in routers/auth.py for the same rule).

One exception, and it is the only permission rule allowed outside the
database (per the design): a titolare cannot demote or deactivate the last
active titolare of a business. RLS and the trigger can only ever see one
row at a time (the row being written); "is this the only active titolare
left" is a count across every row in profiles for the business, which
neither a USING/WITH CHECK expression nor a BEFORE ROW trigger can express
without turning it into a statement-level trigger the schema does not have.
So this one rule lives here, in Python, gated on a COUNT(*) the caller's
own RLS-scoped connection runs (profiles_select already scopes it to their
business) - not on anything read from the JWT.
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db import as_owner, as_user
from ..security import CurrentUser, require_user, revoke_all_refresh_tokens

router = APIRouter(prefix="/users", tags=["users"])

Role = Literal["titolare", "responsabile", "operatore"]


class UserOut(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: str
    active: bool
    last_seen_at: datetime | None
    created_at: datetime


class UpdateUserRequest(BaseModel):
    role: Role | None = None
    active: bool | None = None


def _user_out(row) -> UserOut:
    return UserOut(
        id=row[0], email=row[1], full_name=row[2], role=row[3],
        active=row[4], last_seen_at=row[5], created_at=row[6],
    )


_SELECT_BUSINESS_USER = (
    "select id, email, full_name, role, active, last_seen_at, created_at "
    "from business_users where id = %s"
)


@router.get("", response_model=list[UserOut])
async def list_users(current_user: CurrentUser = Depends(require_user)):
    # Read-only: business_users already scopes to the caller's own business
    # (see migrations/0006), and every role may read it - colleagues' names
    # and emails are not secret within a business.
    async with as_user(current_user.id) as conn:
        cur = await conn.execute(
            "select id, email, full_name, role, active, last_seen_at, created_at "
            "from business_users order by full_name"
        )
        rows = await cur.fetchall()
        return [_user_out(row) for row in rows]


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: UUID, body: UpdateUserRequest, current_user: CurrentUser = Depends(require_user)
):
    error: HTTPException | None = None
    updated_row = None
    became_inactive = False

    async with as_user(current_user.id) as conn:
        if body.role is not None or body.active is not None:
            # RLS (profiles_select) already scopes this to the caller's own
            # business; a user_id from another business simply is not found
            # here, same as it will not be found by the UPDATE below.
            cur = await conn.execute(
                "select role, active from profiles where id = %s", (user_id,)
            )
            target = await cur.fetchone()
            if target is not None:
                target_role, target_active = target
                would_demote = (
                    body.role is not None and body.role != "titolare"
                    and target_role == "titolare"
                )
                would_deactivate = body.active is False and target_role == "titolare"
                if target_active and target_role == "titolare" and (would_demote or would_deactivate):
                    cur = await conn.execute(
                        "select count(*) from profiles where role = 'titolare' and active"
                    )
                    (active_titolare_count,) = await cur.fetchone()
                    if active_titolare_count <= 1:
                        error = HTTPException(status_code=409, detail="last_titolare")

        if error is None:
            # rowcount 0 covers: no such id, a different business (RLS
            # using-filtered), and nothing changed - not an error, just
            # "no row to update". A role/active change a non-titolare tries
            # to make on someone else fails earlier and differently: the
            # profiles_block_self_role_change trigger raises 42501, which
            # propagates uncaught to main.py's InsufficientPrivilege
            # handler (403) - this file never checks who the caller is.
            cur = await conn.execute(
                """
                update profiles set role = coalesce(%s, role), active = coalesce(%s, active)
                where id = %s
                returning active
                """,
                (body.role, body.active, user_id),
            )
            row = await cur.fetchone()
            if row is None:
                error = HTTPException(status_code=404, detail="not_found")
            else:
                (new_active,) = row
                became_inactive = body.active is False and new_active is False
                cur = await conn.execute(_SELECT_BUSINESS_USER, (user_id,))
                updated_row = await cur.fetchone()

    if error is not None:
        raise error

    if became_inactive:
        # runs as owner: revokes every refresh token this user holds, in a
        # separate as_owner() block opened only after the as_user() block
        # above has fully exited (committed) - never nested, per the
        # design's rule against opening a second pool connection inside an
        # open one. Under READ COMMITTED this can miss a successor token a
        # concurrent /auth/refresh mints between that commit and this
        # revoke; up to access_token_minutes (15 min) of exposure, accepted
        # for Bloque 0 (the same gap already documented on
        # revoke_all_refresh_tokens itself).
        async with as_owner() as conn:
            await revoke_all_refresh_tokens(conn, user_id)

    return _user_out(updated_row)
