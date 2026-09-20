"""Password hashing, JWT access tokens, opaque refresh tokens, and the
`require_user` dependency every protected endpoint depends on.

Nothing here talks to the database directly except issue_refresh_token and
rotate_refresh_token, which take an already-open connection (always an
as_owner() one - refresh_tokens has no RLS and no grants to app_user, see
migrations/0003_auth_tables.sql) so the caller controls the transaction.
"""
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from fastapi import Header, HTTPException
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from .config import settings

_password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    # UnknownHashError fires on any hash pwdlib's configured hashers do not
    # recognise - a corrupt or foreign-format row, not the caller's fault.
    # Without this, that one bad row would 500 instead of just failing the
    # login it belongs to, same as a wrong password would.
    try:
        return _password_hasher.verify(password, password_hash)
    except UnknownHashError:
        return False


def sha256_hex(raw: str) -> str:
    """Used to store both refresh tokens and password-reset tokens: the raw
    value is only ever mailed or held by the client, never persisted."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ------------------------------------------------------------- access token

def create_access_token(user_id: UUID, business_id: UUID, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "bid": str(business_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    """Raises jwt.PyJWTError (or a subclass) on any failure - expired,
    tampered signature, malformed - which require_user turns into a 401."""
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    business_id: UUID
    role: str


async def require_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="invalid_token")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_access_token(token)
        return CurrentUser(
            id=UUID(payload["sub"]),
            business_id=UUID(payload["bid"]),
            role=payload["role"],
        )
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="invalid_token")


# ------------------------------------------------------------ refresh token

class RefreshTokenError(Exception):
    """A refresh token that is missing, expired, or already revoked. Never
    raised across an API boundary directly - routers/auth.py catches it and
    answers 401 invalid_token, uniformly for all three causes."""


async def issue_refresh_token(conn, user_id: UUID) -> str:
    raw = secrets.token_urlsafe(32)
    token_hash = sha256_hex(raw)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days)
    await conn.execute(
        "insert into refresh_tokens (user_id, token_hash, expires_at) values (%s, %s, %s)",
        (user_id, token_hash, expires_at),
    )
    return raw


async def rotate_refresh_token(conn, raw: str) -> tuple[UUID, str]:
    """Resolves a refresh token, revokes it, and issues its successor - the
    single code path /auth/refresh uses.

    The revoke is the concurrency gate, not the SELECT below: two
    concurrent calls with the same raw token could both read revoked_at IS
    NULL from the SELECT before either one writes, and without a guard on
    the UPDATE both would go on to mint a successor for the same
    predecessor token. Folding "and revoked_at is null" into the UPDATE's
    own WHERE clause makes the database, not this function's control flow,
    decide which of two racing callers gets to revoke the row; the loser's
    rowcount is 0 and it fails the same way a replayed token would.
    """
    token_hash = sha256_hex(raw)
    cur = await conn.execute(
        "select id, user_id, expires_at, revoked_at from refresh_tokens where token_hash = %s",
        (token_hash,),
    )
    row = await cur.fetchone()
    if row is None:
        raise RefreshTokenError("not_found")
    token_id, user_id, expires_at, revoked_at = row
    if revoked_at is not None:
        raise RefreshTokenError("revoked")
    if expires_at < datetime.now(timezone.utc):
        raise RefreshTokenError("expired")

    cur = await conn.execute(
        "update refresh_tokens set revoked_at = now() where id = %s and revoked_at is null",
        (token_id,),
    )
    if cur.rowcount != 1:
        # Lost the race: another concurrent rotation of this exact token
        # got there first, between the SELECT above and this UPDATE.
        raise RefreshTokenError("revoked")

    new_raw = await issue_refresh_token(conn, user_id)
    return user_id, new_raw


async def revoke_all_refresh_tokens(conn, user_id: UUID) -> None:
    """Revokes every refresh token a user currently holds. Used on a
    successful password reset, and when /auth/refresh or
    /auth/password/reset discover the profile was deactivated after the
    token in hand was issued - a deactivated account must not be able to
    keep minting access tokens for up to refresh_token_days.

    TODO(task-4): also call this from PATCH /users/{id} when a titolare
    deactivates a user, so an existing session cannot outlive the
    deactivation by waiting out access_token_minutes instead of hitting
    /auth/refresh at all.
    """
    await conn.execute(
        "update refresh_tokens set revoked_at = now() "
        "where user_id = %s and revoked_at is null",
        (user_id,),
    )
