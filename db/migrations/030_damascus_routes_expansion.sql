-- ============================================================
-- Migration 030 — Damascus route-network expansion (+10 corridors)
-- ============================================================
-- Adds 10 real Damascus corridors (R009–R018) to bring the network to 18.
-- Reuses the existing stop inventory (S001–S054) — no new stops required.
-- Idempotent (safe to re-run):
--   * routes        ON CONFLICT (route_id) DO NOTHING
--   * route_stops   ON CONFLICT (route_id, stop_sequence) DO NOTHING
--   * schedules     guarded by NOT EXISTS + a column-aware DO block
--
-- IMPORTANT (verified against the live DB, 2026-06-19): the deployed
-- route_stops table has ONLY (id, route_id, stop_id, stop_sequence) with a
-- UNIQUE (route_id, stop_sequence) constraint. The optional metadata columns
-- (distance_from_start_km, typical_arrival_offset_min) from schema.sql are NOT
-- present, so this file inserts only the columns that exist. `id` is omitted so
-- the table's own default fills it.
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
-- STOPS — ensure every stop these routes reference exists.
-- The deployed stops table has stop_id/name/name_ar/location NOT NULL (no
-- defaults), so all four are supplied; id/is_active/created_at use their
-- defaults. Idempotent via the UNIQUE (stop_id) constraint.
-- ------------------------------------------------------------
INSERT INTO stops (stop_id, name, name_ar, location, operator_id) VALUES
('S001','Marjeh Square','ساحة المرجة',ST_SetSRID(ST_MakePoint(36.3025,33.5105),4326),'00000000-0000-0000-0000-000000000001'),
('S002','Hamidiyeh Souq','سوق الحميدية',ST_SetSRID(ST_MakePoint(36.3065,33.5115),4326),'00000000-0000-0000-0000-000000000001'),
('S003','Umayyad Square','ساحة الأمويين',ST_SetSRID(ST_MakePoint(36.2920,33.5130),4326),'00000000-0000-0000-0000-000000000001'),
('S004','Baramkeh','البرامكة',ST_SetSRID(ST_MakePoint(36.2940,33.5060),4326),'00000000-0000-0000-0000-000000000001'),
('S005','Mezzeh Highway','أوتوستراد المزة',ST_SetSRID(ST_MakePoint(36.2600,33.5050),4326),'00000000-0000-0000-0000-000000000001'),
('S006','Mezzeh 86','مزة 86',ST_SetSRID(ST_MakePoint(36.2450,33.5010),4326),'00000000-0000-0000-0000-000000000001'),
('S007','Kafar Souseh','كفرسوسة',ST_SetSRID(ST_MakePoint(36.2750,33.5020),4326),'00000000-0000-0000-0000-000000000001'),
('S008','Malki','المالكي',ST_SetSRID(ST_MakePoint(36.2800,33.5170),4326),'00000000-0000-0000-0000-000000000001'),
('S009','Abu Rummaneh','أبو رمانة',ST_SetSRID(ST_MakePoint(36.2850,33.5160),4326),'00000000-0000-0000-0000-000000000001'),
('S012','Jisr al-Abyad','جسر الأبيض',ST_SetSRID(ST_MakePoint(36.3080,33.5200),4326),'00000000-0000-0000-0000-000000000001'),
('S013','Abbasiyyin Square','ساحة العباسيين',ST_SetSRID(ST_MakePoint(36.3200,33.5175),4326),'00000000-0000-0000-0000-000000000001'),
('S014','Jobar','جوبر',ST_SetSRID(ST_MakePoint(36.3350,33.5220),4326),'00000000-0000-0000-0000-000000000001'),
('S016','Barzeh','برزة',ST_SetSRID(ST_MakePoint(36.3180,33.5450),4326),'00000000-0000-0000-0000-000000000001'),
('S017','Tishreen Park','حديقة تشرين',ST_SetSRID(ST_MakePoint(36.3100,33.5250),4326),'00000000-0000-0000-0000-000000000001'),
('S018','Damascus University','جامعة دمشق',ST_SetSRID(ST_MakePoint(36.2880,33.5130),4326),'00000000-0000-0000-0000-000000000001'),
('S020','Sha''lan','الشعلان',ST_SetSRID(ST_MakePoint(36.2900,33.5155),4326),'00000000-0000-0000-0000-000000000001'),
('S022','Western Bus Station','المحطة الغربية (السومرية)',ST_SetSRID(ST_MakePoint(36.2350,33.5000),4326),'00000000-0000-0000-0000-000000000001'),
('S025','Harasta','حرستا',ST_SetSRID(ST_MakePoint(36.3550,33.5500),4326),'00000000-0000-0000-0000-000000000001'),
('S026','Douma Entrance','مدخل دوما',ST_SetSRID(ST_MakePoint(36.3800,33.5600),4326),'00000000-0000-0000-0000-000000000001'),
('S027','Jaramana','جرمانا',ST_SetSRID(ST_MakePoint(36.3300,33.4900),4326),'00000000-0000-0000-0000-000000000001'),
('S028','Sayyidah Zaynab','السيدة زينب',ST_SetSRID(ST_MakePoint(36.3400,33.4500),4326),'00000000-0000-0000-0000-000000000001'),
('S029','Airport Road','طريق المطار',ST_SetSRID(ST_MakePoint(36.3500,33.4700),4326),'00000000-0000-0000-0000-000000000001'),
('S030','Dwel''a','الدويلعة',ST_SetSRID(ST_MakePoint(36.3250,33.4850),4326),'00000000-0000-0000-0000-000000000001'),
('S031','Midan','الميدان',ST_SetSRID(ST_MakePoint(36.3000,33.4950),4326),'00000000-0000-0000-0000-000000000001'),
('S033','Bab Touma','باب توما',ST_SetSRID(ST_MakePoint(36.3150,33.5130),4326),'00000000-0000-0000-0000-000000000001'),
('S034','Bab Sharqi','باب شرقي',ST_SetSRID(ST_MakePoint(36.3200,33.5120),4326),'00000000-0000-0000-0000-000000000001'),
('S035','Old City Center','وسط المدينة القديمة',ST_SetSRID(ST_MakePoint(36.3100,33.5110),4326),'00000000-0000-0000-0000-000000000001'),
('S038','Mezze Autostrad West','المزة أوتوستراد غرب',ST_SetSRID(ST_MakePoint(36.2500,33.5030),4326),'00000000-0000-0000-0000-000000000001'),
('S039','Dummar','دمر',ST_SetSRID(ST_MakePoint(36.2300,33.5150),4326),'00000000-0000-0000-0000-000000000001'),
('S040','Qudsaya Entrance','مدخل قدسيا',ST_SetSRID(ST_MakePoint(36.2150,33.5200),4326),'00000000-0000-0000-0000-000000000001'),
('S041','Rabweh','الربوة',ST_SetSRID(ST_MakePoint(36.2700,33.5180),4326),'00000000-0000-0000-0000-000000000001'),
('S043','Tabbaleh','الطبالة',ST_SetSRID(ST_MakePoint(36.3050,33.4980),4326),'00000000-0000-0000-0000-000000000001'),
('S044','Shaghour','الشاغور',ST_SetSRID(ST_MakePoint(36.3120,33.5050),4326),'00000000-0000-0000-0000-000000000001'),
('S045','Bab Mousalla','باب مصلى',ST_SetSRID(ST_MakePoint(36.3080,33.4920),4326),'00000000-0000-0000-0000-000000000001'),
('S046','Qadam','القدم',ST_SetSRID(ST_MakePoint(36.3050,33.4870),4326),'00000000-0000-0000-0000-000000000001'),
('S047','Salhiyeh','الصالحية',ST_SetSRID(ST_MakePoint(36.2920,33.5190),4326),'00000000-0000-0000-0000-000000000001'),
('S051','Yusuf al-Azmeh Square','ساحة يوسف العظمة',ST_SetSRID(ST_MakePoint(36.2870,33.5140),4326),'00000000-0000-0000-0000-000000000001'),
('S053','Mazze Military Hospital','مشفى المزة العسكري',ST_SetSRID(ST_MakePoint(36.2650,33.5060),4326),'00000000-0000-0000-0000-000000000001'),
('S054','Kafar Souseh Flyover','جسر كفرسوسة',ST_SetSRID(ST_MakePoint(36.2780,33.5040),4326),'00000000-0000-0000-0000-000000000001')
ON CONFLICT (stop_id) DO NOTHING;

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
-- ROUTE-STOP ASSIGNMENTS — only (route_id, stop_id, stop_sequence)
-- to match the deployed route_stops table. `id` uses its column default.
-- ------------------------------------------------------------
-- R009: Marjeh → Douma
INSERT INTO route_stops (route_id, stop_id, stop_sequence) VALUES
((SELECT id FROM routes WHERE route_id='R009'), (SELECT id FROM stops WHERE stop_id='S001'), 1),
((SELECT id FROM routes WHERE route_id='R009'), (SELECT id FROM stops WHERE stop_id='S002'), 2),
((SELECT id FROM routes WHERE route_id='R009'), (SELECT id FROM stops WHERE stop_id='S013'), 3),
((SELECT id FROM routes WHERE route_id='R009'), (SELECT id FROM stops WHERE stop_id='S014'), 4),
((SELECT id FROM routes WHERE route_id='R009'), (SELECT id FROM stops WHERE stop_id='S025'), 5),
((SELECT id FROM routes WHERE route_id='R009'), (SELECT id FROM stops WHERE stop_id='S026'), 6)
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- R010: Umayyad → University → Mezzeh
INSERT INTO route_stops (route_id, stop_id, stop_sequence) VALUES
((SELECT id FROM routes WHERE route_id='R010'), (SELECT id FROM stops WHERE stop_id='S003'), 1),
((SELECT id FROM routes WHERE route_id='R010'), (SELECT id FROM stops WHERE stop_id='S018'), 2),
((SELECT id FROM routes WHERE route_id='R010'), (SELECT id FROM stops WHERE stop_id='S004'), 3),
((SELECT id FROM routes WHERE route_id='R010'), (SELECT id FROM stops WHERE stop_id='S007'), 4),
((SELECT id FROM routes WHERE route_id='R010'), (SELECT id FROM stops WHERE stop_id='S053'), 5),
((SELECT id FROM routes WHERE route_id='R010'), (SELECT id FROM stops WHERE stop_id='S005'), 6)
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- R011: Old City → Midan → Qadam
INSERT INTO route_stops (route_id, stop_id, stop_sequence) VALUES
((SELECT id FROM routes WHERE route_id='R011'), (SELECT id FROM stops WHERE stop_id='S035'), 1),
((SELECT id FROM routes WHERE route_id='R011'), (SELECT id FROM stops WHERE stop_id='S044'), 2),
((SELECT id FROM routes WHERE route_id='R011'), (SELECT id FROM stops WHERE stop_id='S045'), 3),
((SELECT id FROM routes WHERE route_id='R011'), (SELECT id FROM stops WHERE stop_id='S031'), 4),
((SELECT id FROM routes WHERE route_id='R011'), (SELECT id FROM stops WHERE stop_id='S046'), 5)
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- R012: Western Bus Station → Marjeh
INSERT INTO route_stops (route_id, stop_id, stop_sequence) VALUES
((SELECT id FROM routes WHERE route_id='R012'), (SELECT id FROM stops WHERE stop_id='S022'), 1),
((SELECT id FROM routes WHERE route_id='R012'), (SELECT id FROM stops WHERE stop_id='S038'), 2),
((SELECT id FROM routes WHERE route_id='R012'), (SELECT id FROM stops WHERE stop_id='S005'), 3),
((SELECT id FROM routes WHERE route_id='R012'), (SELECT id FROM stops WHERE stop_id='S007'), 4),
((SELECT id FROM routes WHERE route_id='R012'), (SELECT id FROM stops WHERE stop_id='S004'), 5),
((SELECT id FROM routes WHERE route_id='R012'), (SELECT id FROM stops WHERE stop_id='S001'), 6)
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- R013: Bab Touma → Jaramana
INSERT INTO route_stops (route_id, stop_id, stop_sequence) VALUES
((SELECT id FROM routes WHERE route_id='R013'), (SELECT id FROM stops WHERE stop_id='S033'), 1),
((SELECT id FROM routes WHERE route_id='R013'), (SELECT id FROM stops WHERE stop_id='S034'), 2),
((SELECT id FROM routes WHERE route_id='R013'), (SELECT id FROM stops WHERE stop_id='S043'), 3),
((SELECT id FROM routes WHERE route_id='R013'), (SELECT id FROM stops WHERE stop_id='S030'), 4),
((SELECT id FROM routes WHERE route_id='R013'), (SELECT id FROM stops WHERE stop_id='S027'), 5)
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- R014: Dummar → Qudsaya → Marjeh
INSERT INTO route_stops (route_id, stop_id, stop_sequence) VALUES
((SELECT id FROM routes WHERE route_id='R014'), (SELECT id FROM stops WHERE stop_id='S039'), 1),
((SELECT id FROM routes WHERE route_id='R014'), (SELECT id FROM stops WHERE stop_id='S040'), 2),
((SELECT id FROM routes WHERE route_id='R014'), (SELECT id FROM stops WHERE stop_id='S041'), 3),
((SELECT id FROM routes WHERE route_id='R014'), (SELECT id FROM stops WHERE stop_id='S003'), 4),
((SELECT id FROM routes WHERE route_id='R014'), (SELECT id FROM stops WHERE stop_id='S001'), 5)
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- R015: Mezzeh 86 → Kafar Souseh → Baramkeh
INSERT INTO route_stops (route_id, stop_id, stop_sequence) VALUES
((SELECT id FROM routes WHERE route_id='R015'), (SELECT id FROM stops WHERE stop_id='S006'), 1),
((SELECT id FROM routes WHERE route_id='R015'), (SELECT id FROM stops WHERE stop_id='S038'), 2),
((SELECT id FROM routes WHERE route_id='R015'), (SELECT id FROM stops WHERE stop_id='S054'), 3),
((SELECT id FROM routes WHERE route_id='R015'), (SELECT id FROM stops WHERE stop_id='S007'), 4),
((SELECT id FROM routes WHERE route_id='R015'), (SELECT id FROM stops WHERE stop_id='S004'), 5)
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- R016: Malki → Salhiyeh → Marjeh
INSERT INTO route_stops (route_id, stop_id, stop_sequence) VALUES
((SELECT id FROM routes WHERE route_id='R016'), (SELECT id FROM stops WHERE stop_id='S008'), 1),
((SELECT id FROM routes WHERE route_id='R016'), (SELECT id FROM stops WHERE stop_id='S009'), 2),
((SELECT id FROM routes WHERE route_id='R016'), (SELECT id FROM stops WHERE stop_id='S020'), 3),
((SELECT id FROM routes WHERE route_id='R016'), (SELECT id FROM stops WHERE stop_id='S047'), 4),
((SELECT id FROM routes WHERE route_id='R016'), (SELECT id FROM stops WHERE stop_id='S051'), 5),
((SELECT id FROM routes WHERE route_id='R016'), (SELECT id FROM stops WHERE stop_id='S001'), 6)
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- R017: Sayyidah Zaynab → Airport Rd → Jaramana
INSERT INTO route_stops (route_id, stop_id, stop_sequence) VALUES
((SELECT id FROM routes WHERE route_id='R017'), (SELECT id FROM stops WHERE stop_id='S028'), 1),
((SELECT id FROM routes WHERE route_id='R017'), (SELECT id FROM stops WHERE stop_id='S029'), 2),
((SELECT id FROM routes WHERE route_id='R017'), (SELECT id FROM stops WHERE stop_id='S030'), 3),
((SELECT id FROM routes WHERE route_id='R017'), (SELECT id FROM stops WHERE stop_id='S027'), 4)
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- R018: Barzeh → Tishreen → Abbasiyyin
INSERT INTO route_stops (route_id, stop_id, stop_sequence) VALUES
((SELECT id FROM routes WHERE route_id='R018'), (SELECT id FROM stops WHERE stop_id='S016'), 1),
((SELECT id FROM routes WHERE route_id='R018'), (SELECT id FROM stops WHERE stop_id='S017'), 2),
((SELECT id FROM routes WHERE route_id='R018'), (SELECT id FROM stops WHERE stop_id='S012'), 3),
((SELECT id FROM routes WHERE route_id='R018'), (SELECT id FROM stops WHERE stop_id='S013'), 4)
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- ------------------------------------------------------------
-- SCHEDULES — weekday bands for the new routes (best-effort).
-- Wrapped in a DO block that adapts to whether schedules has an operator_id
-- column and never aborts the migration if the schedules table is shaped
-- differently. Idempotent via NOT EXISTS.
-- ------------------------------------------------------------
DO $$
DECLARE
    has_op BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'schedules' AND column_name = 'operator_id'
    ) INTO has_op;

    IF has_op THEN
        INSERT INTO schedules (route_id, day_of_week, first_departure, last_departure, frequency_min, operator_id)
        SELECT r.id, d.dow, b.fd::TIME, b.ld::TIME, b.fr, r.operator_id
        FROM routes r
        CROSS JOIN (VALUES (0),(1),(2),(3),(4)) AS d(dow)
        CROSS JOIN (VALUES ('06:00','09:00',15),('09:00','16:00',30),('16:00','19:00',15),('19:00','23:00',30)) AS b(fd,ld,fr)
        WHERE r.route_id IN ('R009','R010','R011','R012','R013','R014','R015','R016','R017','R018')
          AND NOT EXISTS (SELECT 1 FROM schedules s WHERE s.route_id = r.id AND s.day_of_week = d.dow AND s.first_departure = b.fd::TIME);
    ELSE
        INSERT INTO schedules (route_id, day_of_week, first_departure, last_departure, frequency_min)
        SELECT r.id, d.dow, b.fd::TIME, b.ld::TIME, b.fr
        FROM routes r
        CROSS JOIN (VALUES (0),(1),(2),(3),(4)) AS d(dow)
        CROSS JOIN (VALUES ('06:00','09:00',15),('09:00','16:00',30),('16:00','19:00',15),('19:00','23:00',30)) AS b(fd,ld,fr)
        WHERE r.route_id IN ('R009','R010','R011','R012','R013','R014','R015','R016','R017','R018')
          AND NOT EXISTS (SELECT 1 FROM schedules s WHERE s.route_id = r.id AND s.day_of_week = d.dow AND s.first_departure = b.fd::TIME);
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Schedules insert skipped (schedules table shape mismatch): %', SQLERRM;
END $$;

-- ============================================================
-- Verify (run after applying):
--   SELECT count(*) FROM routes WHERE is_active;            -- expect 18
--   SELECT r.route_id, count(*) AS stops FROM route_stops rs
--     JOIN routes r ON r.id = rs.route_id
--    WHERE r.route_id BETWEEN 'R009' AND 'R018'
--    GROUP BY r.route_id ORDER BY r.route_id;               -- 4–6 each
-- ============================================================
