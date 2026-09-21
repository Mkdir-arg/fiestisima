-- A movement may be reversed at most once (docs/07: annulling inserts a
-- new row with reverses_id pointing at the original; lot_stock's own sign
-- expression assumes exactly one reversal per reversed row - a second one
-- would double-count). The API's own check ("select 1 from movements
-- where reverses_id = %s" before inserting a reversal) closes this in the
-- common sequential case, but movements intentionally has no UPDATE
-- policy at all (0002: the ledger is immutable, "undoing" is always an
-- INSERT) - which means "select ... for update" cannot be used to
-- serialise two concurrent reversal attempts of the same movement the way
-- routers/users.py's last-titolare guard does on profiles: with RLS
-- enabled and no UPDATE policy, FOR UPDATE's own privilege check would
-- exclude every row, locking nothing, regardless of caller. Two
-- concurrent POST /movements/{id}/reverse calls for the same id could
-- otherwise both pass the pre-check before either commits and both
-- insert a reversal.
--
-- A plain unique index, unlike a CREATE POLICY, is enforced by Postgres
-- independently of RLS and of any role - it needs no grant beyond the
-- INSERT privilege movements_insert already requires, and closes the race
-- outright rather than merely narrowing it. NULLs are excluded (most rows
-- are not reversals at all) with a partial index, matching the shape
-- lots' unique constraints already use for their own optional columns.
create unique index movements_reverses_id_unique
  on movements (reverses_id)
  where reverses_id is not null;
