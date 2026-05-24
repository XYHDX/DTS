-- ============================================================
-- DamascusTransit Database Schema
-- PostgreSQL + PostGIS (Supabase compatible)
-- ============================================================

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- 0. OPERATORS
-- ============================================================

CREATE TABLE operators (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    name_ar TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 1. USERS & AUTH
-- ============================================================

CREATE TYPE user_role AS ENUM ('admin', 'dispatcher', 'driver', 'viewer');

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    full_name_ar TEXT,
    role user_role NOT NULL DEFAULT 'viewer',
    phone TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    operator_id UUID REFERENCES operators(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);

-- ============================================================
-- 2. ROUTES
-- ============================================================

CREATE TYPE route_type AS ENUM ('bus', 'microbus', 'taxi');

CREATE TABLE routes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    route_id TEXT UNIQUE NOT NULL,          -- e.g. "R001"
    name TEXT NOT NULL,                      -- e.g. "Marjeh → Mezzeh Highway"
    name_ar TEXT NOT NULL,                   -- e.g. "المرجة → طريق المزة السريع"
    route_type route_type NOT NULL DEFAULT 'bus',
    color TEXT NOT NULL DEFAULT '#428177',   -- hex color for map
    geometry GEOMETRY(LineString, 4326),     -- full route path
    distance_km NUMERIC(6,2),
    avg_duration_min INTEGER,
    fare_syp INTEGER,                        -- fare in Syrian Pounds
    is_active BOOLEAN NOT NULL DEFAULT true,
    operator_id UUID REFERENCES operators(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_routes_route_id ON routes(route_id);
CREATE INDEX idx_routes_type ON routes(route_type);
CREATE INDEX idx_routes_geometry ON routes USING GIST(geometry);

-- ============================================================
-- 3. STOPS
-- ============================================================

CREATE TABLE stops (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    stop_id TEXT UNIQUE NOT NULL,            -- e.g. "S001"
    name TEXT NOT NULL,
    name_ar TEXT NOT NULL,
    location GEOMETRY(Point, 4326) NOT NULL,
    address TEXT,
    address_ar TEXT,
    has_shelter BOOLEAN DEFAULT false,
    has_display BOOLEAN DEFAULT false,
    is_active BOOLEAN NOT NULL DEFAULT true,
    operator_id UUID REFERENCES operators(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stops_stop_id ON stops(stop_id);
CREATE INDEX idx_stops_location ON stops USING GIST(location);

-- ============================================================
-- 4. ROUTE-STOP RELATIONSHIPS
-- ============================================================

CREATE TABLE route_stops (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    route_id UUID NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
    stop_id UUID NOT NULL REFERENCES stops(id) ON DELETE CASCADE,
    stop_sequence INTEGER NOT NULL,
    distance_from_start_km NUMERIC(6,2),
    typical_arrival_offset_min INTEGER,      -- minutes from route start
    UNIQUE(route_id, stop_sequence)
);

CREATE INDEX idx_route_stops_route ON route_stops(route_id);
CREATE INDEX idx_route_stops_stop ON route_stops(stop_id);

-- ============================================================
-- 5. VEHICLES
-- ============================================================

CREATE TYPE vehicle_status AS ENUM ('active', 'idle', 'maintenance', 'decommissioned');

CREATE TABLE vehicles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vehicle_id TEXT UNIQUE NOT NULL,         -- license plate or fleet ID
    name TEXT NOT NULL,
    name_ar TEXT,
    vehicle_type route_type NOT NULL DEFAULT 'bus',
    capacity INTEGER NOT NULL DEFAULT 40,
    status vehicle_status NOT NULL DEFAULT 'idle',
    assigned_route_id UUID REFERENCES routes(id),
    assigned_driver_id UUID REFERENCES users(id),
    gps_device_id TEXT,                      -- Traccar device ID
    gps_device_type TEXT,                    -- e.g. "FMC650", "OsmAnd"
    is_real_gps BOOLEAN NOT NULL DEFAULT false,
    is_active BOOLEAN NOT NULL DEFAULT true,
    operator_id UUID REFERENCES operators(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_vehicles_vehicle_id ON vehicles(vehicle_id);
CREATE INDEX idx_vehicles_status ON vehicles(status);
CREATE INDEX idx_vehicles_route ON vehicles(assigned_route_id);
CREATE INDEX idx_vehicles_gps ON vehicles(gps_device_id);

-- ============================================================
-- 6. VEHICLE POSITIONS (Time-series)
-- ============================================================

CREATE TABLE vehicle_positions (
    id BIGSERIAL PRIMARY KEY,
    vehicle_id UUID NOT NULL REFERENCES vehicles(id),
    location GEOMETRY(Point, 4326) NOT NULL,
    speed_kmh NUMERIC(5,1) DEFAULT 0,
    heading NUMERIC(5,1) DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'simulator',  -- 'simulator', 'traccar', 'osmand'
    route_id UUID REFERENCES routes(id),
    occupancy_pct INTEGER DEFAULT 0,
    operator_id UUID REFERENCES operators(id),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_positions_vehicle ON vehicle_positions(vehicle_id);
CREATE INDEX idx_positions_time ON vehicle_positions(recorded_at DESC);
CREATE INDEX idx_positions_location ON vehicle_positions USING GIST(location);
CREATE INDEX idx_positions_source ON vehicle_positions(source);

-- Partition hint: for production with high throughput,
-- convert to a TimescaleDB hypertable:
-- SELECT create_hypertable('vehicle_positions', 'recorded_at');

-- ============================================================
-- 7. LATEST POSITIONS (Materialized view for fast queries)
-- ============================================================

CREATE TABLE vehicle_positions_latest (
    vehicle_id UUID PRIMARY KEY REFERENCES vehicles(id),
    location GEOMETRY(Point, 4326) NOT NULL,
    speed_kmh NUMERIC(5,1) DEFAULT 0,
    heading NUMERIC(5,1) DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'simulator',
    route_id UUID REFERENCES routes(id),
    occupancy_pct INTEGER DEFAULT 0,
    operator_id UUID REFERENCES operators(id),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_latest_location ON vehicle_positions_latest USING GIST(location);

-- ============================================================
-- 8. TRIP LOGS
-- ============================================================

CREATE TYPE trip_status AS ENUM ('scheduled', 'in_progress', 'completed', 'cancelled');

CREATE TABLE trips (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vehicle_id UUID NOT NULL REFERENCES vehicles(id),
    route_id UUID NOT NULL REFERENCES routes(id),
    driver_id UUID REFERENCES users(id),
    status trip_status NOT NULL DEFAULT 'scheduled',
    scheduled_start TIMESTAMPTZ,
    actual_start TIMESTAMPTZ,
    actual_end TIMESTAMPTZ,
    passenger_count INTEGER DEFAULT 0,
    distance_km NUMERIC(6,2),
    on_time_pct NUMERIC(5,2),
    notes TEXT,
    operator_id UUID REFERENCES operators(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_trips_vehicle ON trips(vehicle_id);
CREATE INDEX idx_trips_route ON trips(route_id);
CREATE INDEX idx_trips_status ON trips(status);
CREATE INDEX idx_trips_time ON trips(actual_start DESC);

-- ============================================================
-- 9. ALERTS & EVENTS
-- ============================================================

CREATE TYPE alert_severity AS ENUM ('info', 'warning', 'critical');
CREATE TYPE alert_type AS ENUM (
    'speed_violation', 'route_deviation', 'geofence_exit',
    'breakdown', 'delay', 'sos', 'maintenance_due', 'connection_lost'
);

CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vehicle_id UUID REFERENCES vehicles(id),
    alert_type alert_type NOT NULL,
    severity alert_severity NOT NULL DEFAULT 'info',
    title TEXT NOT NULL,
    title_ar TEXT,
    description TEXT,
    location GEOMETRY(Point, 4326),
    is_resolved BOOLEAN NOT NULL DEFAULT false,
    resolved_by UUID REFERENCES users(id),
    resolved_at TIMESTAMPTZ,
    operator_id UUID REFERENCES operators(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_alerts_vehicle ON alerts(vehicle_id);
CREATE INDEX idx_alerts_type ON alerts(alert_type);
CREATE INDEX idx_alerts_unresolved ON alerts(is_resolved) WHERE is_resolved = false;
CREATE INDEX idx_alerts_time ON alerts(created_at DESC);

-- ============================================================
-- 10. GEOFENCES
-- ============================================================

CREATE TABLE geofences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    name_ar TEXT,
    geometry GEOMETRY(Polygon, 4326) NOT NULL,
    geofence_type TEXT NOT NULL DEFAULT 'zone',  -- 'zone', 'depot', 'terminal'
    speed_limit_kmh INTEGER,
    is_active BOOLEAN NOT NULL DEFAULT true,
    operator_id UUID REFERENCES operators(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_geofences_geometry ON geofences USING GIST(geometry);

-- ============================================================
-- 11. SCHEDULES
-- ============================================================

CREATE TABLE schedules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    route_id UUID NOT NULL REFERENCES routes(id),
    day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    first_departure TIME NOT NULL,
    last_departure TIME NOT NULL,
    frequency_min INTEGER NOT NULL DEFAULT 15,
    is_active BOOLEAN NOT NULL DEFAULT true,
    operator_id UUID REFERENCES operators(id)
);

CREATE INDEX idx_schedules_route ON schedules(route_id);
CREATE INDEX idx_schedules_day ON schedules(day_of_week);

-- ============================================================
-- 12. AUDIT LOG
-- ============================================================

CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id UUID,
    details JSONB,
    ip_address TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_user ON audit_log(user_id);
CREATE INDEX idx_audit_time ON audit_log(created_at DESC);

-- ============================================================
-- 13. ROW-LEVEL SECURITY (Supabase)
-- ============================================================

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE vehicles ENABLE ROW LEVEL SECURITY;
ALTER TABLE vehicle_positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE trips ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
-- CRIT-4 fix: enable RLS on tables previously missing it
ALTER TABLE routes ENABLE ROW LEVEL SECURITY;
ALTER TABLE stops ENABLE ROW LEVEL SECURITY;
ALTER TABLE route_stops ENABLE ROW LEVEL SECURITY;
ALTER TABLE schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE geofences ENABLE ROW LEVEL SECURITY;
ALTER TABLE vehicle_positions_latest ENABLE ROW LEVEL SECURITY;
ALTER TABLE operators ENABLE ROW LEVEL SECURITY;

CREATE POLICY public_read_operators ON operators FOR SELECT USING (true);
CREATE POLICY admin_write_operators ON operators FOR ALL USING (auth.jwt() ->> 'role' = 'super_admin');

-- Admins can do everything
CREATE POLICY admin_all ON users FOR ALL
    USING (auth.jwt() ->> 'role' = 'admin');

CREATE POLICY admin_vehicles ON vehicles FOR ALL
    USING (auth.jwt() ->> 'role' IN ('admin', 'dispatcher'));

-- Viewers can read routes, stops, positions (public read-only)
CREATE POLICY public_read_routes ON routes FOR SELECT USING (true);
CREATE POLICY admin_write_routes ON routes FOR ALL
    USING (auth.jwt() ->> 'role' = 'admin');

CREATE POLICY public_read_stops ON stops FOR SELECT USING (true);
CREATE POLICY admin_write_stops ON stops FOR ALL
    USING (auth.jwt() ->> 'role' = 'admin');

CREATE POLICY public_read_route_stops ON route_stops FOR SELECT USING (true);
CREATE POLICY admin_write_route_stops ON route_stops FOR ALL
    USING (auth.jwt() ->> 'role' = 'admin');

CREATE POLICY public_read_schedules ON schedules FOR SELECT USING (true);
CREATE POLICY admin_write_schedules ON schedules FOR ALL
    USING (auth.jwt() ->> 'role' = 'admin');

-- Geofences: admin-only read and write
CREATE POLICY admin_geofences ON geofences FOR ALL
    USING (auth.jwt() ->> 'role' = 'admin');

-- Positions: anyone can read latest, writes are admin/service only
CREATE POLICY public_read_positions ON vehicle_positions_latest FOR SELECT USING (true);
CREATE POLICY admin_write_positions ON vehicle_positions_latest FOR ALL
    USING (auth.jwt() ->> 'role' IN ('admin', 'dispatcher'));

-- ============================================================
-- 14. FUNCTIONS
-- ============================================================

-- Update latest position (upsert)
CREATE OR REPLACE FUNCTION upsert_vehicle_position(
    p_vehicle_id UUID,
    p_lat DOUBLE PRECISION,
    p_lon DOUBLE PRECISION,
    p_speed NUMERIC,
    p_heading NUMERIC,
    p_source TEXT,
    p_route_id UUID DEFAULT NULL,
    p_occupancy INTEGER DEFAULT 0
) RETURNS void AS $$
DECLARE
    v_operator_id UUID;
BEGIN
    SELECT operator_id INTO v_operator_id FROM vehicles WHERE id = p_vehicle_id;

    -- Insert into history
    INSERT INTO vehicle_positions (vehicle_id, location, speed_kmh, heading, source, route_id, occupancy_pct, operator_id)
    VALUES (p_vehicle_id, ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326), p_speed, p_heading, p_source, p_route_id, p_occupancy, v_operator_id);

    -- Upsert latest
    INSERT INTO vehicle_positions_latest (vehicle_id, location, speed_kmh, heading, source, route_id, occupancy_pct, operator_id, recorded_at)
    VALUES (p_vehicle_id, ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326), p_speed, p_heading, p_source, p_route_id, p_occupancy, v_operator_id, NOW())
    ON CONFLICT (vehicle_id)
    DO UPDATE SET
        location = EXCLUDED.location,
        speed_kmh = EXCLUDED.speed_kmh,
        heading = EXCLUDED.heading,
        source = EXCLUDED.source,
        route_id = EXCLUDED.route_id,
        occupancy_pct = EXCLUDED.occupancy_pct,
        operator_id = EXCLUDED.operator_id,
        recorded_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- Find nearest stops
CREATE OR REPLACE FUNCTION find_nearest_stops(
    p_lat DOUBLE PRECISION,
    p_lon DOUBLE PRECISION,
    p_limit INTEGER DEFAULT 5,
    p_radius_m INTEGER DEFAULT 1000
) RETURNS TABLE (
    stop_id TEXT,
    name TEXT,
    name_ar TEXT,
    distance_m DOUBLE PRECISION,
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        s.stop_id,
        s.name,
        s.name_ar,
        ST_Distance(s.location::geography, ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326)::geography) AS distance_m,
        ST_Y(s.location) AS lat,
        ST_X(s.location) AS lon
    FROM stops s
    WHERE s.is_active = true
      AND ST_DWithin(s.location::geography, ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326)::geography, p_radius_m)
    ORDER BY distance_m
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Vehicle ETA to a stop
CREATE OR REPLACE FUNCTION estimate_arrival(
    p_vehicle_id UUID,
    p_stop_id UUID
) RETURNS INTEGER AS $$
DECLARE
    v_speed NUMERIC;
    v_distance NUMERIC;
BEGIN
    SELECT vpl.speed_kmh, ST_Distance(vpl.location::geography, s.location::geography) / 1000.0
    INTO v_speed, v_distance
    FROM vehicle_positions_latest vpl, stops s
    WHERE vpl.vehicle_id = p_vehicle_id AND s.id = p_stop_id;

    IF v_speed IS NULL OR v_speed < 1 THEN
        v_speed := 20; -- default avg speed in Damascus
    END IF;

    RETURN CEIL((v_distance / v_speed) * 60); -- minutes
END;
$$ LANGUAGE plpgsql;

-- Return all geofences with geometry as GeoJSON
CREATE OR REPLACE FUNCTION get_geofences()
RETURNS TABLE (
    id UUID,
    name TEXT,
    name_ar TEXT,
    geometry JSON,
    geofence_type TEXT,
    speed_limit_kmh INTEGER,
    is_active BOOLEAN,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        g.id,
        g.name,
        g.name_ar,
        ST_AsGeoJSON(g.geometry)::JSON AS geometry,
        g.geofence_type,
        g.speed_limit_kmh,
        g.is_active,
        g.created_at
    FROM geofences g
    ORDER BY g.created_at DESC;
END;
$$ LANGUAGE plpgsql;

-- Create a geofence from a GeoJSON polygon string
CREATE OR REPLACE FUNCTION create_geofence(
    p_name TEXT,
    p_name_ar TEXT,
    p_geojson TEXT,
    p_geofence_type TEXT DEFAULT 'zone',
    p_speed_limit INTEGER DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    v_id UUID;
BEGIN
    INSERT INTO geofences (name, name_ar, geometry, geofence_type, speed_limit_kmh)
    VALUES (
        p_name,
        p_name_ar,
        ST_GeomFromGeoJSON(p_geojson),
        p_geofence_type,
        p_speed_limit
    )
    RETURNING id INTO v_id;
    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

-- Return geofences a vehicle just exited (was inside before, now outside)
CREATE OR REPLACE FUNCTION check_geofence_exit(
    p_vehicle_id UUID,
    p_new_lat DOUBLE PRECISION,
    p_new_lon DOUBLE PRECISION
) RETURNS TABLE (
    geofence_id UUID,
    geofence_name TEXT,
    geofence_name_ar TEXT
) AS $$
DECLARE
    v_new_point GEOMETRY;
    v_prev_point GEOMETRY;
BEGIN
    v_new_point := ST_SetSRID(ST_MakePoint(p_new_lon, p_new_lat), 4326);

    SELECT location INTO v_prev_point
    FROM vehicle_positions_latest
    WHERE vehicle_id = p_vehicle_id;

    IF v_prev_point IS NULL THEN
        RETURN;
    END IF;

    RETURN QUERY
    SELECT g.id, g.name, g.name_ar
    FROM geofences g
    WHERE g.is_active = true
      AND ST_Contains(g.geometry, v_prev_point)
      AND NOT ST_Contains(g.geometry, v_new_point);
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 15. REALTIME (Supabase)
-- ============================================================

-- Enable realtime on the latest positions table
-- Run in Supabase SQL editor:
-- ALTER PUBLICATION supabase_realtime ADD TABLE vehicle_positions_latest;
-- ALTER PUBLICATION supabase_realtime ADD TABLE alerts;
