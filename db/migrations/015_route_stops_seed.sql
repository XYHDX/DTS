-- ============================================================
-- Migration 015: Seed route_stops for the 4 demo routes
-- ============================================================
-- Fills the empty route_stops join table so /api/routes returns real
-- stops_count and the passenger app stops showing "0 محطة" for every
-- route. Each route is wired up to its real stop sequence based on
-- the route name and a hand-picked path through the 12 demo stops.
--
-- Idempotent: ON CONFLICT against the (route_id, stop_sequence)
-- unique key. Safe to re-run.
-- ============================================================

BEGIN;

-- R101: Marjeh → Mezzeh Highway
-- S001 Marjeh → S002 Hamidiyeh → S004 Baramkeh → S006 Kafar Souseh
--      → S005 Mezzeh Highway → S011 Mazzeh 86
WITH r AS (SELECT id FROM routes WHERE route_id = 'R101' LIMIT 1)
INSERT INTO route_stops (route_id, stop_id, stop_sequence, typical_arrival_offset_min)
SELECT r.id, s.id, seq.n, seq.eta
FROM r,
     (VALUES
       ('S001',  1,  0),
       ('S002',  2,  4),
       ('S004',  3, 10),
       ('S006',  4, 17),
       ('S005',  5, 25),
       ('S011',  6, 33)
     ) AS seq(stop_code, n, eta)
JOIN stops s ON s.stop_id = seq.stop_code
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- R102: Umayyad Square → Jaramana
-- S003 Umayyad → S007 Abu Rummaneh → S008 Damascus University
--      → S009 Abbasiyyin → S012 Jaramana
WITH r AS (SELECT id FROM routes WHERE route_id = 'R102' LIMIT 1)
INSERT INTO route_stops (route_id, stop_id, stop_sequence, typical_arrival_offset_min)
SELECT r.id, s.id, seq.n, seq.eta
FROM r,
     (VALUES
       ('S003',  1,  0),
       ('S007',  2,  6),
       ('S008',  3, 12),
       ('S009',  4, 22),
       ('S012',  5, 38)
     ) AS seq(stop_code, n, eta)
JOIN stops s ON s.stop_id = seq.stop_code
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- R201: Damascus University → Abbasiyyin (microbus)
-- S008 University → S007 Abu Rummaneh → S003 Umayyad → S009 Abbasiyyin
WITH r AS (SELECT id FROM routes WHERE route_id = 'R201' LIMIT 1)
INSERT INTO route_stops (route_id, stop_id, stop_sequence, typical_arrival_offset_min)
SELECT r.id, s.id, seq.n, seq.eta
FROM r,
     (VALUES
       ('S008',  1,  0),
       ('S007',  2,  6),
       ('S003',  3, 13),
       ('S009',  4, 22)
     ) AS seq(stop_code, n, eta)
JOIN stops s ON s.stop_id = seq.stop_code
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- R202: Bab Tuma → Kafar Souseh (microbus)
-- S010 Bab Tuma → S001 Marjeh → S002 Hamidiyeh → S004 Baramkeh → S006 Kafar Souseh
WITH r AS (SELECT id FROM routes WHERE route_id = 'R202' LIMIT 1)
INSERT INTO route_stops (route_id, stop_id, stop_sequence, typical_arrival_offset_min)
SELECT r.id, s.id, seq.n, seq.eta
FROM r,
     (VALUES
       ('S010',  1,  0),
       ('S001',  2,  5),
       ('S002',  3,  8),
       ('S004',  4, 13),
       ('S006',  5, 20)
     ) AS seq(stop_code, n, eta)
JOIN stops s ON s.stop_id = seq.stop_code
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- distance_from_start_km — best-effort haversine across consecutive stops.
-- We update in-place using a PostGIS computation so the per-stop ETA RPC
-- (added in 6.4) has a real distance to work with.
WITH ordered AS (
    SELECT
        rs.id,
        rs.route_id,
        rs.stop_sequence,
        s.location AS loc,
        LAG(s.location) OVER (
            PARTITION BY rs.route_id ORDER BY rs.stop_sequence
        ) AS prev_loc
    FROM route_stops rs
    JOIN stops s ON s.id = rs.stop_id
),
deltas AS (
    SELECT id, route_id, stop_sequence,
           CASE WHEN prev_loc IS NULL THEN 0
                ELSE ST_Distance(loc::geography, prev_loc::geography) / 1000.0
           END AS leg_km
    FROM ordered
),
cumul AS (
    SELECT id, route_id, stop_sequence,
           SUM(leg_km) OVER (
               PARTITION BY route_id ORDER BY stop_sequence
               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
           )::NUMERIC(6,2) AS dist_km
    FROM deltas
)
UPDATE route_stops rs
   SET distance_from_start_km = c.dist_km
  FROM cumul c
 WHERE rs.id = c.id
   AND (rs.distance_from_start_km IS NULL OR rs.distance_from_start_km <> c.dist_km);

-- Verification — should print 6 / 5 / 4 / 5 for R101 / R102 / R201 / R202
SELECT r.route_id, COUNT(*) AS stop_count
  FROM routes r
  JOIN route_stops rs ON rs.route_id = r.id
 WHERE r.route_id IN ('R101','R102','R201','R202')
 GROUP BY r.route_id
 ORDER BY r.route_id;

COMMIT;
