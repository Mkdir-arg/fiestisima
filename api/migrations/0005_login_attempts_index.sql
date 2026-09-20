-- The login lockout check (POST /auth/login) counts failed attempts for one
-- email in the last 15 minutes on every single login request, successful or
-- not. 0003's login_attempts_email_time_idx already covers (email,
-- attempted_at) but scans every row for that email, including the
-- successful ones the lockout query never looks at. A partial index on
-- just the failed rows keeps that count cheap as login_attempts grows -
-- the table has no retention policy yet (flagged in the Task 1 review),
-- so it only ever gets bigger.
create index login_attempts_failed_idx
  on login_attempts (email, attempted_at)
  where succeeded = false;
