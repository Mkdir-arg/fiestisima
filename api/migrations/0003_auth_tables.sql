-- Tokens and attempt tracking for the API's own auth. Owner-only tables:
-- app_user never reads them, so no RLS and no grants.
create table refresh_tokens (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users (id) on delete cascade,
  token_hash text not null unique,
  expires_at timestamptz not null,
  revoked_at timestamptz,
  created_at timestamptz not null default now()
);
create index refresh_tokens_user_idx on refresh_tokens (user_id);

create table login_attempts (
  email citext not null,
  attempted_at timestamptz not null default now(),
  succeeded boolean not null
);
create index login_attempts_email_time_idx on login_attempts (email, attempted_at desc);

create table password_resets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users (id) on delete cascade,
  token_hash text not null unique,
  expires_at timestamptz not null,
  used_at timestamptz
);
