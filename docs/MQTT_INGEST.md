# MQTT ingestion — turning it on

This is the runbook for sending vehicle GPS over **MQTT** (self‑hosted Mosquitto)
instead of the HTTP path. Everything server‑side already exists in the repo; this
document explains how to switch it on and point hardware at it.

## How it fits together

```
 ESP32 + SIM900 (2G)            self-hosted box (always-on)              Supabase / Redis
 ───────────────────            ───────────────────────────              ────────────────
 NEO-6M GPS ─► ESP32 ─►  MQTT   Mosquitto broker (1883/8883)
                        ─────►  vehicles/<id>/status
                                        │
                                        ▼
                                mqtt-consumer  (api.workers.mqtt_consumer)
                                   ├─ _ingest()  ── reuses the HTTP pipeline
                                   ├─ Redis Geo  ── live map / SSE
                                   └─ persist    ── vehicle_positions
```

**Why a separate consumer?** The API runs on Vercel (serverless), where a
long‑lived MQTT subscription cannot live. The broker **and** the consumer must
run on an always‑on host you control (a small Linux VM, a Raspberry Pi, the
ministry's own server). The consumer reuses the *exact* ingest pipeline as the
HTTP bridge (`api/routers/mqtt_ingest.py`), so MQTT and HTTP behave identically —
only the transport changes.

The passenger/driver **phone** apps keep using HTTPS; MQTT is the path for the
on‑bus hardware. Both feed the same `_ingest()` → same live map → same database.

## What already exists

| Piece | Location |
| --- | --- |
| MQTT broker (dev) | `docker-compose.scale.yml` → `mosquitto` (`monitoring/mosquitto/mosquitto.conf`) |
| Consumer worker | `api/workers/mqtt_consumer.py` (run: `python -m api.workers.mqtt_consumer`) |
| Consumer container | `docker-compose.scale.yml` → `mqtt-consumer` |
| Ingest pipeline (shared) | `api/routers/mqtt_ingest.py` (`_PartialDecode`, `_ingest`) |
| Test publisher (simulator) | `scripts/mqtt_sim_publish.py` |
| Device firmware (MQTT) | `firmware/esp32_sim900_mqtt/esp32_sim900_mqtt.ino` |
| Config | `.env.example` → `MQTT_*` keys; dependency `aiomqtt` in `requirements.txt` |

## Turn it on (self-hosted box)

1. **Set environment** in a `.env` next to `docker-compose.scale.yml`:

   ```bash
   SUPABASE_URL=...                 # so persisted positions reach the DB
   SUPABASE_SERVICE_KEY=...
   REDIS_PUBSUB_URL=redis://redis:6379/0
   MQTT_BROKER_HOST=mosquitto       # service name inside the compose network
   MQTT_BROKER_PORT=1883
   # MQTT_USERNAME= / MQTT_PASSWORD=  (set once you enable broker auth, below)
   MQTT_STATUS_TOPIC=vehicles/+/status
   MQTT_EVENT_TOPIC=vehicles/+/event
   ```

2. **Start the broker + consumer + Redis:**

   ```bash
   docker compose -f docker-compose.scale.yml up -d redis mosquitto mqtt-consumer
   docker compose -f docker-compose.scale.yml logs -f mqtt-consumer
   ```

3. **Smoke‑test with the simulator** (no hardware needed):

   ```bash
   pip install aiomqtt
   python scripts/mqtt_sim_publish.py --host <broker-host> --vehicles 5 --interval 5
   ```

   You should see `mqtt_consumer_connected` then frames flowing; the vehicles
   appear on the admin live map (if the broker host's Redis + Supabase env are set).

4. **Point the hardware at the broker.** Flash
   `firmware/esp32_sim900_mqtt/esp32_sim900_mqtt.ino`, setting `MQTT_HOST` to the
   broker's **public** IP/hostname, `VEHICLE_ID` to a paired vehicle, and the APN
   for your SIM. It publishes one JSON fix every 10 s to `vehicles/<id>/status`.

## Topic + payload

- **Status topic:** `vehicles/<vehicle_id>/status` (QoS 0)
- **Event topic:** `vehicles/<vehicle_id>/event` (QoS 1) — e.g. ignition‑off, which
  also removes the vehicle from the live map.
- **Payload (JSON, `_PartialDecode` shape):**

  ```json
  {
    "vehicle_id": "BUS-101",
    "operator_id": "00000000-0000-0000-0000-000000000001",
    "timestamp": 1718540000000,
    "latitude": 33.513800,
    "longitude": 36.276500,
    "speed_kph": 12.3,
    "heading": 90.0,
    "engine_state": true
  }
  ```

  `vehicle_id`, `timestamp` (ms epoch), `latitude`, `longitude` are required.
  `operator_id` is required for the **live map** (Redis geo); without it the
  position still persists to `vehicle_positions`. A JSON **array** or
  `{"frames":[...]}` batch is also accepted.

## Security

The dev broker (`mosquitto.conf`) sets `allow_anonymous true` for local testing.
**Before any real deployment:**

1. Disable anonymous and add a password file (or per‑device X.509 certs):

   ```conf
   allow_anonymous false
   password_file /mosquitto/config/passwd
   ```

   ```bash
   docker run --rm -v "$PWD/monitoring/mosquitto:/m" eclipse-mosquitto:2 \
     mosquitto_passwd -c -b /m/passwd dts-devices 'a-strong-password'
   ```

2. Set `MQTT_USERNAME` / `MQTT_PASSWORD` for the consumer (and the same creds in
   the firmware), and prefer **TLS on 8883** (see the firmware's TLS note). On 2G,
   plain MQTT over a trusted network/VPN is the most reliable prototype path.

## Notes

- 2G is being wound down globally — use SIM900 for the bench/field prototype, and
  a 4G + GPS board (e.g. LilyGO T‑SIM7600) for the real fleet. The broker, topic,
  and payload stay identical; only the modem changes.
- The HTTP bridge (`/api/v1/telemetry/json` and `/api/traccar/position`) remains
  available; you can run both transports during migration.
