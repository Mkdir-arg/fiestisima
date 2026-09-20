"""The ledger v1 permission matrix, checked against the real database, as
owner (the only role allowed to query these catalogs freely).
"""
import psycopg
import pytest

from app.db import as_user


async def test_lots_column_select_privileges(owner):
    cur = await owner.execute(
        """
        select
          has_column_privilege('app_user', 'public.lots', 'unit_price', 'SELECT'),
          has_column_privilege('app_user', 'public.lots', 'document_url', 'SELECT'),
          has_column_privilege('app_user', 'public.lots', 'lot_code', 'SELECT')
        """
    )
    unit_price, document_url, lot_code = await cur.fetchone()
    assert unit_price is False
    assert document_url is False
    assert lot_code is True


async def test_lots_table_level_update_is_not_granted(owner):
    cur = await owner.execute(
        "select has_table_privilege('app_user', 'public.lots', 'UPDATE')"
    )
    (has_update,) = await cur.fetchone()
    assert has_update is False


async def test_lots_column_update_privileges(owner):
    cur = await owner.execute(
        """
        select
          has_column_privilege('app_user', 'public.lots', 'created_by', 'UPDATE'),
          has_column_privilege('app_user', 'public.lots', 'business_id', 'UPDATE'),
          has_column_privilege('app_user', 'public.lots', 'lot_code', 'UPDATE')
        """
    )
    created_by, business_id, lot_code = await cur.fetchone()
    assert created_by is False
    assert business_id is False
    assert lot_code is True


async def test_lots_table_level_insert_is_granted(owner):
    cur = await owner.execute(
        "select has_table_privilege('app_user', 'public.lots', 'INSERT')"
    )
    (has_insert,) = await cur.fetchone()
    assert has_insert is True


async def test_movements_has_no_update_or_delete_policy(owner):
    # The traceability record is immutable: exactly select/insert, nothing
    # else. Asserted as the exact set, not just "no UPDATE/DELETE/ALL rows"
    # - the earlier version of this filtered the query itself, so it would
    # have passed unchanged against an empty result from a query typo or a
    # dropped policy, not just against the real absence of a write policy.
    cur = await owner.execute(
        """
        select policyname, cmd from pg_policies
        where schemaname = 'public' and tablename = 'movements'
        """
    )
    rows = await cur.fetchall()
    assert set(rows) == {("movements_select", "SELECT"), ("movements_insert", "INSERT")}


async def test_delete_is_scoped_to_invitations_and_categories(owner):
    # 0004's ruling: cancelling an invitation and removing a free-text
    # category label are the only real deletes in the schema. Everything
    # else is either soft-deleted (products, suppliers) or was never
    # deletable to begin with (events, lots, movements, profiles,
    # businesses) - see 0004's own comment for the reasoning per table.
    cur = await owner.execute(
        """
        select
          has_table_privilege('app_user', 'public.invitations', 'DELETE'),
          has_table_privilege('app_user', 'public.categories', 'DELETE'),
          has_table_privilege('app_user', 'public.products', 'DELETE'),
          has_table_privilege('app_user', 'public.suppliers', 'DELETE'),
          has_table_privilege('app_user', 'public.events', 'DELETE'),
          has_table_privilege('app_user', 'public.lots', 'DELETE'),
          has_table_privilege('app_user', 'public.movements', 'DELETE'),
          has_table_privilege('app_user', 'public.profiles', 'DELETE'),
          has_table_privilege('app_user', 'public.businesses', 'DELETE')
        """
    )
    invitations, categories, *closed = await cur.fetchone()
    assert invitations is True
    assert categories is True
    assert all(privilege is False for privilege in closed)


async def test_profiles_role_guard_trigger_only_fires_on_update(owner):
    cur = await owner.execute(
        """
        select event_manipulation from information_schema.triggers
        where event_object_schema = 'public'
          and event_object_table = 'profiles'
          and trigger_name = 'profiles_block_self_role_change_trg'
        """
    )
    rows = await cur.fetchall()
    assert [r[0] for r in rows] == ["UPDATE"]


async def test_app_user_still_has_no_select_on_users_table(owner):
    # business_users (0006) exists precisely so GET /users never needs
    # direct access to users, where password_hash lives - the view is the
    # only door, and it carries no such column to leak through.
    cur = await owner.execute(
        "select has_table_privilege('app_user', 'public.users', 'SELECT')"
    )
    (has_select,) = await cur.fetchone()
    assert has_select is False


async def test_app_user_has_select_on_business_users_view(owner):
    cur = await owner.execute(
        "select has_table_privilege('app_user', 'public.business_users', 'SELECT')"
    )
    (has_select,) = await cur.fetchone()
    assert has_select is True


@pytest.mark.parametrize(
    "table", ["users", "refresh_tokens", "login_attempts", "password_resets"]
)
async def test_app_user_has_no_privilege_on_owner_only_auth_tables(owner, table):
    # These four tables carry credentials/tokens/attempt history and are
    # never touched through app_user's RLS-scoped session: the API reads
    # and writes them exclusively as owner (login, refresh/logout/password
    # endpoints - see routers/auth.py's "# runs as owner:" comments), so
    # app_user must have none of the four DML privileges on any of them.
    cur = await owner.execute(
        """
        select
          has_table_privilege('app_user', %(table)s, 'SELECT'),
          has_table_privilege('app_user', %(table)s, 'INSERT'),
          has_table_privilege('app_user', %(table)s, 'UPDATE'),
          has_table_privilege('app_user', %(table)s, 'DELETE')
        """,
        {"table": f"public.{table}"},
    )
    select_priv, insert_priv, update_priv, delete_priv = await cur.fetchone()
    assert select_priv is False
    assert insert_priv is False
    assert update_priv is False
    assert delete_priv is False


async def test_no_supabase_roles_remain(owner):
    cur = await owner.execute(
        "select rolname from pg_roles where rolname in ('anon', 'authenticated')"
    )
    rows = await cur.fetchall()
    assert rows == []


async def test_app_user_role_exists_and_is_nologin(owner):
    cur = await owner.execute(
        "select rolcanlogin from pg_roles where rolname = 'app_user'"
    )
    (can_login,) = await cur.fetchone()
    assert can_login is False


async def test_app_user_id_is_null_outside_set_local_role(owner):
    # Owner mode (migrations, invitation acceptance, login): no app.user_id
    # is ever set, and the function must resolve to NULL, not raise.
    cur = await owner.execute("select app_user_id(), app_business_id(), app_role()")
    row = await cur.fetchone()
    assert row == (None, None, None)


# ------------------------------------------------------------ app.db.as_user
# The tests above prove the catalog-level grants; these exercise the actual
# mechanism a real request will use: db.py's as_user(), against real
# profiles created through the `business` fixture.


async def test_as_user_sets_role_and_identity_per_profile(business):
    async with as_user(business.titolare_id) as conn:
        cur = await conn.execute(
            "select current_user, app_user_id(), app_business_id(), app_role()"
        )
        current_user, user_id, business_id, role = await cur.fetchone()
        assert current_user == "app_user"
        assert user_id == business.titolare_id
        assert business_id == business.business_id
        assert role == "titolare"

    async with as_user(business.operatore_id) as conn:
        cur = await conn.execute("select app_role()")
        (role,) = await cur.fetchone()
        assert role == "operatore"


async def test_operatore_cannot_select_unit_price_directly_off_lots(business):
    # Column privileges, exercised end to end through the real transaction
    # shape a request handler will use - not just the catalog check above.
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        async with as_user(business.operatore_id) as conn:
            await conn.execute("select unit_price from lots limit 1")


async def test_operatore_can_read_own_business_through_rls(business):
    async with as_user(business.operatore_id) as conn:
        cur = await conn.execute(
            "select id from businesses where id = %s", (business.business_id,)
        )
        row = await cur.fetchone()
        assert row is not None and row[0] == business.business_id


async def test_owner_fixture_and_as_user_share_one_event_loop(owner, business):
    # Regression guard for fix-round-1 finding 1: pytest-asyncio 1.4
    # defaults the *test* loop scope to "function", separate from the
    # *fixture* loop scope pyproject.toml already pinned to "session". A
    # test that holds a fixture-provided connection (owner) and also opens
    # its own as_user() transaction in the same body - exactly Task 4's
    # endpoint-test shape - would run on a per-test loop while the pool's
    # background worker lives on the session loop, and hang for 30s before
    # raising PoolTimeout. asyncio_default_test_loop_scope = "session" is
    # what keeps both fixture and test on the same loop as the pool.
    cur = await owner.execute("select 1")
    (one,) = await cur.fetchone()
    assert one == 1

    async with as_user(business.titolare_id) as conn:
        cur = await conn.execute("select app_role()")
        (role,) = await cur.fetchone()
        assert role == "titolare"
