-- Fiestisima - initial schema
-- Multi-tenant from day one. Every business table carries business_id.

create extension if not exists citext;

-- ---------------------------------------------------------------- types

create type user_role as enum ('titolare', 'responsabile', 'operatore');
create type storage_place as enum ('frigo', 'freezer', 'dispensa');
create type unit_kind as enum ('pz', 'kg', 'l', 'g', 'ml');
create type movement_type as enum ('carico', 'scarico_uso', 'scarico_vendita', 'scarto');

-- ---------------------------------------------------------------- tables

-- The API's own identity table. Replaces auth.users: there is no Supabase
-- Auth any more, so the API issues and verifies its own JWTs against this.
create table users (
  id uuid primary key default gen_random_uuid(),
  email citext not null unique,
  password_hash text not null,
  created_at timestamptz not null default now()
);

create table businesses (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  address text,
  vat_number text,
  expiry_threshold_days int not null default 7 check (expiry_threshold_days > 0),
  created_at timestamptz not null default now()
);

create table profiles (
  id uuid primary key references users (id) on delete cascade,
  business_id uuid not null references businesses (id) on delete cascade,
  full_name text not null,
  role user_role not null default 'operatore',
  active boolean not null default true,
  last_seen_at timestamptz,
  created_at timestamptz not null default now(),
  unique (id, business_id)
);
create index profiles_business_idx on profiles (business_id);

create table invitations (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references businesses (id) on delete cascade,
  email citext not null,
  full_name text not null,
  role user_role not null default 'operatore',
  token uuid not null default gen_random_uuid(),
  invited_by uuid,
  expires_at timestamptz not null default now() + interval '7 days',
  accepted_at timestamptz,
  created_at timestamptz not null default now(),
  -- The database refuses to mix tenants rather than trusting every query to
  -- be written correctly: every intra-tenant reference below is a composite
  -- foreign key paired with business_id against a unique (id, business_id)
  -- on the parent, so a row can only point at a parent row from the same
  -- business. Composite foreign keys default to MATCH SIMPLE, which skips
  -- the check when the referencing column is null - exactly what is wanted
  -- for these optional references. Where the action is "on delete set
  -- null", the column list after it names only the child column: without
  -- it Postgres nulls every column of the key, including business_id,
  -- which is not null and would make the delete fail instead.
  foreign key (invited_by, business_id) references profiles (id, business_id) on delete set null (invited_by)
);
-- Only one pending invitation per email and business.
create unique index invitations_pending_idx
  on invitations (business_id, email) where accepted_at is null;
create unique index invitations_token_idx on invitations (token);

create table suppliers (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references businesses (id) on delete cascade,
  name text not null,
  phone text,
  email text,
  vat_number text,
  address text,
  notes text,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  unique (business_id, name),
  unique (id, business_id)
);

create table categories (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references businesses (id) on delete cascade,
  name text not null,
  unique (business_id, name),
  unique (id, business_id)
);

create table products (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references businesses (id) on delete cascade,
  name text not null check (length(trim(name)) > 0),
  barcode text,
  is_internal_code boolean not null default false,
  brand text,
  category_id uuid,
  unit unit_kind not null default 'pz',
  storage storage_place not null default 'dispensa',
  min_stock numeric not null default 0 check (min_stock >= 0),
  has_expiry boolean not null default true,
  image_url text,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  updated_by uuid,
  -- The code is unique per business, not globally: two businesses can share
  -- the same EAN. Several products with no code coexist because NULL never
  -- collides.
  unique (business_id, barcode),
  unique (id, business_id),
  foreign key (category_id, business_id) references categories (id, business_id) on delete set null (category_id),
  foreign key (updated_by, business_id) references profiles (id, business_id) on delete set null (updated_by)
);
create index products_business_active_idx on products (business_id, active);

create table events (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references businesses (id) on delete cascade,
  name text not null,
  event_date date not null,
  guests int check (guests > 0),
  with_kitchen boolean not null default true,
  status text not null default 'previsto' check (status in ('previsto', 'concluso')),
  client_name text,
  notes text,
  created_at timestamptz not null default now(),
  unique (id, business_id)
);
create index events_business_date_idx on events (business_id, event_date);

create table lots (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references businesses (id) on delete cascade,
  product_id uuid not null,
  supplier_id uuid,
  lot_code text not null,
  expires_on date,
  unit_price numeric check (unit_price >= 0),
  document_url text,
  -- The venue is in Italy; the default has to reflect the day on the wall
  -- clock in Rome, not UTC's, or anything entered between midnight and the
  -- CET/CEST offset gets stamped with the previous day in a date-keyed
  -- register that gets read against paper documents. Hardcoded until the
  -- business gains its own timezone column.
  received_on date not null default (now() at time zone 'Europe/Rome')::date,
  -- Never nulled: who received the goods is part of what an inspector
  -- asks. Profiles are deactivated, not deleted, so this can stay not
  -- null with an on delete restrict and still never block a real delete.
  created_by uuid not null,
  created_at timestamptz not null default now(),
  -- Two identical `carico` entries do not create two lots. NULLS NOT
  -- DISTINCT makes a lot with no date or no supplier collide with itself
  -- too.
  unique nulls not distinct (business_id, product_id, lot_code, expires_on, supplier_id),
  unique (id, business_id),
  foreign key (product_id, business_id) references products (id, business_id) on delete restrict,
  foreign key (supplier_id, business_id) references suppliers (id, business_id) on delete restrict,
  foreign key (created_by, business_id) references profiles (id, business_id) on delete restrict
);
-- Serves the app's most common lookup: lots of a product in this business,
-- soonest expiry first (FEFO). Subsumes a plain (product_id) index.
create index lots_product_idx on lots (business_id, product_id, expires_on);
create index lots_expiry_idx on lots (business_id, expires_on);

create table movements (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references businesses (id) on delete cascade,
  lot_id uuid not null,
  event_id uuid,
  type movement_type not null,
  quantity numeric not null check (quantity > 0),
  reason text,
  -- A reversal repeats the same type as the row it reverses (a reversed
  -- carico is still type carico) and only sets reverses_id to say so.
  -- lot_stock reads the pair from that, not from a signed quantity.
  reverses_id uuid,
  -- Idempotency for the offline queue: a retry does not duplicate the
  -- movement.
  client_id uuid unique,
  -- Never nulled: who recorded the movement is part of what an inspector
  -- asks. Profiles are deactivated, not deleted.
  created_by uuid not null,
  -- occurred_at is when the movement actually happened on the floor;
  -- movements are queued offline (see client_id) and can sync hours or
  -- days later, so this is the legally relevant date, distinct from
  -- created_at below, which is only the sync/insert timestamp.
  occurred_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  constraint scarto_needs_reason check (type <> 'scarto' or reason is not null),
  unique (id, business_id),
  foreign key (lot_id, business_id) references lots (id, business_id) on delete restrict,
  -- Restrict, not set null: which event consumed the goods is part of the
  -- traceability record. Events are concluded, not deleted, once they
  -- have movements against them.
  foreign key (event_id, business_id) references events (id, business_id) on delete restrict,
  foreign key (reverses_id, business_id) references movements (id, business_id) on delete set null (reverses_id),
  foreign key (created_by, business_id) references profiles (id, business_id) on delete restrict
);
create index movements_lot_idx on movements (lot_id);
create index movements_business_date_idx on movements (business_id, occurred_at desc);
create index movements_event_idx on movements (event_id) where event_id is not null;

-- ---------------------------------------------------------------- application role
-- app_user replaces Supabase's `authenticated`. NOLOGIN: nobody connects as
-- app_user directly, it is only ever assumed with `set local role` inside a
-- transaction the API already opened as its owner (`fiestisima`, which owns
-- every table above and therefore bypasses RLS by default - see db.py's
-- as_owner()/as_user() for the only three places that matters).
do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'app_user') then
    create role app_user nologin;
  end if;
end $$;
grant app_user to current_user;
grant usage on schema public to app_user;

-- ---------------------------------------------------------------- functions
-- SECURITY DEFINER on purpose: these functions are used INSIDE the RLS
-- policies on profiles. If they respected RLS, querying profiles to decide
-- whether profiles may be queried would be infinite recursion.
--
-- Identity functions: they read the session setting the API fixes per
-- request (see db.py's as_user()), replacing auth.uid()/auth_business_id()/
-- auth_role(). nullif(..., '') plus current_setting's "missing_ok" true
-- argument make app_user_id() resolve to NULL, not raise, when the setting
-- is absent - which is exactly the owner-mode case (migrations, invitation
-- acceptance, login) where no app.user_id is ever set.

create or replace function app_user_id()
returns uuid
language sql
stable
security definer
set search_path = public
as $$
  select nullif(current_setting('app.user_id', true), '')::uuid
$$;

create or replace function app_business_id()
returns uuid
language sql
stable
security definer
set search_path = public
as $$
  select business_id from profiles where id = app_user_id() and active
$$;

create or replace function app_role()
returns user_role
language sql
stable
security definer
set search_path = public
as $$
  select role from profiles where id = app_user_id() and active
$$;

-- ---------------------------------------------------------------- views
-- Stock is not stored: it is computed. That way it never drifts out of
-- sync with the record.

-- security_barrier on all three views below: they are deliberately not
-- security_invoker, so their own "where business_id = app_business_id()"
-- is the entire tenant boundary. Without security_barrier the planner may
-- push a caller-supplied predicate ahead of that filter, and a cheap
-- predicate that errors on the wrong input (or times differently) can leak
-- whether another tenant's row matched it. security_barrier forces the
-- view's own qualifications to run first.
create view lot_stock with (security_barrier = true) as
select
  l.id as lot_id,
  l.business_id,
  l.product_id,
  coalesce(
    sum(
      -- A reversal carries the same type as the row it reverses (see the
      -- comment on movements.reverses_id), so the sign cannot come from
      -- type alone: it comes from whether type and "is a reversal" agree.
      -- Plain carico: true <> false = true, add. Reversed carico:
      -- true <> true = false, subtract (undoes the addition). Plain
      -- scarico/scarto: false <> false = false, subtract. Reversed
      -- scarico/scarto: false <> true = true, add back.
      case when (m.type = 'carico') <> (m.reverses_id is not null)
           then m.quantity else -m.quantity end
    ),
    0
  ) as stock
from lots l
left join movements m on m.lot_id = l.id
where l.business_id = app_business_id()
group by l.id, l.business_id, l.product_id;

create view product_stock with (security_barrier = true) as
select business_id, product_id, sum(stock) as stock
from lot_stock
group by business_id, product_id;

-- The price is not hidden on the client: it never leaves the database for
-- an operatore. That is why direct access to lots is revoked and it is
-- read through this view instead. document_url gets the same guard: it
-- points at the supplier's scanned document, which is often a fattura
-- carrying the same unit prices this view otherwise withholds. The
-- storage bucket behind that URL needs its own authorization check
-- (configured in a later task) - a view cannot protect an object the
-- client fetches directly from storage.
create view lots_view with (security_barrier = true) as
select
  l.id,
  l.business_id,
  l.product_id,
  l.supplier_id,
  l.lot_code,
  l.expires_on,
  case when app_role() in ('titolare', 'responsabile') then l.document_url end as document_url,
  l.received_on,
  l.created_by,
  l.created_at,
  case when app_role() in ('titolare', 'responsabile') then l.unit_price end as unit_price
from lots l
where l.business_id = app_business_id();
