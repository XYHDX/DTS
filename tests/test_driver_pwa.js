/**
 * Driver PWA frontend logic tests.
 * Covers: DAM-197 — haversine distance, route adherence, speed warnings,
 * ETA calculation, passenger counter, and demo simulation bounds.
 *
 * Run with: node tests/test_driver_pwa.js
 */

'use strict';

// ─── Extracted from public/driver/index.html ───

const SPEED_LIMIT_KMH = 60;
const OFF_ROUTE_THRESHOLD_KM = 0.3;

const ROUTE_STOPS = [
  { name: "Al-Marjeh Square",    nameAr: "ساحة المرجة",     lat: 33.5117, lon: 36.2963 },
  { name: "Hijaz Station",       nameAr: "محطة الحجاز",     lat: 33.5133, lon: 36.2936 },
  { name: "Baramkeh",            nameAr: "البرامكة",        lat: 33.5096, lon: 36.2913 },
  { name: "Shaalan",             nameAr: "الشعلان",         lat: 33.5125, lon: 36.2810 },
  { name: "Jisr Al-Abyad",       nameAr: "جسر الأبيض",     lat: 33.5115, lon: 36.2750 },
  { name: "Mazzeh Jabal",        nameAr: "مزة جبل",         lat: 33.5090, lon: 36.2650 },
  { name: "Western Bus Station", nameAr: "المحطة الغربية",  lat: 33.5098, lon: 36.2587 },
];

function haversine(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function pointToSegmentDist(lat, lon, a, b) {
  const ax = a.lon, ay = a.lat, bx = b.lon, by = b.lat;
  const px = lon, py = lat;
  const dx = bx - ax, dy = by - ay;
  if (dx === 0 && dy === 0) return haversine(lat, lon, a.lat, a.lon);
  const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)));
  return haversine(lat, lon, ay + t * dy, ax + t * dx);
}

function isOnRoute(lat, lon) {
  let minDist = Infinity;
  for (let i = 0; i < ROUTE_STOPS.length - 1; i++) {
    const d = pointToSegmentDist(lat, lon, ROUTE_STOPS[i], ROUTE_STOPS[i + 1]);
    if (d < minDist) minDist = d;
  }
  return minDist < OFF_ROUTE_THRESHOLD_KM;
}

function isOverSpeed(speedKmh) {
  return speedKmh > SPEED_LIMIT_KMH;
}

function calcEtaMinutes(lat, lon, stopLat, stopLon, speedKmh) {
  if (speedKmh <= 0) return null;
  const dist = haversine(lat, lon, stopLat, stopLon);
  return Math.ceil(dist / speedKmh * 60);
}

function adjustPassengers(current, delta) {
  return Math.max(0, current + delta);
}

// ─── Test harness ───

let passed = 0;
let failed = 0;

function assert(condition, label) {
  if (condition) {
    console.log(`  ✅ PASS: ${label}`);
    passed++;
  } else {
    console.error(`  ❌ FAIL: ${label}`);
    failed++;
  }
}

function assertEqual(actual, expected, label) {
  if (actual === expected) {
    console.log(`  ✅ PASS: ${label}`);
    passed++;
  } else {
    console.error(`  ❌ FAIL: ${label} — expected ${expected}, got ${actual}`);
    failed++;
  }
}

function assertClose(actual, expected, tolerance, label) {
  if (Math.abs(actual - expected) <= tolerance) {
    console.log(`  ✅ PASS: ${label}`);
    passed++;
  } else {
    console.error(`  ❌ FAIL: ${label} — expected ~${expected}, got ${actual}`);
    failed++;
  }
}

// ─── Haversine distance ───

console.log('\n── Haversine Distance ──');

// Al-Marjeh → Hijaz Station: approx 0.25 km
assertClose(
  haversine(33.5117, 36.2963, 33.5133, 36.2936),
  0.28, 0.1,
  'Al-Marjeh to Hijaz Station distance ~0.28 km'
);

// Marjeh → Western Bus Station: approx 3.9 km
assertClose(
  haversine(33.5117, 36.2963, 33.5098, 36.2587),
  3.9, 0.5,
  'Full route length Al-Marjeh to Western ~3.9 km'
);

// Same point = 0 distance
assertEqual(haversine(33.5117, 36.2963, 33.5117, 36.2963), 0, 'Same point = 0 km');

// ─── Route Adherence ───

console.log('\n── Route Adherence ──');

// Exactly on a stop → on route
assert(isOnRoute(33.5117, 36.2963), 'Standing at Al-Marjeh stop → on route');
assert(isOnRoute(33.5133, 36.2936), 'Standing at Hijaz Station → on route');
assert(isOnRoute(33.5098, 36.2587), 'Standing at Western Bus Station → on route');

// On the line segment between stops → on route
const midLat = (33.5117 + 33.5133) / 2;
const midLon = (36.2963 + 36.2936) / 2;
assert(isOnRoute(midLat, midLon), 'Midpoint of first segment → on route');

// Far off route (Airport Road area)
assert(!isOnRoute(33.4150, 36.5200), 'Airport area → off route');
assert(!isOnRoute(33.6000, 36.1000), 'North Damascus → off route');

// Just outside threshold (~0.4 km perpendicular off route)
assert(!isOnRoute(33.5117 + 0.005, 36.2963), 'Point 0.5 km north of Marjeh → off route');

// ─── pointToSegmentDist — degenerate segment (same endpoints) ───

console.log('\n── pointToSegmentDist — Edge Cases ──');

// When a === b, should fall back to haversine(point, a)
const degenerateDist = pointToSegmentDist(33.5117, 36.2963, ROUTE_STOPS[0], ROUTE_STOPS[0]);
assertClose(degenerateDist, 0, 0.001, 'Degenerate segment (a===b) at same point = 0');

// ─── Speed Warning ───

console.log('\n── Speed Warning Logic ──');

assert(!isOverSpeed(0), 'Stopped (0 km/h) → no warning');
assert(!isOverSpeed(30), '30 km/h urban speed → no warning');
assert(!isOverSpeed(60), 'Exactly 60 km/h → no warning (limit is >60)');
assert(isOverSpeed(61), '61 km/h → over speed limit');
assert(isOverSpeed(80), '80 km/h → over speed limit');
assert(isOverSpeed(120), '120 km/h → over speed limit');

// ─── ETA Calculation ───

console.log('\n── ETA Calculation ──');

// 1 km at 30 km/h = 2 min
assertEqual(calcEtaMinutes(33.51, 36.29, 33.51, 36.2985, 30), 2, 'ETA ~2 min for short segment at 30 km/h');

// Zero speed → null (cannot estimate)
assertEqual(calcEtaMinutes(33.51, 36.29, 33.5133, 36.2936, 0), null, 'Speed=0 → ETA null');

// Negative speed → null
assertEqual(calcEtaMinutes(33.51, 36.29, 33.5133, 36.2936, -5), null, 'Negative speed → ETA null');

// Very fast speed → rounds up to at least 1 min
const etaFast = calcEtaMinutes(33.5117, 36.2963, 33.5133, 36.2936, 120);
assert(etaFast >= 1, 'Fast speed still gives at least 1 min ETA');

// ─── Passenger Counter ───

console.log('\n── Passenger Counter ──');

assertEqual(adjustPassengers(0, 1), 1, 'Add 1 from 0 = 1');
assertEqual(adjustPassengers(10, 5), 15, 'Add 5 to 10 = 15');
assertEqual(adjustPassengers(1, -1), 0, 'Remove 1 from 1 = 0');
assertEqual(adjustPassengers(0, -1), 0, 'Cannot go below 0 (floor at 0)');
assertEqual(adjustPassengers(0, -5), 0, 'Large decrement from 0 stays at 0');
assertEqual(adjustPassengers(3, -10), 0, 'Decrement below 0 is clamped to 0');

// ─── Demo Simulation Bounds ───

console.log('\n── Demo Simulation ──');

// Simulated positions should stay within Damascus city bounding box
const DAMASCUS_BBOX = { minLat: 33.45, maxLat: 33.58, minLon: 36.20, maxLon: 36.40 };

for (let step = 0; step < ROUTE_STOPS.length - 1; step++) {
  for (let progress = 0; progress <= 1; progress += 0.25) {
    const from = ROUTE_STOPS[step];
    const to = ROUTE_STOPS[step + 1];
    const lat = from.lat + (to.lat - from.lat) * progress;
    const lon = from.lon + (to.lon - from.lon) * progress;
    assert(
      lat >= DAMASCUS_BBOX.minLat && lat <= DAMASCUS_BBOX.maxLat &&
      lon >= DAMASCUS_BBOX.minLon && lon <= DAMASCUS_BBOX.maxLon,
      `Simulated position (step=${step}, p=${progress}) within Damascus bbox`
    );
  }
}

// ─── Route stops completeness ───

console.log('\n── Route Stops Data ──');

assertEqual(ROUTE_STOPS.length, 7, 'Route has 7 stops');
assert(ROUTE_STOPS.every(s => s.name && s.nameAr), 'All stops have English and Arabic names');
assert(ROUTE_STOPS.every(s => s.lat > 33.4 && s.lat < 33.6), 'All stop latitudes in Damascus range');
assert(ROUTE_STOPS.every(s => s.lon > 36.2 && s.lon < 36.4), 'All stop longitudes in Damascus range');

// ─── Summary ───

console.log(`\n${'─'.repeat(50)}`);
console.log(`Driver PWA JS Tests: ${passed} passed, ${failed} failed`);

if (failed > 0) {
  process.exit(1);
}
