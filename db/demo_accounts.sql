-- ============================================================
-- Demo Accounts for Damascus Transit System
-- Password for all accounts: damascus2025
-- Operator: Damascus Transit Authority (00000000-0000-0000-0000-000000000001)
-- ============================================================

-- Insert demo accounts (idempotent — skips if email already exists)
INSERT INTO users (email, password_hash, full_name, full_name_ar, role, phone, operator_id, is_active) VALUES
  -- Admin demo account
  ('admin@damascus-transit.demo',
   '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.',
   'Demo Admin', 'مدير تجريبي', 'admin', '+963900000001',
   '00000000-0000-0000-0000-000000000001', true),

  -- Dispatcher (operator) demo account
  ('operator@damascus-transit.demo',
   '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.',
   'Demo Operator', 'مشغّل تجريبي', 'dispatcher', '+963900000002',
   '00000000-0000-0000-0000-000000000001', true),

  -- Driver demo account
  ('driver@damascus-transit.demo',
   '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.',
   'Demo Driver', 'سائق تجريبي', 'driver', '+963900000003',
   '00000000-0000-0000-0000-000000000001', true),

  -- Passenger (viewer) demo account
  ('passenger@damascus-transit.demo',
   '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.',
   'Demo Passenger', 'راكب تجريبي', 'viewer', '+963900000004',
   '00000000-0000-0000-0000-000000000001', true)
ON CONFLICT (email) DO NOTHING;
