"""The ledger v1 permission matrix, translated: every invariant exercised
directly against the real database through app.db.as_user()/as_owner(),
the same mechanism a request handler uses - not through the HTTP layer
(test_invitations.py/test_users.py/test_businesses.py already cover the
endpoint-level translations of the ones that matter there).

Each test creates the rows it needs (as_owner, for setup only - see the
module comment in routers/invitations.py and rule 4 for why setup is the
one place besides login/invitation-accept/migrations that owner mode is
fine) and tears them down itself, in a finally block, so a failed
assertion never leaves rows behind for the `business`/`other_business`
fixture teardown to trip over (that teardown asserts exactly 0 leftover
lots/movements per business).
"""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import psycopg
import pytest

from app.db import as_owner, as_user


async def _insert_product(conn, business_id, *, barcode=None, name=None):
    cur = await conn.execute(
        "insert into products (business_id, name, barcode) values (%s, %s, %s) returning id",
        (business_id, name or f"Product {uuid.uuid4().hex[:6]}", barcode),
    )
    (product_id,) = await cur.fetchone()
    return product_id


async def _insert_lot(conn, business_id, product_id, created_by, **overrides):
    cur = await conn.execute(
        """
        insert into lots (business_id, product_id, supplier_id, lot_code, expires_on,
                           unit_price, document_url, created_by)
        values (%s, %s, %s, %s, %s, %s, %s, %s)
        returning id
        """,
        (
            business_id,
            product_id,
            overrides.get("supplier_id"),
            overrides.get("lot_code", f"LOT-{uuid.uuid4().hex[:6]}"),
            overrides.get("expires_on"),
            overrides.get("unit_price"),
            overrides.get("document_url"),
            created_by,
        ),
    )
    (lot_id,) = await cur.fetchone()
    return lot_id


# ------------------------------------------------------------ cross-tenant

async def test_cross_tenant_lot_reference_on_movement_is_23503(business, other_business):
    async with as_owner() as conn:
        product_id = await _insert_product(conn, business.business_id)
        lot_id = await _insert_lot(conn, business.business_id, product_id, business.titolare_id)
    try:
        # The lot belongs to `business`; inserting a movement as a member
        # of `other_business` forces business_id = other_business's id
        # (movements_insert's WITH CHECK), so (lot_id, business_id) never
        # matches any row of lots (id, business_id) - a composite FK
        # violation, not an RLS one.
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            async with as_user(other_business.titolare_id) as conn:
                await conn.execute(
                    """
                    insert into movements (business_id, lot_id, type, quantity, created_by)
                    values (app_business_id(), %s, 'carico', 1, app_user_id())
                    """,
                    (lot_id,),
                )
    finally:
        async with as_owner() as conn:
            await conn.execute("delete from lots where id = %s", (lot_id,))
            await conn.execute("delete from products where id = %s", (product_id,))


# ---------------------------------------------------------------- lots_view

async def test_lots_view_hides_price_and_document_from_operatore_shows_titolare(business):
    async with as_owner() as conn:
        product_id = await _insert_product(conn, business.business_id)
        lot_id = await _insert_lot(
            conn, business.business_id, product_id, business.titolare_id,
            unit_price=Decimal("12"), document_url="https://example.invalid/doc.pdf",
        )
    try:
        async with as_user(business.operatore_id) as conn:
            cur = await conn.execute(
                "select unit_price, document_url from lots_view where id = %s", (lot_id,)
            )
            unit_price, document_url = await cur.fetchone()
            assert unit_price is None
            assert document_url is None

        async with as_user(business.titolare_id) as conn:
            cur = await conn.execute(
                "select unit_price, document_url from lots_view where id = %s", (lot_id,)
            )
            unit_price, document_url = await cur.fetchone()
            assert unit_price == Decimal("12")
            assert document_url == "https://example.invalid/doc.pdf"
    finally:
        async with as_owner() as conn:
            await conn.execute("delete from lots where id = %s", (lot_id,))
            await conn.execute("delete from products where id = %s", (product_id,))


async def test_operatore_cannot_select_unit_price_directly_off_lots(business):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        async with as_user(business.operatore_id) as conn:
            await conn.execute("select unit_price from lots limit 1")


# --------------------------------------------------------------- write gates

async def test_operatore_cannot_insert_products(business):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        async with as_user(business.operatore_id) as conn:
            await conn.execute(
                "insert into products (business_id, name) values (app_business_id(), 'Blocked')"
            )


async def test_operatore_cannot_invite(business):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        async with as_user(business.operatore_id) as conn:
            await conn.execute(
                """
                insert into invitations (business_id, email, full_name, role, invited_by)
                values (app_business_id(), 'blocked@fiestisima-tests.invalid', 'Blocked', 'operatore', app_user_id())
                """
            )


# ----------------------------------------------------------- movements immutable

async def test_movements_cannot_be_updated_or_deleted_row_stays_intact(business):
    async with as_owner() as conn:
        product_id = await _insert_product(conn, business.business_id)
        lot_id = await _insert_lot(conn, business.business_id, product_id, business.titolare_id)
    async with as_user(business.titolare_id) as conn:
        cur = await conn.execute(
            """
            insert into movements (business_id, lot_id, type, quantity, created_by)
            values (app_business_id(), %s, 'carico', 3, app_user_id())
            returning id
            """,
            (lot_id,),
        )
        (movement_id,) = await cur.fetchone()
    try:
        # UPDATE: movements has table-level UPDATE granted (0002's blanket
        # grant covers it) but no UPDATE policy exists at all - with RLS
        # enabled and no applicable policy, Postgres defaults to denying
        # every row rather than raising, so this is a silent 0-row filter
        # (rule 5), not an error.
        async with as_user(business.titolare_id) as conn:
            cur = await conn.execute(
                "update movements set quantity = 999 where id = %s", (movement_id,)
            )
            assert cur.rowcount == 0

        # DELETE: unlike UPDATE, movements never received a table-level
        # DELETE grant at all (0004 only grants it on invitations and
        # categories) - this fails on the privilege check itself, before
        # RLS is even consulted, so it is a genuine error, not a 0-row
        # DELETE.
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            async with as_user(business.titolare_id) as conn:
                await conn.execute("delete from movements where id = %s", (movement_id,))

        async with as_owner() as conn:
            cur = await conn.execute(
                "select quantity from movements where id = %s", (movement_id,)
            )
            (quantity,) = await cur.fetchone()
            assert quantity == 3
    finally:
        async with as_owner() as conn:
            await conn.execute("delete from movements where id = %s", (movement_id,))
            await conn.execute("delete from lots where id = %s", (lot_id,))
            await conn.execute("delete from products where id = %s", (product_id,))


async def test_movements_client_id_duplicate_is_23505(business):
    async with as_owner() as conn:
        product_id = await _insert_product(conn, business.business_id)
        lot_id = await _insert_lot(conn, business.business_id, product_id, business.titolare_id)
    client_id = uuid.uuid4()
    movement_id = None
    try:
        async with as_user(business.titolare_id) as conn:
            cur = await conn.execute(
                """
                insert into movements (business_id, lot_id, type, quantity, created_by, client_id)
                values (app_business_id(), %s, 'carico', 1, app_user_id(), %s)
                returning id
                """,
                (lot_id, client_id),
            )
            (movement_id,) = await cur.fetchone()

        with pytest.raises(psycopg.errors.UniqueViolation):
            async with as_user(business.titolare_id) as conn:
                await conn.execute(
                    """
                    insert into movements (business_id, lot_id, type, quantity, created_by, client_id)
                    values (app_business_id(), %s, 'carico', 1, app_user_id(), %s)
                    """,
                    (lot_id, client_id),
                )
    finally:
        async with as_owner() as conn:
            if movement_id is not None:
                await conn.execute("delete from movements where id = %s", (movement_id,))
            await conn.execute("delete from lots where id = %s", (lot_id,))
            await conn.execute("delete from products where id = %s", (product_id,))


async def test_scarto_without_reason_is_23514(business):
    async with as_owner() as conn:
        product_id = await _insert_product(conn, business.business_id)
        lot_id = await _insert_lot(conn, business.business_id, product_id, business.titolare_id)
    try:
        with pytest.raises(psycopg.errors.CheckViolation):
            async with as_user(business.titolare_id) as conn:
                await conn.execute(
                    """
                    insert into movements (business_id, lot_id, type, quantity, created_by)
                    values (app_business_id(), %s, 'scarto', 1, app_user_id())
                    """,
                    (lot_id,),
                )
    finally:
        async with as_owner() as conn:
            await conn.execute("delete from lots where id = %s", (lot_id,))
            await conn.execute("delete from products where id = %s", (product_id,))


@pytest.mark.parametrize("quantity", [0, -1])
async def test_quantity_not_positive_is_23514(business, quantity):
    async with as_owner() as conn:
        product_id = await _insert_product(conn, business.business_id)
        lot_id = await _insert_lot(conn, business.business_id, product_id, business.titolare_id)
    try:
        with pytest.raises(psycopg.errors.CheckViolation):
            async with as_user(business.titolare_id) as conn:
                await conn.execute(
                    """
                    insert into movements (business_id, lot_id, type, quantity, created_by)
                    values (app_business_id(), %s, 'carico', %s, app_user_id())
                    """,
                    (lot_id, quantity),
                )
    finally:
        async with as_owner() as conn:
            await conn.execute("delete from lots where id = %s", (lot_id,))
            await conn.execute("delete from products where id = %s", (product_id,))


# --------------------------------------------------------------------- lots

async def test_duplicate_lot_with_null_expiry_and_supplier_is_23505(business):
    async with as_owner() as conn:
        product_id = await _insert_product(conn, business.business_id)
    lot_id = None
    try:
        async with as_user(business.titolare_id) as conn:
            cur = await conn.execute(
                """
                insert into lots (business_id, product_id, lot_code, created_by)
                values (app_business_id(), %s, 'LOT-DUP', app_user_id())
                returning id
                """,
                (product_id,),
            )
            (lot_id,) = await cur.fetchone()

        with pytest.raises(psycopg.errors.UniqueViolation):
            async with as_user(business.titolare_id) as conn:
                await conn.execute(
                    """
                    insert into lots (business_id, product_id, lot_code, created_by)
                    values (app_business_id(), %s, 'LOT-DUP', app_user_id())
                    """,
                    (product_id,),
                )
    finally:
        async with as_owner() as conn:
            if lot_id is not None:
                await conn.execute("delete from lots where id = %s", (lot_id,))
            await conn.execute("delete from products where id = %s", (product_id,))


async def test_two_products_with_null_barcode_both_insert(business):
    # unique(business_id, barcode) with ordinary (nulls-distinct) semantics:
    # two NULLs never collide, unlike lots' "nulls not distinct" key.
    async with as_owner() as conn:
        p1 = await _insert_product(conn, business.business_id, barcode=None)
        p2 = await _insert_product(conn, business.business_id, barcode=None)
    assert p1 != p2
    async with as_owner() as conn:
        await conn.execute("delete from products where id = any(%s)", ([p1, p2],))


async def test_lot_stock_zero_for_lot_with_no_movements(business):
    async with as_owner() as conn:
        product_id = await _insert_product(conn, business.business_id)
        lot_id = await _insert_lot(conn, business.business_id, product_id, business.titolare_id)
    try:
        async with as_user(business.titolare_id) as conn:
            cur = await conn.execute(
                "select stock from lot_stock where lot_id = %s", (lot_id,)
            )
            row = await cur.fetchone()
            assert row is not None
            assert row[0] == 0
    finally:
        async with as_owner() as conn:
            await conn.execute("delete from lots where id = %s", (lot_id,))
            await conn.execute("delete from products where id = %s", (product_id,))


async def test_titolare_can_correct_lot_code_but_not_created_by(business):
    async with as_owner() as conn:
        product_id = await _insert_product(conn, business.business_id)
        lot_id = await _insert_lot(
            conn, business.business_id, product_id, business.titolare_id, lot_code="ORIGINAL"
        )
    try:
        async with as_user(business.titolare_id) as conn:
            cur = await conn.execute(
                "update lots set lot_code = 'CORRECTED' where id = %s", (lot_id,)
            )
            assert cur.rowcount == 1

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            async with as_user(business.titolare_id) as conn:
                await conn.execute(
                    "update lots set created_by = %s where id = %s",
                    (business.responsabile_id, lot_id),
                )
    finally:
        async with as_owner() as conn:
            await conn.execute("delete from lots where id = %s", (lot_id,))
            await conn.execute("delete from products where id = %s", (product_id,))


# --------------------------------------------------------------- reversals

async def test_reversal_sign_cases(business):
    async with as_owner() as conn:
        product_id = await _insert_product(conn, business.business_id)
        lot_id = await _insert_lot(conn, business.business_id, product_id, business.titolare_id)

    async def _stock(conn) -> int:
        cur = await conn.execute("select stock from lot_stock where lot_id = %s", (lot_id,))
        (stock,) = await cur.fetchone()
        return stock

    async def _insert_movement(conn, type_, quantity, reverses_id=None, reason=None):
        cur = await conn.execute(
            """
            insert into movements (business_id, lot_id, type, quantity, created_by, reverses_id, reason)
            values (app_business_id(), %s, %s, %s, app_user_id(), %s, %s)
            returning id
            """,
            (lot_id, type_, quantity, reverses_id, reason),
        )
        (mid,) = await cur.fetchone()
        return mid

    try:
        async with as_user(business.titolare_id) as conn:
            carico_id = await _insert_movement(conn, "carico", 10)
            assert await _stock(conn) == 10  # plain carico adds

            await _insert_movement(conn, "carico", 10, reverses_id=carico_id)
            assert await _stock(conn) == 0  # carico reversal subtracts, undoing the addition

            scarico_id = await _insert_movement(conn, "scarico_uso", 4)
            assert await _stock(conn) == -4  # plain scarico subtracts

            await _insert_movement(conn, "scarico_uso", 4, reverses_id=scarico_id)
            assert await _stock(conn) == 0  # scarico reversal adds back
    finally:
        async with as_owner() as conn:
            await conn.execute("delete from movements where lot_id = %s", (lot_id,))
            await conn.execute("delete from lots where id = %s", (lot_id,))
            await conn.execute("delete from products where id = %s", (product_id,))


# ------------------------------------------------------------ on delete set null

async def test_delete_category_sets_product_category_null_business_id_intact(business):
    async with as_owner() as conn:
        cur = await conn.execute(
            "insert into categories (business_id, name) values (%s, %s) returning id",
            (business.business_id, f"Cat-{uuid.uuid4().hex[:6]}"),
        )
        (category_id,) = await cur.fetchone()
        product_id = await _insert_product(conn, business.business_id)
        await conn.execute(
            "update products set category_id = %s where id = %s", (category_id, product_id)
        )
    try:
        async with as_user(business.titolare_id) as conn:
            cur = await conn.execute("delete from categories where id = %s", (category_id,))
            assert cur.rowcount == 1

        async with as_owner() as conn:
            cur = await conn.execute(
                "select category_id, business_id from products where id = %s", (product_id,)
            )
            category, biz = await cur.fetchone()
            assert category is None
            assert biz == business.business_id
    finally:
        async with as_owner() as conn:
            await conn.execute("delete from products where id = %s", (product_id,))


async def test_delete_profile_sets_invitation_invited_by_null(business):
    async with as_owner() as conn:
        # A throwaway 4th profile purely to be the "inviter", so deleting
        # it never touches the fixture's own three users.
        temp_email = f"temp-inviter-{uuid.uuid4().hex[:8]}@fiestisima-tests.invalid"
        cur = await conn.execute(
            "insert into users (email, password_hash) values (%s, 'x') returning id",
            (temp_email,),
        )
        (temp_user_id,) = await cur.fetchone()
        await conn.execute(
            "insert into profiles (id, business_id, full_name, role) "
            "values (%s, %s, 'Temp Inviter', 'titolare')",
            (temp_user_id, business.business_id),
        )
        cur = await conn.execute(
            """
            insert into invitations (business_id, email, full_name, role, invited_by)
            values (%s, %s, 'Invited', 'operatore', %s)
            returning id
            """,
            (
                business.business_id,
                f"invited-by-temp-{uuid.uuid4().hex[:6]}@fiestisima-tests.invalid",
                temp_user_id,
            ),
        )
        (invitation_id,) = await cur.fetchone()

    try:
        async with as_owner() as conn:
            # profiles.id -> users.id on delete cascade: deleting the user
            # deletes the profile, which is what fires invitations'
            # "on delete set null (invited_by)".
            await conn.execute("delete from users where id = %s", (temp_user_id,))
            cur = await conn.execute(
                "select invited_by, business_id from invitations where id = %s",
                (invitation_id,),
            )
            invited_by, biz = await cur.fetchone()
            assert invited_by is None
            assert biz == business.business_id
    finally:
        async with as_owner() as conn:
            await conn.execute("delete from invitations where id = %s", (invitation_id,))


async def test_delete_movement_sets_reverses_id_null_on_the_reversal(business):
    async with as_owner() as conn:
        product_id = await _insert_product(conn, business.business_id)
        lot_id = await _insert_lot(conn, business.business_id, product_id, business.titolare_id)
        cur = await conn.execute(
            """
            insert into movements (business_id, lot_id, type, quantity, created_by)
            values (%s, %s, 'carico', 5, %s) returning id
            """,
            (business.business_id, lot_id, business.titolare_id),
        )
        (original_id,) = await cur.fetchone()
        cur = await conn.execute(
            """
            insert into movements (business_id, lot_id, type, quantity, created_by, reverses_id)
            values (%s, %s, 'carico', 5, %s, %s) returning id
            """,
            (business.business_id, lot_id, business.titolare_id, original_id),
        )
        (reversal_id,) = await cur.fetchone()

    try:
        async with as_owner() as conn:
            await conn.execute("delete from movements where id = %s", (original_id,))
            cur = await conn.execute(
                "select reverses_id, business_id from movements where id = %s", (reversal_id,)
            )
            reverses_id, biz = await cur.fetchone()
            assert reverses_id is None
            assert biz == business.business_id
    finally:
        async with as_owner() as conn:
            await conn.execute("delete from movements where id = %s", (reversal_id,))
            await conn.execute("delete from lots where id = %s", (lot_id,))
            await conn.execute("delete from products where id = %s", (product_id,))


# ------------------------------------------------------------------ events

async def test_titolare_cannot_delete_event_no_delete_privilege(business):
    # No DELETE grant on events at all (0002/0004 never add one) - fails on
    # the privilege check itself, before RLS runs. The FK "on delete
    # restrict" from movements.event_id is a second barrier that would
    # only matter for the owner, who bypasses this privilege check
    # entirely.
    async with as_owner() as conn:
        cur = await conn.execute(
            "insert into events (business_id, name, event_date) "
            "values (%s, %s, current_date) returning id",
            (business.business_id, "Test Event"),
        )
        (event_id,) = await cur.fetchone()
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            async with as_user(business.titolare_id) as conn:
                await conn.execute("delete from events where id = %s", (event_id,))
    finally:
        async with as_owner() as conn:
            await conn.execute("delete from events where id = %s", (event_id,))


# ------------------------------------------------------------- deactivated

async def test_deactivated_user_has_null_business_id_and_sees_nothing(business):
    async with as_owner() as conn:
        await conn.execute(
            "update profiles set active = false where id = %s", (business.operatore_id,)
        )
    try:
        async with as_user(business.operatore_id) as conn:
            cur = await conn.execute("select app_business_id()")
            (biz,) = await cur.fetchone()
            assert biz is None

            cur = await conn.execute("select count(*) from lots_view")
            (count,) = await cur.fetchone()
            assert count == 0

            cur = await conn.execute("select count(*) from business_users")
            (count,) = await cur.fetchone()
            assert count == 0
    finally:
        async with as_owner() as conn:
            await conn.execute(
                "update profiles set active = true where id = %s", (business.operatore_id,)
            )


# --------------------------------------------------------------------- roles

async def test_operatore_self_promotion_direct_update_is_42501(business):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        async with as_user(business.operatore_id) as conn:
            await conn.execute(
                "update profiles set role = 'titolare' where id = %s", (business.operatore_id,)
            )


async def test_titolare_can_demote_responsabile(business):
    async with as_user(business.titolare_id) as conn:
        cur = await conn.execute(
            "update profiles set role = 'operatore' where id = %s returning role",
            (business.responsabile_id,),
        )
        (role,) = await cur.fetchone()
        assert role == "operatore"


# --------------------------------------------------------------- date/time

async def test_received_on_defaults_to_rome_date(business):
    # This compares the default expression's result against Python's own
    # zoneinfo-computed Rome date at the same instant, rather than a second
    # copy of the same hardcoded 'Europe/Rome' SQL literal - the point is
    # to catch a regression to UTC (or the server's local zone), not to
    # reproduce the exact SQL. Manufacturing a real UTC/Rome date-boundary
    # instant would need control over the database server's clock, which
    # is not available over the Railway proxy this suite runs against.
    async with as_owner() as conn:
        product_id = await _insert_product(conn, business.business_id)
    lot_id = None
    try:
        async with as_user(business.titolare_id) as conn:
            cur = await conn.execute(
                """
                insert into lots (business_id, product_id, lot_code, created_by)
                values (app_business_id(), %s, 'ROME-DATE', app_user_id())
                returning id, received_on
                """,
                (product_id,),
            )
            lot_id, received_on = await cur.fetchone()
        expected_rome_date = datetime.now(ZoneInfo("Europe/Rome")).date()
        assert received_on == expected_rome_date
    finally:
        async with as_owner() as conn:
            if lot_id is not None:
                await conn.execute("delete from lots where id = %s", (lot_id,))
            await conn.execute("delete from products where id = %s", (product_id,))


async def test_received_on_default_expression_uses_europe_rome(owner):
    # A deterministic companion to the instant-comparison test above: reads
    # the column default straight from the catalog, so this fails the
    # moment the DEFAULT clause itself changes zone, with no dependence on
    # wall-clock timing at all.
    cur = await owner.execute(
        """
        select pg_get_expr(d.adbin, d.adrelid)
        from pg_attrdef d
        join pg_attribute a on a.attrelid = d.adrelid and a.attnum = d.adnum
        where d.adrelid = 'lots'::regclass and a.attname = 'received_on'
        """
    )
    (default_expr,) = await cur.fetchone()
    assert "Europe/Rome" in default_expr


async def test_occurred_at_explicit_is_preserved_created_at_is_insert_time(business):
    async with as_owner() as conn:
        product_id = await _insert_product(conn, business.business_id)
        lot_id = await _insert_lot(conn, business.business_id, product_id, business.titolare_id)
    backdated = (datetime.now(timezone.utc) - timedelta(days=3)).replace(microsecond=0)
    movement_id = None
    try:
        before = datetime.now(timezone.utc)
        async with as_user(business.titolare_id) as conn:
            cur = await conn.execute(
                """
                insert into movements (business_id, lot_id, type, quantity, created_by, occurred_at)
                values (app_business_id(), %s, 'carico', 1, app_user_id(), %s)
                returning id, occurred_at, created_at
                """,
                (lot_id, backdated),
            )
            movement_id, occurred_at, created_at = await cur.fetchone()
        after = datetime.now(timezone.utc)

        assert occurred_at == backdated
        assert before - timedelta(seconds=5) <= created_at <= after + timedelta(seconds=5)
    finally:
        async with as_owner() as conn:
            if movement_id is not None:
                await conn.execute("delete from movements where id = %s", (movement_id,))
            await conn.execute("delete from lots where id = %s", (lot_id,))
            await conn.execute("delete from products where id = %s", (product_id,))
