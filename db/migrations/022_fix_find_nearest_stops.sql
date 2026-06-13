-- ============================================================
-- 022: Fix passenger "nearby stops" (find_nearest_stops RPC)
-- ============================================================
-- Symptom: GET /api/stops/nearest returned an empty list even with stops
-- seeded and within range.
--
-- Root causes found on the deployed DB (2026-06-13):
--   1. The find_nearest_stops() function did not exist at all (schema drift —
--      it lived only in db/schema.sql, which was never fully applied here).
--      The API's graceful fallback then turned the missing-RPC error into [].
--   2. The API's NearestStop model requires `id` (NOT NULL), but the original
--      schema.sql function did not return the stop's id — so even once created,
--      every row failed validation and the endpoint returned [].
--   3. The function read `stops` as SECURITY INVOKER, so anonymous public
--      reads depended on RLS. Making it SECURITY DEFINER guarantees the public
--      "nearby stops" feature works regardless of RLS posture.
--
-- This migration creates the corrected function (returns id, SECURITY DEFINER,
-- pinned search_path) and grants EXECUTE to the API roles. Idempotent.
-- ============================================================

DROP FUNCTION IF EXISTS find_nearest_stops(double precision, double precision, integer, integer);

CREATE FUNCTION find_nearest_stops(
    p_lat       double precision,
    p_lon       double precision,
    p_limit     integer DEFAULT 5,
    p_radius_m  integer DEFAULT 1000
) RETURNS TABLE (
    id          uuid,
    stop_id     text,
    name        text,
    name_ar     text,
    distance_m  double precision,
    lat         double precision,
    lon         double precision
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $func$
BEGIN
    RETURN QUERY
    SELECT
        s.id,
        s.stop_id,
        s.name,
        s.name_ar,
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

GRANT EXECUTE ON FUNCTION find_nearest_stops(double precision, double precision, integer, integer)
    TO anon, authenticated;

-- PostgREST caches the schema; tell it to reload so the RPC is visible.
NOTIFY pgrst, 'reload schema';

-- ------------------------------------------------------------
-- Related data fix already applied live: some vehicles had a NULL name_ar,
-- which broke the SSE position stream (PositionData validation) and
-- GET /api/vehicles. Back-fill kept here for fresh databases:
-- ------------------------------------------------------------
UPDATE public.vehicles
   SET name_ar = COALESCE(NULLIF(name_ar, ''), name, vehicle_id),
       name    = COALESCE(NULLIF(name, ''), name_ar, vehicle_id)
 WHERE name_ar IS NULL OR name_ar = '' OR name IS NULL OR name = '';
