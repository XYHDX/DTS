-- ============================================================
-- Migration 027: One GPS device per vehicle
-- ============================================================
-- Problem (the "wrong bus" bug): vehicles.gps_device_id had only a
-- plain, non-unique index (idx_vehicles_gps). Nothing stopped two
-- vehicles from carrying the same device id — e.g. the real DTS002
-- tracker and a test/demo vehicle both set to 'DTS002'. The Traccar
-- webhook resolves a device with:
--
--     vehicles?gps_device_id=eq.<id>
--
-- and used the FIRST row returned, so a live fix could attach to the
-- wrong vehicle on the map.
--
-- This migration:
--   1. De-duplicates existing data — keeps the device id on the single
--      best vehicle per device (a real-GPS vehicle wins, then the most
--      recently updated), and clears it from any others.
--   2. Normalises empty strings to NULL.
--   3. Adds a partial UNIQUE index so the collision can never recur.
--
-- Pairs with: deterministic resolution in api/routers/traccar.py
-- (order=is_real_gps.desc,updated_at.desc) and a duplicate pre-check in
-- create_vehicle (api/routers/admin.py).
--
-- Apply: Supabase SQL Editor → New query → paste this whole file → Run.
-- Idempotent — safe to run more than once.
-- ============================================================

BEGIN;

-- 1) De-duplicate. Rank vehicles that share a device id and keep it only
--    on rn = 1 (real GPS first, then newest), clearing the rest.
WITH ranked AS (
  SELECT id,
         row_number() OVER (
           PARTITION BY gps_device_id
           ORDER BY is_real_gps DESC,
                    updated_at DESC NULLS LAST,
                    created_at DESC NULLS LAST
         ) AS rn
    FROM public.vehicles
   WHERE gps_device_id IS NOT NULL
     AND gps_device_id <> ''
)
UPDATE public.vehicles v
   SET gps_device_id = NULL,
       updated_at    = NOW()
  FROM ranked
 WHERE v.id = ranked.id
   AND ranked.rn > 1;

-- 2) Treat empty string as "no device".
UPDATE public.vehicles
   SET gps_device_id = NULL
 WHERE gps_device_id = '';

-- 3) Hard guard: at most one vehicle per non-null device id.
CREATE UNIQUE INDEX IF NOT EXISTS uq_vehicles_gps_device_id
    ON public.vehicles (gps_device_id)
 WHERE gps_device_id IS NOT NULL;

COMMIT;

-- Verify (optional) — should return zero rows after this runs:
--   SELECT gps_device_id, count(*)
--     FROM public.vehicles
--    WHERE gps_device_id IS NOT NULL
--    GROUP BY gps_device_id HAVING count(*) > 1;
