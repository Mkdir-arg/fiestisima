"""Login, refresh rotation, logout, /me, and password reset.

Two owner-mode call sites, each named per the design's requirement that
every as_owner() use say why at the call site:
- POST /auth/login needs users.password_hash, which app_user cannot see.
- POST /auth/refresh, /auth/logout and /auth/password/* read or write
  refresh_tokens / password_resets / login_attempts, all owner-only tables
  (no RLS, no grants to app_user - see migrations/0003_auth_tables.sql).

GET /auth/me is the only endpoint here that runs as_user: it reads nothing
an operatore should not see about their own profile and business.

Never open a second pool connection inside an as_owner()/as_user() block.
The pool is small (db.py's max_size=10) and every request already holds
one connection for the duration of its transaction; a handler that opens a
second one while the first is still open (as an earlier version of this
file did, for "record this attempt/revocation in a transaction that
survives the error I'm about to raise") can deadlock the pool under
concurrency - N concurrent requests each hold connection 1 and block on
checking out connection 2, all waiting on each other, until every one of
them times out. The fix used throughout this file instead: never raise
inside the as_owner()/as_user() block. Do every write for both the success
and failure paths on the one `conn` the block already holds, record which
HTTPException (if any) applies in a plain local variable, let the block
exit normally (which commits), and only then raise or return based on
that variable.

Exception: a block that only reads never needs this dance - there is
nothing pending to commit that a raised exception could lose, so a
read-only as_owner()/as_user() block (GET /invitations/{token} and
GET /businesses/me, for instance) may raise HTTPException directly inside
it. The rule above is really about not discarding an unfinished write, not
about the `raise` keyword itself.
"""
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..config import settings
from ..db import as_owner, as_user
from ..mail import get_mailer
from ..security import (
    CurrentUser,
    RefreshTokenError,
    create_access_token,
    hash_password,
    issue_refresh_token,
    require_user,
    revoke_all_refresh_tokens,
    rotate_refresh_token,
    sha256_hex,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

LOCKOUT_THRESHOLD = 5
RESET_TOKEN_TTL = timedelta(hours=1)
# RFC 5321's own limit on a mailbox address, used as a plain sanity bound
# on the request body - not full email validation (kept out to avoid an
# extra dependency; an invalid-but-short string just fails the lookup).
EMAIL_MAX_LENGTH = 254
# Matches the client's invite screen rule (docs/04): 8 characters minimum
# for a password a person chooses. Login has no minimum - a password
# hashed before this rule existed can be shorter, and login must keep
# accepting it.
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 1024

# A fixed, valid argon2id hash of a random string nobody will ever type,
# computed once at import time. login() runs verify_password against this
# whenever the submitted email does not exist, so a real password check
# (argon2id's own, deliberately slow, work factor) always happens on the
# request's critical path - a request for an unknown email should take
# indistinguishably long from one for a real email with a wrong password,
# or timing alone would reveal which addresses are registered.
_DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))


# --------------------------------------------------------------- schemas

class LoginRequest(BaseModel):
    email: str = Field(max_length=EMAIL_MAX_LENGTH)
    # No min_length: a password hashed before the 8-character rule existed
    # must still be able to log in.
    password: str = Field(max_length=PASSWORD_MAX_LENGTH)


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: str = Field(max_length=EMAIL_MAX_LENGTH)


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class BusinessOut(BaseModel):
    id: UUID
    name: str
    expiry_threshold_days: int


class ProfileOut(BaseModel):
    id: UUID
    business_id: UUID
    full_name: str
    role: str
    active: bool
    business: BusinessOut


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    profile: ProfileOut


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str


# ------------------------------------------------------------------ helpers

async def _load_profile(conn, user_id: UUID) -> ProfileOut | None:
    """Profile + business, joined in one query. Callers pass either an
    as_owner() connection (login, right after verifying the password) or an
    as_user() one (GET /me) - RLS scopes the as_user() case to the caller's
    own row either way, so the query itself never needs to change."""
    cur = await conn.execute(
        """
        select p.id, p.business_id, p.full_name, p.role, p.active,
               b.id, b.name, b.expiry_threshold_days
        from profiles p
        join businesses b on b.id = p.business_id
        where p.id = %s
        """,
        (user_id,),
    )
    row = await cur.fetchone()
    if row is None:
        return None
    pid, business_id, full_name, role, active, bid, bname, bexp = row
    return ProfileOut(
        id=pid,
        business_id=business_id,
        full_name=full_name,
        role=role,
        active=active,
        business=BusinessOut(id=bid, name=bname, expiry_threshold_days=bexp),
    )


async def _record_attempt(conn, email: str, succeeded: bool) -> None:
    await conn.execute(
        "insert into login_attempts (email, succeeded) values (%s, %s)",
        (email, succeeded),
    )


# -------------------------------------------------------------------- login

@router.post("/login", response_model=TokenPair)
async def login(body: LoginRequest):
    # runs as owner: needs users.password_hash, which app_user cannot see.
    error: HTTPException | None = None
    result: TokenPair | None = None

    async with as_owner() as conn:
        # Deliberately not self-extending: a request rejected here (423)
        # is never itself inserted into login_attempts, so the lockout
        # always expires 15 minutes after the 5th failure, however many
        # more attempts land while it is in effect. docs/04 specifies
        # "5 fallos -> 15 minutos"; if a rejected attempt also counted, a
        # third party could keep the real owner locked out indefinitely
        # just by continuing to hammer the endpoint.
        cur = await conn.execute(
            """
            select count(*) from login_attempts
            where email = %s and succeeded = false
              and attempted_at > now() - interval '15 minutes'
            """,
            (body.email,),
        )
        (failed_count,) = await cur.fetchone()
        if failed_count >= LOCKOUT_THRESHOLD:
            error = HTTPException(status_code=423, detail="too_many_attempts")
        else:
            cur = await conn.execute(
                "select id, password_hash from users where email = %s", (body.email,)
            )
            row = await cur.fetchone()

            # Unknown email and wrong password both fall through to the
            # same 401 below - never reveal which one it was. verify_password
            # always runs, against a real (if unrelated) argon2id hash even
            # when the email does not exist, so a missing row costs the same
            # wall-clock time as a wrong password on a real one.
            if row is not None:
                user_id, password_hash_value = row
            else:
                user_id, password_hash_value = None, _DUMMY_PASSWORD_HASH
            password_ok = verify_password(body.password, password_hash_value) and user_id is not None

            if not password_ok:
                await _record_attempt(conn, body.email, succeeded=False)
                error = HTTPException(status_code=401, detail="invalid_credentials")
            else:
                profile = await _load_profile(conn, user_id)
                if profile is None or not profile.active:
                    # Correct password but a deactivated (or profile-less)
                    # account still counts as a failed attempt.
                    await _record_attempt(conn, body.email, succeeded=False)
                    error = HTTPException(status_code=403, detail="deactivated")
                else:
                    await _record_attempt(conn, body.email, succeeded=True)
                    access_token = create_access_token(
                        profile.id, profile.business_id, profile.role
                    )
                    refresh_token = await issue_refresh_token(conn, profile.id)
                    result = TokenPair(
                        access_token=access_token,
                        refresh_token=refresh_token,
                        profile=profile,
                    )

    if error is not None:
        raise error
    return result


# ------------------------------------------------------------------ refresh

@router.post("/refresh", response_model=RefreshResponse)
async def refresh(body: RefreshRequest):
    # runs as owner: reads/writes refresh_tokens, an owner-only table with
    # no RLS and no grants to app_user.
    error: HTTPException | None = None
    result: RefreshResponse | None = None

    async with as_owner() as conn:
        try:
            user_id, new_raw = await rotate_refresh_token(conn, body.refresh_token)
        except RefreshTokenError:
            error = HTTPException(status_code=401, detail="invalid_token")
        else:
            cur = await conn.execute(
                "select business_id, role, active from profiles where id = %s", (user_id,)
            )
            row = await cur.fetchone()
            if row is None:
                error = HTTPException(status_code=401, detail="invalid_token")
            else:
                business_id, role, active = row
                if not active:
                    # The profile was deactivated some time after this
                    # refresh token was issued (up to refresh_token_days
                    # ago, including the brand-new one rotate_refresh_token
                    # just minted above). Close the session now instead of
                    # handing back an access token: revoke every refresh
                    # token this user holds, on the same `conn` - it
                    # commits with everything else once this block exits,
                    # since the 403 below is raised only after that.
                    await revoke_all_refresh_tokens(conn, user_id)
                    error = HTTPException(status_code=403, detail="deactivated")
                else:
                    access_token = create_access_token(user_id, business_id, role)
                    result = RefreshResponse(access_token=access_token, refresh_token=new_raw)

    if error is not None:
        raise error
    return result


# ------------------------------------------------------------------- logout

@router.post("/logout")
async def logout(body: RefreshRequest):
    # runs as owner: revokes a row in refresh_tokens, an owner-only table
    # with no RLS and no grants to app_user.
    token_hash = sha256_hex(body.refresh_token)
    async with as_owner() as conn:
        await conn.execute(
            "update refresh_tokens set revoked_at = now() "
            "where token_hash = %s and revoked_at is null",
            (token_hash,),
        )
    return {"ok": True}


# ---------------------------------------------------------------------- me

@router.get("/me", response_model=ProfileOut)
async def me(current_user: CurrentUser = Depends(require_user)):
    async with as_user(current_user.id) as conn:
        profile = await _load_profile(conn, current_user.id)
        if profile is None:
            # Covers a profile that no longer exists, and also a
            # deactivated one: app_business_id() (used by profiles_select's
            # own "business_id = app_business_id()" policy) only resolves a
            # business for an *active* profile, so once deactivated, RLS
            # hides this row even from its own owner, not just from
            # colleagues. A valid, well-signed token for either case is
            # treated the same as any other unusable credential - 401, not
            # 403, here. The client's refresh retry is what actually
            # surfaces 403 deactivated (see /auth/refresh), which is the
            # flow Task 6 implements.
            raise HTTPException(status_code=401, detail="invalid_token")
        return profile


# ----------------------------------------------------------- password reset

@router.post("/password/forgot", status_code=202)
async def forgot_password(body: ForgotPasswordRequest):
    # runs as owner: looks up users (no RLS/grants on that table either)
    # and writes password_resets, an owner-only table.
    async with as_owner() as conn:
        cur = await conn.execute("select id from users where email = %s", (body.email,))
        row = await cur.fetchone()
        if row is not None:
            user_id = row[0]
            # At most one live reset token per user: an earlier request
            # that was never used (a second "forgot my password" click, or
            # an abandoned one) should not stay valid once a fresh token is
            # issued.
            await conn.execute(
                "update password_resets set used_at = now() "
                "where user_id = %s and used_at is null",
                (user_id,),
            )
            raw_token = secrets.token_urlsafe(32)
            token_hash = sha256_hex(raw_token)
            expires_at = datetime.now(timezone.utc) + RESET_TOKEN_TTL
            await conn.execute(
                "insert into password_resets (user_id, token_hash, expires_at) "
                "values (%s, %s, %s)",
                (user_id, token_hash, expires_at),
            )
            await get_mailer().send(
                to=body.email,
                subject="Password reset",
                body=f"Password reset requested for {body.email}: "
                f"{settings.site_url}/reset-password/{raw_token}",
            )
    # Always 202, whether or not the email exists - never reveal that.
    return {"ok": True}


@router.post("/password/reset")
async def reset_password(body: ResetPasswordRequest):
    # runs as owner: password_resets is owner-only, and updating
    # users.password_hash needs the same owner path login itself uses.
    token_hash = sha256_hex(body.token)
    error: HTTPException | None = None

    async with as_owner() as conn:
        # Mark-then-act, and the mark is the single-use gate: an UPDATE
        # that both consumes the token and re-checks it is still live, in
        # one atomic statement, so two concurrent reset requests with the
        # same token cannot both pass this check the way two separate
        # SELECT-then-UPDATE steps could race to do. Exactly one of them
        # gets a row back; the other gets none and is rejected below, same
        # as a token that was never valid.
        cur = await conn.execute(
            """
            update password_resets set used_at = now()
            where token_hash = %s and used_at is null and expires_at > now()
            returning id, user_id
            """,
            (token_hash,),
        )
        row = await cur.fetchone()
        if row is None:
            error = HTTPException(status_code=401, detail="invalid_token")
        else:
            _, user_id = row
            cur = await conn.execute(
                "select active from profiles where id = %s", (user_id,)
            )
            profile_row = await cur.fetchone()
            active = profile_row[0] if profile_row is not None else False
            if not active:
                # Same reasoning as /auth/refresh: a deactivated account
                # must not be able to set a new password or keep any
                # session alive. The token above is already consumed
                # either way - a deactivated account does not get to try
                # it again once reactivated.
                await revoke_all_refresh_tokens(conn, user_id)
                error = HTTPException(status_code=403, detail="deactivated")
            else:
                new_hash = hash_password(body.password)
                await conn.execute(
                    "update users set password_hash = %s where id = %s",
                    (new_hash, user_id),
                )
                await revoke_all_refresh_tokens(conn, user_id)

    if error is not None:
        raise error
    return {"ok": True}
