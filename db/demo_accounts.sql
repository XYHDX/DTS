-- ============================================================
-- Demo Accounts for Damascus Transit System
-- ============================================================
-- ⚠ DEPRECATED as a standalone seed. The canonical, complete seed is
--   db/demo_seed.sql  (operator + accounts + fleet + live positions).
--   See db/RESTORE_RUNBOOK.md.
--
-- This file is kept only for the accounts-only case and now uses the SAME
-- password as demo_seed.sql so the two can never disagree again.
--
--   Password for ALL accounts: Damascus2026!
--   Operator: Damascus Transit Authority (00000000-0000-0000-0000-000000000001)
--
-- NOTE: requires the operator row to exist first. Prefer db/demo_seed.sql,
-- which creates the operator for you.
-- ============================================================

-- Distinct bcrypt hash per account (same password "Damascus2026!", different salt).
INSERT INTO users (email, password_hash, full_name, full_name_ar, role, phone, operator_id, is_active) VALUES
  ('admin@damascus-transit.demo',
   '$2b$12$HpbfV7OnWCfrsLxLp8UiZO4Rc0BNiCUPrf56PF0vSaQTGnbS7PafK',
   'Demo Admin', 'مدير تجريبي', 'admin', '+963900000001',
   '00000000-0000-0000-0000-000000000001', true),

  ('operator@damascus-transit.demo',
   '$2b$12$Q7hJksvGrI1.N/iI/38vL.IaT7jRdtqIgX2./NpebcIRrOdas1I2S',
   'Demo Operator', 'مشغّل تجريبي', 'dispatcher', '+963900000002',
   '00000000-0000-0000-0000-000000000001', true),

  ('driver@damascus-transit.demo',
   '$2b$12$M.p/tkNKxnl38YzWkElLxuZ3p1rSbj3G.QTNLM1DQo9Fz.RaGXyKy',
   'Demo Driver', 'سائق تجريبي', 'driver', '+963900000003',
   '00000000-0000-0000-0000-000000000001', true),

  ('passenger@damascus-transit.demo',
   '$2b$12$pD32ASlAmQFiCfMoh8rFFOQaL5UqEev5.FA9zbhyCPqlbxJOWwwWS',
   'Demo Passenger', 'راكب تجريبي', 'viewer', '+963900000004',
   '00000000-0000-0000-0000-000000000001', true)
ON CONFLICT (email) DO NOTHING;
