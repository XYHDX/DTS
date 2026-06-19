-- Migration 009 — promote vehicle_positions to a TimescaleDB hypertable
-- and add the telemetry-rich columns from the Protobuf schema (§S1.4 of
-- Scale_100k_Roadmap.md).
--
-- SAFETY: This migration is gated on the timescaledb extension. On a
-- vanilla Postgres or Supabase free-tier instance the gated CREATE
-- TIMESCALEDB section is skipped — the column additions still apply.
-- The query path in the FastAPI side does not depend on TimescaleDB; it
-- only benefits from chunk pruning when the extension is present.
--
-- TARGET CHUNK SIZE: 7 days per chunk. At 24 vehicles × 6/min ping that's
-- ~1.5M rows per chunk — well under the 1.5GB sweet spot. At 100,000
-- vehicles × 6/min that's ~6 billion rows per chunk; halve the interval
-- to 3 days at that scale.

BEGIN;

-- ── 1. Add telemetry columns matching telematics.proto ───────────────────
ALTER TABLE vehicle_positions
    ADD COLUMN IF NOT EXISTS engine_state     BOOLEAN,
    ADD COLUMN IF NOT EXISTS fuel_level       REAL CHECK (fuel_level IS NULL OR (fuel_level >= 0 AND fuel_level <= 100)),
    ADD COLUMN IF NOT EXISTS trigger_event    SMALLINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS satellite_count  SMALLINT,
    ADD COLUMN IF NOT EXISTS hdop             REAL,
    ADD COLUMN IF NOT EXISTS cell_signal_dbm  SMALLINT,
    ADD COLUMN IF NOT EXISTS firmware_version INTEGER,
    ADD COLUMN IF NOT EXISTS battery_mv       INTEGER,
    ADD COLUMN IF NOT EXISTS is_replay        BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN vehicle_positions.engine_state     IS 'Per Protobuf VehicleStatus.engine_state. NULL = unknown / legacy frame.';
COMMENT ON COLUMN vehicle_positions.fuel_level       IS 'EMA-smoothed at the edge (α≈0.1). 0–100. NULL when the device has no fuel sensor.';
COMMENT ON COLUMN vehicle_positions.trigger_event    IS 'Enum value from VehicleStatus.EventType (0 = PERIODIC).';
COMMENT ON COLUMN vehicle_positions.is_replay        IS 'TRUE when this frame came from the device offline FIFO buffer.';

-- ── 2. Indexes for the common analytics queries ──────────────────────────
-- FIX (2026-06-19): the timestamp column on vehicle_positions is `recorded_at`
-- and the speed column is `speed_kmh` (see db/schema.sql) — NOT `ts`/`speed_kph`.
-- The previous draft referenced non-existent columns, which aborted this whole
-- BEGIN/COMMIT block on a fresh deploy (so the telemetry columns above never
-- landed and the hot composite index below was missing). Corrected throughout.
CREATE INDEX IF NOT EXISTS ix_vp_ts_event
    ON vehicle_positions (recorded_at DESC, trigger_event)
    WHERE trigger_event <> 0;

CREATE INDEX IF NOT EXISTS ix_vp_vehicle_ts
    ON vehicle_positions (vehicle_id, recorded_at DESC);

-- ── 3. TimescaleDB hypertable (only when the extension is available) ─────
DO $$
DECLARE
    has_ts BOOLEAN;
BEGIN
    SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') INTO has_ts;
    IF NOT has_ts THEN
        RAISE NOTICE 'timescaledb extension not present — skipping hypertable creation.';
        RETURN;
    END IF;

    -- Promote to hypertable. Migrate existing rows. 7-day chunks.
    PERFORM create_hypertable(
        'vehicle_positions',
        'recorded_at',
        chunk_time_interval => INTERVAL '7 days',
        migrate_data        => TRUE,
        if_not_exists       => TRUE
    );

    -- 90-day retention policy: drop chunks older than 90 days.
    PERFORM add_retention_policy(
        'vehicle_positions',
        INTERVAL '90 days',
        if_not_exists => TRUE
    );

    -- Native compression after 7 days; ~10× reduction expected.
    ALTER TABLE vehicle_positions SET (
        timescaledb.compress,
        timescaledb.compress_segmentby = 'vehicle_id',
        timescaledb.compress_orderby   = 'recorded_at DESC'
    );

    PERFORM add_compression_policy(
        'vehicle_positions',
        INTERVAL '7 days',
        if_not_exists => TRUE
    );

    RAISE NOTICE 'vehicle_positions promoted to hypertable with 7-day chunks, 90-day retention, post-7d compression.';
END $$;

-- ── 4. Continuous aggregate: 1-minute rollup per vehicle (optional) ──────
DO $$
DECLARE
    has_ts BOOLEAN;
BEGIN
    SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') INTO has_ts;
    IF NOT has_ts THEN RETURN; END IF;

    EXECUTE $cagg$
        CREATE MATERIALIZED VIEW IF NOT EXISTS vehicle_positions_1m
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket(INTERVAL '1 minute', recorded_at) AS bucket,
            vehicle_id,
            operator_id,
            route_id,
            avg(speed_kmh)           AS avg_speed_kmh,
            max(speed_kmh)           AS max_speed_kmh,
            avg(fuel_level)          AS avg_fuel_level,
            bool_or(engine_state)    AS engine_was_on,
            count(*)                 AS samples
        FROM vehicle_positions
        GROUP BY bucket, vehicle_id, operator_id, route_id
        WITH NO DATA;
    $cagg$;

    PERFORM add_continuous_aggregate_policy(
        'vehicle_positions_1m',
        start_offset => INTERVAL '2 hours',
        end_offset   => INTERVAL '1 minute',
        schedule_interval => INTERVAL '1 minute',
        if_not_exists => TRUE
    );
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Continuous aggregate skipped: %', SQLERRM;
END $$;

COMMIT;
