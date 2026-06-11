# إعداد العتاد — Hardware ↔ Software Setup

**Last updated:** 2026-06-11
**Who this is for:** whoever wires the GPS/SIM units into vehicles and connects
them to the backend, stands up monitoring, and prepares the store accounts.
For the full journey from a bare GPS unit to the phone app, follow
[GPS_TO_APP_ROADMAP.md](GPS_TO_APP_ROADMAP.md) — this file is the deep
reference for Parts 1–4 of that roadmap.

This guide answers, in order:

1. [Your SIM/GPS device → the backend — exactly what data to send](#part-1)
2. [The broker and the topics (MQTT)](#part-2)
3. [Grafana + the time-series DB ("Influx" → what you actually have)](#part-3)
4. [Monitoring everything + debugging errors](#part-4)
5. [Firebase service account — what and why](#part-5)
6. [Apple App Store enrollment](#part-6)
7. [Google Play Store enrollment](#part-7)
8. [Recommended order of operations](#part-8)

---

<a name="part-1"></a>
## 1. Your SIM/GPS device → the backend — what data I need

Your serial monitor is already producing a clean fix (10 satellites, HDOP 1.00 — that's a good lock). The backend doesn't need *all* of it, and two fields in your current payload will stop it from working. Here is the contract.

### The contract (what the server accepts)

The backend ingest (`api/routers/mqtt_ingest.py` → `_PartialDecode`, mirroring `schemas/telematics.proto`) accepts this shape. Field names must match **exactly**:

| Field | Type | Required? | Your serial line | Notes |
|---|---|---|---|---|
| `vehicle_id` | string | **Yes** | (your `car_01`) | **Rename `car_id` → `vehicle_id`.** This is the #1 fix. |
| `timestamp` | int (ms since epoch) | **Yes** | `Date` + `UTC Time` | Milliseconds since 1970, UTC. Not the modem clock — use the GPS fix. |
| `latitude` | float | **Yes** | `Latitude: 33.520229` | as-is |
| `longitude` | float | **Yes** | `Longitude: 36.286177` | as-is |
| `operator_id` | string | **Strongly** | — (add it) | **Without this the live map won't update** (see box below). Use your operator UUID. |
| `speed_kph` | float | optional | `Speed km/h: 0.85` | note the name is `speed_kph`, not `speed_kmh` |
| `heading` | float | optional | `Course degree: 170.41` | 0–360 from north |
| `engine_state` | bool | optional | — | from your ACC/ignition line; defaults `false` |
| `satellite_count` | int | optional | `Satellites: 10` | health breadcrumb |
| `hdop` | float | optional | `HDOP: 1.00` | health breadcrumb; server rejects junk fixes with it |
| `fuel_level` | float | optional | — | 0–100 if you have a sender |
| `trigger_event` | int | optional | — | `0` = periodic ping (default) |
| `route_id`, `driver_id`, `trip_id` | string | optional | — | populated by ops, not the device |
| `cell_signal_dbm`, `firmware_version`, `battery_mv` | int | optional | — | health breadcrumbs |

**Drop these — the backend doesn't use them:** `Altitude`, `Location Age`, `Chars Processed`, `Failed Checksums`. They're useful *on the device* for debugging, but don't send them.

> ⚠️ **Two changes that matter most**
> 1. **`car_id` → `vehicle_id`.** Your code currently builds `"car_id":"car_01"`. The server ignores `car_id`, so every frame is rejected as "missing vehicle_id."
> 2. **Add `operator_id`.** The live-map cache (Redis Geo) and the new live SSE stream (S3.4) only fire when `operator_id` is present (`_ingest` gates the geo write on it). Without it, the frame is *stored* but never shows on the map. Use your seeded Damascus operator UUID: `00000000-0000-0000-0000-000000000001` (or your real operator's `id` from the `operators` table).

### The minimal correct payload

This is all you need to send for a vehicle to appear and move on the map:

```json
{
  "vehicle_id": "car_01",
  "operator_id": "00000000-0000-0000-0000-000000000001",
  "timestamp": 1781048676000,
  "latitude": 33.520229,
  "longitude": 36.286177,
  "speed_kph": 0.85,
  "heading": 170.41,
  "satellite_count": 10,
  "hdop": 1.00
}
```

### Getting `timestamp` right (ms since epoch)

You have `Date: 10/06/2026` and `UTC Time: 23:44:36`. The server wants that as **milliseconds since the Unix epoch, UTC**. With TinyGPS++ on the ESP32:

```cpp
#include <time.h>
// gps.date and gps.time are valid after a fix
struct tm t = {0};
t.tm_year = gps.date.year()  - 1900;
t.tm_mon  = gps.date.month() - 1;
t.tm_mday = gps.date.day();
t.tm_hour = gps.time.hour();
t.tm_min  = gps.time.minute();
t.tm_sec  = gps.time.second();
time_t epoch = timegm(&t);                 // UTC → seconds (use timegm, NOT mktime)
uint64_t timestamp_ms = (uint64_t)epoch * 1000ULL;
```

(If `timegm` isn't available in your toolchain, set `TZ=UTC`, call `tzset()`, then use `mktime`.)

### Where to send it — two paths

You have two transports into the **same** ingest pipeline. Use the HTTP bridge first to prove the data, then switch to MQTT.

**A. HTTP bridge (easiest for first light — no broker needed)**

```
POST https://<your-api>/api/v1/telemetry/json
Content-Type: application/json
X-Device-Signature: <HMAC-SHA256 of the body using DEVICE_INGEST_SECRET>
Body: the JSON above
```

- Enable it in dev with `DEV_INGEST_ENABLED=true`.
- The signature is `hex( HMAC_SHA256(DEVICE_INGEST_SECRET, raw_body) )`. The same secret is set on the server. This is what stops a stranger from injecting fake buses.

**B. MQTT (production transport)** — publish the same JSON to `vehicles/car_01/status` (details in Part 2).

> 🛡️ **Approval workflow (migration 019):** telemetry is only *accepted* for
> vehicles an admin has **approved** on `/admin/approvals.html`. Frames from
> pending/rejected/suspended vehicles are dropped (the ingest logs
> `telemetry_dropped_unapproved`). Register + approve the vehicle first —
> see [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md) and [ADMIN_GUIDE.md](ADMIN_GUIDE.md).

Both routes run `_ingest()`, so behaviour is identical — MQTT is just a transport swap, by design.

---

<a name="part-2"></a>
## 2. The broker and the topics

### What a broker is (30 seconds)

MQTT is a publish/subscribe protocol for tiny devices. A **broker** is the post office in the middle: devices **publish** messages to a named **topic**; the broker delivers each message to whoever **subscribed** to that topic. Your ESP32 never talks to the backend directly — it publishes to the broker, and your backend consumer subscribes. That decoupling is what lets you scale to thousands of buses.

### Your broker

| Environment | Broker | Where |
|---|---|---|
| Dev / pilot | **Mosquitto** | `docker-compose.scale.yml` → service `mosquitto`, port `1883` (TCP), `9001` (WebSocket). Config: `monitoring/mosquitto/mosquitto.conf`. |
| Production (per `firmware/SPEC.md`, ADR-005) | **EMQX / HiveMQ** + per-device **X.509 certs** over TLS `8883` | Swap the host; the topics don't change. |

Bring the dev broker up:

```bash
docker compose -f docker-compose.scale.yml up -d mosquitto redis
```

### The topics

The device identifier (`car_01`, an IMEI, or a `DAM-###` code) goes in the topic path:

| Topic | Direction | QoS | Purpose |
|---|---|---|---|
| `vehicles/<vehicle_id>/status` | device → broker | 0 | Periodic position pings (the JSON from Part 1). |
| `vehicles/<vehicle_id>/event` | device → broker | 1 | Critical events (ignition on/off, panic, harsh braking). QoS 1 = guaranteed delivery. |
| `vehicles/<vehicle_id>/ack` | broker → device | 1 | Server receipt so the device can clear a frame from its offline buffer. |

Your backend consumer (`api/workers/mqtt_consumer.py`) subscribes to `vehicles/+/status` and `vehicles/+/event` (the `+` is a single-level wildcard = "any vehicle") and feeds every frame into `_ingest()`.

### Run the end-to-end loop locally

```bash
# 1) broker + redis are up (above)

# 2) start the consumer (subscribes and ingests)
python -m api.workers.mqtt_consumer

# 3a) quick test publish with the mosquitto CLI:
mosquitto_pub -h localhost -t vehicles/car_01/status -m '{"vehicle_id":"car_01","operator_id":"00000000-0000-0000-0000-000000000001","timestamp":1781048676000,"latitude":33.520229,"longitude":36.286177,"speed_kph":0.85,"heading":170.41,"satellite_count":10,"hdop":1.0}'

# 3b) or simulate many moving buses at once:
python scripts/mqtt_sim_publish.py --vehicles 10 --interval 2
```

If the consumer logs `mqtt_consumer_connected` and then ingests, you're done. Open `/api/stream` (or the passenger map) and the vehicle should appear.

### What your ESP32 needs to do

Per `firmware/SPEC.md`: connect to the broker, **subscribe** to `vehicles/car_01/ack`, then **publish** to `vehicles/car_01/status` at the adaptive heartbeat rate (10 s moving / 60 s idling / sleep when parked), and send events to `vehicles/car_01/event` at QoS 1. For the SIM900A the raw AT sequence is in `firmware/SPEC.md` ("AT command sequence").

---

<a name="part-3"></a>
## 3. Grafana + the time-series DB

> **Heads-up: you said "Influx," but this project doesn't use InfluxDB.** Your stack stores time-series data in **two** places, and Grafana reads both:
> - **Prometheus** — operational *metrics* (request rate, latency, error rate, ingest rate). Already wired and auto-scraped.
> - **TimescaleDB** — the *telemetry* history (every vehicle position over time), a PostgreSQL extension. The hypertable is defined in `db/migrations/009_telemetry_hypertable.sql`.
>
> You don't need InfluxDB. If you ever specifically want it, it's a drop-in swap for the Prometheus role, but everything here is already built around Timescale + Prometheus, so that's what we'll connect.

### Step 1 — bring up the observability stack

```bash
docker compose -f docker-compose.scale.yml up -d
```

This starts Grafana (`:3001`), Prometheus (`:9090`), Mosquitto, and Redis.

### Step 2 — log in to Grafana

Open `http://localhost:3001`, log in with `admin` / `admin`, change the password when prompted.

### Step 3 — Prometheus is already connected

Grafana auto-provisions the Prometheus datasource and an "API Overview" dashboard (`monitoring/grafana/dashboards/dam-overview.json`). Open **Dashboards → Damascus Transit → API Overview**. If panels are empty, you haven't enabled metrics yet → Step 5.

### Step 4 — add TimescaleDB as a datasource (for telemetry history)

1. Grafana → **Connections → Data sources → Add data source → PostgreSQL**.
2. Fill in:
   - **Host:** your Supabase/Postgres host (e.g. `db.<project>.supabase.co:5432` or your self-hosted Postgres).
   - **Database:** your database name.
   - **User / Password:** a **read-only** Grafana DB user (create one; don't reuse the service key).
   - **TLS/SSL:** `require` for Supabase.
   - **PostgreSQL version:** 15+; enable **TimescaleDB** in the toggle at the bottom.
3. **Save & test.**
4. Build a panel with a time-series query, e.g.:

```sql
SELECT ts AS "time", speed AS value, vehicle_id AS metric
FROM vehicle_positions
WHERE $__timeFilter(ts) AND operator_id = '00000000-0000-0000-0000-000000000001'
ORDER BY ts;
```

### Step 5 — turn on API metrics

Prometheus can only chart what the API exposes. Metrics are **off by default** (they don't work on Vercel serverless). On your self-hosted / Docker API:

```bash
METRICS_ENABLED=true uvicorn api.index:app --port 8000
```

Now `http://localhost:8000/metrics` returns data, Prometheus scrapes it, and the Grafana panels fill in.

### Who stores what

| Question you're answering | Look in |
|---|---|
| "Is the API healthy right now?" (latency, errors, throughput) | Prometheus → Grafana API Overview |
| "Where was bus car_01 at 3pm yesterday?" / route history / analytics | TimescaleDB (`vehicle_positions`) → Grafana Postgres panels |
| "Which vehicles are near this point *right now*?" | Redis Geo (sub-millisecond; not Grafana) |

---

<a name="part-4"></a>
## 4. Monitoring everything + debugging errors

You have three layers. Use the right one for the question.

### Layer 1 — Metrics (is the system healthy?)

Grafana API Overview (Part 3): request rate, p95 latency, 5xx error rate, telemetry ingest rate. This is your "glance at the wall" dashboard. When ingest rate drops to zero, devices stopped reaching you.

### Layer 2 — Errors (what exactly broke, with a stack trace?)

**Sentry** is wired into the API (`api/index.py`, guarded by `SENTRY_DSN`).

1. Create a free project at sentry.io → copy the DSN.
2. Set `SENTRY_DSN=https://...` and `APP_RELEASE=damascustransit@1.0.0` in your env (see `.env.ministry.example`).
3. Every unhandled exception now lands in Sentry with the request ID, release tag, and stack trace. Failures are also summarized as a daily breadcrumb.

### Layer 3 — Logs (the play-by-play)

The API emits **structured JSON logs** (`api/core/logging.py`). Each line has `request_id`, `level`, `logger`, `msg`. Grep them:

```bash
docker compose -f docker-compose.scale.yml logs -f mqtt-consumer | grep -i mqtt
```

Useful log events you'll see: `mqtt_consumer_connected`, `mqtt_frame_invalid` (a device sent a bad frame), `telemetry_persist_failed`, `live_bus_publish_failed`.

### Debugging the device path specifically

| Symptom | Where to look | Likely cause |
|---|---|---|
| Vehicle never appears on the map | consumer logs: `mqtt_frame_invalid` | `car_id` instead of `vehicle_id`, or bad JSON |
| Frame ingested but no map marker | — | missing `operator_id` (Part 1 box) |
| Marker appears then freezes | device serial | device stopped publishing / lost signal — check FIFO drain on reconnect |
| Wrong/old timestamps | device | used modem clock instead of GPS UTC, or seconds instead of ms |
| Position jumps around | device serial: `HDOP`, `Satellites` | weak fix — server should reject HDOP > 5 or sats < 4 |
| `Failed Checksums: 6` climbing | device wiring | GPS UART noise / baud mismatch (you're at 115200 GPS, 9600 is typical for NEO-6M — verify `Serial.begin`) |

### Watching MQTT traffic live

```bash
# see every frame any vehicle publishes:
mosquitto_sub -h localhost -t 'vehicles/#' -v
```

Or use a GUI like **MQTT Explorer** (free, point it at `localhost:1883`) to watch the topic tree fill up in real time — the fastest way to confirm your ESP32 is actually publishing.

---

<a name="part-5"></a>
## 5. Firebase service account — what and why

### Why you need Firebase at all

Your **native mobile app** (`flutter_app/` — the official iOS+Android app) gets push notifications — "bus arriving in 2 min," incident alerts — through **Firebase Cloud Messaging (FCM)**, which fronts Apple's APNs for iOS too. The web PWA uses a different mechanism (VAPID/web-push, already in `api/routers/push.py`); Firebase is specifically for the **app** on phones. The end-to-end flow is documented in `docs/technical/Push_Notification_Flow.md`.

There are **two different Firebase artifacts**, and people constantly confuse them:

| Artifact | Lives where | Job |
|---|---|---|
| **Client config** — `google-services.json` (Android), `GoogleService-Info.plist` (iOS) | inside the app build | Tells *the phone app* which Firebase project it belongs to, so it can fetch a device token. (This is ROADMAP_100 **#86**.) |
| **Service account JSON** (private key) | on the **server**, as a secret | Lets *your backend* authenticate to Google and **send** pushes via the Firebase Admin SDK / FCM HTTP v1 API. |

You need both: the client files so phones can *register*, and the service account so the server can *send*.

### Steps

**A. Create the project + client config**

1. Go to the [Firebase console](https://console.firebase.google.com/) → **Add project** → name it (e.g. `damascus-transit`).
2. **Add an Android app**: enter the package name **`sy.gov.damascus.transit`** (your real app ID — keep it identical in `flutter_app/android/app/build.gradle`) → **Download `google-services.json`** → place it in `flutter_app/android/app/`.
3. **Add an iOS app**: enter the bundle ID (same `sy.gov.damascus.transit`) → **Download `GoogleService-Info.plist`** → add it to the iOS Runner target in Xcode.

**B. Create the server service account**

4. Firebase console → **⚙ Project settings → Service accounts**.
5. Click **Generate new private key** → confirm → a `.json` file downloads. **This is a secret — treat it like a password.**
6. Give it to the backend one of two ways:
   - Set `GOOGLE_APPLICATION_CREDENTIALS=/secure/path/serviceAccount.json` (the Admin SDK reads this automatically), **or**
   - Store the JSON contents in your secret manager / an env var and load it at startup.
7. **Never commit it.** Add the filename to `.gitignore`; on Vercel/Docker inject it as a secret, not a file in the repo.

### Cost

Firebase Cloud Messaging is **free** at any volume. You only pay if you use other Firebase products (Firestore, etc.), which this project doesn't require.

---

<a name="part-6"></a>
## 6. Apple App Store enrollment

**Cost:** **$99 USD / year**. **Timeline:** ~1–3 days (individual), 7+ days (organization).

### Individual vs Organization

| | Individual / sole proprietor | Organization |
|---|---|---|
| Seller name on the store | your personal name | your **legal entity** name (better for a Ministry-backed product) |
| Extra requirement | 2FA Apple Account, legal age | a **D-U-N-S Number** (free from Dun & Bradstreet) + verification call/email |
| Approval time | 1–3 days | 7+ days |

For a government/transit-authority product, enroll as an **organization** so the Ministry's legal name is the publisher. If the Ministry is a government entity or nonprofit, you may qualify for an **Apple fee waiver** (the $99 is waived).

### Steps

1. Create an **Apple Account** with two-factor authentication enabled.
2. Go to [developer.apple.com/programs/enroll](https://developer.apple.com/programs/enroll/).
3. Choose entity type (Individual or Organization). For org: have your **legal entity name** and **D-U-N-S Number** ready.
4. Apple verifies (email/phone for org). Approve, then pay the $99 (or request a fee waiver).
5. Once active: builds are uploaded from **Xcode on a Mac**, and beta-tested via **TestFlight** (ROADMAP_100 **#89**, **#95**).

> You need a Mac with Xcode to build and sign iOS apps — there's no way around this for the App Store.

---

<a name="part-7"></a>
## 7. Google Play Store enrollment

**Cost:** **$25 USD, one-time** (no annual renewal).

### The catch most people miss: the 12-tester rule

| | Personal account | Organization account |
|---|---|---|
| Registration fee | $25 one-time | $25 one-time |
| ID verification | government ID + proof of address | + a **D-U-N-S Number** |
| **Closed testing before you can go live** | **Yes — 12 testers for 14 continuous days** | **No** such requirement |

➡️ **Register as an Organization** if you can. It skips the 12-testers-for-14-days gate, which otherwise blocks your first production release. For a Ministry product this is the natural choice anyway.

### Steps

1. Go to the [Play Console](https://play.google.com/console/signup).
2. Choose **Organization** (recommended) or Personal account type.
3. Pay the **$25** one-time fee.
4. Complete **identity verification**: upload a passport/ID/residence permit **and** proof of address (bank statement or utility bill with your name + address). Org accounts also provide a D-U-N-S Number.
5. Create the app listing , upload the **AAB** (Android App Bundle), and roll out to the **internal test** track first (ROADMAP_100 **#90**, **#94**).

---

<a name="part-8"></a>
## 8. Recommended order of operations

Do it in this sequence — each step unblocks the next, and several close open roadmap items:

1. **Fix the device payload** (Part 1): rename `car_id`→`vehicle_id`, add `operator_id`, send `timestamp` in ms. Prove it via the HTTP bridge.
2. **Bring up the stack** (Part 2/3): `docker compose -f docker-compose.scale.yml up -d`, run the consumer, watch the bus appear.
3. **Wire monitoring** (Part 4): set `SENTRY_DSN`, open the Grafana dashboard, keep `mosquitto_sub` handy while you test.
4. **Switch the device to MQTT** once the JSON is proven.
5. **Firebase** (Part 5): create the project, drop in the client config files (closes #86), generate the service account for the server.
6. **Enroll the stores** (Parts 6–7) — start these early, the verification takes days. Organization accounts on both. (Closes #89, #90; then #94/#95 for the test rollouts.)

---

## Sources

- [Apple — Choosing a Membership](https://developer.apple.com/support/compare-memberships/) and [Enroll](https://developer.apple.com/programs/enroll/)
- [Apple — Program enrollment help](https://developer.apple.com/help/account/membership/program-enrollment/) and [Fee waivers](https://developer.apple.com/help/account/membership/fee-waivers/)
- [Google Play — Register on Play Console (developer verification)](https://developer.android.com/developer-verification/guides/google-play-console) and [Get started with Play Console](https://support.google.com/googleplay/android-developer/answer/6112435?hl=en)
- [Google Play developer account fee 2026 (one-time $25)](https://www.iconikai.com/blog/google-play-developer-account-fee-2026)
- [Google Play developer verification 2026 (ID + 12-tester rule)](https://www.testerscommunity.com/blog/google-play-developer-verification-2026)
- [Firebase — Send with FCM HTTP v1 API](https://firebase.google.com/docs/cloud-messaging/send/v1-api) and [Server environment & Admin SDK](https://firebase.google.com/docs/cloud-messaging/server-environment)
- Project files referenced: `schemas/telematics.proto`, `api/routers/mqtt_ingest.py`, `api/workers/mqtt_consumer.py`, `firmware/SPEC.md`, `docker-compose.scale.yml`, `monitoring/`, `docs/technical/Push_Notification_Flow.md`, `db/migrations/009_telemetry_hypertable.sql`.
