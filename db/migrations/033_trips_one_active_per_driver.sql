-- ============================================================
-- 033: One active trip per driver  (M6 — start_trip TOCTOU backstop)
-- ============================================================
-- start_trip() pre-checks for an in-progress trip and then inserts, which is a
-- check-then-write race: two near-simultaneous starts (double-tap, retry, two
-- devices) both pass the check and both insert an in_progress trip. This
-- partial-unique index makes the database reject the second concurrent
-- in_progress trip; PostgREST returns 409, which the API now translates into
-- the friendly "you already have a trip in progress" error.
--
-- Idempotent and safe to apply on a live DB: we first close any pre-existing
-- duplicate in_progress trips (keeping the most recent per driver) so the
-- unique index can be built.
-- ============================================================

BEGIN;

-- Close older duplicates so the unique index can be created.
WITH ranked AS (
    SELECT id,
           row_number() OVER (
               PARTITION BY driver_id
               ORDER BY actual_start DESC NULLS LAST, id DESC
           ) AS rn
    FROM trips
    WHERE status = 'in_progress'
)
UPDATE trips t
SET status = 'completed',
    actual_end = COALESCE(t.actual_end, NOW())
FROM ranked r
WHERE t.id = r.id
  AND r.rn > 1;

CREATE UNIQUE INDEX IF NOT EXISTS uq_trips_one_active_per_driver
    ON trips (driver_id)
    WHERE status = 'in_progress';

COMMIT;

-- Rollback:
--   DROP INDEX IF EXISTS uq_trips_one_active_per_driver;
