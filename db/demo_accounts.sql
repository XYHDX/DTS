-- ============================================================
-- Demo Accounts for Damascus Transit System
-- ============================================================
--   • Each role now has its OWN distinct password and bcrypt hash.
--   • A new `super_admin` user is added (cross-operator visibility).
--   • All accounts start with must_change_password = true so the first
--     real login forces a password rotation.
--   • Operator: Damascus Transit Authority
--       (00000000-0000-0000-0000-000000000001)
-- ============================================================
--
--   Email                                | Role         | Initial password
--   -------------------------------------+--------------+----------------------
--   superadmin@damascus-transit.demo     | super_admin  | SuperAdmin#2026
--   admin@damascus-transit.demo          | admin        | AdminDamascus#2026
--   operator@damascus-transit.demo       | dispatcher   | Dispatcher#2026
--   driver@damascus-transit.demo         | driver       | Driver#2026
--   passenger@damascus-transit.demo      | viewer       | Passenger#2026
--
-- ============================================================

-- Insert demo accounts (idempotent — UPDATE the hash if email already exists
-- so old single-shared-hash data is rotated to the new per-role hashes).
INSERT INTO users (email, password_hash, full_name, full_name_ar, role, phone, operator_id, is_active, must_change_password) VALUES

  -- Super-admin (cross-operator) — password: SuperAdmin#2026
  ('superadmin@damascus-transit.demo',
   '$2b$12$4/4lR/08KTXOl0KNeVMoYulozlfW.0fOE3AnB2p01qm/B5UVcg6Ay',
   'Demo Super Admin', 'مدير عام تجريبي', 'super_admin', '+963900000000',
   '00000000-0000-0000-0000-000000000001', true, true),

  -- Admin (operator-scoped) — password: AdminDamascus#2026
  ('admin@damascus-transit.demo',
   '$2b$12$gsX6Wfr1WOJNVpR33qdwd.i51s/ZPfkX1s0XOMWYTKYtyqwRn6uK2',
   'Demo Admin', 'مدير تجريبي', 'admin', '+963900000001',
   '00000000-0000-0000-0000-000000000001', true, true),

  -- Dispatcher (operator) — password: Dispatcher#2026
  ('operator@damascus-transit.demo',
   '$2b$12$EGJqI/Z9F.VkcD7UfI7cMuz.BLFzma86/QEus9vs4m/BWkUyOz1FC',
   'Demo Operator', 'مشغّل تجريبي', 'dispatcher', '+963900000002',
   '00000000-0000-0000-0000-000000000001', true, true),

  -- Driver — password: Driver#2026
  ('driver@damascus-transit.demo',
   '$2b$12$x7mNcqOi7PWNwWXxJZCVcuqal.P4y4diJnjCOGKtFkcrRyFiM9IiS',
   'Demo Driver', 'سائق تجريبي', 'driver', '+963900000003',
   '00000000-0000-0000-0000-000000000001', true, true),

  -- Passenger (viewer / read-only) — password: Passenger#2026
  ('passenger@damascus-transit.demo',
   '$2b$12$pbToHYgalKBwiWGZt/9/u.qaFonoB2HYpn/FxV41m3K1iVePhtSke',
   'Demo Passenger', 'راكب تجريبي', 'viewer', '+963900000004',
   '00000000-0000-0000-0000-000000000001', true, true)

ON CONFLICT (email) DO UPDATE
   SET password_hash        = EXCLUDED.password_hash,
       role                 = EXCLUDED.role,
       is_active            = true,
       must_change_password = true,
       updated_at           = NOW();
