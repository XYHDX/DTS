-- ============================================================
-- 021: Restore PUBLIC READ on the public-facing tables
-- ============================================================
-- Why: migration 002 (multi-tenancy) DROPPED the original public_read_*
-- policies and replaced them with tenant_read_* policies of the form:
--
--     USING (operator_id = current_operator_id()
--            OR auth.jwt() ->> 'role' = 'super_admin')
--
-- and current_operator_id() = (auth.jwt() ->> 'operator_id')::uuid, which is
-- NULL for an anonymous request. So an anonymous visitor (the passenger app,
-- the public home page, the live map, AND the operator-slug resolution in
-- api/core/tenancy.py) can read NOTHING. The symptom is every operator-scoped
-- endpoint returning 404 "Operator 'damascus' not found" even when the data
-- is seeded.
--
-- Damascus Transit data (operators, routes, stops, schedules, live positions)
-- is public by design. This migration restores the pre-002 public SELECT
-- access (schema.sql's public_read_* policies) WITHOUT touching the
-- tenant_write_* policies, so writes stay tenant-scoped. It does NOT open the
-- `users` table (password hashes stay private — login uses the service key
-- in api/routers/auth.py instead).
--
-- Idempotent: safe to run multiple times.
-- ============================================================

-- operators — needed so anonymous reads can resolve the default operator slug
DROP POLICY IF EXISTS public_read_operators ON public.operators;
CREATE POLICY public_read_operators ON public.operators
  FOR SELECT USING (true);

-- routes
DROP POLICY IF EXISTS public_read_routes ON public.routes;
CREATE POLICY public_read_routes ON public.routes
  FOR SELECT USING (true);

-- stops
DROP POLICY IF EXISTS public_read_stops ON public.stops;
CREATE POLICY public_read_stops ON public.stops
  FOR SELECT USING (true);

-- route_stops
DROP POLICY IF EXISTS public_read_route_stops ON public.route_stops;
CREATE POLICY public_read_route_stops ON public.route_stops
  FOR SELECT USING (true);

-- schedules
DROP POLICY IF EXISTS public_read_schedules ON public.schedules;
CREATE POLICY public_read_schedules ON public.schedules
  FOR SELECT USING (true);

-- vehicle_positions_latest — the live map
DROP POLICY IF EXISTS public_read_positions ON public.vehicle_positions_latest;
CREATE POLICY public_read_positions ON public.vehicle_positions_latest
  FOR SELECT USING (true);

-- Verify (run as service role in the SQL editor — bypasses RLS):
--   SELECT slug, is_active FROM public.operators WHERE slug = 'damascus';
-- Then from the public API:
--   curl https://dts-brown.vercel.app/api/stats   -> expect 200, not 404
