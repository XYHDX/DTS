-- ============================================================
-- DamascusTransit — DEMO SEED (accounts + a testable fleet)
-- ============================================================
-- Run this in the Supabase SQL editor (it runs as the service role,
-- so it bypasses RLS). Safe to re-run, and SAFE EVEN IF some of this
-- data already exists: every parent row is matched by its natural
-- business key (email / route_id / stop_id / vehicle_id) and every
-- foreign key is resolved by sub-query against that key — never by a
-- hard-coded UUID. So pre-existing stops/routes/vehicles are reused
-- instead of colliding.
--
--   ┌──────────────────────────────────┬───────────┬────────────┐
--   │  ALL DEMO ACCOUNTS — PASSWORD: Damascus2026!               │
--   ├──────────────────────────────────┼───────────┼────────────┤
--   │ Email                            │ Role      │ Login tab   │
--   ├──────────────────────────────────┼───────────┼────────────┤
--   │ admin@damascus-transit.demo      │ admin       │ إدارة (Admin)   │
--   │ operator@damascus-transit.demo   │ dispatcher  │ موزّع (Operator)│
--   │ driver@damascus-transit.demo     │ driver      │ سائق (Driver)  │
--   │ driver2@damascus-transit.demo    │ driver      │ سائق           │
--   │ passenger@damascus-transit.demo  │ viewer      │ (passenger app)│
--   └──────────────────────────────────┴───────────┴────────────┘
--
--   super_admin is OPTIONAL (your user_role enum may not include it yet)
--   — see the block at the very bottom of this file.
--
--   ⚠ DEMO credentials. Rotate or delete them before production
--     (a "Clean-up" block is at the bottom).
-- ============================================================

BEGIN;

-- ── 1. Operator (well-known fixed UUID — matches the app's default) ─
INSERT INTO public.operators (id, slug, name, name_ar, is_active)
VALUES ('00000000-0000-0000-0000-000000000001',
        'damascus', 'Damascus Transit Authority', 'هيئة نقل دمشق', true)
ON CONFLICT (slug) DO NOTHING;

-- ── 2. Demo users (password for ALL: Damascus2026!) ────────────────
-- Distinct bcrypt hash per account (same password, different salt).
INSERT INTO public.users
  (email, password_hash, full_name, full_name_ar, role, phone, is_active, operator_id)
VALUES
  ('admin@damascus-transit.demo',
   '$2b$12$HpbfV7OnWCfrsLxLp8UiZO4Rc0BNiCUPrf56PF0vSaQTGnbS7PafK',
   'Damascus Admin', 'مدير دمشق', 'admin', '+963900000002', true,
   (SELECT id FROM public.operators WHERE slug='damascus')),
  ('operator@damascus-transit.demo',
   '$2b$12$Q7hJksvGrI1.N/iI/38vL.IaT7jRdtqIgX2./NpebcIRrOdas1I2S',
   'Fleet Operator', 'مشغّل الأسطول', 'dispatcher', '+963900000003', true,
   (SELECT id FROM public.operators WHERE slug='damascus')),
  ('driver@damascus-transit.demo',
   '$2b$12$M.p/tkNKxnl38YzWkElLxuZ3p1rSbj3G.QTNLM1DQo9Fz.RaGXyKy',
   'Ahmad Khalil', 'أحمد خليل', 'driver', '+963900000004', true,
   (SELECT id FROM public.operators WHERE slug='damascus')),
  ('driver2@damascus-transit.demo',
   '$2b$12$VkbIGspNV2Si./.WvVdjoO3XsOhh7syEshukCj3XThthyPjYnQD6K',
   'Samer Haddad', 'سامر حداد', 'driver', '+963900000005', true,
   (SELECT id FROM public.operators WHERE slug='damascus')),
  ('passenger@damascus-transit.demo',
   '$2b$12$pD32ASlAmQFiCfMoh8rFFOQaL5UqEev5.FA9zbhyCPqlbxJOWwwWS',
   'Passenger Demo', 'راكب تجريبي', 'viewer', '+963900000006', true,
   (SELECT id FROM public.operators WHERE slug='damascus'))
ON CONFLICT (email) DO NOTHING;

-- ── 3. Routes ──────────────────────────────────────────────────────
INSERT INTO public.routes
  (route_id, name, name_ar, route_type, color, distance_km, avg_duration_min, fare_syp, is_active, operator_id)
VALUES
  ('R001', 'Marjeh → Mezzeh', 'المرجة → المزة', 'bus', '#0E5650', 8.4, 35, 2000, true,
   (SELECT id FROM public.operators WHERE slug='damascus')),
  ('M014', 'Umayyad Sq → Baramkeh', 'الأمويين → البرامكة', 'microbus', '#C9A95B', 5.1, 22, 3500, true,
   (SELECT id FROM public.operators WHERE slug='damascus')),
  ('T100', 'Bab Touma → Qasioun', 'باب توما → قاسيون', 'taxi', '#CE1126', 6.7, 18, 10000, true,
   (SELECT id FROM public.operators WHERE slug='damascus'))
ON CONFLICT (route_id) DO NOTHING;

-- ── 4. Stops (PostGIS Point geometry, lon/lat WGS84) ───────────────
INSERT INTO public.stops (stop_id, name, name_ar, location, has_shelter, is_active, operator_id)
VALUES
  ('S001', 'Marjeh Square', 'ساحة المرجة',   ST_SetSRID(ST_MakePoint(36.3060, 33.5138), 4326), true,  true, (SELECT id FROM public.operators WHERE slug='damascus')),
  ('S002', 'Baramkeh',      'البرامكة',       ST_SetSRID(ST_MakePoint(36.2870, 33.5090), 4326), true,  true, (SELECT id FROM public.operators WHERE slug='damascus')),
  ('S003', 'Mezzeh',        'المزة',          ST_SetSRID(ST_MakePoint(36.2400, 33.5020), 4326), false, true, (SELECT id FROM public.operators WHERE slug='damascus')),
  ('S004', 'Umayyad Square','ساحة الأمويين',  ST_SetSRID(ST_MakePoint(36.2760, 33.5180), 4326), true,  true, (SELECT id FROM public.operators WHERE slug='damascus')),
  ('S005', 'Bab Touma',     'باب توما',        ST_SetSRID(ST_MakePoint(36.3180, 33.5125), 4326), false, true, (SELECT id FROM public.operators WHERE slug='damascus')),
  ('S006', 'Qasioun',       'قاسيون',          ST_SetSRID(ST_MakePoint(36.2790, 33.5320), 4326), false, true, (SELECT id FROM public.operators WHERE slug='damascus'))
ON CONFLICT (stop_id) DO NOTHING;

-- ── 5. Route ⇄ stop ordering (FKs resolved by business key) ────────
INSERT INTO public.route_stops (route_id, stop_id, stop_sequence)
SELECT r.id, s.id, v.seq
FROM (VALUES
        ('R001','S001',1), ('R001','S002',2), ('R001','S003',3),
        ('M014','S004',1), ('M014','S002',2),
        ('T100','S005',1), ('T100','S006',2)
     ) AS v(rcode, scode, seq)
JOIN public.routes r ON r.route_id = v.rcode
JOIN public.stops  s ON s.stop_id  = v.scode
WHERE NOT EXISTS (
  SELECT 1 FROM public.route_stops rs WHERE rs.route_id = r.id AND rs.stop_id = s.id
);

-- ── 6. Vehicles (driver@ bound to BUS-101 on R001) ─────────────────
INSERT INTO public.vehicles
  (vehicle_id, name, name_ar, vehicle_type, capacity, status,
   assigned_route_id, assigned_driver_id, gps_device_id, is_real_gps, is_active, operator_id)
VALUES
  ('BUS-101', 'Bus 101', 'الحافلة ١٠١', 'bus', 50, 'active',
   (SELECT id FROM public.routes WHERE route_id='R001'),
   (SELECT id FROM public.users  WHERE email='driver@damascus-transit.demo'),
   'DTS-GPS-0001', false, true, (SELECT id FROM public.operators WHERE slug='damascus')),
  ('BUS-102', 'Bus 102', 'الحافلة ١٠٢', 'bus', 50, 'idle',
   (SELECT id FROM public.routes WHERE route_id='R001'),
   NULL, 'DTS-GPS-0002', false, true, (SELECT id FROM public.operators WHERE slug='damascus')),
  ('MIC-014', 'Microbus 14', 'ميكروباص ١٤', 'microbus', 14, 'active',
   (SELECT id FROM public.routes WHERE route_id='M014'),
   (SELECT id FROM public.users  WHERE email='driver2@damascus-transit.demo'),
   'DTS-GPS-0003', false, true, (SELECT id FROM public.operators WHERE slug='damascus')),
  ('TAX-100', 'Taxi 100', 'تكسي ١٠٠', 'taxi', 4, 'idle',
   (SELECT id FROM public.routes WHERE route_id='T100'),
   NULL, NULL, false, true, (SELECT id FROM public.operators WHERE slug='damascus'))
ON CONFLICT (vehicle_id) DO NOTHING;

-- Make sure the demo driver is bound to BUS-101 even if the vehicle
-- already existed (ON CONFLICT above would have skipped the link).
UPDATE public.vehicles
   SET assigned_driver_id = (SELECT id FROM public.users  WHERE email='driver@damascus-transit.demo'),
       assigned_route_id  = (SELECT id FROM public.routes WHERE route_id='R001'),
       status = 'active'
 WHERE vehicle_id = 'BUS-101';

UPDATE public.vehicles
   SET assigned_driver_id = (SELECT id FROM public.users  WHERE email='driver2@damascus-transit.demo'),
       assigned_route_id  = (SELECT id FROM public.routes WHERE route_id='M014'),
       status = 'active'
 WHERE vehicle_id = 'MIC-014';

-- ── 6b. Approve the demo vehicles IF the approval workflow exists ──
-- Migration 019 adds vehicles.approval_status. If present, mark the demo
-- fleet 'approved' so they operate and show on the public map. If the
-- column doesn't exist yet, this is silently skipped.
DO $$
BEGIN
  UPDATE public.vehicles SET approval_status = 'approved'
   WHERE vehicle_id IN ('BUS-101', 'BUS-102', 'MIC-014', 'TAX-100');
EXCEPTION WHEN undefined_column THEN
  RAISE NOTICE 'approval_status not present (migration 019 not applied) — skipped';
END $$;

-- ── 7. Latest positions (so the live map isn't empty on first load) ─
INSERT INTO public.vehicle_positions_latest
  (vehicle_id, location, speed_kmh, heading, source, route_id, occupancy_pct, operator_id, recorded_at)
SELECT v.id, p.geom, p.spd, p.hdg, 'simulator', v.assigned_route_id, p.occ,
       (SELECT id FROM public.operators WHERE slug='damascus'), now()
FROM (VALUES
        ('BUS-101', ST_SetSRID(ST_MakePoint(36.2980, 33.5110), 4326), 28::numeric, 215::numeric, 60),
        ('MIC-014', ST_SetSRID(ST_MakePoint(36.2810, 33.5150), 4326), 22::numeric,  95::numeric, 40)
     ) AS p(vcode, geom, spd, hdg, occ)
JOIN public.vehicles v ON v.vehicle_id = p.vcode
ON CONFLICT (vehicle_id) DO UPDATE
  SET location = EXCLUDED.location,
      speed_kmh = EXCLUDED.speed_kmh,
      occupancy_pct = EXCLUDED.occupancy_pct,
      recorded_at = now();

COMMIT;

-- ── Verify ─────────────────────────────────────────────────────────
SELECT email, role, is_active FROM public.users
 WHERE email LIKE '%@damascus-transit.demo' ORDER BY role, email;

-- ============================================================
-- Optional: super_admin account
-- ============================================================
-- Run these TWO statements ONLY if you want a cross-operator super admin.
-- `ALTER TYPE ... ADD VALUE` cannot run inside a transaction, so run the
-- ALTER alone first, THEN the INSERT.
--
--   Step 1 (run alone):
-- ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'super_admin';
--
--   Step 2 (run after step 1 has committed):
-- INSERT INTO public.users
--   (email, password_hash, full_name, full_name_ar, role, phone, is_active, operator_id)
-- VALUES
--   ('superadmin@damascus-transit.demo',
--    '$2b$12$VJMfh9cBYdtvoJ43Of0JwuLDYmbEmwYYA4f7o2ynSC9mqdzFFf/im',
--    'Super Admin', 'المدير العام', 'super_admin', '+963900000001', true,
--    (SELECT id FROM public.operators WHERE slug='damascus'))
-- ON CONFLICT (email) DO NOTHING;

-- ============================================================
-- Clean-up (remove all demo data):
-- ============================================================
-- DELETE FROM public.vehicle_positions_latest WHERE vehicle_id IN
--   (SELECT id FROM public.vehicles WHERE vehicle_id IN ('BUS-101','BUS-102','MIC-014','TAX-100'));
-- DELETE FROM public.route_stops WHERE route_id IN (SELECT id FROM public.routes WHERE route_id IN ('R001','M014','T100'));
-- DELETE FROM public.vehicles WHERE vehicle_id IN ('BUS-101','BUS-102','MIC-014','TAX-100');
-- DELETE FROM public.stops    WHERE stop_id  IN ('S001','S002','S003','S004','S005','S006');
-- DELETE FROM public.routes   WHERE route_id IN ('R001','M014','T100');
-- DELETE FROM public.users    WHERE email LIKE '%@damascus-transit.demo';
