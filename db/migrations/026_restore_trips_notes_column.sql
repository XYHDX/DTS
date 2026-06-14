-- ============================================================
-- 026: Restore trips.notes column (schema-drift repair)
-- ============================================================
-- The deployed `trips` table was missing the `notes` column even though
-- db/schema.sql defines it. The trip-dispatch endpoint
-- (POST /api/admin/trips/dispatch) writes `notes`, so every dispatch failed
-- with PostgREST error 42703 ("column 'notes' of relation 'trips' does not
-- exist") surfaced as HTTP 500. Adding the column (idempotent) and reloading
-- the PostgREST schema cache fixes dispatch.
--
-- Applied live on the production DB 2026-06-14, discovered during the
-- operator→driver dispatch smoke test.
-- ============================================================

ALTER TABLE trips ADD COLUMN IF NOT EXISTS notes TEXT;

-- PostgREST caches table columns; tell it to pick up the restored column.
NOTIFY pgrst, 'reload schema';

-- Rollback:
--   ALTER TABLE trips DROP COLUMN IF EXISTS notes;
