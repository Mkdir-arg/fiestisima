from contextlib import asynccontextmanager
from uuid import UUID
from psycopg_pool import AsyncConnectionPool
from .config import settings

pool = AsyncConnectionPool(settings.database_url, open=False, min_size=1, max_size=10)

@asynccontextmanager
async def as_user(user_id: UUID):
    """One transaction as the application role, with the caller's identity set.
    RLS policies read app.user_id through app_user_id(). set local is undone at commit/rollback."""
    async with pool.connection() as conn:
        async with conn.transaction():
            await conn.execute("set local role app_user")
            await conn.execute("select set_config('app.user_id', %s, true)", (str(user_id),))
            yield conn

@asynccontextmanager
async def as_owner():
    """-- runs as owner: no set role, RLS does not apply. Call sites: login,
    refresh/logout/password (routers/auth.py - refresh_tokens/password_resets/
    login_attempts have no RLS and no grants to app_user), invitation preview
    and acceptance (routers/invitations.py), the post-deactivation refresh
    token revoke in PATCH /users/{id} (routers/users.py, in its own block
    after the as_user() write has committed), migrations (scripts/migrate.py),
    and /health (main.py, no caller identity to set). Say why at every call
    site."""
    async with pool.connection() as conn:
        async with conn.transaction():
            yield conn
