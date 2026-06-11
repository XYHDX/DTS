-- ============================================================
-- DamascusTransit — DEMO SEED (accounts + a testable fleet)
-- ============================================================
-- Run this in the Supabase SQL editor (it runs as the service role,
-- so it bypasses RLS). Safe to re-run: every INSERT is idempotent
-- via ON CONFLICT DO NOTHING.
--
-- It matches your CURRENT live schema (base + migrations 002/010) and
-- deliberately does NOT reference columns added by later migrations
-- (must_change_password, password_changed_at, approval_status, payments),
-- so it runs cleanly whether or not those are applied yet.
--
--   ┌───────────────────────────────────────────────────────────┐
--   │  ALL DEMO ACCOUNTS — PASSWORD:  Damascus2026!              │
--   ├──────────────────────────────┬───────────┬────────────────┤
--   │ Email                        │ Role      │ Login tab       │
--   ├──────────────────────────────┼───────────┼────────────────┤
--   │ superadmin@damascus-transit.demo │ super_admin │ إدارة      │
--   │ admin@damascus-transit.demo      │ admin       │ إدارة (Admin) │
--   │ operator@damascus-transit.demo   │ dispatcher  │ موزّع (Operator)│
--   │ driver@damascus-transit.demo     │ driver      │ سائق (Driver) │
--   │ driver2@damascus-transit.demo    │ driver      │ سائق          │
--   │ passenger@damascus-transit.demo  │ viewer      │ (passenger app)│
--   └──────────────────────────────┴───────────┴────────────────┘
--
--   ⚠ These are DEMO credentials. Rotate or delete them before any
--     real production use (see the "Clean-up" block at the bottom).
-- ============================================================

BEGIN;

-- ── 1. Operator (tenant) ───────────────────────────────────────────
INSERT INTO public.operators (id, slug, name, name_ar, is_active)
VALUES (
  '00000000-0000-0000-0000-000000000001',
  'damascus',
  'Damascus Transit Authority',
  'هيئة نقل دمشق',
  true
)
ON CONFLICT (id) DO NOTHING;

-- ── 2. Demo users (password for ALL: Damascus2026!) ────────────────
-- Each row uses a DISTINCT bcrypt hash of the same password (different
-- salt) so a single leaked hash never reveals they share a password.
INSERT INTO public.users
  (id, email, password_hash, full_name, full_name_ar, role, phone, is_active, operator_id)
VALUES
  ('a0000000-0000-0000-0000-000000000001',
   'superadmin@damascus-transit.demo',
   '$2b$12$VJMfh9cBYdtvoJ43Of0JwuLDYmbEmwYYA4f7o2ynSC9mqdzFFf/im',
   'Super Admin', 'المدير العام', 'super_admin', '+963900000001', true,
   '00000000-0000-0000-0000-000000000001'),

  ('a0000000-0000-0000-0000-000000000002',
   'admin@damascus-transit.demo',
   '$2b$12$HpbfV7OnWCfrsLxLp8UiZO4Rc0BNiCUPrf56PF0vSaQTGnbS7PafK',
   'Damascus Admin', 'مدير دمشق', 'admin', '+963900000002', true,
   '00000000-0000-0000-0000-000000000001'),

  ('a0000000-0000-0000-0000-000000000003',
   'operator@damascus-transit.demo',
   '$2b$12$Q7hJksvGrI1.N/iI/38vL.IaT7jRdtqIgX2./NpebcIRrOdas1I2S',
   'Fleet Operator', 'مشغّل الأسطول', 'dispatcher', '+963900000003', true,
   '00000000-0000-0000-0000-000000000001'),

  ('a0000000-0000-0000-0000-000000000004',
   'driver@damascus-transit.demo',
   '$2b$12$M.p/tkNKxnl38YzWkElLxuZ3p1rSbj3G.QTNLM1DQo9Fz.RaGXyKy',
   'Ahmad Khalil', 'أحمد خليل', 'driver', '+963900000004', true,
   '00000000-0000-0000-0000-000000000001'),

  ('a0000000-0000-0000-0000-000000000005',
   'driver2@damascus-transit.demo',
   '$2b$12$VkbIGspNV2Si./.WvVdjoO3XsOhh7syEshukCj3XThthyPjYnQD6K',
   'Samer Haddad', 'سامر حداد', 'driver', '+963900000005', true,
   '00000000-0000-0000-0000-000000000001'),

  ('a0000000-0000-0000-0000-000000000006',
   'passenger@damascus-transit.demo',
   '$2b$12$pD32ASlAmQFiCfMoh8rFFOQaL5UqEev5.FA9zbhyCPqlbxJOWwwWS',
   'Passenger Demo', 'راكب تجريبي', 'viewer', '+963900000006', true,
   '00000000-0000-0000-0000-000000000001')
ON CONFLICT (email) DO NOTHING;

-- ── 3. Routes ──────────────────────────────────────────────────────
INSERT INTO public.routes
  (id, route_id, name, name_ar, route_type, color, distance_km, avg_duration_min, fare_syp, is_active, operator_id)
VALUES
  ('b0000000-0000-0000-0000-000000000001', 'R001',
   'Marjeh → Mezzeh', 'المرجة → المزة', 'bus', '#0E5650', 8.4, 35, 2000, true,
   '00000000-0000-0000-0000-000000000001'),
  ('b0000000-0000-0000-0000-000000000002', 'M014',
   'Umayyad Sq → Baramkeh', 'الأمويين → البرامكة', 'microbus', '#C9A95B', 5.1, 22, 3500, true,
   '00000000-0000-0000-0000-000000000001'),
  ('b0000000-0000-0000-0000-000000000003', 'T100',
   'Bab Touma → Qasioun', 'باب توما → قاسيون', 'taxi', '#CE1126', 6.7, 18, 10000, true,
   '00000000-0000-0000-0000-000000000001')
ON CONFLICT (route_id) DO NOTHING;

-- ── 4. Stops (PostGIS Point geometry, lon/lat WGS84) ───────────────
INSERT INTO public.stops
  (id, stop_id, name, name_ar, location, has_shelter, is_active, operator_id)
VALUES
  ('c0000000-0000-0000-0000-000000000001', 'S001', 'Marjeh Square', 'ساحة المرجة',
   ST_SetSRID(ST_MakePoint(36.3060, 33.5138), 4326), true, true, '00000000-0000-0000-0000-000000000001'),
  ('c0000000-0000-0000-0000-000000000002', 'S002', 'Baramkeh', 'البرامكة',
   ST_SetSRID(ST_MakePoint(36.2870, 33.5090), 4326), true, true, '00000000-0000-0000-0000-000000000001'),
  ('c0000000-0000-0000-0000-000000000003', 'S003', 'Mezzeh', 'المزة',
   ST_SetSRID(ST_MakePoint(36.2400, 33.5020), 4326), false, true, '00000000-0000-0000-0000-000000000001'),
  ('c0000000-0000-0000-0000-000000000004', 'S004', 'Umayyad Square', 'ساحة الأمويين',
   ST_SetSRID(ST_MakePoint(36.2760, 33.5180), 4326), true, true, '00000000-0000-0000-0000-000000000001'),
  ('c0000000-0000-0000-0000-000000000005', 'S005', 'Bab Touma', 'باب توما',
   ST_SetSRID(ST_MakePoint(36.3180, 33.5125), 4326), false, true, '00000000-0000-0000-0000-000000000001'),
  ('c0000000-0000-0000-0000-000000000006', 'S006', 'Qasioun', 'قاسيون',
   ST_SetSRID(ST_MakePoint(36.2790, 33.5320), 4326), false, true, '00000000-0000-0000-0000-000000000001')
ON CONFLICT (stop_id) DO NOTHING;

-- ── 5. Route ⇄ stop ordering ───────────────────────────────────────
INSERT INTO public.route_stops (id, route_id, stop_id, stop_sequence)
VALUES
  ('e0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000001', 1),
  ('e0000000-0000-0000-0000-000000000002', 'b0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000002', 2),
  ('e0000000-0000-0000-0000-000000000003', 'b0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000003', 3),
  ('e0000000-0000-0000-0000-000000000004', 'b0000000-0000-0000-0000-000000000002', 'c0000000-0000-0000-0000-000000000004', 1),
  ('e0000000-0000-0000-0000-000000000005', 'b0000000-0000-0000-0000-000000000002', 'c0000000-0000-0000-0000-000000000002', 2),
  ('e0000000-0000-0000-0000-000000000006', 'b0000000-0000-0000-0000-000000000003', 'c0000000-0000-0000-0000-000000000005', 1),
  ('e0000000-0000-0000-0000-000000000007', 'b0000000-0000-0000-0000-000000000003', 'c0000000-0000-0000-0000-000000000006', 2)
ON CONFLICT (id) DO NOTHING;

-- ── 6. Vehicles (driver@ is bound to BUS-101 on route R001) ────────
INSERT INTO public.vehicles
  (id, vehicle_id, name, name_ar, vehicle_type, capacity, status,
   assigned_route_id, assigned_driver_id, gps_device_id, is_real_gps, is_active, operator_id)
VALUES
  ('d0000000-0000-0000-0000-000000000001', 'BUS-101', 'Bus 101', 'الحافلة ١٠١', 'bus', 50, 'active',
   'b0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000004', 'DTS-GPS-0001', false, true,
   '00000000-0000-0000-0000-000000000001'),
  ('d0000000-0000-0000-0000-000000000002', 'BUS-102', 'Bus 102', 'الحافلة ١٠٢', 'bus', 50, 'idle',
   'b0000000-0000-0000-0000-000000000001', NULL, 'DTS-GPS-0002', false, true,
   '00000000-0000-0000-0000-000000000001'),
  ('d0000000-0000-0000-0000-000000000003', 'MIC-014', 'Microbus 14', 'ميكروباص ١٤', 'microbus', 14, 'active',
   'b0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000005', 'DTS-GPS-0003', false, true,
   '00000000-0000-0000-0000-000000000001'),
  ('d0000000-0000-0000-0000-000000000004', 'TAX-100', 'Taxi 100', 'تكسي ١٠٠', 'taxi', 4, 'idle',
   'b0000000-0000-0000-0000-000000000003', NULL, NULL, false, true,
   '00000000-0000-0000-0000-000000000001')
ON CONFLICT (vehicle_id) DO NOTHING;

-- ── 6b. Approve the demo vehicles IF the approval workflow exists ──
-- Migration 019 adds vehicles.approval_status (default 'pending'). If it is
-- present, mark the demo fleet 'approved' so they operate and show on the
-- public map. If the column doesn't exist yet, this is silently skipped —
-- so the seed works on any migration state, in any order.
DO $$
BEGIN
  UPDATE public.vehicles
     SET approval_status = 'approved'
   WHERE vehicle_id IN ('BUS-101', 'BUS-102', 'MIC-014', 'TAX-100');
EXCEPTION WHEN undefined_column THEN
  RAISE NOTICE 'approval_status not present (migration 019 not applied yet) — skipped';
END $$;

-- ── 7. Latest positions (so the live map isn't empty on first load) ─
INSERT INTO public.vehicle_positions_latest
  (vehicle_id, location, speed_kmh, heading, source, route_id, occupancy_pct, operator_id, recorded_at)
VALUES
  ('d0000000-0000-0000-0000-000000000001',
   ST_SetSRID(ST_MakePoint(36.2980, 33.5110), 4326), 28, 215, 'simulator',
   'b0000000-0000-0000-0000-000000000001', 60, '00000000-0000-0000-0000-000000000001', now()),
  ('d0000000-0000-0000-0000-000000000003',
   ST_SetSRID(ST_MakePoint(36.2810, 33.5150), 4326), 22, 95, 'simulator',
   'b0000000-0000-0000-0000-000000000002', 40, '00000000-0000-0000-0000-000000000001', now())
ON CONFLICT (vehicle_id) DO UPDATE
  SET location = EXCLUDED.location,
      speed_kmh = EXCLUDED.speed_kmh,
      occupancy_pct = EXCLUDED.occupancy_pct,
      recorded_at = now();

COMMIT;

-- ── Verify ─────────────────────────────────────────────────────────
SELECT email, role, is_active FROM public.users
 WHERE email LIKE '%@damascus-transit.demo' ORDER BY role;

-- ============================================================
-- Clean-up (run to remove all demo data):
-- ============================================================
-- DELETE FROM public.vehicle_positions_latest WHERE operator_id='00000000-0000-0000-0000-000000000001' AND source='simulator';
-- DELETE FROM public.vehicles      WHERE vehicle_id IN ('BUS-101','BUS-102','MIC-014','TAX-100');
-- DELETE FROM public.route_stops   WHERE id::text LIKE 'e0000000-%';
-- DELETE FROM public.stops         WHERE stop_id  IN ('S001','S002','S003','S004','S005','S006');
-- DELETE FROM public.routes        WHERE route_id IN ('R001','M014','T100');
-- DELETE FROM public.users         WHERE email LIKE '%@damascus-transit.demo';
