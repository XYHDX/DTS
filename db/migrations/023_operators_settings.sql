-- Migration 023 — operators.settings JSONB
-- ---------------------------------------------------------------------------
-- The admin Settings page stores per-operator config (Sham Cash mode +
-- merchant ID) in operators.settings. The base schema (migration 002) defines
-- this column, but some live databases predate it, which makes
-- GET/PUT /api/admin/settings fail. This adds it idempotently.
--
-- Safe to run more than once. Apply in the Supabase SQL editor.
-- ---------------------------------------------------------------------------

ALTER TABLE operators
  ADD COLUMN IF NOT EXISTS settings JSONB NOT NULL DEFAULT '{}'::jsonb;
