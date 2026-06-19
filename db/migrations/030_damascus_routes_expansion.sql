-- ============================================================
-- Migration 030 — Damascus route-network expansion (+10 corridors)
-- ============================================================
-- Adds 10 real Damascus corridors (R009–R018) to bring the network to 18.
-- Reuses the existing stop inventory (S001–S054) — no new stops required.
-- All rows are operator-scoped to the default Damascus operator and the
-- whole migration is idempotent (safe to re-run):
--   * routes        ON CONFLICT (route_id) DO NOTHING
--   * route_stops   ON CONFLICT (route_id, stop_sequence) DO NOTHING
--   * schedules     guarded by NOT EXISTS (no unique key to conflict on)
--
-- Apply AFTER db/schema.sql + seed.sql + migrations 002→029.
-- ============================================================

DO $$
DECLARE
    v_op UUID := '00000000-0000-0000-0000-000000000001';  -- Damascus Transit Authority
BEGIN
    IF NOT EXISTS (SELECT 1 FROM operators WHERE id = v_op) THEN
        RAISE NOTICE 'Default Damascus operator % not found — run seed.sql / migration 002 first.', v_op;
    END IF;
END $$;

-- ------------------------------------------------------------
-- ROUTES (R009–R018)
-- ------------------------------------------------------------
INSERT INTO routes (route_id, name, name_ar, route_type, color, distance_km, avg_duration_min, fare_syp, geometry, operator_id, is_active) VALUES
('R009', 'Marjeh → Douma', 'المرجة → دوما', 'bus', '#1d6f63', 14.0, 50, 3000,
    ST_SetSRID(ST_GeomFromText('LINESTRING(36.3025 33.5105, 36.3065 33.5115, 36.3200 33.5175, 36.3350 33.5220, 36.3550 33.5500, 36.3800 33.5600)'), 4326),
    '00000000-0000-0000-0000-000000000001', true),
('R010', 'Umayyad → University → Mezzeh', 'الأمويين → الجامعة → المزة', 'bus', '#2a7d72', 7.0, 30, 2000,
    ST_SetSRID(ST_GeomFromText('LINESTRING(36.2920 33.5130, 36.2880 33.5130, 36.2940 33.5060, 36.2750 33.5020, 36.2650 33.5060, 36.2600 33.5050)'), 4326),
    '00000000-0000-0000-0000-000000000001', true),
('R011', 'Old City → Midan → Qadam', 'المدينة القديمة → الميدان → القدم', 'microbus', '#8a5a2b', 5.0, 25, 2500,
    ST_SetSRID(ST_GeomFromText('LINESTRING(36.3100 33.5110, 36.3120 33.5050, 36.3080 33.4920, 36.3000 33.4950, 36.3050 33.4870)'), 4326),
    '00000000-0000-0000-0000-000000000001', true),
('R012', 'Western Bus Station → Marjeh', 'المحطة الغربية → المرجة', 'bus', '#3a6ea5', 8.0, 40, 2500,
    ST_SetSRID(ST_GeomFromText('LINESTRING(36.2350 33.5000, 36.2500 33.5030, 36.2600 33.5050, 36.2750 33.5020, 36.2940 33.5060, 36.3025 33.5105)'), 4326),
    '00000000-0000-0000-0000-000000000001', true),
('R013', 'Bab Touma → Jaramana', 'باب توما → جرمانا', 'microbus', '#6b4f8a', 7.0, 30, 3000,
    ST_SetSRID(ST_GeomFromText('LINESTRING(36.3150 33.5130, 36.3200 33.5120, 36.3050 33.4980, 36.3250 33.4850, 36.3300 33.4900)'), 4326),
    '00000000-0000-0000-0000-000000000001', true),
('R014', 'Dummar → Qudsaya → Marjeh', 'دمر → قدسيا → المرجة', 'bus', '#1f7a5f', 13.0, 45, 3000,
    ST_SetSRID(ST_GeomFromText('LINESTRING(36.2300 33.5150, 36.2150 33.5200, 36.2700 33.5180, 36.2920 33.5130, 36.3025 33.5105)'), 4326),
    '00000000-0000-0000-0000-000000000001', true),
('R015', 'Mezzeh 86 → Kafar Souseh → Baramkeh', 'مزة 86 → كفرسوسة → البرامكة', 'microbus', '#9c4a55', 6.0, 25, 2500,
    ST_SetSRID(ST_GeomFromText('LINESTRING(36.2450 33.5010, 36.2500 33.5030, 36.2780 33.5040, 36.2750 33.5020, 36.2940 33.5060)'), 4326),
    '00000000-0000-0000-0000-000000000001', true),
('R016', 'Malki → Salhiyeh → Marjeh', 'المالكي → الصالحية → المرجة', 'bus', '#4a7c2f', 5.0, 25, 2000,
    ST_SetSRID(ST_GeomFromText('LINESTRING(36.2800 33.5170, 36.2850 33.5160, 36.2900 33.5155, 36.2920 33.5190, 36.2870 33.5140, 36.3025 33.5105)'), 4326),
    '00000000-0000-0000-0000-000000000001', true),
('R017', 'Sayyidah Zaynab → Airport Rd → Jaramana', 'السيدة زينب → طريق المطار → جرمانا', 'bus', '#2f5c7c', 12.0, 40, 3500,
    ST_SetSRID(ST_GeomFromText('LINESTRING(36.3400 33.4500, 36.3500 33.4700, 36.3250 33.4850, 36.3300 33.4900)'), 4326),
    '00000000-0000-0000-0000-000000000001', true),
('R018', 'Barzeh → Tishreen → Abbasiyyin', 'برزة → تشرين → العباسيين', 'microbus', '#7a6b1f', 6.0, 25, 2500,
    ST_SetSRID(ST_GeomFromText('LINESTRING(36.3180 33.5450, 36.3100 33.5250, 36.3080 33.5200, 36.3200 33.5175)'), 4326),
    '00000000-0000-0000-0000-000000000001', true)
ON CONFLICT (route_id) DO NOTHING;

-- ------------------------------------------------------------
-- ROUTE-STOP ASSIGNMENTS (sequence · cumulative km · arrival offset min)
-- ------------------------------------------------------------
-- R009: Marjeh → Douma
INSERT INTO route_stops (route_id, stop_id, stop_sequence, distance_from_start_km, typical_arrival_offset_min) VALUES
((SELECT id FROM routes WHERE route_id='R009'), (SELECT id FROM stops WHERE stop_id='S001'), 1, 0.0, 0),
((SELECT id FROM routes WHERE route_id='R009'), (SELECT id FROM stops WHERE stop_id='S002'), 2, 0.6, 3),
((SELECT id FROM routes WHERE route_id='R009'), (SELECT id FROM stops WHERE stop_id='S013'), 3, 3.5, 15),
((SELECT id FROM routes WHERE route_id='R009'), (SELECT id FROM stops WHERE stop_id='S014'), 4, 5.5, 22),
((SELECT id FROM routes WHERE route_id='R009'), (SELECT id FROM stops WHERE stop_id='S025'), 5, 9.5, 38),
((SELECT id FROM routes WHERE route_id='R009'), (SELECT id FROM stops WHERE stop_id='S026'), 6, 14.0, 50)
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- R010: Umayyad → University → Mezzeh
INSERT INTO route_stops (route_id, stop_id, stop_sequence, distance_from_start_km, typical_arrival_offset_min) VALUES
((SELECT id FROM routes WHERE route_id='R010'), (SELECT id FROM stops WHERE stop_id='S003'), 1, 0.0, 0),
((SELECT id FROM routes WHERE route_id='R010'), (SELECT id FROM stops WHERE stop_id='S018'), 2, 0.5, 3),
((SELECT id FROM routes WHERE route_id='R010'), (SELECT id FROM stops WHERE stop_id='S004'), 3, 1.4, 8),
((SELECT id FROM routes WHERE route_id='R010'), (SELECT id FROM stops WHERE stop_id='S007'), 4, 3.2, 16),
((SELECT id FROM routes WHERE route_id='R010'), (SELECT id FROM stops WHERE stop_id='S053'), 5, 4.5, 23),
((SELECT id FROM routes WHERE route_id='R010'), (SELECT id FROM stops WHERE stop_id='S005'), 6, 7.0, 30)
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- R011: Old City → Midan → Qadam
INSERT INTO route_stops (route_id, stop_id, stop_sequence, distance_from_start_km, typical_arrival_offset_min) VALUES
((SELECT id FROM routes WHERE route_id='R011'), (SELECT id FROM stops WHERE stop_id='S035'), 1, 0.0, 0),
((SELECT id FROM routes WHERE route_id='R011'), (SELECT id FROM stops WHERE stop_id='S044'), 2, 0.8, 5),
((SELECT id FROM routes WHERE route_id='R011'), (SELECT id FROM stops WHERE stop_id='S045'), 3, 2.2, 12),
((SELECT id FROM routes WHERE route_id='R011'), (SELECT id FROM stops WHERE stop_id='S031'), 4, 3.3, 18),
((SELECT id FROM routes WHERE route_id='R011'), (SELECT id FROM stops WHERE stop_id='S046'), 5, 5.0, 25)
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- R012: Western Bus Station → Marjeh
INSERT INTO route_stops (route_id, stop_id, stop_sequence, distance_from_start_km, typical_arrival_offset_min) VALUES
((SELECT id FROM routes WHERE route_id='R012'), (SELECT id FROM stops WHERE stop_id='S022'), 1, 0.0, 0),
((SELECT id FROM routes WHERE route_id='R012'), (SELECT id FROM stops WHERE stop_id='S038'), 2, 1.6, 8),
((SELECT id FROM routes WHERE route_id='R012'), (SELECT id FROM stops WHERE stop_id='S005'), 3, 2.8, 14),
((SELECT id FROM routes WHERE route_id='R012'), (SELECT id FROM stops WHERE stop_id='S007'), 4, 4.6, 22),
((SELECT id FROM routes WHERE route_id='R012'), (SELECT id FROM stops WHERE stop_id='S004'), 5, 6.4, 32),
((SELECT id FROM routes WHERE route_id='R012'), (SELECT id FROM stops WHERE stop_id='S001'), 6, 8.0, 40)
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- R013: Bab Touma → Jaramana
INSERT INTO route_stops (route_id, stop_id, stop_sequence, distance_from_start_km, typical_arrival_offset_min) VALUES
((SELECT id FROM routes WHERE route_id='R013'), (SELECT id FROM stops WHERE stop_id='S033'), 1, 0.0, 0),
((SELECT id FROM routes WHERE route_id='R013'), (SELECT id FROM stops WHERE stop_id='S034'), 2, 0.7, 4),
((SELECT id FROM routes WHERE route_id='R013'), (SELECT id FROM stops WHERE stop_id='S043'), 3, 2.4, 12),
((SELECT id FROM routes WHERE route_id='R013'), (SELECT id FROM stops WHERE stop_id='S030'), 4, 4.8, 22),
((SELECT id FROM routes WHERE route_id='R013'), (SELECT id FROM stops WHERE stop_id='S027'), 5, 7.0, 30)
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- R014: Dummar → Qudsaya → Marjeh
INSERT INTO route_stops (route_id, stop_id, stop_sequence, distance_from_start_km, typical_arrival_offset_min) VALUES
((SELECT id FROM routes WHERE route_id='R014'), (SELECT id FROM stops WHERE stop_id='S039'), 1, 0.0, 0),
((SELECT id FROM routes WHERE route_id='R014'), (SELECT id FROM stops WHERE stop_id='S040'), 2, 2.0, 8),
((SELECT id FROM routes WHERE route_id='R014'), (SELECT id FROM stops WHERE stop_id='S041'), 3, 7.0, 25),
((SELECT id FROM routes WHERE route_id='R014'), (SELECT id FROM stops WHERE stop_id='S003'), 4, 10.5, 38),
((SELECT id FROM routes WHERE route_id='R014'), (SELECT id FROM stops WHERE stop_id='S001'), 5, 13.0, 45)
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- R015: Mezzeh 86 → Kafar Souseh → Baramkeh
INSERT INTO route_stops (route_id, stop_id, stop_sequence, distance_from_start_km, typical_arrival_offset_min) VALUES
((SELECT id FROM routes WHERE route_id='R015'), (SELECT id FROM stops WHERE stop_id='S006'), 1, 0.0, 0),
((SELECT id FROM routes WHERE route_id='R015'), (SELECT id FROM stops WHERE stop_id='S038'), 2, 0.7, 4),
((SELECT id FROM routes WHERE route_id='R015'), (SELECT id FROM stops WHERE stop_id='S054'), 3, 3.0, 12),
((SELECT id FROM routes WHERE route_id='R015'), (SELECT id FROM stops WHERE stop_id='S007'), 4, 3.6, 16),
((SELECT id FROM routes WHERE route_id='R015'), (SELECT id FROM stops WHERE stop_id='S004'), 5, 6.0, 25)
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- R016: Malki → Salhiyeh → Marjeh
INSERT INTO route_stops (route_id, stop_id, stop_sequence, distance_from_start_km, typical_arrival_offset_min) VALUES
((SELECT id FROM routes WHERE route_id='R016'), (SELECT id FROM stops WHERE stop_id='S008'), 1, 0.0, 0),
((SELECT id FROM routes WHERE route_id='R016'), (SELECT id FROM stops WHERE stop_id='S009'), 2, 0.6, 3),
((SELECT id FROM routes WHERE route_id='R016'), (SELECT id FROM stops WHERE stop_id='S020'), 3, 1.2, 7),
((SELECT id FROM routes WHERE route_id='R016'), (SELECT id FROM stops WHERE stop_id='S047'), 4, 2.0, 11),
((SELECT id FROM routes WHERE route_id='R016'), (SELECT id FROM stops WHERE stop_id='S051'), 5, 3.2, 17),
((SELECT id FROM routes WHERE route_id='R016'), (SELECT id FROM stops WHERE stop_id='S001'), 6, 5.0, 25)
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- R017: Sayyidah Zaynab → Airport Rd → Jaramana
INSERT INTO route_stops (route_id, stop_id, stop_sequence, distance_from_start_km, typical_arrival_offset_min) VALUES
((SELECT id FROM routes WHERE route_id='R017'), (SELECT id FROM stops WHERE stop_id='S028'), 1, 0.0, 0),
((SELECT id FROM routes WHERE route_id='R017'), (SELECT id FROM stops WHERE stop_id='S029'), 2, 3.0, 12),
((SELECT id FROM routes WHERE route_id='R017'), (SELECT id FROM stops WHERE stop_id='S030'), 3, 8.0, 28),
((SELECT id FROM routes WHERE route_id='R017'), (SELECT id FROM stops WHERE stop_id='S027'), 4, 12.0, 40)
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- R018: Barzeh → Tishreen → Abbasiyyin
INSERT INTO route_stops (route_id, stop_id, stop_sequence, distance_from_start_km, typical_arrival_offset_min) VALUES
((SELECT id FROM routes WHERE route_id='R018'), (SELECT id FROM stops WHERE stop_id='S016'), 1, 0.0, 0),
((SELECT id FROM routes WHERE route_id='R018'), (SELECT id FROM stops WHERE stop_id='S017'), 2, 2.4, 11),
((SELECT id FROM routes WHERE route_id='R018'), (SELECT id FROM stops WHERE stop_id='S012'), 3, 3.6, 17),
((SELECT id FROM routes WHERE route_id='R018'), (SELECT id FROM stops WHERE stop_id='S013'), 4, 6.0, 25)
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- ------------------------------------------------------------
-- SCHEDULES — weekday service bands for the new routes.
-- Guarded by NOT EXISTS so re-running this migration does not duplicate rows.
-- Bands: AM peak (06–09, 15min) · midday (09–16, 30min) · PM peak (16–19, 15min)
--        · evening (19–23, 30min), Sun–Thu (day_of_week 0–4).
-- ------------------------------------------------------------
INSERT INTO schedules (route_id, day_of_week, first_departure, last_departure, frequency_min, operator_id)
SELECT r.id, d.dow, b.first_dep::TIME, b.last_dep::TIME, b.freq, r.operator_id
FROM routes r
CROSS JOIN (VALUES (0),(1),(2),(3),(4)) AS d(dow)
CROSS JOIN (VALUES
    ('06:00','09:00',15),
    ('09:00','16:00',30),
    ('16:00','19:00',15),
    ('19:00','23:00',30)
) AS b(first_dep, last_dep, freq)
WHERE r.route_id IN ('R009','R010','R011','R012','R013','R014','R015','R016','R017','R018')
  AND NOT EXISTS (
      SELECT 1 FROM schedules s
      WHERE s.route_id = r.id
        AND s.day_of_week = d.dow
        AND s.first_departure = b.first_dep::TIME
  );

-- ============================================================
-- Verify (run manually after applying):
--   SELECT route_id, name, name_ar, route_type, fare_syp FROM routes
--   WHERE route_id BETWEEN 'R009' AND 'R018' ORDER BY route_id;
--   SELECT count(*) FROM routes WHERE is_active;            -- expect 18
--   SELECT r.route_id, count(*) AS stops FROM route_stops rs
--     JOIN routes r ON r.id = rs.route_id GROUP BY r.route_id ORDER BY r.route_id;
-- ============================================================
