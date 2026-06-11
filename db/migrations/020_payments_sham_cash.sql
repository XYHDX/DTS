-- ============================================================
-- Migration 020: Sham Cash payments scaffold
-- ============================================================
-- Fare payment via Sham Cash QR scan:
--
--   1. Each approved vehicle carries a printed/displayed QR sticker.
--      The QR payload is HMAC-signed by the server (vehicle + operator
--      + nonce) so passengers cannot be redirected to a fake vehicle.
--   2. The passenger app scans the QR → POST /api/pay/initiate →
--      a `payments` row in status 'pending' + a Sham Cash deep link.
--   3. Sham Cash calls POST /api/pay/webhook/shamcash (HMAC-verified,
--      idempotent by provider_ref) → status 'confirmed'.
--   4. Settlement to the operator happens outside this system
--      (Sham Cash merchant account), but every transaction is
--      recorded here per vehicle / route / operator for reporting.
--
-- SANDBOX MODE: until real merchant credentials are configured
-- (SHAM_CASH_MERCHANT_ID / SHAM_CASH_API_SECRET), the API runs in
-- sandbox and payments are confirmed via a test endpoint instead of
-- the real webhook. No real money moves.
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS payments (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id  UUID NOT NULL REFERENCES operators(id),
    vehicle_id   UUID NOT NULL REFERENCES vehicles(id),
    route_id     UUID REFERENCES routes(id),
    amount_syp   INTEGER NOT NULL CHECK (amount_syp > 0 AND amount_syp <= 1000000),
    currency     TEXT NOT NULL DEFAULT 'SYP',
    status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending', 'confirmed', 'failed', 'refunded', 'expired')),
    -- HMAC-signed QR nonce that initiated this payment (replay protection:
    -- one initiate per nonce per passenger session).
    qr_nonce     TEXT NOT NULL,
    -- Sham Cash transaction reference — unique so webhook retries are
    -- idempotent and a captured callback cannot be replayed into a
    -- second credit.
    provider_ref TEXT UNIQUE,
    provider     TEXT NOT NULL DEFAULT 'sham_cash',
    sandbox      BOOLEAN NOT NULL DEFAULT true,
    payer_hint   TEXT,            -- masked wallet id, never the full account
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    confirmed_at TIMESTAMPTZ,
    expires_at   TIMESTAMPTZ NOT NULL DEFAULT now() + interval '15 minutes'
);

-- Reporting + webhook lookups
CREATE INDEX IF NOT EXISTS idx_payments_operator_created
    ON payments (operator_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_payments_vehicle_created
    ON payments (vehicle_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_payments_status
    ON payments (status) WHERE status = 'pending';

-- RLS — same tenant model as the rest of the schema (policies follow
-- the pattern of migration 002; service role bypasses RLS).
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS payments_tenant_isolation ON payments;
CREATE POLICY payments_tenant_isolation ON payments
    USING (operator_id = current_operator_id());

COMMIT;

-- Rollback:
--   DROP TABLE IF EXISTS payments;
