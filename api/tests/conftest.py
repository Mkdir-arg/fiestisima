"""Shared fixtures for the API test suite.

Tests run against the real database configured in api/.env.test (Railway's
fiestisima-db). There is no API yet (Task 3 brings routers and password
hashing), so fixtures that need users/profiles insert directly as the
database owner, exactly the way login/invitation-acceptance/migrations are
the only three owner-mode call sites the design allows.
"""
import asyncio
import os
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

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


@pytest.fixture(scope="session")
def db_url() -> str:
    return os.environ["DATABASE_URL"]


@pytest.fixture(scope="session", autouse=True)
async def _pool_lifecycle():
    await pool.open()
    yield
    await pool.close()


@pytest.fixture
async def owner():
    """A single owner-mode transaction (RLS does not apply): the fixture
    equivalent of the runner/login/invitation-acceptance call sites."""
    async with as_owner() as conn:
        yield conn


async def _insert_user_profile(conn, business_id, role: str, suffix: str) -> uuid.UUID:
    email = f"test-{role}-{suffix}@fiestisima-tests.invalid"
    cur = await conn.execute(
        "insert into users (email, password_hash) values (%s, %s) returning id",
        (email, "not-a-real-hash-task-3-brings-argon2"),
    )
    row = await cur.fetchone()
    user_id = row[0]
    await conn.execute(
        "insert into profiles (id, business_id, full_name, role) values (%s, %s, %s, %s)",
        (user_id, business_id, f"Test {role} {suffix}", role),
    )
    return user_id


@pytest.fixture
async def business():
    """A throwaway business with a titolare, a responsabile and an
    operatore, each with a real profile. Random suffix per run so the
    suite can be re-run against the same database indefinitely."""
    suffix = uuid.uuid4().hex[:8]

    async with as_owner() as conn:
        cur = await conn.execute(
            "insert into businesses (name) values (%s) returning id",
            (f"Test business {suffix}",),
        )
        row = await cur.fetchone()
        business_id = row[0]

        titolare_id = await _insert_user_profile(conn, business_id, "titolare", suffix)
        responsabile_id = await _insert_user_profile(conn, business_id, "responsabile", suffix)
        operatore_id = await _insert_user_profile(conn, business_id, "operatore", suffix)

    data = SimpleNamespace(
        business_id=business_id,
        titolare_id=titolare_id,
        responsabile_id=responsabile_id,
        operatore_id=operatore_id,
        user_ids=[titolare_id, responsabile_id, operatore_id],
    )

    yield data

    # Dependency order: movements -> lots -> profiles -> users -> businesses.
    # profiles.id already cascades from users, and businesses cascades to
    # profiles/lots/movements on its own, but lots/movements are "on delete
    # restrict" against profiles - deleting a business straight through
    # would fire the profiles cascade before the lots/movements ones and
    # abort on the still-referenced rows. Explicit order avoids that and
    # makes a teardown regression fail loudly, one assertion per step.
    async with as_owner() as conn:
        result = await conn.execute(
            "delete from movements where business_id = %s", (business_id,)
        )
        assert result.rowcount is not None, "movements teardown did not run"

        result = await conn.execute("delete from lots where business_id = %s", (business_id,))
        assert result.rowcount is not None, "lots teardown did not run"

        result = await conn.execute(
            "delete from profiles where business_id = %s", (business_id,)
        )
        assert result.rowcount == 3, f"expected 3 profiles deleted, got {result.rowcount}"

        result = await conn.execute(
            "delete from users where id = any(%s)", (data.user_ids,)
        )
        assert result.rowcount == 3, f"expected 3 users deleted, got {result.rowcount}"

        result = await conn.execute("delete from businesses where id = %s", (business_id,))
        assert result.rowcount == 1, "business teardown did not run"
