-- Fiestisima - initial schema
-- Multi-tenant from day one. Every business table carries business_id.

create extension if not exists citext;

-- ---------------------------------------------------------------- types

create type user_role as enum ('titolare', 'responsabile', 'operatore');
create type storage_place as enum ('frigo', 'freezer', 'dispensa');
create type unit_kind as enum ('pz', 'kg', 'l', 'g', 'ml');
create type movement_type as enum ('carico', 'scarico_uso', 'scarico_vendita', 'scarto');

-- ---------------------------------------------------------------- tables

create table businesses (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  address text,
  vat_number text,
  expiry_threshold_days int not null default 7 check (expiry_threshold_days > 0),
  created_at timestamptz not null default now()
);

create table profiles (
  id uuid primary key references auth.users (id) on delete cascade,
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
  -- for these optional references.
  foreign key (invited_by, business_id) references profiles (id, business_id) on delete set null
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
  foreign key (category_id, business_id) references categories (id, business_id) on delete set null,
  foreign key (updated_by, business_id) references profiles (id, business_id) on delete set null
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
  received_on date not null default current_date,
  created_by uuid,
  created_at timestamptz not null default now(),
  -- Two identical goods-in entries do not create two lots. NULLS NOT
  -- DISTINCT makes a lot with no date or no supplier collide with itself
  -- too.
  unique nulls not distinct (business_id, product_id, lot_code, expires_on, supplier_id),
  unique (id, business_id),
  foreign key (product_id, business_id) references products (id, business_id) on delete restrict,
  foreign key (supplier_id, business_id) references suppliers (id, business_id) on delete restrict,
  foreign key (created_by, business_id) references profiles (id, business_id) on delete set null
);
create index lots_product_idx on lots (product_id);
create index lots_expiry_idx on lots (business_id, expires_on);

create table movements (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references businesses (id) on delete cascade,
  lot_id uuid not null,
  event_id uuid,
  type movement_type not null,
  quantity numeric not null check (quantity > 0),
  reason text,
  reverses_id uuid,
  -- Idempotency for the offline queue: a retry does not duplicate the
  -- movement.
  client_id uuid unique,
  created_by uuid,
  created_at timestamptz not null default now(),
  constraint scarto_needs_reason check (type <> 'scarto' or reason is not null),
  unique (id, business_id),
  foreign key (lot_id, business_id) references lots (id, business_id) on delete restrict,
  foreign key (event_id, business_id) references events (id, business_id) on delete set null,
  foreign key (reverses_id, business_id) references movements (id, business_id) on delete set null,
  foreign key (created_by, business_id) references profiles (id, business_id) on delete set null
);
create index movements_lot_idx on movements (lot_id);
create index movements_business_date_idx on movements (business_id, created_at desc);
create index movements_event_idx on movements (event_id) where event_id is not null;

-- ---------------------------------------------------------------- functions
-- SECURITY DEFINER on purpose: these functions are used INSIDE the RLS
-- policies on profiles. If they respected RLS, querying profiles to decide
-- whether profiles may be queried would be infinite recursion.

create or replace function auth_business_id()
returns uuid
language sql
stable
security definer
set search_path = public
as $$
  select business_id from profiles where id = auth.uid() and active
$$;

create or replace function auth_role()
returns user_role
language sql
stable
security definer
set search_path = public
as $$
  select role from profiles where id = auth.uid() and active
$$;

-- ---------------------------------------------------------------- views
-- Stock is not stored: it is computed. That way it never drifts out of
-- sync with the record.

create view lot_stock as
select
  l.id as lot_id,
  l.business_id,
  l.product_id,
  coalesce(
    sum(case when m.type = 'carico' then m.quantity else -m.quantity end),
    0
  ) as stock
from lots l
left join movements m on m.lot_id = l.id
where l.business_id = auth_business_id()
group by l.id, l.business_id, l.product_id;

create view product_stock as
select business_id, product_id, sum(stock) as stock
from lot_stock
group by business_id, product_id;

-- The price is not hidden on the client: it never leaves the database for
-- an operatore. That is why direct access to lots is revoked and it is
-- read through this view instead.
create view lots_view as
select
  l.id,
  l.business_id,
  l.product_id,
  l.supplier_id,
  l.lot_code,
  l.expires_on,
  l.document_url,
  l.received_on,
  l.created_by,
  l.created_at,
  case when auth_role() in ('titolare', 'responsabile') then l.unit_price end as unit_price
from lots l
where l.business_id = auth_business_id();
