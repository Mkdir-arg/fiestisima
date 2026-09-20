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

from .config import settings

_password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hasher.verify(password, password_hash)


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
    """Looks the token up by hash, rejects it if missing/expired/revoked,
    marks it revoked, and issues its replacement - all inside the caller's
    transaction, so a failure here leaves nothing rotated."""
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

    await conn.execute(
        "update refresh_tokens set revoked_at = now() where id = %s", (token_id,)
    )
    new_raw = await issue_refresh_token(conn, user_id)
    return user_id, new_raw
