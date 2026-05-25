-- ============================================================
-- Migration 002: Multi-tenancy support for multiple fleet operators
-- ============================================================
-- Adds an `operators` table and ties all major entities to a tenant.
-- Existing single-tenant data is migrated to a default "damascus" operator.
-- ============================================================

BEGIN;

-- ============================================================
-- 1. OPERATORS TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS operators (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug          TEXT UNIQUE NOT NULL,          -- e.g. "damascus", "aleppo-transit"
    name          TEXT NOT NULL,                  -- display name
    name_ar       TEXT,
    plan          TEXT NOT NULL DEFAULT 'free',   -- 'free', 'pro', 'enterprise'
    is_active     BOOLEAN NOT NULL DEFAULT true,
    settings      JSONB NOT NULL DEFAULT '{}',    -- operator-level config
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_operators_slug ON operators(slug);

-- Seed the default Damascus operator so existing data stays valid
INSERT INTO operators (id, slug, name, name_ar, plan)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'damascus',
    'Damascus Transit Authority',
    'هيئة نقل دمشق',
    'enterprise'
)
ON CONFLICT (slug) DO NOTHING;

-- ============================================================
-- 2. ADD operator_id TO ALL TENANT-SCOPED TABLES
--    Default the existing rows to the Damascus operator.
-- ============================================================

-- users
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS operator_id UUID
        REFERENCES operators(id) ON DELETE CASCADE;

UPDATE users SET operator_id = '00000000-0000-0000-0000-000000000001'
    WHERE operator_id IS NULL;

ALTER TABLE users
    ALTER COLUMN operator_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_users_operator ON users(operator_id);

-- routes
ALTER TABLE routes
    ADD COLUMN IF NOT EXISTS operator_id UUID
        REFERENCES operators(id) ON DELETE CASCADE;

UPDATE routes SET operator_id = '00000000-0000-0000-0000-000000000001'
    WHERE operator_id IS NULL;

ALTER TABLE routes
    ALTER COLUMN operator_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_routes_operator ON routes(operator_id);

-- stops (stops may be shared between operators in future, but for now scoped)
ALTER TABLE stops
    ADD COLUMN IF NOT EXISTS operator_id UUID
        REFERENCES operators(id) ON DELETE CASCADE;

UPDATE stops SET operator_id = '00000000-0000-0000-0000-000000000001'
    WHERE operator_id IS NULL;

ALTER TABLE stops
    ALTER COLUMN operator_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_stops_operator ON stops(operator_id);

-- vehicles
ALTER TABLE vehicles
    ADD COLUMN IF NOT EXISTS operator_id UUID
        REFERENCES operators(id) ON DELETE CASCADE;

UPDATE vehicles SET operator_id = '00000000-0000-0000-0000-000000000001'
    WHERE operator_id IS NULL;

ALTER TABLE vehicles
    ALTER COLUMN operator_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_vehicles_operator ON vehicles(operator_id);

-- vehicle_positions
ALTER TABLE vehicle_positions
    ADD COLUMN IF NOT EXISTS operator_id UUID
        REFERENCES operators(id) ON DELETE CASCADE;

UPDATE vehicle_positions SET operator_id = '00000000-0000-0000-0000-000000000001'
    WHERE operator_id IS NULL;

ALTER TABLE vehicle_positions
    ALTER COLUMN operator_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_positions_operator ON vehicle_positions(operator_id);

-- vehicle_positions_latest
ALTER TABLE vehicle_positions_latest
    ADD COLUMN IF NOT EXISTS operator_id UUID
        REFERENCES operators(id) ON DELETE CASCADE;

UPDATE vehicle_positions_latest SET operator_id = '00000000-0000-0000-0000-000000000001'
    WHERE operator_id IS NULL;

ALTER TABLE vehicle_positions_latest
    ALTER COLUMN operator_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_latest_operator ON vehicle_positions_latest(operator_id);

-- trips
ALTER TABLE trips
    ADD COLUMN IF NOT EXISTS operator_id UUID
        REFERENCES operators(id) ON DELETE CASCADE;

UPDATE trips SET operator_id = '00000000-0000-0000-0000-000000000001'
    WHERE operator_id IS NULL;

ALTER TABLE trips
    ALTER COLUMN operator_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_trips_operator ON trips(operator_id);

-- alerts
ALTER TABLE alerts
    ADD COLUMN IF NOT EXISTS operator_id UUID
        REFERENCES operators(id) ON DELETE CASCADE;

UPDATE alerts SET operator_id = '00000000-0000-0000-0000-000000000001'
    WHERE operator_id IS NULL;

ALTER TABLE alerts
    ALTER COLUMN operator_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_alerts_operator ON alerts(operator_id);

-- geofences
ALTER TABLE geofences
    ADD COLUMN IF NOT EXISTS operator_id UUID
        REFERENCES operators(id) ON DELETE CASCADE;

UPDATE geofences SET operator_id = '00000000-0000-0000-0000-000000000001'
    WHERE operator_id IS NULL;

ALTER TABLE geofences
    ALTER COLUMN operator_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_geofences_operator ON geofences(operator_id);

-- schedules
ALTER TABLE schedules
    ADD COLUMN IF NOT EXISTS operator_id UUID
        REFERENCES operators(id) ON DELETE CASCADE;

UPDATE schedules SET operator_id = '00000000-0000-0000-0000-000000000001'
    WHERE operator_id IS NULL;

ALTER TABLE schedules
    ALTER COLUMN operator_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_schedules_operator ON schedules(operator_id);

-- audit_log
ALTER TABLE audit_log
    ADD COLUMN IF NOT EXISTS operator_id UUID
        REFERENCES operators(id) ON DELETE SET NULL;

UPDATE audit_log SET operator_id = '00000000-0000-0000-0000-000000000001'
    WHERE operator_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_audit_operator ON audit_log(operator_id);

-- ============================================================
-- 3. ADD super_admin ROLE
-- ============================================================

ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'super_admin';

-- ============================================================
-- 4. UPDATE RLS POLICIES FOR TENANT ISOLATION
-- ============================================================

-- Helper: extract operator_id from JWT claims
-- The API injects operator_id into the JWT.  Supabase passes it via auth.jwt().
-- We expose it as a SQL helper so policies stay readable.
CREATE OR REPLACE FUNCTION current_operator_id() RETURNS UUID AS $$
BEGIN
    RETURN (auth.jwt() ->> 'operator_id')::UUID;
EXCEPTION
    WHEN others THEN RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

-- Drop old single-tenant policies and replace with tenant-scoped ones.

-- users
DROP POLICY IF EXISTS admin_all ON users;
CREATE POLICY tenant_users ON users
    USING (
        operator_id = current_operator_id()
        OR auth.jwt() ->> 'role' = 'super_admin'
    );

-- routes
DROP POLICY IF EXISTS public_read_routes ON routes;
DROP POLICY IF EXISTS admin_write_routes ON routes;
CREATE POLICY tenant_read_routes ON routes FOR SELECT
    USING (
        operator_id = current_operator_id()
        OR auth.jwt() ->> 'role' = 'super_admin'
    );
CREATE POLICY tenant_write_routes ON routes FOR ALL
    USING (
        operator_id = current_operator_id()
        AND auth.jwt() ->> 'role' IN ('admin', 'super_admin')
    );

-- stops
DROP POLICY IF EXISTS public_read_stops ON stops;
DROP POLICY IF EXISTS admin_write_stops ON stops;
CREATE POLICY tenant_read_stops ON stops FOR SELECT
    USING (
        operator_id = current_operator_id()
        OR auth.jwt() ->> 'role' = 'super_admin'
    );
CREATE POLICY tenant_write_stops ON stops FOR ALL
    USING (
        operator_id = current_operator_id()
        AND auth.jwt() ->> 'role' IN ('admin', 'super_admin')
    );

-- route_stops
DROP POLICY IF EXISTS public_read_route_stops ON route_stops;
DROP POLICY IF EXISTS admin_write_route_stops ON route_stops;
CREATE POLICY tenant_read_route_stops ON route_stops FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM routes r
            WHERE r.id = route_stops.route_id
              AND (r.operator_id = current_operator_id() OR auth.jwt() ->> 'role' = 'super_admin')
        )
    );
CREATE POLICY tenant_write_route_stops ON route_stops FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM routes r
            WHERE r.id = route_stops.route_id
              AND r.operator_id = current_operator_id()
              AND auth.jwt() ->> 'role' IN ('admin', 'super_admin')
        )
    );

-- vehicles
DROP POLICY IF EXISTS admin_vehicles ON vehicles;
CREATE POLICY tenant_vehicles ON vehicles
    USING (
        operator_id = current_operator_id()
        OR auth.jwt() ->> 'role' = 'super_admin'
    );

-- vehicle_positions_latest
DROP POLICY IF EXISTS public_read_positions ON vehicle_positions_latest;
DROP POLICY IF EXISTS admin_write_positions ON vehicle_positions_latest;
CREATE POLICY tenant_read_positions ON vehicle_positions_latest FOR SELECT
    USING (
        operator_id = current_operator_id()
        OR auth.jwt() ->> 'role' = 'super_admin'
    );
CREATE POLICY tenant_write_positions ON vehicle_positions_latest FOR ALL
    USING (
        operator_id = current_operator_id()
        AND auth.jwt() ->> 'role' IN ('admin', 'dispatcher', 'super_admin')
    );

-- schedules
DROP POLICY IF EXISTS public_read_schedules ON schedules;
DROP POLICY IF EXISTS admin_write_schedules ON schedules;
CREATE POLICY tenant_read_schedules ON schedules FOR SELECT
    USING (
        operator_id = current_operator_id()
        OR auth.jwt() ->> 'role' = 'super_admin'
    );
CREATE POLICY tenant_write_schedules ON schedules FOR ALL
    USING (
        operator_id = current_operator_id()
        AND auth.jwt() ->> 'role' IN ('admin', 'super_admin')
    );

-- geofences
DROP POLICY IF EXISTS admin_geofences ON geofences;
CREATE POLICY tenant_geofences ON geofences
    USING (
        operator_id = current_operator_id()
        OR auth.jwt() ->> 'role' = 'super_admin'
    );

-- operators table RLS (super_admin sees all; others see their own)
ALTER TABLE operators ENABLE ROW LEVEL SECURITY;
CREATE POLICY operators_read ON operators FOR SELECT
    USING (
        id = current_operator_id()
        OR auth.jwt() ->> 'role' = 'super_admin'
    );
CREATE POLICY operators_write ON operators FOR ALL
    USING (auth.jwt() ->> 'role' = 'super_admin');

-- ============================================================
-- 5. UPDATE upsert_vehicle_position TO INCLUDE operator_id
-- ============================================================

CREATE OR REPLACE FUNCTION upsert_vehicle_position(
    p_vehicle_id  UUID,
    p_lat         DOUBLE PRECISION,
    p_lon         DOUBLE PRECISION,
    p_speed       NUMERIC,
    p_heading     NUMERIC,
    p_source      TEXT,
    p_route_id    UUID    DEFAULT NULL,
    p_occupancy   INTEGER DEFAULT 0,
    p_operator_id UUID    DEFAULT NULL
) RETURNS void AS $$
DECLARE
    v_operator_id UUID;
BEGIN
    -- Resolve operator_id from the vehicle if not explicitly provided
    IF p_operator_id IS NOT NULL THEN
        v_operator_id := p_operator_id;
    ELSE
        SELECT operator_id INTO v_operator_id FROM vehicles WHERE id = p_vehicle_id;
    END IF;

    -- Insert into history
    INSERT INTO vehicle_positions (vehicle_id, operator_id, location, speed_kmh, heading, source, route_id, occupancy_pct)
    VALUES (
        p_vehicle_id,
        v_operator_id,
        ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326),
        p_speed,
        p_heading,
        p_source,
        p_route_id,
        p_occupancy
    );

    -- Upsert latest
    INSERT INTO vehicle_positions_latest (vehicle_id, operator_id, location, speed_kmh, heading, source, route_id, occupancy_pct, recorded_at)
    VALUES (
        p_vehicle_id,
        v_operator_id,
        ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326),
        p_speed,
        p_heading,
        p_source,
        p_route_id,
        p_occupancy,
        NOW()
    )
    ON CONFLICT (vehicle_id)
    DO UPDATE SET
        operator_id  = EXCLUDED.operator_id,
        location     = EXCLUDED.location,
        speed_kmh    = EXCLUDED.speed_kmh,
        heading      = EXCLUDED.heading,
        source       = EXCLUDED.source,
        route_id     = EXCLUDED.route_id,
        occupancy_pct = EXCLUDED.occupancy_pct,
        recorded_at  = NOW();
END;
$$ LANGUAGE plpgsql;

COMMIT;
