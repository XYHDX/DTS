-- ============================================================
-- 035: Reconcile audit_log.details to JSONB  (L7 — type drift)
-- ============================================================
-- Migration 024 created audit_log.details as TEXT; db/schema.sql and migration
-- 032 treat it as JSONB. 032 never converted the type, so a DB built via 024
-- keeps `details` as TEXT and can't query it as JSON, diverging from a fresh
-- schema.sql build. This converts it in place where it is still non-JSONB.
-- Idempotent and guarded (no-op when already jsonb or column absent).
-- ============================================================

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'audit_log'
          AND column_name = 'details'
          AND data_type <> 'jsonb'
    ) THEN
        ALTER TABLE public.audit_log
            ALTER COLUMN details TYPE jsonb
            -- Wrap every existing TEXT value as a JSON string. This is lossless
            -- and CANNOT fail (no parsing of JSON-looking text), so the prod
            -- apply is safe; the app treats details as opaque anyway.
            USING (CASE WHEN details IS NULL THEN NULL ELSE to_jsonb(details) END);
    END IF;
END $$;
