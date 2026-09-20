"""Invite, preview, accept, resend, cancel.

Two call sites here run as owner, each named per the design's rule that
every as_owner() use say why:
- GET /invitations/{token} is public and read-only: no caller identity to
  set, and it exposes only full_name/business name/expires_at, never the
  email or business id (the accept screen must not leak who was invited to
  a stranger holding the link).
- POST /invitations/{token}/accept is public and creates users + profiles
  atomically, exactly the one owner-mode write path the design carves out
  for invitation acceptance (besides login and migrations).

Everything else here runs as_user: RLS (invitations_all) already restricts
POST /invitations and DELETE/resend to a titolare of the same business, so
none of this file ever inspects current_user.role or .business_id to decide
who may do what - see db.py's as_user()/as_owner() and the module comment
in routers/auth.py for the same rule.

One departure worth flagging: resend and delete are UPDATE/DELETE
statements gated only by invitations_all's USING clause (no trigger, unlike
profiles). A USING-clause mismatch is not a Postgres error - Postgres just
filters the row out of the target set (see the CREATE POLICY docs: "rows
for which the expression returns false or null will not be visible" - no
exception, rowcount 0 exactly as if the id did not exist). A responsabile
resending or deleting therefore gets 404, not 403 - the same rowcount-0-is-
not-an-error rule this file follows for PATCH /users/{id} and PATCH
/businesses/me. Only POST /invitations (an INSERT) can produce a genuine
42501 here, because an INSERT's WITH CHECK failure IS a Postgres error
(there is no existing row to filter).
"""
import logging
from datetime import datetime
from typing import Literal
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..config import settings
from ..db import as_owner, as_user
from ..mail import get_mailer
from ..security import CurrentUser, create_access_token, hash_password, issue_refresh_token, require_user
from .auth import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH, TokenPair, _load_profile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invitations", tags=["invitations"])

Role = Literal["titolare", "responsabile", "operatore"]

# Same rationale as auth.py's EMAIL_MAX_LENGTH: RFC 5321's own mailbox
# length limit, a sanity bound, not full email validation.
EMAIL_MAX_LENGTH = 254
FULL_NAME_MAX_LENGTH = 200


# --------------------------------------------------------------- schemas

class CreateInvitationRequest(BaseModel):
    email: str = Field(max_length=EMAIL_MAX_LENGTH)
    full_name: str = Field(min_length=1, max_length=FULL_NAME_MAX_LENGTH)
    role: Role


class InvitationOut(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: str
    expires_at: datetime
    # False when the row committed but the mail provider failed - the
    # invitation still exists and can be resent; the caller should not be
    # told the whole request failed (mailing is best-effort, the write is
    # not) but does need to know the link never actually went out.
    mail_sent: bool


class InvitationPreview(BaseModel):
    full_name: str
    business_name: str
    expires_at: datetime


class AcceptInvitationRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=FULL_NAME_MAX_LENGTH)
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


async def _send_invite_mail(email: str, token) -> bool:
    """Sends the invite mail after its transaction has already committed,
    and never lets a mail-provider failure turn a committed invitation into
    a 500 - retrying the request would just hit invitation_pending (409)
    for a row that already exists. Returns whether the send succeeded so
    the caller can report it in the response instead."""
    link = f"{settings.site_url}/invito/{token}"
    try:
        await get_mailer().send(
            to=email,
            subject="Sei stato invitato su Fiestisima",
            body=f"Completa la registrazione: {link}",
        )
        return True
    except Exception:
        logger.exception("failed to send invitation mail to=%s", email)
        return False


# ------------------------------------------------------------------ create

@router.post("", response_model=InvitationOut, status_code=201)
async def create_invitation(
    body: CreateInvitationRequest, current_user: CurrentUser = Depends(require_user)
):
    # RLS (invitations_all's WITH CHECK) restricts this INSERT to a
    # titolare of the caller's own business - a non-titolare's insert
    # raises psycopg.errors.InsufficientPrivilege here, uncaught, and the
    # main.py handler turns it into 403. Nothing in this function checks
    # current_user.role.
    error: HTTPException | None = None
    created: dict | None = None

    async with as_user(current_user.id) as conn:
        try:
            cur = await conn.execute(
                """
                insert into invitations (business_id, email, full_name, role, invited_by)
                values (app_business_id(), %s, %s, %s, app_user_id())
                returning id, email, full_name, role, expires_at, token
                """,
                (body.email, body.full_name, body.role),
            )
            row = await cur.fetchone()
        except psycopg.errors.UniqueViolation:
            # invitations_pending_idx: one pending invite per (business,
            # email). The insert already failed and aborted this
            # transaction; letting the block exit normally below just
            # rolls it back, same as raising would have, without a second
            # connection.
            error = HTTPException(status_code=409, detail="invitation_pending")
        else:
            created = {
                "id": row[0], "email": row[1], "full_name": row[2],
                "role": row[3], "expires_at": row[4], "token": row[5],
            }

    if error is not None:
        raise error
    # Mailed after the transaction committed, not before: a mail that goes
    # out for a row that never actually got committed would be worse than
    # a committed row whose mail is delayed or lost.
    mail_sent = await _send_invite_mail(created["email"], created["token"])
    return InvitationOut(
        mail_sent=mail_sent,
        **{k: v for k, v in created.items() if k != "token"},
    )


# ------------------------------------------------------------------ preview

@router.get("/{token}", response_model=InvitationPreview)
async def preview_invitation(token: UUID):
    # runs as owner: public, no caller identity to set. Read-only, so
    # raising inside the block is fine (see the exemption noted in
    # routers/auth.py's module comment).
    async with as_owner() as conn:
        cur = await conn.execute(
            """
            select i.full_name, b.name, i.expires_at
            from invitations i
            join businesses b on b.id = i.business_id
            where i.token = %s and i.accepted_at is null and i.expires_at > now()
            """,
            (token,),
        )
        row = await cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="not_found")
        full_name, business_name, expires_at = row
        return InvitationPreview(
            full_name=full_name, business_name=business_name, expires_at=expires_at
        )


# ------------------------------------------------------------------- accept

@router.post("/{token}/accept", response_model=TokenPair)
async def accept_invitation(token: UUID, body: AcceptInvitationRequest):
    # runs as owner: creates users + profiles atomically, the one owner-mode
    # write path (besides login and migrations) the design allows. Single
    # transaction: the invitation gate, the users insert, and the profiles
    # insert all commit together or none does.
    error: HTTPException | None = None
    result: TokenPair | None = None

    async with as_owner() as conn:
        # The gate: marks the invitation accepted only if it is still
        # pending and unexpired, in one atomic statement so two concurrent
        # accepts of the same token cannot both pass.
        cur = await conn.execute(
            """
            update invitations set accepted_at = now()
            where token = %s and accepted_at is null and expires_at > now()
            returning business_id, email, role
            """,
            (token,),
        )
        row = await cur.fetchone()
        if row is None:
            error = HTTPException(status_code=410, detail="invitation_expired")
        else:
            business_id, email, role = row
            password_hash = hash_password(body.password)
            try:
                # citext (see 0001) makes this comparison and the unique
                # constraint it can violate case-insensitive: an email
                # differing only by case from an existing users row still
                # collides here, not just a byte-for-byte match.
                cur = await conn.execute(
                    "insert into users (email, password_hash) values (%s, %s) returning id",
                    (email, password_hash),
                )
            except psycopg.errors.UniqueViolation:
                # That email already has a users row. Postgres has already
                # aborted this transaction; letting the block exit normally
                # below commits nothing - the accepted_at write above rolls
                # back too, so the invitation is left exactly as pending as
                # it was before this request.
                error = HTTPException(status_code=409, detail="email_taken")
            else:
                (user_id,) = await cur.fetchone()
                await conn.execute(
                    "insert into profiles (id, business_id, full_name, role) "
                    "values (%s, %s, %s, %s)",
                    (user_id, business_id, body.full_name, role),
                )
                access_token = create_access_token(user_id, business_id, role)
                refresh_token = await issue_refresh_token(conn, user_id)
                profile = await _load_profile(conn, user_id)
                result = TokenPair(
                    access_token=access_token,
                    refresh_token=refresh_token,
                    profile=profile,
                )

    if error is not None:
        raise error
    return result


# ------------------------------------------------------------------- resend

@router.post("/{invitation_id}/resend", response_model=InvitationOut)
async def resend_invitation(
    invitation_id: UUID, current_user: CurrentUser = Depends(require_user)
):
    error: HTTPException | None = None
    created: dict | None = None

    async with as_user(current_user.id) as conn:
        cur = await conn.execute(
            """
            update invitations set expires_at = now() + interval '7 days'
            where id = %s and accepted_at is null
            returning id, email, full_name, role, expires_at, token
            """,
            (invitation_id,),
        )
        row = await cur.fetchone()
        if row is None:
            # Covers: no such invitation, a different business's
            # invitation, a non-titolare caller (invitations_all's USING
            # clause filters all three the same way, with no error to tell
            # them apart - see the module comment), and an already-accepted
            # invitation - resending a dead link is not a thing to do.
            error = HTTPException(status_code=404, detail="not_found")
        else:
            created = {
                "id": row[0], "email": row[1], "full_name": row[2],
                "role": row[3], "expires_at": row[4], "token": row[5],
            }

    if error is not None:
        raise error
    mail_sent = await _send_invite_mail(created["email"], created["token"])
    return InvitationOut(
        mail_sent=mail_sent,
        **{k: v for k, v in created.items() if k != "token"},
    )


# ------------------------------------------------------------------- delete

@router.delete("/{invitation_id}", status_code=204)
async def delete_invitation(
    invitation_id: UUID, current_user: CurrentUser = Depends(require_user)
):
    async with as_user(current_user.id) as conn:
        cur = await conn.execute(
            "delete from invitations where id = %s and accepted_at is null",
            (invitation_id,),
        )
        deleted = cur.rowcount
    if deleted == 0:
        raise HTTPException(status_code=404, detail="not_found")
    return None
