-- app_user cannot read `users` (that is where password_hash lives - see
-- 0002/0003's grants, which never touch that table), but GET /users needs
-- each colleague's email for the Utenti screen. Same pattern as lots_view
-- in 0001: a security_barrier view owned by the migration role (the owner,
-- `fiestisima`) does the join as owner and re-applies the tenant filter
-- itself, then is granted to app_user column-by-column-free (the view
-- exposes no password_hash column at all, so there is nothing to hide with
-- a case expression the way lots_view hides unit_price).
create view business_users with (security_barrier = true) as
select
  p.id,
  u.email,
  p.full_name,
  p.role,
  p.active,
  p.last_seen_at,
  p.created_at
from profiles p
join users u on u.id = p.id
where p.business_id = app_business_id();

grant select on business_users to app_user;
