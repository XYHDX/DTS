-- ============================================================
-- Migration 016: Edge-case bug fixes from Phase 6.2 scenario sweep
-- ============================================================
-- Closes five real defects discovered by walking through the v5.0
-- code scenario-by-scenario:
--
--   A. Concurrent vehicle registration could leave one driver assigned
--      to two active vehicles (no DB-level constraint).
--   B. trip_end could overwrite a previously cancelled trip status
--      because the API didn't check the existing status.
--   C. Decommissioning a vehicle orphaned its in-progress trips.
--   D. Demoted / deactivated users kept admin-level JWT validity for
--      up to 24h. We add a `session_invalidate_after` column the API
--      compares against the JWT's `iat`.
--   E. `geofences.max_vehicles = 0` is a valid "no-entry" zone; the
--      column comment now documents that.
-- ============================================================

BEGIN;

-- A. Partial unique index — one active vehicle per driver, max.
DROP INDEX IF EXISTS one_active_vehicle_per_driver;
CREATE UNIQUE INDEX one_active_vehicle_per_driver
    ON vehicles (assigned_driver_id)
    WHERE is_active AND assigned_driver_id IS NOT NULL;

COMMENT ON INDEX one_active_vehicle_per_driver IS
    'Phase 6.2 — guarantees one driver can have at most one ACTIVE vehicle. '
    'Combined with the API''s pre-check this also stops the concurrent-create race.';

-- D. JWT invalidation timestamp.
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS session_invalidate_after TIMESTAMPTZ;
COMMENT ON COLUMN users.session_invalidate_after IS
    'Any JWT with iat < this timestamp is treated as revoked. Set this '
    'when demoting a user, deactivating them, or rotating their password '
    'so old tokens stop working immediately instead of after 24h.';

CREATE INDEX IF NOT EXISTS idx_users_session_invalidate_after
    ON users(session_invalidate_after)
    WHERE session_invalidate_after IS NOT NULL;

-- E. Document max_vehicles=0 semantics.
COMMENT ON COLUMN geofences.max_vehicles IS
    'Hard cap on simultaneous vehicles inside this geofence. '
    'NULL = no limit. 0 = no-entry zone (every vehicle is rejected).';

-- C. Helper RPC: cancel all in-progress trips for a vehicle.
-- Used by the API when DELETEing (decommissioning) a vehicle so the
-- driver's mid-trip state doesn't dangle.
CREATE OR REPLACE FUNCTION cancel_active_trips_for_vehicle(
    p_vehicle_id UUID,
    p_reason     TEXT DEFAULT 'vehicle decommissioned'
) RETURNS INTEGER AS $$
DECLARE
    n INTEGER;
BEGIN
    WITH upd AS (
        UPDATE trips
           SET status              = 'cancelled',
               actual_end          = COALESCE(actual_end, NOW()),
               cancellation_reason = p_reason
         WHERE vehicle_id = p_vehicle_id
           AND status IN ('scheduled','dispatched','acked','in_progress')
        RETURNING id
    )
    SELECT count(*) INTO n FROM upd;
    RETURN n;
END;
$$ LANGUAGE plpgsql;

COMMIT;
