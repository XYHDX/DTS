-- ============================================================
-- Damascus Transit System — Supabase bootstrap
-- ============================================================
-- Paste this entire file into Supabase SQL Editor (one-time setup).
-- Safe to re-run: all statements are idempotent (IF NOT EXISTS / ON CONFLICT).
--
-- After running this:
--   • Schema is created in the default `public` schema
--   • One operator (damascus) + 4 demo users seeded
--   • 4 demo routes, 12 demo stops, 6 demo vehicles seeded
--   • A verification query at the bottom prints row counts
--
-- Demo login (all 4 accounts use the SAME password): damascus2025
--   admin@damascus-transit.demo      → /admin/
--   operator@damascus-transit.demo   → /admin/  (dispatcher)
--   driver@damascus-transit.demo     → /driver/
--   passenger@damascus-transit.demo  → /passenger/
-- ============================================================

-- ---------- 1. EXTENSIONS ----------
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------- 2. ENUMS ----------
DO $$ BEGIN
  CREATE TYPE user_role     AS ENUM ('admin', 'dispatcher', 'driver', 'viewer');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE route_type    AS ENUM ('bus', 'microbus', 'taxi');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE vehicle_status AS ENUM ('active', 'idle', 'maintenance', 'decommissioned');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE trip_status   AS ENUM ('scheduled', 'in_progress', 'completed', 'cancelled');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE alert_severity AS ENUM ('info', 'warning', 'critical');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE alert_type    AS ENUM (
    'speed_violation', 'route_deviation', 'geofence_exit',
    'breakdown', 'delay', 'sos', 'maintenance_due', 'connection_lost'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ---------- 3. CORE TABLES ----------
CREATE TABLE IF NOT EXISTS operators (
  id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  slug       TEXT UNIQUE NOT NULL,
  name       TEXT NOT NULL,
  name_ar    TEXT,
  is_active  BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  email         TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  full_name     TEXT NOT NULL,
  full_name_ar  TEXT,
  role          user_role NOT NULL DEFAULT 'viewer',
  phone         TEXT,
  is_active     BOOLEAN NOT NULL DEFAULT true,
  operator_id   UUID REFERENCES operators(id),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role  ON users(role);

CREATE TABLE IF NOT EXISTS routes (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  route_id        TEXT UNIQUE NOT NULL,
  name            TEXT NOT NULL,
  name_ar         TEXT NOT NULL,
  route_type      route_type NOT NULL DEFAULT 'bus',
  color           TEXT NOT NULL DEFAULT '#0E5650',
  geometry        GEOMETRY(LineString, 4326),
  distance_km     NUMERIC(6,2),
  avg_duration_min INTEGER,
  fare_syp        INTEGER,
  is_active       BOOLEAN NOT NULL DEFAULT true,
  operator_id     UUID REFERENCES operators(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_routes_route_id ON routes(route_id);
CREATE INDEX IF NOT EXISTS idx_routes_geometry ON routes USING GIST(geometry);

CREATE TABLE IF NOT EXISTS stops (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  stop_id     TEXT UNIQUE NOT NULL,
  name        TEXT NOT NULL,
  name_ar     TEXT NOT NULL,
  location    GEOMETRY(Point, 4326) NOT NULL,
  has_shelter BOOLEAN DEFAULT false,
  is_active   BOOLEAN NOT NULL DEFAULT true,
  operator_id UUID REFERENCES operators(id),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_stops_stop_id  ON stops(stop_id);
CREATE INDEX IF NOT EXISTS idx_stops_location ON stops USING GIST(location);

CREATE TABLE IF NOT EXISTS route_stops (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  route_id      UUID NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
  stop_id       UUID NOT NULL REFERENCES stops(id)  ON DELETE CASCADE,
  stop_sequence INTEGER NOT NULL,
  UNIQUE(route_id, stop_sequence)
);

CREATE TABLE IF NOT EXISTS vehicles (
  id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  vehicle_id         TEXT UNIQUE NOT NULL,
  name               TEXT NOT NULL,
  name_ar            TEXT,
  vehicle_type       route_type NOT NULL DEFAULT 'bus',
  capacity           INTEGER NOT NULL DEFAULT 40,
  status             vehicle_status NOT NULL DEFAULT 'idle',
  assigned_route_id  UUID REFERENCES routes(id),
  assigned_driver_id UUID REFERENCES users(id),
  gps_device_id      TEXT,
  is_real_gps        BOOLEAN NOT NULL DEFAULT false,
  is_active          BOOLEAN NOT NULL DEFAULT true,
  operator_id        UUID REFERENCES operators(id),
  created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_vehicles_vehicle_id ON vehicles(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_vehicles_status     ON vehicles(status);

CREATE TABLE IF NOT EXISTS vehicle_positions (
  id            BIGSERIAL PRIMARY KEY,
  vehicle_id    UUID NOT NULL REFERENCES vehicles(id),
  location      GEOMETRY(Point, 4326) NOT NULL,
  speed_kmh     NUMERIC(5,1) DEFAULT 0,
  heading       NUMERIC(5,1) DEFAULT 0,
  source        TEXT NOT NULL DEFAULT 'simulator',
  route_id      UUID REFERENCES routes(id),
  occupancy_pct INTEGER DEFAULT 0,
  operator_id   UUID REFERENCES operators(id),
  recorded_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  received_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_positions_vehicle  ON vehicle_positions(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_positions_time     ON vehicle_positions(recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_positions_location ON vehicle_positions USING GIST(location);

CREATE TABLE IF NOT EXISTS vehicle_positions_latest (
  vehicle_id    UUID PRIMARY KEY REFERENCES vehicles(id),
  location      GEOMETRY(Point, 4326) NOT NULL,
  speed_kmh     NUMERIC(5,1) DEFAULT 0,
  heading       NUMERIC(5,1) DEFAULT 0,
  source        TEXT NOT NULL DEFAULT 'simulator',
  route_id      UUID REFERENCES routes(id),
  occupancy_pct INTEGER DEFAULT 0,
  operator_id   UUID REFERENCES operators(id),
  recorded_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_latest_location ON vehicle_positions_latest USING GIST(location);

CREATE TABLE IF NOT EXISTS trips (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  vehicle_id      UUID NOT NULL REFERENCES vehicles(id),
  route_id        UUID NOT NULL REFERENCES routes(id),
  driver_id       UUID REFERENCES users(id),
  status          trip_status NOT NULL DEFAULT 'scheduled',
  scheduled_start TIMESTAMPTZ,
  actual_start    TIMESTAMPTZ,
  actual_end      TIMESTAMPTZ,
  passenger_count INTEGER DEFAULT 0,
  distance_km     NUMERIC(6,2),
  operator_id     UUID REFERENCES operators(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alerts (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  vehicle_id  UUID REFERENCES vehicles(id),
  alert_type  alert_type NOT NULL,
  severity    alert_severity NOT NULL DEFAULT 'info',
  title       TEXT NOT NULL,
  title_ar    TEXT,
  description TEXT,
  location    GEOMETRY(Point, 4326),
  is_resolved BOOLEAN NOT NULL DEFAULT false,
  resolved_by UUID REFERENCES users(id),
  resolved_at TIMESTAMPTZ,
  operator_id UUID REFERENCES operators(id),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_alerts_unresolved ON alerts(is_resolved) WHERE is_resolved = false;

-- ============================================================
-- 4. SEED — operator
-- ============================================================
INSERT INTO operators (id, slug, name, name_ar, is_active) VALUES
  ('00000000-0000-0000-0000-000000000001', 'damascus',
   'Damascus Transit Authority', 'هيئة نقل دمشق', true)
ON CONFLICT (slug) DO UPDATE SET is_active = true;

-- ============================================================
-- 5. SEED — demo users (password = damascus2025 for all)
-- bcrypt hash of "damascus2025"
-- ============================================================
INSERT INTO users (email, password_hash, full_name, full_name_ar, role, phone, operator_id, is_active) VALUES
  ('admin@damascus-transit.demo',
   '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.',
   'Demo Admin', 'مدير تجريبي', 'admin', '+963900000001',
   '00000000-0000-0000-0000-000000000001', true),

  ('operator@damascus-transit.demo',
   '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.',
   'Demo Operator', 'مشغّل تجريبي', 'dispatcher', '+963900000002',
   '00000000-0000-0000-0000-000000000001', true),

  ('driver@damascus-transit.demo',
   '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.',
   'Demo Driver', 'سائق تجريبي', 'driver', '+963900000003',
   '00000000-0000-0000-0000-000000000001', true),

  ('passenger@damascus-transit.demo',
   '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.',
   'Demo Passenger', 'راكب تجريبي', 'viewer', '+963900000004',
   '00000000-0000-0000-0000-000000000001', true)
ON CONFLICT (email) DO NOTHING;

-- ============================================================
-- 6. SEED — 12 Damascus stops
-- ============================================================
INSERT INTO stops (stop_id, name, name_ar, location, has_shelter, operator_id) VALUES
  ('S001', 'Marjeh Square',       'ساحة المرجة',        ST_SetSRID(ST_MakePoint(36.3025, 33.5105), 4326), true,  '00000000-0000-0000-0000-000000000001'),
  ('S002', 'Hamidiyeh Souq',      'سوق الحميدية',       ST_SetSRID(ST_MakePoint(36.3065, 33.5115), 4326), true,  '00000000-0000-0000-0000-000000000001'),
  ('S003', 'Umayyad Square',      'ساحة الأمويين',      ST_SetSRID(ST_MakePoint(36.2920, 33.5130), 4326), true,  '00000000-0000-0000-0000-000000000001'),
  ('S004', 'Baramkeh',            'البرامكة',           ST_SetSRID(ST_MakePoint(36.2940, 33.5060), 4326), true,  '00000000-0000-0000-0000-000000000001'),
  ('S005', 'Mezzeh Highway',      'أوتوستراد المزة',    ST_SetSRID(ST_MakePoint(36.2600, 33.5050), 4326), true,  '00000000-0000-0000-0000-000000000001'),
  ('S006', 'Kafar Souseh',        'كفرسوسة',            ST_SetSRID(ST_MakePoint(36.2750, 33.5020), 4326), true,  '00000000-0000-0000-0000-000000000001'),
  ('S007', 'Abu Rummaneh',        'أبو رمانة',          ST_SetSRID(ST_MakePoint(36.2850, 33.5160), 4326), true,  '00000000-0000-0000-0000-000000000001'),
  ('S008', 'Damascus University', 'جامعة دمشق',         ST_SetSRID(ST_MakePoint(36.2880, 33.5130), 4326), true,  '00000000-0000-0000-0000-000000000001'),
  ('S009', 'Abbasiyyin Square',   'ساحة العباسيين',     ST_SetSRID(ST_MakePoint(36.3200, 33.5175), 4326), true,  '00000000-0000-0000-0000-000000000001'),
  ('S010', 'Bab Tuma',            'باب توما',           ST_SetSRID(ST_MakePoint(36.3160, 33.5145), 4326), false, '00000000-0000-0000-0000-000000000001'),
  ('S011', 'Mazzeh 86',           'مزة ٨٦',             ST_SetSRID(ST_MakePoint(36.2450, 33.5010), 4326), false, '00000000-0000-0000-0000-000000000001'),
  ('S012', 'Jaramana',            'جرمانا',             ST_SetSRID(ST_MakePoint(36.3530, 33.4870), 4326), true,  '00000000-0000-0000-0000-000000000001')
ON CONFLICT (stop_id) DO NOTHING;

-- ============================================================
-- 7. SEED — 4 routes
-- ============================================================
INSERT INTO routes (route_id, name, name_ar, route_type, color, distance_km, avg_duration_min, fare_syp, operator_id) VALUES
  ('R101', 'Marjeh → Mezzeh Highway', 'المرجة → أوتوستراد المزة',          'bus',      8.4,  35, 500, '00000000-0000-0000-0000-000000000001'),
  ('R102', 'Umayyad Square → Jaramana','ساحة الأمويين → جرمانا',          'bus',      9.1,  40, 500, '00000000-0000-0000-0000-000000000001'),
  ('R201', 'Damascus Univ. → Abbasiyyin','جامعة دمشق → العباسيين',         'microbus', 6.2,  25, 300, '00000000-0000-0000-0000-000000000001'),
  ('R202', 'Bab Tuma → Kafar Souseh', 'باب توما → كفرسوسة',                'microbus', 5.8,  22, 300, '00000000-0000-0000-0000-000000000001')
ON CONFLICT (route_id) DO NOTHING;

-- ============================================================
-- 8. SEED — 6 vehicles (4 active, 2 idle), assigned to drivers
-- ============================================================
WITH demo_driver AS (SELECT id FROM users WHERE email = 'driver@damascus-transit.demo' LIMIT 1),
     route_r101  AS (SELECT id FROM routes WHERE route_id = 'R101' LIMIT 1),
     route_r102  AS (SELECT id FROM routes WHERE route_id = 'R102' LIMIT 1),
     route_r201  AS (SELECT id FROM routes WHERE route_id = 'R201' LIMIT 1),
     route_r202  AS (SELECT id FROM routes WHERE route_id = 'R202' LIMIT 1)
INSERT INTO vehicles (vehicle_id, name, name_ar, vehicle_type, capacity, status, assigned_route_id, assigned_driver_id, operator_id) VALUES
  ('B-101', 'Bus 101', 'الحافلة ١٠١', 'bus',      60, 'active', (SELECT id FROM route_r101), (SELECT id FROM demo_driver), '00000000-0000-0000-0000-000000000001'),
  ('B-102', 'Bus 102', 'الحافلة ١٠٢', 'bus',      60, 'active', (SELECT id FROM route_r102), NULL,                          '00000000-0000-0000-0000-000000000001'),
  ('M-201', 'Microbus 201', 'ميكروباص ٢٠١', 'microbus', 20, 'active', (SELECT id FROM route_r201), NULL,                    '00000000-0000-0000-0000-000000000001'),
  ('M-202', 'Microbus 202', 'ميكروباص ٢٠٢', 'microbus', 20, 'active', (SELECT id FROM route_r202), NULL,                    '00000000-0000-0000-0000-000000000001'),
  ('B-103', 'Bus 103', 'الحافلة ١٠٣', 'bus',      60, 'idle',   NULL,                                NULL,                  '00000000-0000-0000-0000-000000000001'),
  ('M-203', 'Microbus 203', 'ميكروباص ٢٠٣', 'microbus', 20, 'idle', NULL,                            NULL,                  '00000000-0000-0000-0000-000000000001')
ON CONFLICT (vehicle_id) DO NOTHING;

-- ============================================================
-- 9. SEED — initial positions so the live map shows something
-- ============================================================
INSERT INTO vehicle_positions_latest (vehicle_id, location, speed_kmh, heading, source, route_id, occupancy_pct, operator_id, recorded_at)
SELECT v.id,
       ST_SetSRID(ST_MakePoint(36.295 + (random()*0.04 - 0.02), 33.510 + (random()*0.04 - 0.02)), 4326),
       (10 + random()*40)::numeric(5,1),
       (random()*360)::numeric(5,1),
       'simulator',
       v.assigned_route_id,
       (20 + random()*60)::int,
       v.operator_id,
       NOW()
FROM vehicles v
WHERE v.status = 'active'
ON CONFLICT (vehicle_id) DO UPDATE SET
  location    = EXCLUDED.location,
  speed_kmh   = EXCLUDED.speed_kmh,
  heading     = EXCLUDED.heading,
  recorded_at = EXCLUDED.recorded_at;

-- ============================================================
-- 10. VERIFICATION — should print one row with all counts
-- ============================================================
SELECT
  (SELECT count(*) FROM operators)                AS operators,
  (SELECT count(*) FROM users)                    AS users,
  (SELECT count(*) FROM routes)                   AS routes,
  (SELECT count(*) FROM stops)                    AS stops,
  (SELECT count(*) FROM vehicles)                 AS vehicles,
  (SELECT count(*) FROM vehicles WHERE status='active') AS active_vehicles,
  (SELECT count(*) FROM vehicle_positions_latest) AS positions_latest;
