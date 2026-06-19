-- ============================================================
-- Migration 031 — telemetry index repair
-- ============================================================
-- Migration 009 originally referenced a non-existent `ts` column, so on any
-- environment where it aborted, the hot composite index for per-vehicle
-- history/ETA queries (vehicle_id, recorded_at DESC) was never created.
-- 009 is now corrected for fresh deploys; this migration ensures the index
-- exists on already-migrated databases too. Idempotent.
--
-- Apply: Supabase SQL Editor → paste → Run. Safe to re-run.
-- ============================================================

CREATE INDEX IF NOT EXISTS ix_vp_vehicle_ts
    ON vehicle_positions (vehicle_id, recorded_at DESC);

-- Event-only partial index (skips PERIODIC frames). Guarded because the
-- trigger_event column only exists once migration 009's column-add ran.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'vehicle_positions' AND column_name = 'trigger_event'
    ) THEN
        CREATE INDEX IF NOT EXISTS ix_vp_ts_event
            ON vehicle_positions (recorded_at DESC, trigger_event)
            WHERE trigger_event <> 0;
    END IF;
END $$;
