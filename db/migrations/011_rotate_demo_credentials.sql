-- ============================================================
-- Migration 011: ROTATE shared demo password + add super_admin role
-- ============================================================
-- Critical security fix.
-- Before: admin / dispatcher / driver / viewer demo accounts ALL shared
--         the same bcrypt hash for password "damascus2025". A single
--         credential leak compromised every role at once.
-- After:  one unique strong password per role + must_change_password=true
--         so the first login is forced to rotate.
-- ============================================================

BEGIN;

-- 1. Ensure super_admin exists in the user_role enum.
DO $$ BEGIN
  ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'super_admin';
EXCEPTION WHEN others THEN NULL; END $$;

-- 2. Ensure required columns exist (idempotent for fresh DBs that ran the
--    older bootstrap before columns were added).
ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_changed_at  TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen_at         TIMESTAMPTZ;

-- 3. Rotate the five demo accounts to per-role hashes.
--    Hashes were generated locally with bcrypt rounds=12 and verified
--    against their plaintexts before commit.
INSERT INTO users (email, password_hash, full_name, full_name_ar, role, phone, operator_id, is_active, must_change_password) VALUES
  ('superadmin@damascus-transit.demo',
   '$2b$12$4/4lR/08KTXOl0KNeVMoYulozlfW.0fOE3AnB2p01qm/B5UVcg6Ay',
   'Demo Super Admin', 'مدير عام تجريبي', 'super_admin', '+963900000000',
   '00000000-0000-0000-0000-000000000001', true, true),

  ('admin@damascus-transit.demo',
   '$2b$12$gsX6Wfr1WOJNVpR33qdwd.i51s/ZPfkX1s0XOMWYTKYtyqwRn6uK2',
   'Demo Admin', 'مدير تجريبي', 'admin', '+963900000001',
   '00000000-0000-0000-0000-000000000001', true, true),

  ('operator@damascus-transit.demo',
   '$2b$12$EGJqI/Z9F.VkcD7UfI7cMuz.BLFzma86/QEus9vs4m/BWkUyOz1FC',
   'Demo Operator', 'مشغّل تجريبي', 'dispatcher', '+963900000002',
   '00000000-0000-0000-0000-000000000001', true, true),

  ('driver@damascus-transit.demo',
   '$2b$12$x7mNcqOi7PWNwWXxJZCVcuqal.P4y4diJnjCOGKtFkcrRyFiM9IiS',
   'Demo Driver', 'سائق تجريبي', 'driver', '+963900000003',
   '00000000-0000-0000-0000-000000000001', true, true),

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

-- 4. Audit-log the rotation so post-incident reviewers can see it happened.
INSERT INTO audit_log (action, entity_type, details)
VALUES (
  'demo_credential_rotation',
  'users',
  jsonb_build_object(
    'reason', 'CRITICAL: admin & dispatcher shared one bcrypt hash',
    'migration', '011_rotate_demo_credentials.sql',
    'rotated_emails', ARRAY[
      'superadmin@damascus-transit.demo',
      'admin@damascus-transit.demo',
      'operator@damascus-transit.demo',
      'driver@damascus-transit.demo',
      'passenger@damascus-transit.demo'
    ]
  )
);

COMMIT;
