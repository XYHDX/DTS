-- ============================================================
-- 025: Restore upsert_vehicle_position() RPC (schema-drift repair)
-- ============================================================
-- The deployed database was missing this function entirely, even though it
-- is defined in db/schema.sql. Every driver GPS report
-- (POST /api/driver/position → _service_rpc('upsert_vehicle_position', …))
-- therefore failed with PostgREST error PGRST202 / 42883
-- ("function ... does not exist"), surfacing as HTTP 500 and no live dot on
-- the public map. Recreating it here (idempotent) and reloading the PostgREST
-- schema cache fixes live GPS streaming.
--
-- Definition kept byte-for-byte in step with db/schema.sql. SECURITY DEFINER
-- so it can write the position history/latest tables regardless of the
-- caller's row-level policies (the API already calls it with the service
-- role, but this keeps the MQTT ingest and any future callers safe too).
--
-- Applied live on the production DB 2026-06-14.
-- ============================================================

BEGIN;

CREATE OR REPLACE FUNCTION upsert_vehicle_position(
    p_vehicle_id UUID,
    p_lat DOUBLE PRECISION,
    p_lon DOUBLE PRECISION,
    p_speed NUMERIC,
    p_heading NUMERIC,
    p_source TEXT,
    p_route_id UUID DEFAULT NULL,
    p_occupancy INTEGER DEFAULT 0
) RETURNS void AS $$
DECLARE
    v_operator_id UUID;
BEGIN
    SELECT operator_id INTO v_operator_id FROM vehicles WHERE id = p_vehicle_id;

    -- Insert into history
    INSERT INTO vehicle_positions (vehicle_id, location, speed_kmh, heading, source, route_id, occupancy_pct, operator_id)
    VALUES (p_vehicle_id, ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326), p_speed, p_heading, p_source, p_route_id, p_occupancy, v_operator_id);

    -- Upsert latest
    INSERT INTO vehicle_positions_latest (vehicle_id, location, speed_kmh, heading, source, route_id, occupancy_pct, operator_id, recorded_at)
    VALUES (p_vehicle_id, ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326), p_speed, p_heading, p_source, p_route_id, p_occupancy, v_operator_id, NOW())
    ON CONFLICT (vehicle_id)
    DO UPDATE SET
        location = EXCLUDED.location,
        speed_kmh = EXCLUDED.speed_kmh,
        heading = EXCLUDED.heading,
        source = EXCLUDED.source,
        route_id = EXCLUDED.route_id,
        occupancy_pct = EXCLUDED.occupancy_pct,
        operator_id = EXCLUDED.operator_id,
        recorded_at = NOW();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION upsert_vehicle_position(
    UUID, DOUBLE PRECISION, DOUBLE PRECISION, NUMERIC, NUMERIC, TEXT, UUID, INTEGER
) TO anon, authenticated, service_role;

COMMIT;

-- PostgREST caches the function catalogue; tell it to pick up the new RPC.
NOTIFY pgrst, 'reload schema';

-- Rollback:
--   DROP FUNCTION IF EXISTS upsert_vehicle_position(
--     UUID, DOUBLE PRECISION, DOUBLE PRECISION, NUMERIC, NUMERIC, TEXT, UUID, INTEGER);
