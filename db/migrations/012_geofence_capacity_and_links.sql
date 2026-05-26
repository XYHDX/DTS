-- ============================================================
-- Migration 012: Geofence capacity caps + vehicle-zone links
-- ============================================================
-- Adds:
--   • geofences.max_vehicles   — hard cap on simultaneous vehicles in zone
--   • vehicle_geofences         — many-to-many link (a vehicle "belongs to"
--                                  a depot/zone); used by the atomic
--                                  registration endpoint.
--   • alert_type 'capacity_exceeded' — new enum value (older deployments
--                                       may still see 'geofence_exit').
-- ============================================================

BEGIN;

-- 1. max_vehicles column on geofences (NULL = no cap)
ALTER TABLE geofences
    ADD COLUMN IF NOT EXISTS max_vehicles INTEGER;

COMMENT ON COLUMN geofences.max_vehicles IS
    'Hard cap on simultaneous vehicles inside this geofence. NULL = no limit.';

CREATE INDEX IF NOT EXISTS idx_geofences_max_vehicles
    ON geofences(max_vehicles) WHERE max_vehicles IS NOT NULL;

-- 2. vehicle ↔ geofence association (depot / home zone)
CREATE TABLE IF NOT EXISTS vehicle_geofences (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vehicle_id   UUID NOT NULL REFERENCES vehicles(id)  ON DELETE CASCADE,
    geofence_id  UUID NOT NULL REFERENCES geofences(id) ON DELETE CASCADE,
    operator_id  UUID REFERENCES operators(id),
    role         TEXT NOT NULL DEFAULT 'home',   -- 'home', 'allowed', 'restricted'
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(vehicle_id, geofence_id)
);

CREATE INDEX IF NOT EXISTS idx_vg_vehicle  ON vehicle_geofences(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_vg_geofence ON vehicle_geofences(geofence_id);
CREATE INDEX IF NOT EXISTS idx_vg_operator ON vehicle_geofences(operator_id);

ALTER TABLE vehicle_geofences ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_vehicle_geofences ON vehicle_geofences;
CREATE POLICY tenant_vehicle_geofences ON vehicle_geofences
    USING (
        operator_id = current_operator_id()
        OR auth.jwt() ->> 'role' = 'super_admin'
    );

-- 3. New alert_type value. ENUM ADD VALUE is not transactional on every
--    Postgres version — wrap defensively.
DO $$ BEGIN
  ALTER TYPE alert_type ADD VALUE IF NOT EXISTS 'capacity_exceeded';
EXCEPTION WHEN others THEN NULL; END $$;

-- 4. Helper view: how many vehicles are currently inside each geofence.
--    Used by the admin overview to flag near-capacity zones.
CREATE OR REPLACE VIEW geofence_occupancy AS
SELECT
    g.id              AS geofence_id,
    g.name            AS geofence_name,
    g.name_ar         AS geofence_name_ar,
    g.operator_id     AS operator_id,
    g.max_vehicles    AS max_vehicles,
    COUNT(vpl.vehicle_id) FILTER (
        WHERE vpl.location IS NOT NULL
          AND ST_Contains(g.geometry, vpl.location)
    )                 AS current_count
FROM geofences g
LEFT JOIN vehicle_positions_latest vpl
       ON vpl.operator_id = g.operator_id
GROUP BY g.id;

COMMIT;
