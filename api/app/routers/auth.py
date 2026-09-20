"""Login, refresh rotation, logout, /me, and password reset.

Two owner-mode call sites, each named per the design's requirement that
every as_owner() use say why at the call site:
- POST /auth/login needs users.password_hash, which app_user cannot see.
- POST /auth/refresh, /auth/logout and /auth/password/* read or write
  refresh_tokens / password_resets / login_attempts, all owner-only tables
  (no RLS, no grants to app_user - see migrations/0003_auth_tables.sql).

GET /auth/me is the only endpoint here that runs as_user: it reads nothing
an operatore should not see about their own profile and business.
"""
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

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
    rotate_refresh_token,
    sha256_hex,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

LOCKOUT_THRESHOLD = 5
RESET_TOKEN_TTL = timedelta(hours=1)


# --------------------------------------------------------------- schemas

class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


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


async def _record_attempt(email: str, succeeded: bool) -> None:
    """Deliberately its own owner-mode transaction, not the caller's: the
    caller usually inserts a failure and then raises an HTTPException in
    the same breath, and raising inside the *same* as_owner() transaction
    would roll the insert back along with everything else - the whole
    point of recording a failed attempt is that it survives the 401/403
    that follows it."""
    async with as_owner() as conn:
        await conn.execute(
            "insert into login_attempts (email, succeeded) values (%s, %s)",
            (email, succeeded),
        )


# -------------------------------------------------------------------- login

@router.post("/login", response_model=TokenPair)
async def login(body: LoginRequest):
    # runs as owner: needs users.password_hash, which app_user cannot see.
    async with as_owner() as conn:
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
            raise HTTPException(status_code=423, detail="too_many_attempts")

        cur = await conn.execute(
            "select id, password_hash from users where email = %s", (body.email,)
        )
        row = await cur.fetchone()

        # Unknown email and wrong password both fall through to the same
        # 401 below - never reveal which one it was.
        user_id = None
        password_ok = False
        if row is not None:
            user_id, password_hash_value = row
            password_ok = verify_password(body.password, password_hash_value)

        if not password_ok:
            await _record_attempt(body.email, succeeded=False)
            raise HTTPException(status_code=401, detail="invalid_credentials")

        profile = await _load_profile(conn, user_id)
        if profile is None or not profile.active:
            # Correct password but a deactivated (or profile-less) account
            # still counts as a failed attempt.
            await _record_attempt(body.email, succeeded=False)
            raise HTTPException(status_code=403, detail="deactivated")

        await _record_attempt(body.email, succeeded=True)

        access_token = create_access_token(profile.id, profile.business_id, profile.role)
        refresh_token = await issue_refresh_token(conn, profile.id)

        return TokenPair(
            access_token=access_token, refresh_token=refresh_token, profile=profile
        )


# ------------------------------------------------------------------ refresh

@router.post("/refresh", response_model=RefreshResponse)
async def refresh(body: RefreshRequest):
    # runs as owner: rotates a row in refresh_tokens, an owner-only table
    # with no RLS and no grants to app_user.
    async with as_owner() as conn:
        try:
            user_id, new_raw = await rotate_refresh_token(conn, body.refresh_token)
        except RefreshTokenError:
            raise HTTPException(status_code=401, detail="invalid_token")

        cur = await conn.execute(
            "select business_id, role from profiles where id = %s", (user_id,)
        )
        row = await cur.fetchone()
        if row is None:
            raise HTTPException(status_code=401, detail="invalid_token")
        business_id, role = row

        access_token = create_access_token(user_id, business_id, role)
        return RefreshResponse(access_token=access_token, refresh_token=new_raw)


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
            # A valid, well-signed token for a profile that no longer
            # exists (or was deactivated - RLS still returns it here since
            # profiles_select does not filter on active, only /me's own
            # code would need to for that) is treated the same as any
            # other unusable credential.
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
    async with as_owner() as conn:
        cur = await conn.execute(
            "select id, user_id, expires_at, used_at from password_resets "
            "where token_hash = %s",
            (token_hash,),
        )
        row = await cur.fetchone()
        if row is None:
            raise HTTPException(status_code=401, detail="invalid_token")
        reset_id, user_id, expires_at, used_at = row
        if used_at is not None or expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="invalid_token")

        new_hash = hash_password(body.password)
        await conn.execute(
            "update users set password_hash = %s where id = %s", (new_hash, user_id)
        )
        await conn.execute(
            "update password_resets set used_at = now() where id = %s", (reset_id,)
        )
        await conn.execute(
            "update refresh_tokens set revoked_at = now() "
            "where user_id = %s and revoked_at is null",
            (user_id,),
        )
    return {"ok": True}
