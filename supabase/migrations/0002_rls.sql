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
-- yourself the titolare role or reactivate yourself.

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
-- deactivated. The guard only fires on self-updates (old.id = auth.uid()):
-- a titolare changing a colleague's role or active flag through
-- profiles_update_titolare touches a different row and is unaffected. It is
-- also inert for the service role used in test fixtures and admin tooling,
-- since auth.uid() is null outside of a user session and null never equals
-- old.id.
create or replace function profiles_block_self_role_change()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if auth.uid() = old.id
     and (new.role is distinct from old.role or new.active is distinct from old.active) then
    raise exception 'cannot change your own role or active flag';
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
-- the floor); only titolare and responsabile correct a lot afterwards. There
-- is deliberately no select policy here: reads go through lots_view only
-- (see the grants at the bottom of this file), so a direct "select from
-- lots" returns nothing for anyone, whatever their role.
--
-- created_by must match the caller, the same rule movements_insert applies
-- below: it is not null and on delete restrict precisely because "who
-- received the goods" is an audit fact, so nothing should be able to write
-- someone else's uid into it.
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

-- authenticated reads lots through the view, never the base table.
grant select on lots_view to authenticated;
grant select on lot_stock to authenticated;
grant select on product_stock to authenticated;

-- Also granted to anon (no session at all) so that an unauthenticated probe
-- against these views is a deterministic empty result rather than depending
-- on whatever ambient default privileges the project happens to have. This
-- is safe to grant: auth_business_id() is null with no session, so the
-- views' own "where business_id = auth_business_id()" filters out every
-- row before anon sees anything. The base tables are not granted to anon at
-- all; only the views, which cannot leak a column they do not expose.
grant select on lots_view to anon;
grant select on lot_stock to anon;
grant select on product_stock to anon;
