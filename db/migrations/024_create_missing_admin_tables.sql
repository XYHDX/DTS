-- ============================================================
-- 024: Create missing admin tables (schema drift repair)
-- ============================================================
-- The deployed DB was missing three tables the API expects, so the
-- corresponding admin pages returned 500:
--   • audit_log  → Audit-log page + every admin write (approve/assign/etc.)
--   • payments   → Payments page (Sham Cash scaffold, migration 020)
--   • schedules  → route schedules
--
-- ⚠ IMPORTANT: db/schema.sql defines `audit_log` with columns
--   (user_id, entity_type, entity_id, details JSONB, ip_address) — but the
--   application code (api/routers/admin.py) actually writes/reads
--   (admin_id, action, details TEXT, operator_id, created_at). The table
--   below matches the CODE (the source of truth), not the stale schema.sql.
--   Consider updating db/schema.sql to match.
--
-- The admin endpoints read/write these via the service role (see
-- api/core/database.py), which bypasses RLS, so RLS is enabled here purely
-- as defence-in-depth. schedules also gets a public-read policy (passenger
-- timetable use), consistent with migration 021.
--
-- Idempotent.
-- ============================================================

-- ── audit_log (matches api/routers/admin.py) ──────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    admin_id    UUID REFERENCES users(id),
    action      TEXT NOT NULL,
    details     TEXT,
    operator_id UUID REFERENCES operators(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

-- ── schedules (matches db/schema.sql + the seed) ──────────────────
CREATE TABLE IF NOT EXISTS schedules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    route_id        UUID NOT NULL REFERENCES routes(id),
    day_of_week     INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    first_departure TIME NOT NULL,
    last_departure  TIME NOT NULL,
    frequency_min   INTEGER NOT NULL DEFAULT 15,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    operator_id     UUID REFERENCES operators(id)
);
ALTER TABLE schedules ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS public_read_schedules ON schedules;
CREATE POLICY public_read_schedules ON schedules FOR SELECT USING (true);

-- ── payments (matches db/migrations/020_payments_sham_cash.sql) ────
CREATE TABLE IF NOT EXISTS payments (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id  UUID NOT NULL REFERENCES operators(id),
    vehicle_id   UUID NOT NULL REFERENCES vehicles(id),
    route_id     UUID REFERENCES routes(id),
    amount_syp   INTEGER NOT NULL CHECK (amount_syp > 0 AND amount_syp <= 1000000),
    currency     TEXT NOT NULL DEFAULT 'SYP',
    status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending','confirmed','failed','refunded','expired')),
    qr_nonce     TEXT NOT NULL,
    provider_ref TEXT UNIQUE,
    provider     TEXT NOT NULL DEFAULT 'sham_cash',
    sandbox      BOOLEAN NOT NULL DEFAULT true,
    payer_hint   TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    confirmed_at TIMESTAMPTZ,
    expires_at   TIMESTAMPTZ NOT NULL DEFAULT now() + interval '15 minutes'
);
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;

-- PostgREST caches the schema; tell it to pick up the new tables.
NOTIFY pgrst, 'reload schema';
