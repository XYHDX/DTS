-- ============================================================
-- Remove DEMO data — keep everything you created
-- ============================================================
-- Deletes ONLY the rows seeded by db/demo_seed.sql:
--   • vehicles  BUS-101, BUS-102, MIC-014, TAX-100
--   • routes    R001, M014, T100        (+ their route_stops, via cascade)
--   • stops     S001 … S006
--   • accounts  every *@damascus-transit.demo  (all 5)
--
-- Your real data — the DTS002 bus, any routes/drivers/vehicles YOU created,
-- and the account you log in with — is NOT touched (anything not in the lists
-- above is left alone).
--
-- Runs as ONE transaction: if anything unexpected blocks it, NOTHING is
-- deleted (send me the error and I'll adjust). Reversible: re-run
-- db/demo_seed.sql to bring the demo data back. Safe to re-run.
--
-- How to run: Supabase dashboard → SQL Editor → New query → paste → Run.
-- ============================================================

BEGIN;

-- Resolve the demo rows by their business keys (never by hard-coded UUID).
CREATE TEMP TABLE _demo_v ON COMMIT DROP AS
  SELECT id FROM public.vehicles WHERE vehicle_id IN ('BUS-101','BUS-102','MIC-014','TAX-100');
CREATE TEMP TABLE _demo_r ON COMMIT DROP AS
  SELECT id FROM public.routes   WHERE route_id   IN ('R001','M014','T100');
CREATE TEMP TABLE _demo_u ON COMMIT DROP AS
  SELECT id FROM public.users    WHERE email LIKE '%@damascus-transit.demo';

-- 1) Protect real rows: detach any assignment pointing at a demo route/driver.
UPDATE public.vehicles SET assigned_route_id  = NULL WHERE assigned_route_id  IN (SELECT id FROM _demo_r);
UPDATE public.vehicles SET assigned_driver_id = NULL WHERE assigned_driver_id IN (SELECT id FROM _demo_u);

-- 2) Delete child rows that reference demo vehicles / routes / users.
--    Each is guarded so a table that isn't on your DB is simply skipped.
DO $$ BEGIN DELETE FROM public.vehicle_positions_latest WHERE vehicle_id IN (SELECT id FROM _demo_v); EXCEPTION WHEN undefined_table THEN NULL; END $$;
DO $$ BEGIN DELETE FROM public.vehicle_positions        WHERE vehicle_id IN (SELECT id FROM _demo_v); EXCEPTION WHEN undefined_table THEN NULL; END $$;
DO $$ BEGIN DELETE FROM public.payments  WHERE vehicle_id IN (SELECT id FROM _demo_v) OR route_id IN (SELECT id FROM _demo_r); EXCEPTION WHEN undefined_table THEN NULL; END $$;
DO $$ BEGIN DELETE FROM public.alerts    WHERE vehicle_id IN (SELECT id FROM _demo_v); EXCEPTION WHEN undefined_table THEN NULL; END $$;
DO $$ BEGIN DELETE FROM public.trips     WHERE vehicle_id IN (SELECT id FROM _demo_v) OR route_id IN (SELECT id FROM _demo_r) OR driver_id IN (SELECT id FROM _demo_u); EXCEPTION WHEN undefined_table THEN NULL; END $$;
DO $$ BEGIN DELETE FROM public.schedules WHERE route_id   IN (SELECT id FROM _demo_r); EXCEPTION WHEN undefined_table THEN NULL; END $$;
DO $$ BEGIN DELETE FROM public.headway_observations WHERE route_id IN (SELECT id FROM _demo_r); EXCEPTION WHEN undefined_table THEN NULL; END $$;

-- 3) Clear remaining user references so the demo accounts can be removed.
DO $$ BEGIN UPDATE public.alerts SET resolved_by = NULL WHERE resolved_by IN (SELECT id FROM _demo_u); EXCEPTION WHEN undefined_column THEN NULL; END $$;
DO $$ BEGIN UPDATE public.trips  SET dispatched_by_user_id = NULL WHERE dispatched_by_user_id IN (SELECT id FROM _demo_u); EXCEPTION WHEN undefined_column OR undefined_table THEN NULL; END $$;
DO $$ BEGIN DELETE FROM public.audit_log WHERE admin_id IN (SELECT id FROM _demo_u); EXCEPTION WHEN undefined_column OR undefined_table THEN NULL; END $$;
DO $$ BEGIN DELETE FROM public.audit_log WHERE user_id  IN (SELECT id FROM _demo_u); EXCEPTION WHEN undefined_column OR undefined_table THEN NULL; END $$;

-- 4) Delete the demo parents. route_stops cascades from routes/stops.
DELETE FROM public.vehicles WHERE id IN (SELECT id FROM _demo_v);
DELETE FROM public.routes   WHERE id IN (SELECT id FROM _demo_r);
DELETE FROM public.stops    WHERE stop_id IN ('S001','S002','S003','S004','S005','S006');
DELETE FROM public.users    WHERE id IN (SELECT id FROM _demo_u);

COMMIT;

-- Verify — every count below should be 0:
--   SELECT count(*) FROM public.vehicles WHERE vehicle_id IN ('BUS-101','BUS-102','MIC-014','TAX-100');
--   SELECT count(*) FROM public.routes   WHERE route_id   IN ('R001','M014','T100');
--   SELECT count(*) FROM public.stops    WHERE stop_id    IN ('S001','S002','S003','S004','S005','S006');
--   SELECT count(*) FROM public.users    WHERE email LIKE '%@damascus-transit.demo';
