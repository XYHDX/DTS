-- ============================================================
-- Migration 014: Headway control + bunching detection
-- ============================================================
-- Adds the data + RPC the Dispatcher Console and driver app need to
-- implement basic real-time headway control. The transit-ops research
-- (TransitCenter / Metro Magazine) flagged headway-based dispatch as
-- the highest-leverage way to reduce real-world bunching for an urban
-- fleet, especially in a Damascus-style context where signal priority
-- and dedicated lanes don't exist yet.
-- ============================================================

BEGIN;

-- 1. Per-route target headway (minutes between consecutive vehicles).
--    NULL = headway control disabled for this route.
ALTER TABLE routes
    ADD COLUMN IF NOT EXISTS target_headway_min INTEGER;
COMMENT ON COLUMN routes.target_headway_min IS
    'Target spacing (minutes) between consecutive vehicles on this route. '
    'Used by the driver app to compute hold instructions when buses bunch. '
    'NULL disables headway control for the route.';

-- 2. Alert type for bunching events.
DO $$ BEGIN
  ALTER TYPE alert_type ADD VALUE IF NOT EXISTS 'bus_bunching';
EXCEPTION WHEN others THEN NULL; END $$;

-- 3. Append-only observation table — one row per detected bunching event.
--    Useful for after-the-fact analytics ("how many minutes per day did
--    our fleet spend bunched on each route?") without flooding the
--    alerts table.
CREATE TABLE IF NOT EXISTS headway_observations (
    id            BIGSERIAL PRIMARY KEY,
    route_id      UUID NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
    operator_id   UUID REFERENCES operators(id),
    vehicle_a     UUID NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    vehicle_b     UUID NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    gap_m         NUMERIC(7,1) NOT NULL,
    hold_seconds  INTEGER NOT NULL DEFAULT 0,
    recorded_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_headway_route_time
    ON headway_observations(route_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_headway_operator
    ON headway_observations(operator_id);

ALTER TABLE headway_observations ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_headway ON headway_observations;
CREATE POLICY tenant_headway ON headway_observations
    USING (
        operator_id = current_operator_id()
        OR auth.jwt() ->> 'role' = 'super_admin'
    );

-- 4. RPC: route_headway_status — for the Dispatcher Console gauge.
-- Returns one row per active route with:
--   target_headway_min   — what we want
--   actual_headway_min   — mean pairwise gap converted to minutes,
--                          assuming an average revenue-service speed of
--                          18 km/h (Damascus dense-traffic median).
--   vehicles_on_route    — how many vehicles are currently in service
-- The "actual" figure is a coarse estimate; for true precision an
-- agency runs scheduled stop-to-stop AVL — but for an operational
-- gauge "are buses bunched right now?" this is good enough.
CREATE OR REPLACE FUNCTION route_headway_status(p_operator UUID DEFAULT NULL)
RETURNS TABLE (
    route_id            UUID,
    route_code          TEXT,
    target_headway_min  INTEGER,
    actual_headway_min  NUMERIC,
    vehicles_on_route   INTEGER,
    min_gap_m           NUMERIC
) AS $$
DECLARE
    avg_speed_kmh CONSTANT NUMERIC := 18.0;
BEGIN
    RETURN QUERY
    WITH live AS (
        SELECT
            r.id                AS route_id,
            r.route_id          AS route_code,
            r.target_headway_min,
            r.operator_id,
            vpl.vehicle_id,
            vpl.location
        FROM routes r
        LEFT JOIN vehicle_positions_latest vpl
               ON vpl.route_id = r.id
        WHERE r.is_active
          AND (p_operator IS NULL OR r.operator_id = p_operator)
    ),
    pairs AS (
        SELECT
            a.route_id,
            a.route_code,
            a.target_headway_min,
            a.vehicle_id        AS vehicle_a,
            b.vehicle_id        AS vehicle_b,
            ST_Distance(a.location::geography, b.location::geography) AS gap_m
        FROM live a
        JOIN live b
          ON a.route_id   = b.route_id
         AND a.vehicle_id < b.vehicle_id
         AND a.location IS NOT NULL
         AND b.location IS NOT NULL
    )
    SELECT
        l.route_id,
        l.route_code,
        l.target_headway_min,
        CASE WHEN COUNT(p.gap_m) > 0
             THEN ROUND((AVG(p.gap_m) / 1000.0) / avg_speed_kmh * 60.0, 1)
             ELSE NULL
        END                                                       AS actual_headway_min,
        COUNT(DISTINCT l.vehicle_id) FILTER (WHERE l.vehicle_id IS NOT NULL)::INTEGER
                                                                  AS vehicles_on_route,
        MIN(p.gap_m)::NUMERIC                                     AS min_gap_m
    FROM live l
    LEFT JOIN pairs p USING (route_id, route_code, target_headway_min)
    GROUP BY l.route_id, l.route_code, l.target_headway_min
    ORDER BY l.route_code;
END;
$$ LANGUAGE plpgsql STABLE;

-- 5. RPC: detect_bunching — called from the driver position writer.
-- Returns the closest same-route vehicle within p_threshold_m and the
-- recommended hold_seconds the driver should sit at the next stop.
-- hold_seconds is the gap deficit converted back to seconds using the
-- same avg_speed_kmh estimate.
CREATE OR REPLACE FUNCTION detect_bunching(
    p_vehicle_id UUID,
    p_lat        DOUBLE PRECISION,
    p_lon        DOUBLE PRECISION,
    p_threshold_m INTEGER DEFAULT 250
) RETURNS TABLE (
    other_vehicle_id UUID,
    gap_m            NUMERIC,
    hold_seconds     INTEGER
) AS $$
DECLARE
    v_route_id     UUID;
    v_target_min   INTEGER;
    avg_speed_kmh  CONSTANT NUMERIC := 18.0;
BEGIN
    SELECT assigned_route_id INTO v_route_id FROM vehicles WHERE id = p_vehicle_id;
    IF v_route_id IS NULL THEN
        RETURN;
    END IF;
    SELECT target_headway_min INTO v_target_min FROM routes WHERE id = v_route_id;
    IF v_target_min IS NULL OR v_target_min <= 0 THEN
        -- Headway control disabled for this route.
        RETURN;
    END IF;

    RETURN QUERY
    SELECT
        vpl.vehicle_id,
        ST_Distance(
            vpl.location::geography,
            ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326)::geography
        )::NUMERIC AS gap_m,
        -- Hold = (target_gap_m - actual_gap_m) / avg_m_per_s, clamped.
        GREATEST(0, LEAST(180,
            CEIL(
                (
                    (v_target_min * 60.0 * avg_speed_kmh * 1000.0 / 3600.0)
                    -
                    ST_Distance(
                        vpl.location::geography,
                        ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326)::geography
                    )
                ) / (avg_speed_kmh * 1000.0 / 3600.0)
            )
        ))::INTEGER                AS hold_seconds
    FROM vehicle_positions_latest vpl
    WHERE vpl.route_id = v_route_id
      AND vpl.vehicle_id <> p_vehicle_id
      AND ST_DWithin(
            vpl.location::geography,
            ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326)::geography,
            p_threshold_m
          )
    ORDER BY gap_m
    LIMIT 1;
END;
$$ LANGUAGE plpgsql STABLE;

-- 6. Seed reasonable target headways for the demo routes.
--    R101 / R102 (bus, busy corridors)        → 8 min target
--    R201 / R202 (microbus, smaller vehicles) → 5 min target
UPDATE routes SET target_headway_min = 8 WHERE route_id IN ('R101','R102') AND target_headway_min IS NULL;
UPDATE routes SET target_headway_min = 5 WHERE route_id IN ('R201','R202') AND target_headway_min IS NULL;

COMMIT;
