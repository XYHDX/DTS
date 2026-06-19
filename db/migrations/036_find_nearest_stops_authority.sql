-- ============================================================
-- 036: find_nearest_stops — single source of truth  (L8)
-- ============================================================
-- The function's security posture flips across migrations: 022 created it
-- SECURITY DEFINER, 028 recreated it SECURITY INVOKER. That's only correct if
-- migrations run strictly in numeric order; re-running 022, or applying out of
-- order, silently flips it back to DEFINER. This migration re-asserts the
-- intended INVOKER definition verbatim so the LATEST migration is the
-- authority. Kept byte-for-byte in step with 028 / db/schema.sql.
-- Idempotent (CREATE OR REPLACE).
-- ============================================================

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
