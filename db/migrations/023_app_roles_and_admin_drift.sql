-- ============================================================
-- 023: App Postgres roles + admin-console schema drift notes
-- ============================================================
-- Context (deployed DB, 2026-06-13): every /api/admin/* list endpoint
-- (vehicles, users, routes, analytics, alerts) returned 500 while anonymous
-- public reads worked.
--
-- The backend forwards the signed-in user's JWT to PostgREST so RLS applies
-- per tenant. For that to work, two things must be true on the database:
--
--   1. The JWT `role` claim must be a real Postgres role that the
--      `authenticator` role may SET ROLE into. The app puts the application
--      role (admin / dispatcher / driver / viewer / super_admin) in the JWT
--      `role` claim, but those roles did NOT exist here (drift) — so PostgREST
--      could not `SET ROLE admin` and every staff request failed. This
--      migration creates them (NOLOGIN), grants them the `authenticated`
--      privilege set, and lets `authenticator` switch into them.
--
--   2. **The app's JWT_SECRET env var must equal the Supabase project JWT
--      secret** (Supabase → Project Settings → API → JWT Secret). Otherwise
--      PostgREST rejects the token's signature and staff reads still 500 even
--      after the roles exist. This is a Vercel ENV change, not SQL — see the
--      note at the bottom.
-- ============================================================

DO $rolefix$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'admin')       THEN CREATE ROLE admin NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dispatcher')  THEN CREATE ROLE dispatcher NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'driver')      THEN CREATE ROLE driver NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'viewer')      THEN CREATE ROLE viewer NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'super_admin') THEN CREATE ROLE super_admin NOLOGIN; END IF;

  -- App roles inherit the standard Supabase "authenticated" grants (gated by RLS).
  GRANT authenticated TO admin, dispatcher, driver, viewer, super_admin;
  -- PostgREST connects as authenticator and must be able to SET ROLE into them.
  GRANT admin, dispatcher, driver, viewer, super_admin TO authenticator;
END $rolefix$;

NOTIFY pgrst, 'reload schema';

-- ------------------------------------------------------------
-- REQUIRED env fix (do this in Vercel, then redeploy):
--   JWT_SECRET = <Supabase project JWT secret>
-- so the user JWTs the API mints are accepted by PostgREST. Without it, the
-- admin/dispatcher dashboards keep returning 500 on their list endpoints.
--
-- Alternative (code) fix if you cannot align the secret: make the server-
-- trusted admin read endpoints in api/routers/admin.py use the service-role
-- key (_service_get) instead of forwarding the user token (_supabase_get) —
-- the same pattern already applied to login in api/routers/auth.py. They
-- already scope by operator_id in code, so RLS is not required for them.
-- ------------------------------------------------------------

-- ------------------------------------------------------------
-- Remaining schema drift on this database (create from db/schema.sql when
-- reconciling): tables  schedules, audit_log, payments  and column
-- vehicles.approval_status (migration 019) are absent. Admin *write* features
-- (approve vehicle, audit trail, payments page) need these.
-- ------------------------------------------------------------
