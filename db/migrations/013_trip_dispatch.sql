-- ============================================================
-- Migration 013: Trip dispatch workflow
-- ============================================================
-- Closes the operational gap that "nobody assigns trips" — adds the
-- columns + helpers needed for the dispatcher console to schedule
-- a trip ahead of time, push it to a driver, and track acknowledgement.
-- ============================================================

BEGIN;

-- 1. Status enum already has 'scheduled' | 'in_progress' | 'completed' |
--    'cancelled'. Add 'dispatched' (scheduled AND a driver has been
--    pushed the notification but hasn't acknowledged yet) and 'acked'
--    (driver acknowledged but hasn't pressed Start Trip yet).
DO $$ BEGIN
  ALTER TYPE trip_status ADD VALUE IF NOT EXISTS 'dispatched';
EXCEPTION WHEN others THEN NULL; END $$;
DO $$ BEGIN
  ALTER TYPE trip_status ADD VALUE IF NOT EXISTS 'acked';
EXCEPTION WHEN others THEN NULL; END $$;

-- 2. Dispatch metadata columns (idempotent).
ALTER TABLE trips ADD COLUMN IF NOT EXISTS dispatched_by_user_id UUID REFERENCES users(id);
ALTER TABLE trips ADD COLUMN IF NOT EXISTS dispatched_at         TIMESTAMPTZ;
ALTER TABLE trips ADD COLUMN IF NOT EXISTS acked_at              TIMESTAMPTZ;
ALTER TABLE trips ADD COLUMN IF NOT EXISTS cancellation_reason   TEXT;
ALTER TABLE trips ADD COLUMN IF NOT EXISTS planned_passengers    INTEGER;

-- 3. Helpful indexes for the dispatcher console queries.
CREATE INDEX IF NOT EXISTS idx_trips_scheduled_start ON trips(scheduled_start);
CREATE INDEX IF NOT EXISTS idx_trips_driver_status   ON trips(driver_id, status);
CREATE INDEX IF NOT EXISTS idx_trips_operator_status ON trips(operator_id, status);

-- 4. RPC: detect schedule conflicts before inserting a new trip.
--    Returns the IDs of trips that overlap [scheduled_start, scheduled_start + 30min]
--    for the same driver — used by the API to 409 before INSERTing.
CREATE OR REPLACE FUNCTION trip_conflicts_for_driver(
    p_driver_id  UUID,
    p_start      TIMESTAMPTZ,
    p_window_min INTEGER DEFAULT 30
) RETURNS TABLE (id UUID, scheduled_start TIMESTAMPTZ, status trip_status) AS $$
BEGIN
    RETURN QUERY
    SELECT t.id, t.scheduled_start, t.status
      FROM trips t
     WHERE t.driver_id = p_driver_id
       AND t.status IN ('scheduled','dispatched','acked','in_progress')
       AND t.scheduled_start IS NOT NULL
       AND t.scheduled_start <= p_start + (p_window_min || ' minutes')::interval
       AND t.scheduled_start >= p_start - (p_window_min || ' minutes')::interval;
END;
$$ LANGUAGE plpgsql STABLE;

-- 5. Tenant-scoped policies for trips (idempotent — DROP first).
ALTER TABLE trips ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_trips        ON trips;
DROP POLICY IF EXISTS tenant_trips_select ON trips;
DROP POLICY IF EXISTS tenant_trips_write  ON trips;
CREATE POLICY tenant_trips_select ON trips FOR SELECT
    USING (
        operator_id = current_operator_id()
        OR auth.jwt() ->> 'role' = 'super_admin'
    );
CREATE POLICY tenant_trips_write ON trips FOR ALL
    USING (
        operator_id = current_operator_id()
        AND auth.jwt() ->> 'role' IN ('admin','dispatcher','super_admin')
    );

COMMIT;
