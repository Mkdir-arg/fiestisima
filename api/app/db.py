from contextlib import asynccontextmanager
from uuid import UUID
from psycopg_pool import AsyncConnectionPool
from .config import settings

# `check` is what makes a restarted database survivable: without it the
# pool hands out a connection it still believes is good, the first query
# on it raises OperationalError, and every request until the pool happens
# to recycle that entry 500s. Seen for real after a fiestisima-db restart,
# when /health kept failing on a dead pooled connection. check_connection
# tests the connection on checkout and discards it if it is broken.
pool = AsyncConnectionPool(
    settings.database_url,
    open=False,
    min_size=1,
    max_size=10,
    check=AsyncConnectionPool.check_connection,
    # The default is 30s. A request that cannot get a connection should
    # answer 503 while the phone is still holding the screen open, not
    # half a minute later once the healthcheck has already given up.
    timeout=8,
)

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
