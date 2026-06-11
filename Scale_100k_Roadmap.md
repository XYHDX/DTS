# Scale-to-100k Roadmap

> Authored 24 May 2026, derived from `docs/transit_architecture_guide.md`. Maps the enterprise architecture onto the existing DamascusTransit codebase. The 100-step revival roadmap (`ROADMAP_100.md`) is now **complete on the codeable items**; this document is the next phase.

## Why a new phase

The original system was sized for **~500 vehicles**. The guide describes a target of **100,000 vehicles** — a 200× scale jump that crosses three architectural boundaries:

| Boundary | At 500 vehicles | At 100,000 vehicles |
|---|---|---|
| Ingest protocol | HTTP webhook (Traccar) | **MQTT broker** (EMQX / HiveMQ) |
| Payload | JSON | **Protobuf** (80% bandwidth saving) |
| Streaming buffer | none | **Kafka / Redpanda** |
| Storage | PostGIS rows | **TimescaleDB hypertable** or ClickHouse |
| Live geofencing | per-request PostGIS | **Redis Geo** cache |
| Edge intelligence | server-side | **device-side** (adaptive heartbeat, EMA fuel, watchdog) |

This document plans the migration without breaking the 500-vehicle deployment that ships today. Each phase preserves a working fallback to the current stack.

---

## Phase S1 — Decision + schema freeze (week 1)

- [x] **S1.1.** ADR-004 — lock the ingestion stack choice (MQTT + Kafka + TimescaleDB). See `docs/adr/ADR-004-ingestion-stack.md`.
- [x] **S1.2.** Production-ready Protobuf schema published at `schemas/telematics.proto`. Includes `VehicleStatus` with adaptive `EventType`, ignition state, fuel level.
- [x] **S1.3.** Edge firmware spec at `firmware/SPEC.md` — covers SIM900A AT-sequence MVP, adaptive heartbeat tiers, FIFO offline queue, hardware watchdog, ignition sense via optocoupler.
- [x] **S1.4.** Database migration `009_telemetry_hypertable.sql` — promotes `vehicle_positions` to a TimescaleDB hypertable, adds `engine_state`, `fuel_level`, `trigger_event` columns.
- [ ] **S1.5.** Capacity-planning ADR-005: at what vehicle count do we add the MQTT broker (decision: at 5,000 sustained connections).
- [ ] **S1.6.** Cost model — bandwidth, broker, Kafka, TimescaleDB on Hetzner vs Cloud at 5k, 25k, 100k scale.

## Phase S2 — Protocol bridge (weeks 2–3)

- [x] **S2.1.** `api/routers/mqtt_ingest.py` — HTTP-bridge endpoint that accepts Protobuf-encoded payloads compatible with the future MQTT pipeline. Lets the firmware switch transport without changing the wire format.
- [x] **S2.2.** Embedded MQTT broker in dev — `mosquitto` service in **`docker-compose.scale.yml`** (kept out of `docker-compose.prod.yml` so the working deployment is untouched) + async consumer worker `api/workers/mqtt_consumer.py` that subscribes to `vehicles/+/status|event` and reuses the existing `_ingest` pipeline (Redis Geo + persist). Test publisher: `scripts/mqtt_sim_publish.py`. _(2026-06-02)_
- [ ] **S2.3.** Devices switch to Protobuf-over-HTTP first (S2.1 endpoint), MQTT later. Keeps `/api/traccar/position` working until every device is migrated.
- [ ] **S2.4.** Backpressure: drop QoS-0 messages when the ingest path is over `MQTT_INGEST_HIGH_WATERMARK` (configurable, default 5,000 in-flight).

## Phase S3 — Hot path (weeks 4–5)

- [x] **S3.1.** Redis Geo cache helper at `api/core/geo_cache.py` — `GEOADD` on every successful ingest, `GEOSEARCH` for nearest-vehicle queries, less than 1 ms.
- [x] **S3.2.** Edge-side EMA helper at `api/core/ema.py` — referenced by the ingest path to smooth fuel level when devices haven't done it themselves yet.
- [ ] **S3.3.** Bounding-box pre-filter before PostGIS `ST_Contains` in `/api/stops/nearest` — already partly done by the GiST index, but explicitly gate complex polygons on a bbox match.
- [x] **S3.4.** Move `/api/stream` SSE generation off the FastAPI process onto a Redis pub-sub consumer (scales horizontally without sticky sessions). Live bus at `api/core/live_bus.py` (Redis pub/sub over `REDIS_PUBSUB_URL`; in-memory backend for one-box/dev; disabled default → legacy poll, so Vercel is unchanged). Ingest paths (`driver.report_driver_position`, `mqtt_ingest._ingest`) publish each accepted frame; `/api/stream` sends one snapshot per connection then relays bus updates — one DB query per *connection* instead of per client every 2 s, and no in-process state to pin a client to a worker. `redis` service added to `docker-compose.scale.yml`; tests in `tests/test_live_bus.py`. _(2026-06-11)_

## Phase S4 — Cold path (weeks 6–7)

- [ ] **S4.1.** Provision a TimescaleDB hypertable for `vehicle_positions` with a 7-day chunk interval and 90-day retention. Migration 009 lays the foundation.
- [ ] **S4.2.** Continuous aggregates: per-route 1-minute and 5-minute rollups so analytics queries don't touch the hot data.
- [ ] **S4.3.** Compress chunks older than 7 days with TimescaleDB native compression (≥10× ratio expected for telemetry).
- [ ] **S4.4.** Daily archive job: export compressed chunks older than 90 days to S3-compatible cold storage.

## Phase S5 — Kafka shim (weeks 8–9)

- [ ] **S5.1.** Single-node Redpanda dev container (`docker-compose.yml`); production cluster decision deferred until 25,000 vehicle threshold.
- [ ] **S5.2.** Producer in `api/routers/mqtt_ingest.py` writes every accepted message to a `vehicles.positions` topic partitioned by `vehicle_id`.
- [ ] **S5.3.** Consumer worker — `api/workers/ingest_consumer.py` — reads from Kafka and writes to TimescaleDB + Redis Geo. Replaces the inline write path once stable.
- [ ] **S5.4.** Replay tool: re-process from a Kafka offset for backfill or post-incident reanalysis.

## Phase S6 — Edge firmware reference (weeks 6–10, parallel)

- [x] **S6.1.** `firmware/SPEC.md` — AT command sequence, watchdog, ignition sense, offline FIFO, adaptive heartbeat.
- [ ] **S6.2.** Reference firmware in C++ (`firmware/sim900a-reference/main.cpp`) — production-quality, MIT-licensed, importable by city partners.
- [ ] **S6.3.** Hardware bill-of-materials sheet (`firmware/HARDWARE.md`) — SIM900A vs alternatives (Quectel BG95, A7670), accelerometer choices, MOSFET for SIM reset, optocoupler for ACC.

## Phase S7 — Observability at scale (weeks 9–10)

- [ ] **S7.1.** Per-device metrics in Sentry: device-id tag, firmware-version tag, last-seen-at, dropped-frame count.
- [x] **S7.2.** Grafana dashboard (starter) — Prometheus + Grafana in `docker-compose.scale.yml`, provisioned datasource + dashboard `monitoring/grafana/dashboards/dam-overview.json` (request rate, p95 latency, 5xx error rate, telemetry ingest rate). API exposes `/metrics` when `METRICS_ENABLED=true`. _Redis Geo p99 + TimescaleDB chunk-size panels follow once S3.4/S4 land._ _(2026-06-02)_
- [ ] **S7.3.** Synthetic-load tool — extends `tests/load_sse.js` to publish 10k–100k synthetic MQTT clients via `mqtt-bench`.

## Phase S8 — Cutover (week 11)

- [ ] **S8.1.** Migrate the 24 production vehicles to Protobuf-over-HTTP (Phase S2.3).
- [ ] **S8.2.** Migrate the 24 production vehicles to MQTT once S5.x is green.
- [ ] **S8.3.** Sunset `/api/traccar/position` legacy endpoint after a 30-day overlap.

---

## What's already shipped in Phase S1 + early S2/S3 (this session)

| File | Purpose |
|---|---|
| `docs/adr/ADR-004-ingestion-stack.md` | Locks MQTT + Kafka + TimescaleDB as the long-term ingestion stack. |
| `schemas/telematics.proto` | Production-ready Protobuf schema with adaptive `EventType`. |
| `db/migrations/009_telemetry_hypertable.sql` | Promotes `vehicle_positions` to TimescaleDB hypertable, adds telemetry-rich columns. |
| `api/core/geo_cache.py` | Redis Geo (`GEOADD` / `GEOSEARCH`) wrapper, sub-millisecond nearest-vehicle. |
| `api/core/ema.py` | Exponential moving average filter for edge-or-cloud fuel smoothing. |
| `api/routers/mqtt_ingest.py` | HTTP bridge endpoint accepting Protobuf payloads. Enables firmware to migrate before MQTT broker exists. |
| `firmware/SPEC.md` | Edge firmware specification covering all of guide §1 and §5. |

## What does *not* change

The customer-facing surface — passenger PWA, driver PWA, admin dashboard, Flutter app, the eight CI workflows, the runbooks — all remain valid and shippable. The 100k scale work is **invisible to the user** when done right.

The 100-step revival roadmap (`ROADMAP_100.md`) stands. Anything completed there is still complete; this file adds **new** work above and beyond.

## Progress log

| Date | Items | Notes |
|---|---|---|
| 2026-05-24 | S1.1–S1.4, S2.1, S3.1–S3.2, S6.1 | First wave: ADR-004, protobuf, hypertable migration, Redis Geo cache, EMA, MQTT-bridge endpoint, firmware spec. |
| 2026-06-02 | S2.2, S7.2 | MQTT dev broker (mosquitto) + async consumer worker (`api/workers/mqtt_consumer.py`) reusing `_ingest`; sim publisher (`scripts/mqtt_sim_publish.py`); optional Prometheus `/metrics` + Grafana stack (`docker-compose.scale.yml`, `monitoring/`) with starter dashboard. Also closed ROADMAP_100 #72 + #80. See `PROJECT_STATUS.md`. |
| 2026-06-11 | S3.4 | Live position bus (`api/core/live_bus.py`): Redis pub/sub fan-out for `/api/stream`, removing per-client DB polling and the sticky-session limit. Ingest paths publish; stream subscribes (snapshot-on-connect + relay). `redis` service in `docker-compose.scale.yml`; `redis>=5` dep; env `REDIS_PUBSUB_URL` / `LIVE_BUS_BACKEND`; `tests/test_live_bus.py`. |
