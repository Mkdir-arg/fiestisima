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
    # The traceability record is immutable: only select/insert policies may
    # exist on movements. cmd = 'ALL' is also disallowed, since a policy
    # declared "for all" would silently cover update/delete too.
    cur = await owner.execute(
        """
        select policyname, cmd from pg_policies
        where schemaname = 'public' and tablename = 'movements'
          and cmd in ('UPDATE', 'DELETE', 'ALL')
        """
    )
    rows = await cur.fetchall()
    assert rows == []


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
