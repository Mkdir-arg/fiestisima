"""Shared fixtures for the API test suite.

Tests run against the real database configured in api/.env.test (Railway's
fiestisima-db). Fixtures that need users/profiles insert directly as the
database owner, exactly the way login/invitation-acceptance/migrations are
the only three owner-mode call sites the design allows.
"""
import asyncio
import os
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from dotenv import load_dotenv

# psycopg's async mode cannot run on Windows' default ProactorEventLoop.
# No-op on Linux/macOS (already selector-based there, including CI/Railway).
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

API_DIR = Path(__file__).resolve().parent.parent
load_dotenv(API_DIR / ".env.test", override=True)

# Imported only after .env.test is loaded into the environment, so
# app.config.settings (built at import time) resolves DATABASE_URL to the
# test database, not whatever api/.env would otherwise supply.
from app.db import pool, as_owner  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402

# Every test user in the `business` fixture shares this password, hashed
# once at import time with the real argon2id hasher (not a fake string) so
# test_auth.py can exercise actual login/verify against it. Hashing is slow
# by design (argon2id); doing it once per test session instead of once per
# fixture instance keeps the suite fast.
TEST_PASSWORD = "Correct-Horse-Battery-Staple-1"
TEST_PASSWORD_HASH = hash_password(TEST_PASSWORD)


@pytest.fixture(scope="session")
def db_url() -> str:
    return os.environ["DATABASE_URL"]


@pytest.fixture(scope="session", autouse=True)
async def _pool_lifecycle():
    await pool.open()
    yield
    await pool.close()


@pytest.fixture
async def client():
    """An httpx client talking to the real FastAPI app in-process (ASGI
    transport, no network/socket), sharing the same connection pool the
    _pool_lifecycle fixture already opened - the app's own lifespan is not
    triggered by ASGITransport, so the pool must already be open."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def owner():
    """A single owner-mode transaction (RLS does not apply): the fixture
    equivalent of the runner/login/invitation-acceptance call sites."""
    async with as_owner() as conn:
        yield conn


async def _insert_user_profile(conn, business_id, role: str, suffix: str) -> tuple[uuid.UUID, str]:
    email = f"test-{role}-{suffix}@fiestisima-tests.invalid"
    cur = await conn.execute(
        "insert into users (email, password_hash) values (%s, %s) returning id",
        (email, TEST_PASSWORD_HASH),
    )
    row = await cur.fetchone()
    user_id = row[0]
    await conn.execute(
        "insert into profiles (id, business_id, full_name, role) values (%s, %s, %s, %s)",
        (user_id, business_id, f"Test {role} {suffix}", role),
    )
    return user_id, email


async def _create_business_with_profiles(conn, label: str) -> SimpleNamespace:
    suffix = uuid.uuid4().hex[:8]
    cur = await conn.execute(
        "insert into businesses (name) values (%s) returning id",
        (f"Test business {label} {suffix}",),
    )
    row = await cur.fetchone()
    business_id = row[0]

    titolare_id, titolare_email = await _insert_user_profile(conn, business_id, "titolare", suffix)
    responsabile_id, responsabile_email = await _insert_user_profile(
        conn, business_id, "responsabile", suffix
    )
    operatore_id, operatore_email = await _insert_user_profile(conn, business_id, "operatore", suffix)

    return SimpleNamespace(
        business_id=business_id,
        titolare_id=titolare_id,
        responsabile_id=responsabile_id,
        operatore_id=operatore_id,
        user_ids=[titolare_id, responsabile_id, operatore_id],
        titolare_email=titolare_email,
        responsabile_email=responsabile_email,
        operatore_email=operatore_email,
        # Every user above shares this plaintext password; TEST_PASSWORD_HASH
        # is what got stored, this is what a login request sends.
        password=TEST_PASSWORD,
    )


async def _teardown_business(data: SimpleNamespace) -> None:
    # Dependency order: movements -> lots -> profiles -> users -> businesses.
    # profiles.id already cascades from users, and businesses cascades to
    # profiles/lots/movements on its own, but lots/movements are "on delete
    # restrict" against profiles - deleting a business straight through
    # would fire the profiles cascade before the lots/movements ones and
    # abort on the still-referenced rows. Explicit order avoids that and
    # makes a teardown regression fail loudly, one assertion per step.
    async with as_owner() as conn:
        # These two deletes are guaranteed to affect zero rows for any
        # fixture that never creates lots or movements itself - asserted as
        # such rather than "rowcount is not None", which DELETE always
        # satisfies (0, not None) and so proves nothing about the delete
        # actually running.
        result = await conn.execute(
            "delete from movements where business_id = %s", (data.business_id,)
        )
        assert result.rowcount == 0, f"expected no movements, got {result.rowcount}"

        result = await conn.execute(
            "delete from lots where business_id = %s", (data.business_id,)
        )
        assert result.rowcount == 0, f"expected no lots, got {result.rowcount}"

        result = await conn.execute(
            "delete from profiles where business_id = %s", (data.business_id,)
        )
        assert result.rowcount == 3, f"expected 3 profiles deleted, got {result.rowcount}"

        result = await conn.execute(
            "delete from users where id = any(%s)", (data.user_ids,)
        )
        assert result.rowcount == 3, f"expected 3 users deleted, got {result.rowcount}"

        result = await conn.execute(
            "delete from businesses where id = %s", (data.business_id,)
        )
        assert result.rowcount == 1, "business teardown did not run"


@pytest.fixture
async def business():
    """A throwaway business with a titolare, a responsabile and an
    operatore, each with a real profile. Random suffix per run so the
    suite can be re-run against the same database indefinitely."""
    async with as_owner() as conn:
        data = await _create_business_with_profiles(conn, "a")
    yield data
    await _teardown_business(data)


@pytest.fixture
async def other_business():
    """A second, independent business - for cross-tenant checks (a token
    from `business` must never reach these rows, and vice versa)."""
    async with as_owner() as conn:
        data = await _create_business_with_profiles(conn, "b")
    yield data
    await _teardown_business(data)
