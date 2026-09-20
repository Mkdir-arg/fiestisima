-- Fiestisima - row level security
-- Every access rule lives here. Hiding a button is not a permission: an
-- operatore who calls the API directly with curl must not receive
-- unit_price, must not be able to write the catalog, and must not be able
-- to touch another business's rows no matter what predicate they send.

alter table businesses  enable row level security;
alter table profiles    enable row level security;
alter table invitations enable row level security;
alter table suppliers   enable row level security;
alter table categories  enable row level security;
alter table products    enable row level security;
alter table events      enable row level security;
alter table lots        enable row level security;
alter table movements   enable row level security;

-- ---------------------------------------------------------------- businesses
-- Everyone sees their own business; only the titolare edits it.

create policy businesses_select on businesses for select to authenticated
  using (id = auth_business_id());
create policy businesses_update on businesses for update to authenticated
  using (id = auth_business_id() and auth_role() = 'titolare')
  with check (id = auth_business_id());

-- ---------------------------------------------------------------- profiles
-- Everyone sees their colleagues; only the titolare edits someone else's
-- profile. A user may also edit their own row (e.g. full_name), but see the
-- trigger below: that self-update path must not become a way to grant
-- yourself the titolare role or reactivate yourself. There is deliberately
-- no delete policy: people are deactivated (profiles.active), never
-- deleted, so lots.created_by/movements.created_by never have to explain a
-- vanished user - see the "on delete restrict" comments on those columns
-- in 0001.

create policy profiles_select on profiles for select to authenticated
  using (business_id = auth_business_id());
create policy profiles_update_self on profiles for update to authenticated
  using (id = auth.uid())
  with check (id = auth.uid() and business_id = auth_business_id());
create policy profiles_update_titolare on profiles for update to authenticated
  using (business_id = auth_business_id() and auth_role() = 'titolare')
  with check (business_id = auth_business_id());

-- RLS's using/with check clauses each see only one version of the row (the
-- pre-update row for using, the post-update row for with check); neither can
-- compare old and new values of the same column in one expression. Without
-- this guard, profiles_update_self would let an operatore set their own
-- role to titolare, or flip their own active flag back on after being
-- deactivated.
--
-- The gate is the caller's own role, not whose row is being written: if
-- role or active is changing and the caller is not a titolare, reject.
-- That lets a titolare change anyone's role or active flag, including
-- their own (ownership transfer is a titolare action, per the functional
-- spec, with its own double-confirmation UI - not this trigger's job), and
-- lets everyone else update their own row (full_name, etc.) but never
-- those two columns, on their own row or anyone else's.
--
-- The service role's exemption is written explicitly (auth.uid() is not
-- null), not implied by null propagation, and the role-gate uses "is
-- distinct from", not "<>". A first version of this trigger used a plain
-- "auth_role() <> 'titolare'" with no separate service-role check, on the
-- reasoning that a null auth_role() would make the whole condition null and
-- therefore inert - true for the service role, whose auth.uid() actually is
-- null, but auth_role() is *also* null for a deactivated caller who still
-- holds a valid, pre-deactivation JWT (profiles_update_self's using clause
-- only tests id = auth.uid(), which a deactivated user still satisfies). "<>"
-- against that null silently did not fire, so a "harmless" future edit that
-- dropped profiles_update_self's with check business_id = auth_business_id()
-- (it looks redundant next to id = auth.uid(), but it is the only other
-- thing failing that update today) would have reopened self-reactivation and
-- self-promotion for exactly that caller. "is distinct from" treats that
-- null as "not titolare" - true, not null - so the guard fires on its own,
-- independent of whatever profiles_update_self's with check does or stops
-- doing. The explicit "auth.uid() is not null" is what carves out the
-- service role instead, since without it "null is distinct from 'titolare'"
-- would also be true and would block admin/service-role writes to role or
-- active, breaking every test fixture that deactivates a profile directly.
--
-- Deliberately left out: a titolare cannot step down or deactivate
-- themselves while they are the only titolare of their business. That
-- rule needs a count of active titolare in the business, which belongs
-- with the Utenti screen that manages this transfer (not part of this
-- block) - not baked into this trigger. Leaving it out here is a known
-- gap, not an oversight.
--
-- This trigger is declared "before update" only (see the create trigger
-- statement below), so it never fires on insert - the clause that
-- guarantees that is the trigger's own "before update on profiles", not
-- anything in the function body. That matters because a newly invited user
-- inserting their own profiles row has auth.uid() set but auth_role() null
-- (no profile exists yet to resolve a role from): were this ever an
-- insert-or-update trigger, the condition above would misfire on every
-- signup. It also could not safely run on insert regardless, since old is
-- null for an insert and old.role/old.active would themselves error.
create or replace function profiles_block_self_role_change()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if (new.role is distinct from old.role or new.active is distinct from old.active)
     and auth.uid() is not null
     and auth_role() is distinct from 'titolare' then
    raise exception 'only a titolare can change role or active' using errcode = '42501';
  end if;
  return new;
end;
$$;

create trigger profiles_block_self_role_change_trg
before update on profiles
for each row execute function profiles_block_self_role_change();

-- ---------------------------------------------------------------- invitations
-- Only the titolare invites, sees pending invitations, or revokes them.

create policy invitations_all on invitations for all to authenticated
  using (business_id = auth_business_id() and auth_role() = 'titolare')
  with check (business_id = auth_business_id() and auth_role() = 'titolare');

-- ---------------------------------------------------------------- suppliers / categories / products / events
-- Everyone reads the catalog; only titolare and responsabile write it.

create policy suppliers_select on suppliers for select to authenticated
  using (business_id = auth_business_id());
create policy suppliers_write on suppliers for all to authenticated
  using (business_id = auth_business_id() and auth_role() in ('titolare', 'responsabile'))
  with check (business_id = auth_business_id() and auth_role() in ('titolare', 'responsabile'));

create policy categories_select on categories for select to authenticated
  using (business_id = auth_business_id());
create policy categories_write on categories for all to authenticated
  using (business_id = auth_business_id() and auth_role() in ('titolare', 'responsabile'))
  with check (business_id = auth_business_id() and auth_role() in ('titolare', 'responsabile'));

create policy products_select on products for select to authenticated
  using (business_id = auth_business_id());
create policy products_write on products for all to authenticated
  using (business_id = auth_business_id() and auth_role() in ('titolare', 'responsabile'))
  with check (business_id = auth_business_id() and auth_role() in ('titolare', 'responsabile'));

create policy events_select on events for select to authenticated
  using (business_id = auth_business_id());
create policy events_write on events for all to authenticated
  using (business_id = auth_business_id() and auth_role() in ('titolare', 'responsabile'))
  with check (business_id = auth_business_id() and auth_role() in ('titolare', 'responsabile'));

-- ---------------------------------------------------------------- lots
-- Anyone with a session can register a carico (goods-in is everyone's job on
-- the floor); only titolare and responsabile correct a lot afterwards.
--
-- lots_select exists so that lots_update and an insert-then-read-it-back
-- round trip have a row to work with. Postgres applies SELECT *policies* -
-- not only SELECT privileges - to any UPDATE whose WHERE or RETURNING
-- touches the table, and to any INSERT that asks for a RETURNING clause:
-- with no select policy at all, lots_update's own USING clause can never
-- match a row (there is nothing for it to see), so a titolare's correction
-- silently matches zero rows - PostgREST reports that as success, not an
-- error - and `supabase.from('lots').insert(row).select('id')`, which the
-- app needs because a carico movement has to reference the new lot's id,
-- raises an RLS violation instead of returning it. An earlier version of
-- this file argued the absence of a select policy was deliberate, on the
-- theory that it was needed to protect the price; that reasoning was
-- wrong. The price is protected entirely by the column-level revoke below
-- (unit_price/document_url are not selectable by anyone, this policy or
-- no), not by making the whole table invisible.
--
-- created_by must match the caller, the same rule movements_insert applies
-- below: it is not null and on delete restrict precisely because "who
-- received the goods" is an audit fact, so nothing should be able to write
-- someone else's uid into it. lots_update's own with check does not repeat
-- that guarantee for an existing row - see the column-level revoke on
-- created_by/business_id in the grants section below, which is what
-- actually keeps an existing lot's audit trail and tenant from being
-- reassigned after the fact.
--
-- There is also deliberately no delete policy on lots. A lot is part of
-- the traceability record in the same way a movement is: correcting a
-- mistake goes through lots_update (or, once movements exist against it,
-- through a reversal), not by removing the row.
create policy lots_select on lots for select to authenticated
  using (business_id = auth_business_id());
create policy lots_insert on lots for insert to authenticated
  with check (business_id = auth_business_id() and created_by = auth.uid());
create policy lots_update on lots for update to authenticated
  using (business_id = auth_business_id() and auth_role() in ('titolare', 'responsabile'))
  with check (business_id = auth_business_id());

-- ---------------------------------------------------------------- movements
-- Insert and select only. Never update or delete: the traceability record is
-- immutable. Voiding a movement means inserting its reverse (see
-- movements.reverses_id in 0001), not editing history.

create policy movements_select on movements for select to authenticated
  using (business_id = auth_business_id());
create policy movements_insert on movements for insert to authenticated
  with check (business_id = auth_business_id() and created_by = auth.uid());

-- ---------------------------------------------------------------- grants
-- The price and the supplier document never leave the database for an
-- operatore. Hiding them in the client is not enough, so direct select on
-- lots is revoked and select is granted back only on the columns that carry
-- no pricing information; unit_price and document_url are reachable solely
-- through lots_view, whose own case expression decides who gets a value and
-- who gets null (see 0001). This is a column-level revoke, not a table-level
-- one: a blanket "revoke select on lots" would also take away the SELECT
-- privilege Postgres requires on any column referenced in an UPDATE's WHERE
-- clause or RETURNING list (see the UPDATE privileges note in the Postgres
-- manual), which would break lots_update for titolare and responsabile -
-- the exact "revoke that takes too much" failure mode. Selecting unit_price
-- or document_url directly - or a bare "select *" - still fails outright
-- for every role, because neither column is granted to anyone; that failure
-- happens at the privilege check, before RLS even runs, so it applies
-- identically to titolare, responsabile and operatore. INSERT and UPDATE
-- privileges on lots are untouched by this revoke: they still come from the
-- default privileges Supabase grants new tables, so goods-in (insert) and
-- corrections (update) keep working for whichever role the RLS policies
-- above already allow.
revoke select on lots from authenticated;
grant select (
  id, business_id, product_id, supplier_id, lot_code,
  expires_on, received_on, created_by, created_at
) on lots to authenticated;

-- lots_update's with check only re-tests business_id against
-- auth_business_id(), and only for the row's post-update value - it says
-- nothing about created_by, and nothing stops the new business_id from
-- being a different (still equal-to-itself-after-the-fact) value the
-- caller chooses. Left to policy alone, a titolare or responsabile could
-- reassign an existing lot's created_by to any profile in the business -
-- overwriting the exact audit fact lots.created_by.not null and its "on
-- delete restrict" exist to protect - or move the lot to a different
-- business_id outright. Column privileges close both without relying on
-- the update policy to keep enforcing it: this cannot be bypassed by a
-- future policy edit the way the with check above could be, because it is
-- not a policy at all.
--
-- This has to be a table-level revoke followed by a column-level grant
-- back, the same shape as the SELECT handling above, not a column-level
-- revoke on its own. Per the Postgres GRANT/REVOKE reference: "if a role
-- has been granted privileges on a table, then revoking the same
-- privileges from individual columns will have no effect" - a column-level
-- revoke cannot claw anything back from a broader table-level grant that
-- is still in force, and Supabase's default privileges grant UPDATE on the
-- whole table to authenticated. An earlier version of this file tried the
-- column-level revoke alone; it is a silent no-op (Postgres only warns),
-- so created_by stayed rewritable while the migration still applied
-- cleanly - exactly the kind of failure that looks fine until someone
-- checks. INSERT is untouched either way (lots_insert still sets
-- created_by/business_id when a lot is created); this only ever governs
-- UPDATE.
--
-- unit_price and document_url are deliberately in the grant-back list:
-- UPDATE and SELECT are separate privileges, and a titolare correcting a
-- price needs to write it without being able to read it off the base
-- table (reads of it still only ever happen through lots_view). The
-- WHERE clause on a correction still works because SELECT on id and
-- business_id is granted per column above, independent of this UPDATE
-- grant.
revoke update on lots from authenticated;
grant update (
  product_id, supplier_id, lot_code, expires_on,
  unit_price, document_url, received_on
) on lots to authenticated;

-- authenticated reads lots through the view, never the base table.
grant select on lots_view to authenticated;
grant select on lot_stock to authenticated;
grant select on product_stock to authenticated;

-- anon gets nothing on these views, on lots, or on any other table in this
-- file. An unauthenticated caller getting zero rows back would say "you
-- asked correctly and there is nothing here"; a permission error says "you
-- are not allowed to ask" - the second is the truth for a caller with no
-- session, and it is the one that fails loudly if a screen ever queries
-- before a session exists, rather than silently rendering an empty state
-- that looks like "no data yet". lots is named explicitly alongside the
-- three views: without this, anon keeps whatever default select privilege
-- Supabase grants new tables, unit_price and document_url included - RLS
-- alone would only be saving it because no policy above names anon, which
-- is not a property worth depending on. The revoke is explicit everywhere
-- here, not just an omitted grant, for the same reason: Supabase's default
-- privileges may otherwise hand anon select on a relation regardless of
-- what this file asks for.
revoke select on lots, lots_view, lot_stock, product_stock from anon;
