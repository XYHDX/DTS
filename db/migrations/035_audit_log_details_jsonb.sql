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
            USING (
                CASE
                    WHEN details IS NULL OR btrim(details) = '' THEN NULL
                    -- Already-JSON text converts directly; plain strings are
                    -- wrapped as a JSON string so nothing is lost.
                    WHEN left(btrim(details), 1) IN ('{', '[') THEN details::jsonb
                    ELSE to_jsonb(details)
                END
            );
    END IF;
END $$;
