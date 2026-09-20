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
So this one rule lives here, in Python, gated on a count the caller's own
RLS-scoped connection runs (profiles_select already scopes it to their
business) - not on anything read from the JWT. That count is taken with
`for update` (see update_user's comment), not a plain SELECT, to close a
race between two concurrent titolare-count checks.

GET /users is served to every role, not titolare-only as the spec table
in the design doc suggests: profiles_select already lets colleagues see
each other's names, and restricting the list to titolare would need a
Python role check to enforce - exactly what this file otherwise never
does. Accepted as-is in fix round 1; the spec table gets amended in
Task 9.
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
    # (see migrations/0006), and every role may read it - see the module
    # comment for why this is not titolare-only despite the spec table.
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
        # Read business_users *before* the write, not after: the response
        # row must not depend on app_business_id() still resolving once
        # the UPDATE has run. It stops resolving the instant a caller
        # deactivates their own profile (app_business_id() only resolves
        # for an active profile - see 0001) - a titolare stepping down
        # with a co-titolare present used to 500 here, because the old
        # code re-read business_users *after* committing its own
        # deactivation, by which point its own app_business_id() was
        # already NULL and the view had nothing left to return. Reading
        # first and overlaying the written columns from RETURNING avoids
        # that, and costs one query fewer than the old
        # pre-check-then-post-fetch shape.
        cur = await conn.execute(_SELECT_BUSINESS_USER, (user_id,))
        target_row = await cur.fetchone()
        if target_row is None:
            # Covers: no such id, and a different business (business_users
            # is scoped by app_business_id() same as profiles_select) -
            # not an error, just nothing to act on.
            error = HTTPException(status_code=404, detail="not_found")
        else:
            if body.role is not None or body.active is not None:
                target_role, target_active = target_row[3], target_row[4]
                would_demote = (
                    body.role is not None and body.role != "titolare"
                    and target_role == "titolare"
                )
                would_deactivate = body.active is False and target_role == "titolare"
                if target_active and target_role == "titolare" and (would_demote or would_deactivate):
                    # Locked, not a plain count: two titolari demoting (or
                    # deactivating) each other concurrently would otherwise
                    # both read "2 active titolari" before either commits,
                    # both pass this check, and both updates would go
                    # through - leaving zero titolari. `for update` makes
                    # the second transaction block on whichever row the
                    # first one is about to change, then re-evaluate once
                    # the first commits - by then the first titolare's row
                    # already reads back as demoted/inactive, so the
                    # loser's own count is 1, and it correctly gets 409.
                    # `for update` needs UPDATE privilege (granted at the
                    # table level in 0002) and is itself subject to RLS:
                    # combined with a SELECT's row security, it additionally
                    # requires satisfying the USING clause of whichever
                    # UPDATE policy applies. For the titolare who is the
                    # only caller who can ever actually complete a
                    # role/active change on someone else,
                    # profiles_update_titolare's using clause makes every
                    # row in the business visible for locking. A
                    # non-titolare reaching this branch (their own attempt
                    # would fail via RLS or the trigger regardless) may see
                    # fewer locked rows than actually exist and get 409
                    # instead of the write's own 403/404 - a cosmetic
                    # status-code mismatch on a path that was never going
                    # to succeed either way, not a security gap.
                    cur = await conn.execute(
                        "select id from profiles where role = 'titolare' and active for update"
                    )
                    active_titolari = await cur.fetchall()
                    if len(active_titolari) <= 1:
                        error = HTTPException(status_code=409, detail="last_titolare")

            if error is None:
                # rowcount 0 here covers a non-titolare's attempt to change
                # a *colleague's* role/active: profiles_update_titolare's
                # using clause requires the caller be titolare, so the row
                # is invisible to this UPDATE before the
                # profiles_block_self_role_change trigger ever runs - 404,
                # not the trigger's 403 (see
                # test_non_titolare_patch_colleague_is_404). The trigger's
                # 42501 (uncaught here, mapped to 403 by main.py) only
                # fires for a *self*-update, where profiles_update_self
                # always makes the row visible regardless of role.
                cur = await conn.execute(
                    """
                    update profiles set role = coalesce(%s, role), active = coalesce(%s, active)
                    where id = %s
                    returning role, active
                    """,
                    (body.role, body.active, user_id),
                )
                row = await cur.fetchone()
                if row is None:
                    error = HTTPException(status_code=404, detail="not_found")
                else:
                    new_role, new_active = row
                    became_inactive = body.active is False and new_active is False
                    updated_row = (
                        target_row[0], target_row[1], target_row[2], new_role,
                        new_active, target_row[5], target_row[6],
                    )

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
