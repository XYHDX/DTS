-- ============================================================
-- DamascusTransit Seed Data
-- 8 routes (with polylines), 54 stops, 24 vehicles, 20 users
-- ============================================================

-- Seed default operator (must exist before routes/vehicles reference it)
INSERT INTO operators (id, slug, name, name_ar, is_active) VALUES
('00000000-0000-0000-0000-000000000001', 'damascus', 'Damascus Transit Authority', 'هيئة نقل دمشق', true)
ON CONFLICT (slug) DO UPDATE SET is_active = true;

-- Seed users (demo password: damascus2025 — CHANGE IN PRODUCTION)
INSERT INTO users (email, password_hash, full_name, full_name_ar, role, phone) VALUES
('admin@damascustransit.sy', '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.', 'System Admin', 'مدير النظام', 'admin', '+963000000001'),
('dispatcher@damascustransit.sy', '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.', 'Operations Center', 'مركز العمليات', 'dispatcher', '+963000000002'),
-- Drivers (one per active vehicle — assign via UPDATE below)
('driver01@damascustransit.sy', '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.', 'Ahmad Khalil', 'أحمد خليل', 'driver', '+963110000001'),
('driver02@damascustransit.sy', '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.', 'Omar Sayed', 'عمر سيد', 'driver', '+963110000002'),
('driver03@damascustransit.sy', '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.', 'Hassan Nouri', 'حسن نوري', 'driver', '+963110000003'),
('driver04@damascustransit.sy', '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.', 'Sami Darwish', 'سامي درويش', 'driver', '+963110000004'),
('driver05@damascustransit.sy', '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.', 'Fadi Haddad', 'فادي حداد', 'driver', '+963110000005'),
('driver06@damascustransit.sy', '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.', 'Khaled Mansour', 'خالد منصور', 'driver', '+963110000006'),
('driver07@damascustransit.sy', '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.', 'Youssef Amin', 'يوسف أمين', 'driver', '+963110000007'),
('driver08@damascustransit.sy', '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.', 'Rami Jabr', 'رامي جبر', 'driver', '+963110000008'),
('driver09@damascustransit.sy', '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.', 'Nizar Shami', 'نزار شامي', 'driver', '+963110000009'),
('driver10@damascustransit.sy', '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.', 'Tariq Bazzi', 'طارق بزي', 'driver', '+963110000010'),
('driver11@damascustransit.sy', '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.', 'Bilal Hamdi', 'بلال حمدي', 'driver', '+963110000011'),
('driver12@damascustransit.sy', '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.', 'Wael Khoury', 'وائل خوري', 'driver', '+963110000012'),
('driver13@damascustransit.sy', '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.', 'Mazen Rida', 'مازن رضا', 'driver', '+963110000013'),
('driver14@damascustransit.sy', '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.', 'Adel Fayad', 'عادل فياض', 'driver', '+963110000014'),
('driver15@damascustransit.sy', '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.', 'Samir Qasim', 'سمير قاسم', 'driver', '+963110000015'),
('driver16@damascustransit.sy', '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.', 'Jamil Sabbagh', 'جميل صباغ', 'driver', '+963110000016'),
('driver17@damascustransit.sy', '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.', 'Hani Tlass', 'هاني طلاس', 'driver', '+963110000017'),
('driver18@damascustransit.sy', '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.', 'Ziad Farah', 'زياد فرح', 'driver', '+963110000018')
ON CONFLICT (email) DO NOTHING;

-- ============================================================
-- STOPS (54 real Damascus locations)
-- ============================================================

INSERT INTO stops (stop_id, name, name_ar, location, has_shelter) VALUES
('S001', 'Marjeh Square', 'ساحة المرجة', ST_SetSRID(ST_MakePoint(36.3025, 33.5105), 4326), true),
('S002', 'Hamidiyeh Souq', 'سوق الحميدية', ST_SetSRID(ST_MakePoint(36.3065, 33.5115), 4326), true),
('S003', 'Umayyad Square', 'ساحة الأمويين', ST_SetSRID(ST_MakePoint(36.2920, 33.5130), 4326), true),
('S004', 'Baramkeh', 'البرامكة', ST_SetSRID(ST_MakePoint(36.2940, 33.5060), 4326), true),
('S005', 'Mezzeh Highway', 'أوتوستراد المزة', ST_SetSRID(ST_MakePoint(36.2600, 33.5050), 4326), true),
('S006', 'Mezzeh 86', 'مزة 86', ST_SetSRID(ST_MakePoint(36.2450, 33.5010), 4326), false),
('S007', 'Kafar Souseh', 'كفرسوسة', ST_SetSRID(ST_MakePoint(36.2750, 33.5020), 4326), true),
('S008', 'Malki', 'المالكي', ST_SetSRID(ST_MakePoint(36.2800, 33.5170), 4326), false),
('S009', 'Abu Rummaneh', 'أبو رمانة', ST_SetSRID(ST_MakePoint(36.2850, 33.5160), 4326), true),
('S010', 'Muhajirin', 'المهاجرين', ST_SetSRID(ST_MakePoint(36.2880, 33.5210), 4326), false),
('S011', 'Saroujah', 'الصالحية', ST_SetSRID(ST_MakePoint(36.3050, 33.5180), 4326), true),
('S012', 'Jisr al-Abyad', 'جسر الأبيض', ST_SetSRID(ST_MakePoint(36.3080, 33.5200), 4326), false),
('S013', 'Abbasiyyin Square', 'ساحة العباسيين', ST_SetSRID(ST_MakePoint(36.3200, 33.5175), 4326), true),
('S014', 'Jobar', 'جوبر', ST_SetSRID(ST_MakePoint(36.3350, 33.5220), 4326), false),
('S015', 'Qaboun', 'القابون', ST_SetSRID(ST_MakePoint(36.3400, 33.5350), 4326), false),
('S016', 'Barzeh', 'برزة', ST_SetSRID(ST_MakePoint(36.3180, 33.5450), 4326), true),
('S017', 'Tishreen Park', 'حديقة تشرين', ST_SetSRID(ST_MakePoint(36.3100, 33.5250), 4326), true),
('S018', 'Damascus University', 'جامعة دمشق', ST_SetSRID(ST_MakePoint(36.2880, 33.5130), 4326), true),
('S019', 'Rawda', 'الروضة', ST_SetSRID(ST_MakePoint(36.2960, 33.5140), 4326), false),
('S020', 'Sha''lan', 'الشعلان', ST_SetSRID(ST_MakePoint(36.2900, 33.5155), 4326), true),
('S021', 'Mazraa', 'المزرعة', ST_SetSRID(ST_MakePoint(36.2830, 33.5030), 4326), false),
('S022', 'Western Bus Station', 'المحطة الغربية (السومرية)', ST_SetSRID(ST_MakePoint(36.2350, 33.5000), 4326), true),
('S023', 'Daraya Junction', 'مفرق داريا', ST_SetSRID(ST_MakePoint(36.2400, 33.4950), 4326), false),
('S024', 'Moadamiyeh', 'المعضمية', ST_SetSRID(ST_MakePoint(36.2200, 33.4800), 4326), true),
('S025', 'Harasta', 'حرستا', ST_SetSRID(ST_MakePoint(36.3550, 33.5500), 4326), true),
('S026', 'Douma Entrance', 'مدخل دوما', ST_SetSRID(ST_MakePoint(36.3800, 33.5600), 4326), true),
('S027', 'Jaramana', 'جرمانا', ST_SetSRID(ST_MakePoint(36.3300, 33.4900), 4326), true),
('S028', 'Sayyidah Zaynab', 'السيدة زينب', ST_SetSRID(ST_MakePoint(36.3400, 33.4500), 4326), true),
('S029', 'Airport Road', 'طريق المطار', ST_SetSRID(ST_MakePoint(36.3500, 33.4700), 4326), false),
('S030', 'Dwel''a', 'الدويلعة', ST_SetSRID(ST_MakePoint(36.3250, 33.4850), 4326), false),
('S031', 'Midan', 'الميدان', ST_SetSRID(ST_MakePoint(36.3000, 33.4950), 4326), true),
('S032', 'Zahira', 'الظاهرة', ST_SetSRID(ST_MakePoint(36.2970, 33.4970), 4326), false),
('S033', 'Bab Touma', 'باب توما', ST_SetSRID(ST_MakePoint(36.3150, 33.5130), 4326), true),
('S034', 'Bab Sharqi', 'باب شرقي', ST_SetSRID(ST_MakePoint(36.3200, 33.5120), 4326), true),
('S035', 'Old City Center', 'وسط المدينة القديمة', ST_SetSRID(ST_MakePoint(36.3100, 33.5110), 4326), true),
('S036', 'Kassaa', 'القصاع', ST_SetSRID(ST_MakePoint(36.3180, 33.5160), 4326), false),
('S037', 'Tijara Center', 'مركز التجارة', ST_SetSRID(ST_MakePoint(36.2950, 33.5100), 4326), true),
('S038', 'Mezze Autostrad West', 'المزة أوتوستراد غرب', ST_SetSRID(ST_MakePoint(36.2500, 33.5030), 4326), false),
('S039', 'Dummar', 'دمر', ST_SetSRID(ST_MakePoint(36.2300, 33.5150), 4326), true),
('S040', 'Qudsaya Entrance', 'مدخل قدسيا', ST_SetSRID(ST_MakePoint(36.2150, 33.5200), 4326), false),
('S041', 'Rabweh', 'الربوة', ST_SetSRID(ST_MakePoint(36.2700, 33.5180), 4326), true),
('S042', 'Muhajireen Heights', 'أعالي المهاجرين', ST_SetSRID(ST_MakePoint(36.2860, 33.5250), 4326), false),
-- Additional stops (S043-S054)
('S043', 'Tabbaleh', 'الطبالة', ST_SetSRID(ST_MakePoint(36.3050, 33.4980), 4326), false),
('S044', 'Shaghour', 'الشاغور', ST_SetSRID(ST_MakePoint(36.3120, 33.5050), 4326), true),
('S045', 'Bab Mousalla', 'باب مصلى', ST_SetSRID(ST_MakePoint(36.3080, 33.4920), 4326), true),
('S046', 'Qadam', 'القدم', ST_SetSRID(ST_MakePoint(36.3050, 33.4870), 4326), false),
('S047', 'Salhiyeh', 'الصالحية', ST_SetSRID(ST_MakePoint(36.2920, 33.5190), 4326), true),
('S048', 'Mezzeh Villas', 'فيلات المزة', ST_SetSRID(ST_MakePoint(36.2550, 33.5080), 4326), false),
('S049', 'Barada Bridge', 'جسر بردى', ST_SetSRID(ST_MakePoint(36.2980, 33.5120), 4326), true),
('S050', 'Arnous Square', 'ساحة الأرنؤوس', ST_SetSRID(ST_MakePoint(36.2930, 33.5110), 4326), true),
('S051', 'Yusuf al-Azmeh Square', 'ساحة يوسف العظمة', ST_SetSRID(ST_MakePoint(36.2870, 33.5140), 4326), true),
('S052', 'Jisr al-Raees', 'جسر الرئيس', ST_SetSRID(ST_MakePoint(36.2810, 33.5100), 4326), false),
('S053', 'Mazze Military Hospital', 'مشفى المزة العسكري', ST_SetSRID(ST_MakePoint(36.2650, 33.5060), 4326), true),
('S054', 'Kafar Souseh Flyover', 'جسر كفرسوسة', ST_SetSRID(ST_MakePoint(36.2780, 33.5040), 4326), false)
ON CONFLICT (stop_id) DO NOTHING;

-- ============================================================
-- ROUTES (8 Damascus corridors)
-- ============================================================

INSERT INTO routes (route_id, name, name_ar, route_type, color, distance_km, avg_duration_min, fare_syp, geometry) VALUES
('R001', 'Marjeh → Mezzeh Highway', 'المرجة → أوتوستراد المزة', 'bus', '#428177', 8.5, 35, 2000,
    ST_SetSRID(ST_GeomFromText('LINESTRING(36.3025 33.5105, 36.299 33.51, 36.295 33.51, 36.294 33.506, 36.29 33.504, 36.283 33.503, 36.275 33.502, 36.265 33.506, 36.26 33.505, 36.25 33.503, 36.245 33.501)'), 4326)),
('R002', 'Baramkeh → Barzeh', 'البرامكة → برزة', 'bus', '#054239', 12.0, 45, 2500,
    ST_SetSRID(ST_GeomFromText('LINESTRING(36.294 33.506, 36.293 33.509, 36.292 33.513, 36.295 33.516, 36.305 33.518, 36.308 33.52, 36.31 33.525, 36.315 33.522, 36.32 33.5175, 36.319 33.53, 36.318 33.545, 36.335 33.548, 36.355 33.55)'), 4326)),
('R003', 'Umayyad → Qaboun', 'الأمويين → القابون', 'bus', '#002623', 10.5, 40, 2000,
    ST_SetSRID(ST_GeomFromText('LINESTRING(36.292 33.513, 36.296 33.514, 36.3 33.516, 36.305 33.518, 36.31 33.518, 36.32 33.5175, 36.328 33.52, 36.335 33.522, 36.338 33.528, 36.34 33.535, 36.348 33.542, 36.355 33.55)'), 4326)),
('R004', 'Old City → Jaramana', 'المدينة القديمة → جرمانا', 'microbus', '#b9a779', 9.0, 35, 3000,
    ST_SetSRID(ST_GeomFromText('LINESTRING(36.31 33.511, 36.315 33.5115, 36.32 33.512, 36.315 33.513, 36.318 33.516, 36.322 33.51, 36.325 33.498, 36.325 33.485, 36.328 33.488, 36.33 33.49, 36.335 33.47, 36.34 33.45)'), 4326)),
('R005', 'Marjeh → Sayyidah Zaynab', 'المرجة → السيدة زينب', 'bus', '#988561', 18.0, 55, 3500,
    ST_SetSRID(ST_GeomFromText('LINESTRING(36.3025 33.5105, 36.302 33.505, 36.301 33.5, 36.3 33.495, 36.297 33.497, 36.305 33.492, 36.31 33.488, 36.325 33.485, 36.33 33.49, 36.34 33.48, 36.35 33.47, 36.345 33.46, 36.34 33.45)'), 4326)),
('R006', 'Muhajirin → Kafar Souseh', 'المهاجرين → كفرسوسة', 'microbus', '#6b1f2a', 6.5, 25, 2500,
    ST_SetSRID(ST_GeomFromText('LINESTRING(36.288 33.521, 36.286 33.519, 36.285 33.516, 36.282 33.517, 36.28 33.517, 36.285 33.5155, 36.29 33.5155, 36.288 33.513, 36.285 33.508, 36.283 33.503, 36.278 33.502, 36.275 33.502)'), 4326)),
('R007', 'Abbasiyyin → Harasta', 'العباسيين → حرستا', 'bus', '#4a151e', 8.0, 30, 2000,
    ST_SetSRID(ST_GeomFromText('LINESTRING(36.32 33.5175, 36.328 33.52, 36.335 33.522, 36.338 33.529, 36.34 33.535, 36.335 33.54, 36.318 33.545, 36.33 33.547, 36.355 33.55, 36.368 33.555, 36.38 33.56)'), 4326)),
('R008', 'Mezzeh → Dummar', 'المزة → دمر', 'microbus', '#3d3a3b', 11.0, 40, 3000,
    ST_SetSRID(ST_GeomFromText('LINESTRING(36.26 33.505, 36.255 33.504, 36.25 33.503, 36.255 33.508, 36.26 33.512, 36.27 33.518, 36.255 33.516, 36.24 33.515, 36.23 33.515, 36.22 33.518, 36.215 33.52, 36.235 33.5)'), 4326))
ON CONFLICT (route_id) DO NOTHING;

-- ============================================================
-- ROUTE-STOP ASSIGNMENTS
-- ============================================================

-- R001: Marjeh → Mezzeh Highway (9 stops)
INSERT INTO route_stops (route_id, stop_id, stop_sequence, distance_from_start_km, typical_arrival_offset_min) VALUES
((SELECT id FROM routes WHERE route_id='R001'), (SELECT id FROM stops WHERE stop_id='S001'), 1, 0.0, 0),
((SELECT id FROM routes WHERE route_id='R001'), (SELECT id FROM stops WHERE stop_id='S037'), 2, 1.2, 5),
((SELECT id FROM routes WHERE route_id='R001'), (SELECT id FROM stops WHERE stop_id='S004'), 3, 2.5, 10),
((SELECT id FROM routes WHERE route_id='R001'), (SELECT id FROM stops WHERE stop_id='S054'), 4, 3.8, 14),
((SELECT id FROM routes WHERE route_id='R001'), (SELECT id FROM stops WHERE stop_id='S007'), 5, 4.8, 18),
((SELECT id FROM routes WHERE route_id='R001'), (SELECT id FROM stops WHERE stop_id='S053'), 6, 5.8, 22),
((SELECT id FROM routes WHERE route_id='R001'), (SELECT id FROM stops WHERE stop_id='S005'), 7, 6.8, 28),
((SELECT id FROM routes WHERE route_id='R001'), (SELECT id FROM stops WHERE stop_id='S038'), 8, 7.5, 30),
((SELECT id FROM routes WHERE route_id='R001'), (SELECT id FROM stops WHERE stop_id='S006'), 9, 8.5, 35)
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- R002: Baramkeh → Barzeh (7 stops)
INSERT INTO route_stops (route_id, stop_id, stop_sequence, distance_from_start_km, typical_arrival_offset_min) VALUES
((SELECT id FROM routes WHERE route_id='R002'), (SELECT id FROM stops WHERE stop_id='S004'), 1, 0.0, 0),
((SELECT id FROM routes WHERE route_id='R002'), (SELECT id FROM stops WHERE stop_id='S003'), 2, 1.8, 8),
((SELECT id FROM routes WHERE route_id='R002'), (SELECT id FROM stops WHERE stop_id='S011'), 3, 3.5, 15),
((SELECT id FROM routes WHERE route_id='R002'), (SELECT id FROM stops WHERE stop_id='S017'), 4, 5.0, 22),
((SELECT id FROM routes WHERE route_id='R002'), (SELECT id FROM stops WHERE stop_id='S013'), 5, 7.0, 30),
((SELECT id FROM routes WHERE route_id='R002'), (SELECT id FROM stops WHERE stop_id='S016'), 6, 9.5, 40),
((SELECT id FROM routes WHERE route_id='R002'), (SELECT id FROM stops WHERE stop_id='S025'), 7, 12.0, 45)
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- R003: Umayyad → Qaboun (7 stops)
INSERT INTO route_stops (route_id, stop_id, stop_sequence, distance_from_start_km, typical_arrival_offset_min) VALUES
((SELECT id FROM routes WHERE route_id='R003'), (SELECT id FROM stops WHERE stop_id='S003'), 1, 0.0, 0),
((SELECT id FROM routes WHERE route_id='R003'), (SELECT id FROM stops WHERE stop_id='S019'), 2, 1.0, 6),
((SELECT id FROM routes WHERE route_id='R003'), (SELECT id FROM stops WHERE stop_id='S011'), 3, 2.5, 12),
((SELECT id FROM routes WHERE route_id='R003'), (SELECT id FROM stops WHERE stop_id='S013'), 4, 4.5, 20),
((SELECT id FROM routes WHERE route_id='R003'), (SELECT id FROM stops WHERE stop_id='S014'), 5, 6.5, 28),
((SELECT id FROM routes WHERE route_id='R003'), (SELECT id FROM stops WHERE stop_id='S015'), 6, 8.5, 36),
((SELECT id FROM routes WHERE route_id='R003'), (SELECT id FROM stops WHERE stop_id='S025'), 7, 10.5, 40)
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- R004: Old City → Jaramana (8 stops, added Shaghour)
INSERT INTO route_stops (route_id, stop_id, stop_sequence, distance_from_start_km, typical_arrival_offset_min) VALUES
((SELECT id FROM routes WHERE route_id='R004'), (SELECT id FROM stops WHERE stop_id='S035'), 1, 0.0, 0),
((SELECT id FROM routes WHERE route_id='R004'), (SELECT id FROM stops WHERE stop_id='S034'), 2, 0.8, 5),
((SELECT id FROM routes WHERE route_id='R004'), (SELECT id FROM stops WHERE stop_id='S033'), 3, 1.5, 10),
((SELECT id FROM routes WHERE route_id='R004'), (SELECT id FROM stops WHERE stop_id='S036'), 4, 2.5, 15),
((SELECT id FROM routes WHERE route_id='R004'), (SELECT id FROM stops WHERE stop_id='S044'), 5, 3.8, 19),
((SELECT id FROM routes WHERE route_id='R004'), (SELECT id FROM stops WHERE stop_id='S030'), 6, 5.0, 22),
((SELECT id FROM routes WHERE route_id='R004'), (SELECT id FROM stops WHERE stop_id='S027'), 7, 7.0, 30),
((SELECT id FROM routes WHERE route_id='R004'), (SELECT id FROM stops WHERE stop_id='S028'), 8, 9.0, 35)
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- R005: Marjeh → Sayyidah Zaynab (9 stops, added Tabbaleh & Bab Mousalla)
INSERT INTO route_stops (route_id, stop_id, stop_sequence, distance_from_start_km, typical_arrival_offset_min) VALUES
((SELECT id FROM routes WHERE route_id='R005'), (SELECT id FROM stops WHERE stop_id='S001'), 1, 0.0, 0),
((SELECT id FROM routes WHERE route_id='R005'), (SELECT id FROM stops WHERE stop_id='S043'), 2, 2.0, 8),
((SELECT id FROM routes WHERE route_id='R005'), (SELECT id FROM stops WHERE stop_id='S031'), 3, 3.5, 12),
((SELECT id FROM routes WHERE route_id='R005'), (SELECT id FROM stops WHERE stop_id='S032'), 4, 4.0, 15),
((SELECT id FROM routes WHERE route_id='R005'), (SELECT id FROM stops WHERE stop_id='S045'), 5, 5.5, 20),
((SELECT id FROM routes WHERE route_id='R005'), (SELECT id FROM stops WHERE stop_id='S030'), 6, 8.0, 28),
((SELECT id FROM routes WHERE route_id='R005'), (SELECT id FROM stops WHERE stop_id='S027'), 7, 10.0, 35),
((SELECT id FROM routes WHERE route_id='R005'), (SELECT id FROM stops WHERE stop_id='S029'), 8, 14.0, 45),
((SELECT id FROM routes WHERE route_id='R005'), (SELECT id FROM stops WHERE stop_id='S028'), 9, 18.0, 55)
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- R006: Muhajirin → Kafar Souseh (8 stops, added Kafar Souseh Flyover)
INSERT INTO route_stops (route_id, stop_id, stop_sequence, distance_from_start_km, typical_arrival_offset_min) VALUES
((SELECT id FROM routes WHERE route_id='R006'), (SELECT id FROM stops WHERE stop_id='S010'), 1, 0.0, 0),
((SELECT id FROM routes WHERE route_id='R006'), (SELECT id FROM stops WHERE stop_id='S009'), 2, 0.8, 4),
((SELECT id FROM routes WHERE route_id='R006'), (SELECT id FROM stops WHERE stop_id='S008'), 3, 1.5, 8),
((SELECT id FROM routes WHERE route_id='R006'), (SELECT id FROM stops WHERE stop_id='S020'), 4, 2.5, 12),
((SELECT id FROM routes WHERE route_id='R006'), (SELECT id FROM stops WHERE stop_id='S018'), 5, 3.5, 16),
((SELECT id FROM routes WHERE route_id='R006'), (SELECT id FROM stops WHERE stop_id='S021'), 6, 4.8, 20),
((SELECT id FROM routes WHERE route_id='R006'), (SELECT id FROM stops WHERE stop_id='S054'), 7, 5.5, 22),
((SELECT id FROM routes WHERE route_id='R006'), (SELECT id FROM stops WHERE stop_id='S007'), 8, 6.5, 25)
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- R007: Abbasiyyin → Harasta (6 stops)
INSERT INTO route_stops (route_id, stop_id, stop_sequence, distance_from_start_km, typical_arrival_offset_min) VALUES
((SELECT id FROM routes WHERE route_id='R007'), (SELECT id FROM stops WHERE stop_id='S013'), 1, 0.0, 0),
((SELECT id FROM routes WHERE route_id='R007'), (SELECT id FROM stops WHERE stop_id='S014'), 2, 1.5, 8),
((SELECT id FROM routes WHERE route_id='R007'), (SELECT id FROM stops WHERE stop_id='S015'), 3, 3.5, 16),
((SELECT id FROM routes WHERE route_id='R007'), (SELECT id FROM stops WHERE stop_id='S016'), 4, 5.0, 22),
((SELECT id FROM routes WHERE route_id='R007'), (SELECT id FROM stops WHERE stop_id='S025'), 5, 6.5, 28),
((SELECT id FROM routes WHERE route_id='R007'), (SELECT id FROM stops WHERE stop_id='S026'), 6, 8.0, 30)
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- R008: Mezzeh → Dummar (7 stops, added Mezzeh Villas)
INSERT INTO route_stops (route_id, stop_id, stop_sequence, distance_from_start_km, typical_arrival_offset_min) VALUES
((SELECT id FROM routes WHERE route_id='R008'), (SELECT id FROM stops WHERE stop_id='S005'), 1, 0.0, 0),
((SELECT id FROM routes WHERE route_id='R008'), (SELECT id FROM stops WHERE stop_id='S038'), 2, 1.5, 6),
((SELECT id FROM routes WHERE route_id='R008'), (SELECT id FROM stops WHERE stop_id='S048'), 3, 2.5, 10),
((SELECT id FROM routes WHERE route_id='R008'), (SELECT id FROM stops WHERE stop_id='S041'), 4, 4.0, 14),
((SELECT id FROM routes WHERE route_id='R008'), (SELECT id FROM stops WHERE stop_id='S039'), 5, 7.0, 28),
((SELECT id FROM routes WHERE route_id='R008'), (SELECT id FROM stops WHERE stop_id='S040'), 6, 9.0, 36),
((SELECT id FROM routes WHERE route_id='R008'), (SELECT id FROM stops WHERE stop_id='S022'), 7, 11.0, 40)
ON CONFLICT (route_id, stop_sequence) DO NOTHING;

-- ============================================================
-- VEHICLES (24 vehicles across fleet)
-- ============================================================

INSERT INTO vehicles (vehicle_id, name, name_ar, vehicle_type, capacity, status, assigned_route_id) VALUES
-- Buses (12)
('BUS-001', 'Bus Damascus 001', 'باص دمشق 001', 'bus', 45, 'active', (SELECT id FROM routes WHERE route_id='R001')),
('BUS-002', 'Bus Damascus 002', 'باص دمشق 002', 'bus', 45, 'active', (SELECT id FROM routes WHERE route_id='R001')),
('BUS-003', 'Bus Damascus 003', 'باص دمشق 003', 'bus', 45, 'active', (SELECT id FROM routes WHERE route_id='R002')),
('BUS-004', 'Bus Damascus 004', 'باص دمشق 004', 'bus', 45, 'active', (SELECT id FROM routes WHERE route_id='R002')),
('BUS-005', 'Bus Damascus 005', 'باص دمشق 005', 'bus', 45, 'active', (SELECT id FROM routes WHERE route_id='R003')),
('BUS-006', 'Bus Damascus 006', 'باص دمشق 006', 'bus', 45, 'active', (SELECT id FROM routes WHERE route_id='R003')),
('BUS-007', 'Bus Damascus 007', 'باص دمشق 007', 'bus', 45, 'active', (SELECT id FROM routes WHERE route_id='R005')),
('BUS-008', 'Bus Damascus 008', 'باص دمشق 008', 'bus', 45, 'active', (SELECT id FROM routes WHERE route_id='R005')),
('BUS-009', 'Bus Damascus 009', 'باص دمشق 009', 'bus', 45, 'active', (SELECT id FROM routes WHERE route_id='R007')),
('BUS-010', 'Bus Damascus 010', 'باص دمشق 010', 'bus', 45, 'idle', NULL),
('BUS-011', 'Bus Damascus 011', 'باص دمشق 011', 'bus', 45, 'maintenance', NULL),
('BUS-012', 'Bus Damascus 012', 'باص دمشق 012', 'bus', 45, 'idle', NULL),
-- Microbuses (8)
('MIC-001', 'Microbus 001', 'ميكروباص 001', 'microbus', 14, 'active', (SELECT id FROM routes WHERE route_id='R004')),
('MIC-002', 'Microbus 002', 'ميكروباص 002', 'microbus', 14, 'active', (SELECT id FROM routes WHERE route_id='R004')),
('MIC-003', 'Microbus 003', 'ميكروباص 003', 'microbus', 14, 'active', (SELECT id FROM routes WHERE route_id='R006')),
('MIC-004', 'Microbus 004', 'ميكروباص 004', 'microbus', 14, 'active', (SELECT id FROM routes WHERE route_id='R006')),
('MIC-005', 'Microbus 005', 'ميكروباص 005', 'microbus', 14, 'active', (SELECT id FROM routes WHERE route_id='R008')),
('MIC-006', 'Microbus 006', 'ميكروباص 006', 'microbus', 14, 'active', (SELECT id FROM routes WHERE route_id='R008')),
('MIC-007', 'Microbus 007', 'ميكروباص 007', 'microbus', 14, 'idle', NULL),
('MIC-008', 'Microbus 008', 'ميكروباص 008', 'microbus', 14, 'idle', NULL),
-- Taxis (4)
('TAX-001', 'Taxi 001', 'تاكسي 001', 'taxi', 4, 'active', NULL),
('TAX-002', 'Taxi 002', 'تاكسي 002', 'taxi', 4, 'active', NULL),
('TAX-003', 'Taxi 003', 'تاكسي 003', 'taxi', 4, 'active', NULL),
('TAX-004', 'Taxi 004', 'تاكسي 004', 'taxi', 4, 'idle', NULL)
ON CONFLICT (vehicle_id) DO NOTHING;

-- ============================================================
-- SCHEDULES (daily service)
-- ============================================================

-- Weekdays (Sunday=0 to Thursday=4) — peak (15min) / off-peak (30min)
-- Morning peak: 06:00-09:00
INSERT INTO schedules (route_id, day_of_week, first_departure, last_departure, frequency_min)
SELECT r.id, d.dow, '06:00'::TIME, '09:00'::TIME, 15
FROM routes r CROSS JOIN (VALUES (0),(1),(2),(3),(4)) AS d(dow)
WHERE r.is_active = true;

-- Midday off-peak: 09:00-16:00
INSERT INTO schedules (route_id, day_of_week, first_departure, last_departure, frequency_min)
SELECT r.id, d.dow, '09:00'::TIME, '16:00'::TIME, 30
FROM routes r CROSS JOIN (VALUES (0),(1),(2),(3),(4)) AS d(dow)
WHERE r.is_active = true;

-- Evening peak: 16:00-19:00
INSERT INTO schedules (route_id, day_of_week, first_departure, last_departure, frequency_min)
SELECT r.id, d.dow, '16:00'::TIME, '19:00'::TIME, 15
FROM routes r CROSS JOIN (VALUES (0),(1),(2),(3),(4)) AS d(dow)
WHERE r.is_active = true;

-- Night off-peak: 19:00-23:00
INSERT INTO schedules (route_id, day_of_week, first_departure, last_departure, frequency_min)
SELECT r.id, d.dow, '19:00'::TIME, '23:00'::TIME, 30
FROM routes r CROSS JOIN (VALUES (0),(1),(2),(3),(4)) AS d(dow)
WHERE r.is_active = true;

-- Friday & Saturday (reduced service, flat 25min)
INSERT INTO schedules (route_id, day_of_week, first_departure, last_departure, frequency_min)
SELECT r.id, d.dow, '07:00'::TIME, '22:00'::TIME, 25
FROM routes r CROSS JOIN (VALUES (5),(6)) AS d(dow)
WHERE r.is_active = true;

-- ============================================================
-- GEOFENCES (key zones)
-- ============================================================

INSERT INTO geofences (name, name_ar, geometry, geofence_type, speed_limit_kmh) VALUES
('Damascus City Center', 'وسط مدينة دمشق',
    ST_SetSRID(ST_GeomFromText('POLYGON((36.295 33.505, 36.325 33.505, 36.325 33.525, 36.295 33.525, 36.295 33.505))'), 4326),
    'zone', 30),
('Western Bus Station', 'محطة السومرية',
    ST_SetSRID(ST_GeomFromText('POLYGON((36.230 33.496, 36.240 33.496, 36.240 33.504, 36.230 33.504, 36.230 33.496))'), 4326),
    'terminal', 20),
('Old City Zone', 'منطقة المدينة القديمة',
    ST_SetSRID(ST_GeomFromText('POLYGON((36.305 33.508, 36.322 33.508, 36.322 33.516, 36.305 33.516, 36.305 33.508))'), 4326),
    'zone', 20);

-- ============================================================
-- DRIVER → VEHICLE ASSIGNMENTS (18 active vehicles)
-- ============================================================

UPDATE vehicles SET assigned_driver_id = (SELECT id FROM users WHERE email='driver01@damascustransit.sy') WHERE vehicle_id='BUS-001';
UPDATE vehicles SET assigned_driver_id = (SELECT id FROM users WHERE email='driver02@damascustransit.sy') WHERE vehicle_id='BUS-002';
UPDATE vehicles SET assigned_driver_id = (SELECT id FROM users WHERE email='driver03@damascustransit.sy') WHERE vehicle_id='BUS-003';
UPDATE vehicles SET assigned_driver_id = (SELECT id FROM users WHERE email='driver04@damascustransit.sy') WHERE vehicle_id='BUS-004';
UPDATE vehicles SET assigned_driver_id = (SELECT id FROM users WHERE email='driver05@damascustransit.sy') WHERE vehicle_id='BUS-005';
UPDATE vehicles SET assigned_driver_id = (SELECT id FROM users WHERE email='driver06@damascustransit.sy') WHERE vehicle_id='BUS-006';
UPDATE vehicles SET assigned_driver_id = (SELECT id FROM users WHERE email='driver07@damascustransit.sy') WHERE vehicle_id='BUS-007';
UPDATE vehicles SET assigned_driver_id = (SELECT id FROM users WHERE email='driver08@damascustransit.sy') WHERE vehicle_id='BUS-008';
UPDATE vehicles SET assigned_driver_id = (SELECT id FROM users WHERE email='driver09@damascustransit.sy') WHERE vehicle_id='BUS-009';
UPDATE vehicles SET assigned_driver_id = (SELECT id FROM users WHERE email='driver10@damascustransit.sy') WHERE vehicle_id='MIC-001';
UPDATE vehicles SET assigned_driver_id = (SELECT id FROM users WHERE email='driver11@damascustransit.sy') WHERE vehicle_id='MIC-002';
UPDATE vehicles SET assigned_driver_id = (SELECT id FROM users WHERE email='driver12@damascustransit.sy') WHERE vehicle_id='MIC-003';
UPDATE vehicles SET assigned_driver_id = (SELECT id FROM users WHERE email='driver13@damascustransit.sy') WHERE vehicle_id='MIC-004';
UPDATE vehicles SET assigned_driver_id = (SELECT id FROM users WHERE email='driver14@damascustransit.sy') WHERE vehicle_id='MIC-005';
UPDATE vehicles SET assigned_driver_id = (SELECT id FROM users WHERE email='driver15@damascustransit.sy') WHERE vehicle_id='MIC-006';
UPDATE vehicles SET assigned_driver_id = (SELECT id FROM users WHERE email='driver16@damascustransit.sy') WHERE vehicle_id='TAX-001';
UPDATE vehicles SET assigned_driver_id = (SELECT id FROM users WHERE email='driver17@damascustransit.sy') WHERE vehicle_id='TAX-002';
UPDATE vehicles SET assigned_driver_id = (SELECT id FROM users WHERE email='driver18@damascustransit.sy') WHERE vehicle_id='TAX-003';
