-- ============================================================
-- Migration 032 — reconcile audit_log to the superset shape
-- ============================================================
-- db/schema.sql historically created audit_log as
--   (user_id, action, entity_type NOT NULL, entity_id, details JSONB, ip_address)
-- but api/routers/admin.py writes (admin_id, action, details, operator_id) and
-- omits entity_type. On a DB built from that old schema, every admin write
-- (vehicle approve/assign/decommission, alert resolve, …) 500s.
--
-- This migration widens any existing audit_log to the superset that satisfies
-- BOTH the app writer and the legacy migration-011 writer. All operations are
-- additive / widening, so it is safe on a table already created by migration
-- 024 (those columns simply already exist) and idempotent.
--
-- Apply: Supabase SQL Editor → paste → Run. Safe to re-run.
-- ============================================================

ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS admin_id    UUID REFERENCES users(id);
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS operator_id UUID REFERENCES operators(id);

-- The app does not supply entity_type; if it is still NOT NULL the insert fails.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'audit_log'
          AND column_name = 'entity_type'
          AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE audit_log ALTER COLUMN entity_type DROP NOT NULL;
    END IF;
END $$;

-- PostgREST caches the schema; pick up the new columns.
NOTIFY pgrst, 'reload schema';
