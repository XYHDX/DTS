# خارطة الطريق: من تشغيل GPS إلى رؤيته في تطبيق الهاتف
# Roadmap: from initializing a GPS unit to seeing it live on iOS & Android

This is the **complete, ordered path**. Each stage says what you do, what must be
true before it, and how to *prove* it worked before moving on. Times assume the
backend is already deployed (Vercel or Docker — `docs/DEPLOY.md`).

```
Stage 0   Prerequisites (backend live, migrations applied)
Stage 1   Bench-test the GPS unit (serial, clean fix)            ~30 min
Stage 2   Point the device at the backend (HTTP bridge first)    ~30 min
Stage 3   Register vehicle + driver, link the device ID          ~10 min
Stage 4   ADMIN APPROVAL — the gate                              ~1 min
Stage 5   Switch the device to MQTT (production transport)       ~30 min
Stage 6   Watch it on the web map + Grafana                      ~10 min
Stage 7   Build & run the iOS / Android app and see the bus      ~1–2 h first time
Stage 8   (When ready) store rollout + real Sham Cash payments
```

---

## Stage 0 — Prerequisites · المتطلبات

* Backend reachable: `curl https://<your-host>/api/health` → `{"status":"ok"...}`.
* **All migrations applied through `020`** (`docs/APPLY_MIGRATIONS.md`). The
  approval workflow (019) and payments (020) must exist before devices register.
* Env vars set (`.env.example` documents each): at minimum `JWT_SECRET`,
  `SUPABASE_*`, `ALLOWED_ORIGINS`, `DEVICE_INGEST_SECRET` (invent a long random
  string — it is the shared secret your GPS units will sign frames with),
  `DEFAULT_OPERATOR_SLUG=damascus`.
* An admin account and an operator (dispatcher) account exist
  (`docs/DEMO_ACCOUNTS.md` for the seeded ones — rotate those passwords).

## Stage 1 — Bench-test the GPS unit · فحص الوحدة على الطاولة

Hardware reference: `firmware/SPEC.md` (MCU, modem, GPS module, power, watchdog).

1. Power the board (bench supply or USB), antenna near a window.
2. Open the serial monitor. Wait for a **clean fix**: ≥ 4 satellites and
   **HDOP ≤ 5** (you saw 10 sats / HDOP 1.0 on your unit — that's excellent).
3. Verify the unit prints: latitude, longitude, speed (from `$GPVTG`), course,
   date+time (UTC, **from the GPS fix, never the modem clock**), satellite
   count, HDOP.
4. Note the unit's identifier — you will register it as `gps_device_id`
   (e.g. `DTS-GPS-0042`). Put a printed sticker with this ID on the unit.

✅ **Exit check:** stable coordinates that match where you actually are.

## Stage 2 — First light to the backend (HTTP bridge) · أول إرسال للخادم

Use HTTPS first — it needs no broker and proves your payload is right.
Full field-by-field contract: [HARDWARE_SETUP.md](HARDWARE_SETUP.md) §1.

1. The exact JSON the server accepts (names must match **exactly** — the classic
   mistakes are `car_id` instead of `vehicle_id`, and a missing `operator_id`):

```json
{
  "vehicle_id": "DAM-104",
  "operator_id": "00000000-0000-0000-0000-000000000001",
  "timestamp": 1781048676000,
  "latitude": 33.520229,
  "longitude": 36.286177,
  "speed_kph": 12.4,
  "heading": 170.4,
  "satellite_count": 10,
  "hdop": 1.0
}
```

2. Sign the **raw body** with HMAC-SHA256 using `DEVICE_INGEST_SECRET`, hex-encode,
   send as the `X-Device-Signature` header:

```
POST https://<your-host>/api/v1/telemetry/json
Content-Type: application/json
X-Device-Signature: <hex hmac>
```

3. Simulate it from your laptop before flashing firmware:

```bash
BODY='{"vehicle_id":"DAM-104","operator_id":"00000000-0000-0000-0000-000000000001","timestamp":'$(date +%s000)',"latitude":33.5202,"longitude":36.2861,"speed_kph":0}'
SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$DEVICE_INGEST_SECRET" -hex | awk '{print $2}')
curl -i -X POST "https://<your-host>/api/v1/telemetry/json" \
     -H "Content-Type: application/json" -H "X-Device-Signature: $SIG" -d "$BODY"
```

✅ **Exit check:** HTTP **204**. A 401 means the signature/secret mismatch; a 404
in production means `DEV_INGEST_ENABLED` isn't set (it's allowed in dev only —
use the protobuf endpoint or enable it deliberately).

> ⚠️ At this stage the frame is accepted but **dropped before the map** if the
> vehicle isn't registered+approved yet — the log will show
> `telemetry_dropped_unapproved`. That's Stage 3+4's job. (Unknown
> `vehicle_id`s are dropped the same way — devices can't invent buses.)

## Stage 3 — Register the vehicle, driver, and device · التسجيل

Done by the **operator** in the dashboard — full detail in
[OPERATOR_GUIDE.md](OPERATOR_GUIDE.md):

1. `/admin/vehicles.html` → **+ إضافة مركبة** → fleet code `DAM-104`, type, capacity,
   and **معرّف جهاز GPS = the sticker ID from Stage 1** (`DTS-GPS-0042`).
2. `/admin/users.html` → **+ إضافة مستخدم** → create the driver (email + temporary
   password) and link them to `DAM-104` in the same form.
3. `/admin/routes.html` if the route doesn't exist yet → assign it on the
   Vehicles page (**تعيين / Assign**).

✅ **Exit check:** Vehicles page shows `DAM-104` with driver, route, and badge
**قيد الانتظار / Pending**.

## Stage 4 — Admin approval · الاعتماد (THE GATE)

The **admin** opens `/admin/approvals.html` (the sidebar badge shows the count),
reviews the card — vehicle, type, operator's driver, GPS ID — and clicks
**اعتماد / Approve**. ([ADMIN_GUIDE.md](ADMIN_GUIDE.md) §2 has the checklist.)

From this second: telemetry is accepted onto the map, the driver can start
trips, and the payment QR becomes valid.

✅ **Exit check:** badge turns **معتمدة / Approved**; the driver console's yellow
banner disappears.

## Stage 5 — Switch the device to MQTT · الانتقال إلى MQTT

Same JSON, different transport — built for cellular reliability
([HARDWARE_SETUP.md](HARDWARE_SETUP.md) §2 explains brokers + topics).

```bash
# dev broker + consumer
docker compose -f docker-compose.scale.yml up -d mosquitto redis
python -m api.workers.mqtt_consumer

# device publishes to:
#   vehicles/DAM-104/status   (QoS 0, periodic pings)
#   vehicles/DAM-104/event    (QoS 1, ignition/panic events)

# watch every frame live while testing:
mosquitto_sub -h <broker-host> -t 'vehicles/#' -v
```

Firmware behaviour (per `firmware/SPEC.md`): adaptive heartbeat — **10 s moving,
60 s idling, deep sleep parked**; offline frames buffered to flash and replayed
with `is_replay=true`; HDOP > 5 or < 4 sats rejected on-device.

✅ **Exit check:** consumer logs `mqtt_consumer_connected` then steady ingest;
no `mqtt_frame_invalid`.

## Stage 6 — See it on the web + monitoring · المشاهدة على الويب

1. Public map `/` (or passenger app `/passenger/`): your vehicle appears and
   moves. The marker comes via SSE (`/api/stream`) — sub-second after each frame.
2. Admin Overview map shows it too, with occupancy once trips run.
3. Grafana (`docker compose -f docker-compose.scale.yml up -d`, then
   `http://localhost:3001`): **API Overview** dashboard — telemetry ingest rate
   should tick once per heartbeat. History queries come from TimescaleDB
   ([HARDWARE_SETUP.md](HARDWARE_SETUP.md) §3).

✅ **Exit check:** drive around the block; the marker follows you with ≤ 15 s lag.

## Stage 7 — The iOS & Android app · تطبيق الهاتف

The official mobile app is **`flutter_app/`** (one Dart codebase → both
platforms). It talks to the same API the web uses.

### 7.1 One-time machine setup

* Install **Flutter 3.22+** (`flutter doctor` must be clean).
* **Android:** Android Studio + an emulator, or a real phone with USB debugging.
* **iOS:** a Mac with Xcode 15+; for a real iPhone you need a (free or paid)
  Apple developer account for local signing.

### 7.2 Point the app at your backend

The API base URL is injected at build time (`lib/core/api_client.dart`):

```bash
cd flutter_app
flutter pub get

# Android emulator (10.0.2.2 = your laptop's localhost) against a local API:
flutter run --dart-define=API_BASE=http://10.0.2.2:8000

# Real phone / production backend:
flutter run --dart-define=API_BASE=https://<your-host>
```

### 7.3 What you should see

1. **Passenger home** opens with the Damascus map → your approved vehicle
   `DAM-104` is moving on it (the app subscribes to the same `/api/stream` SSE).
2. **Routes** tab lists the routes you created; opening one shows its vehicles.
3. **Driver mode:** log in with the driver account → `/driver` screen → start a
   trip from the phone. (Driver login requires the password already rotated —
   first login is easiest in the web console.)
4. Pull to refresh / watch live: positions update without reloading.

### 7.4 Release builds (when you're ready to distribute)

```bash
# Android — installable APK (sideload) or AAB (Play Store):
flutter build apk --release --dart-define=API_BASE=https://<your-host>
flutter build appbundle --release --dart-define=API_BASE=https://<your-host>

# iOS (on the Mac):
flutter build ipa --release --dart-define=API_BASE=https://<your-host>
```

✅ **Exit check:** the same bus moving on the web map moves in the app on both an
Android device and an iPhone.

## Stage 8 — Production rollout · الإطلاق

* **Stores:** Firebase config (push notifications), Apple Developer Program,
  Google Play Console — costs, timelines, the 12-tester rule, and the
  organization-account advice are all in
  [HARDWARE_SETUP.md](HARDWARE_SETUP.md) §5–§7.
* **Payments go live:** obtain Sham Cash merchant credentials, set
  `SHAM_CASH_MODE=live` + secrets (`.env.example`), and the sandbox QR flow
  becomes real money — no code changes (`docs/ARCHITECTURE_DECISIONS.md` §10).
* **Fleet scale-out:** repeat Stages 1→4 per vehicle. Frames from anything
  unregistered or unapproved are dropped automatically, so a misconfigured
  device can never pollute the map.

---

## Troubleshooting quick table · جدول الأعطال

| Symptom | Stage | Fix |
|---|---|---|
| `401 Invalid device signature` | 2/5 | `DEVICE_INGEST_SECRET` mismatch, or you signed the *pretty-printed* JSON instead of the exact raw bytes sent |
| 204 accepted but nothing on the map | 3/4 | vehicle not registered (`vehicle_id` mismatch), not **approved**, or `operator_id` missing from the frame |
| Marker frozen | 5 | device stopped publishing — check broker connectivity, FIFO drain, `mosquitto_sub` |
| Wrong position / jumping | 1 | weak fix — HDOP > 5; reposition antenna |
| Timestamps hours off | 1 | modem clock used instead of GPS UTC, or seconds instead of **milliseconds** |
| App shows no vehicles | 7 | wrong `API_BASE` (emulator must use `10.0.2.2`, not `localhost`); or the backend's `ALLOWED_ORIGINS`/network blocks the device |
| Driver can't start trip | 4 | vehicle still pending/suspended, or no route assigned |
