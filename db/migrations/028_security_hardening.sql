-- ============================================================
-- Migration 028: Security Advisor hardening (splinter linter)
-- ============================================================
-- Clears the Supabase → Advisors → Security findings that are safe to fix:
--
--  WARN "Function Search Path Mutable"  → pin a fixed search_path on every
--       function WE own (PostGIS functions are skipped).
--  WARN "…Can Execute" on upsert_vehicle_position → SECURITY DEFINER *write*
--       RPC; only the backend (service role) should call it, so revoke it from
--       anon/authenticated (closes a real position-spoofing hole).
--  WARN "…Can Execute" on find_nearest_stops → switch it to SECURITY INVOKER
--       (the advisor's recommended fix). It only reads the public `stops`
--       table, which has a public-read policy, so the passenger search keeps
--       working without elevated privileges.
--  WARN "…Can Execute" on st_estimatedextent (PostGIS) → the app never calls
--       it; revoke EXECUTE from anon/authenticated as the advisor suggests.
--  ERROR "RLS Disabled" on spatial_ref_sys → enable RLS + a read-for-all
--       policy (PostGIS reference data). Skipped if this role can't alter it.
--
-- NOT changed: "Extension in Public" (postgis). Moving an installed PostGIS to
-- another schema can break every geometry column/query; it is a warning, not a
-- real risk for this app. See the note at the bottom.
--
-- Idempotent. Apply: Supabase SQL Editor → paste → Run → Rerun linter.
-- ============================================================

-- 1) Pin search_path on every function we own (skip extension-owned PostGIS).
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT p.oid::regprocedure AS sig
      FROM pg_proc p
      JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'public'
       AND p.prokind = 'f'
       AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = p.oid AND d.deptype = 'e')
  LOOP
    EXECUTE format('ALTER FUNCTION %s SET search_path = public, pg_temp', r.sig);
  END LOOP;
END $$;

-- 2) Lock the position-ingest RPC to the service role only.
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT p.oid::regprocedure AS sig
      FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'public' AND p.proname = 'upsert_vehicle_position'
  LOOP
    EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC, anon, authenticated', r.sig);
    EXECUTE format('GRANT  EXECUTE ON FUNCTION %s TO service_role', r.sig);
  END LOOP;
END $$;

-- 3) find_nearest_stops → SECURITY INVOKER. Ensure the public read policy on
--    stops exists first so the anon passenger search keeps returning results.
DO $$ BEGIN EXECUTE 'ALTER TABLE public.stops ENABLE ROW LEVEL SECURITY'; EXCEPTION WHEN others THEN NULL; END $$;
DROP POLICY IF EXISTS public_read_stops ON public.stops;
CREATE POLICY public_read_stops ON public.stops FOR SELECT USING (true);

CREATE OR REPLACE FUNCTION public.find_nearest_stops(
    p_lat       double precision,
    p_lon       double precision,
    p_limit     integer DEFAULT 5,
    p_radius_m  integer DEFAULT 1000
) RETURNS TABLE (
    id uuid, stop_id text, name text, name_ar text,
    distance_m double precision, lat double precision, lon double precision
)
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $func$
BEGIN
    RETURN QUERY
    SELECT
        s.id, s.stop_id, s.name, s.name_ar,
        ST_Distance(s.location::geography,
                    ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326)::geography) AS distance_m,
        ST_Y(s.location) AS lat,
        ST_X(s.location) AS lon
    FROM stops s
    WHERE s.is_active = true
      AND ST_DWithin(s.location::geography,
                     ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326)::geography,
                     p_radius_m)
    ORDER BY distance_m
    LIMIT p_limit;
END;
$func$;
GRANT EXECUTE ON FUNCTION public.find_nearest_stops(double precision, double precision, integer, integer)
  TO anon, authenticated;

-- 4) Revoke anon/authenticated EXECUTE on the PostGIS st_estimatedextent
--    overloads (the app never calls them). Per-overload, guarded.
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT p.oid::regprocedure AS sig
      FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'public' AND p.proname = 'st_estimatedextent'
  LOOP
    BEGIN
      EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM anon, authenticated', r.sig);
    EXCEPTION WHEN insufficient_privilege THEN
      RAISE NOTICE 'st_estimatedextent: cannot revoke (PostGIS-owned) — skipped %', r.sig;
    END;
  END LOOP;
END $$;

-- 5) spatial_ref_sys: PostGIS reference data in the public schema. Enable RLS
--    with a read-for-all policy so PostGIS keeps working; skip if not owner.
DO $$
BEGIN
  EXECUTE 'ALTER TABLE public.spatial_ref_sys ENABLE ROW LEVEL SECURITY';
  EXECUTE 'DROP POLICY IF EXISTS spatial_ref_sys_read ON public.spatial_ref_sys';
  EXECUTE 'CREATE POLICY spatial_ref_sys_read ON public.spatial_ref_sys FOR SELECT USING (true)';
EXCEPTION
  WHEN insufficient_privilege OR undefined_table THEN
    RAISE NOTICE 'spatial_ref_sys: owned by PostGIS, cannot alter here — left as-is (reference data only).';
END $$;

-- PostgREST caches the schema; reload so the changed RPCs are picked up.
NOTIFY pgrst, 'reload schema';

-- ============================================================
-- Deliberately NOT changed: "Extension in Public" (postgis). Relocating an
-- installed PostGIS to another schema after the fact can break every geometry
-- column and spatial query in the app. It is a warning, not an exploit path —
-- leaving PostGIS in `public` is the standard, safe choice here.
-- ============================================================
