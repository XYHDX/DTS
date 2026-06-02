# DamascusTransit — Project Status

**Last updated:** 2026-06-02
**Purpose:** Single source of truth for what is **done** and what **remains**, across both roadmaps.

This project tracks two roadmaps:

1. **`ROADMAP_100.md`** — the 100-step *revival* (productionising the existing 500-vehicle system).
2. **`Scale_100k_Roadmap.md`** — the *scale-to-100k* track (MQTT → Kafka → TimescaleDB ingestion + observability).

---

## TL;DR

| Track | Status |
|---|---|
| **Revival (ROADMAP_100)** | ✅ **All codeable items complete.** Only **user actions** remain (Firebase, Apple/Google enrolment, store rollout). |
| **Scale-to-100k** | 🟡 In progress. Foundations + protocol bridge + hot-path cache + **MQTT dev broker + observability** done. Cold path (TimescaleDB), Kafka shim, and cutover remain. |

The customer-facing system (passenger PWA, driver PWA, admin dashboard, Flutter app, 8 CI workflows) is **live and unchanged** — all scale work is additive and invisible to users.

---

## 1. Revival roadmap (`ROADMAP_100.md`)

**98 / 100 codeable steps complete** (plus 5 out-of-band additions N1–N5). The two items closed on 2026-06-02:

- **#72** — Python pinned to `3.12-slim-bookworm` in `Dockerfile.prod` (verified; landed with #73).
- **#80** — Sentry initialised on FastAPI startup with a `release` tag (`api/index.py`, guarded by `SENTRY_DSN`).

### Remaining — all require **human action** (cannot be done from code)

| Step | Item | Owner |
|---|---|---|
| #86 | Create Firebase project; download `google-services.json` + `GoogleService-Info.plist` | User |
| #87 | Generate Android signing keystore; store in a secret manager | User |
| #89 | Enrol in the Apple Developer Program | User |
| #90 | Enrol in Google Play Console | User |
| #94 | Internal-test rollout (Play Console internal track) | User |
| #95 | TestFlight rollout (once Apple membership is active) | User |
| #42 | "Build debug APK on every PR" — overlaps #41 (already builds + uploads a debug APK); optional dedicated job | Optional |

---

## 2. Scale-to-100k roadmap (`Scale_100k_Roadmap.md`)

The target is a 200× jump (500 → 100,000 vehicles), crossing ingest protocol (HTTP → **MQTT**), payload (JSON → **Protobuf**), buffer (none → **Kafka**), storage (PostGIS rows → **TimescaleDB**), and live geofencing (PostGIS → **Redis Geo**).

| Phase | Scope | Status |
|---|---|---|
| **S1 — Decision + schema freeze** | ADR-004, Protobuf schema, hypertable migration, firmware spec | ✅ Done (S1.5 capacity-ADR, S1.6 cost-model **remain**) |
| **S2 — Protocol bridge** | HTTP Protobuf bridge (S2.1) + **MQTT dev broker & consumer (S2.2)** | 🟢 S2.1 + S2.2 done · S2.3 (device migration), S2.4 (backpressure) remain |
| **S3 — Hot path** | Redis Geo cache (S3.1), EMA (S3.2) | 🟢 S3.1/S3.2 done · S3.3 (bbox pre-filter), S3.4 (SSE→Redis pub/sub) remain |
| **S4 — Cold path** | TimescaleDB hypertable, continuous aggregates, compression, archive | 🔴 Not started (migration 009 lays the foundation) |
| **S5 — Kafka shim** | Redpanda + producer + consumer + replay | 🔴 Not started |
| **S6 — Edge firmware** | Spec (S6.1) done · reference C++ firmware + BOM | 🟡 Spec done · S6.2/S6.3 remain |
| **S7 — Observability** | **Starter Grafana + Prometheus + /metrics (S7.2)** | 🟢 S7.2 (starter) done · S7.1 (per-device Sentry tags), S7.3 (synthetic load) remain |
| **S8 — Cutover** | Migrate 24 production vehicles to Protobuf-over-HTTP → MQTT; sunset legacy webhook | 🔴 Not started (depends on S2.3 + S5) |

---

## 3. What was built this session (2026-06-02)

A complete, **opt-in** observability + MQTT-ingestion dev stack — additive, with zero changes to the working production deployment.

### New files

| File | Purpose |
|---|---|
| `api/workers/mqtt_consumer.py` | **S2.2** — async MQTT consumer; subscribes to `vehicles/+/status` and `vehicles/+/event`, reuses the existing `_ingest` pipeline (Redis Geo + persist). |
| `api/workers/__init__.py` | Workers package. |
| `scripts/mqtt_sim_publish.py` | Test publisher — simulates N moving Damascus vehicles over MQTT. |
| `docker-compose.scale.yml` | Opt-in stack: `mosquitto`, `mqtt-consumer`, `prometheus`, `grafana`. |
| `monitoring/mosquitto/mosquitto.conf` | Dev MQTT broker config (TCP 1883 + WebSocket 9001). |
| `monitoring/prometheus/prometheus.yml` | Scrapes the API `/metrics`. |
| `monitoring/grafana/provisioning/...` | Auto-provisioned Prometheus datasource + dashboard loader. |
| `monitoring/grafana/dashboards/dam-overview.json` | **S7.2** starter dashboard: request rate, p95 latency, 5xx error rate, telemetry ingest rate. |
| `monitoring/README.md` | How to run the stack. |

### Changed files (minimal, guarded, backward-compatible)

| File | Change |
|---|---|
| `api/index.py` | Optional Prometheus `/metrics` (only when `METRICS_ENABLED=true`); Sentry `release` tag added. |
| `requirements.txt` | `aiomqtt`, `prometheus-fastapi-instrumentator`. |
| `.env.example` | `APP_RELEASE`, `METRICS_ENABLED`, `MQTT_*`, `GRAFANA_*`. |

> **Safety:** `/metrics` stays off on Vercel (serverless). The MQTT consumer runs only as its own container. Redis and Supabase both **soft-fail** (no-op) when unset, so the stack runs locally with no cloud services attached.

---

## 4. How to run the new stack

**Local dev — watch MQTT ingestion end-to-end:**

```bash
# 1) start the broker + observability stack
docker compose -f docker-compose.scale.yml up -d

# 2) run the API with metrics on (separate terminal)
METRICS_ENABLED=true uvicorn api.index:app --reload --port 8000

# 3) publish fake vehicles, then watch the consumer ingest them
pip install aiomqtt
python scripts/mqtt_sim_publish.py --vehicles 10 --interval 5
python -m api.workers.mqtt_consumer
```

- Grafana → http://localhost:3001 (`admin` / `admin` — change on first login) → "Damascus Transit" folder → **API Overview**.
- Prometheus → http://localhost:9090
- API metrics → http://localhost:8000/metrics

---

## 5. Recommended next steps (priority order)

1. **S3.4 — SSE off the web process** onto a Redis pub/sub consumer (removes sticky-session limit; unblocks horizontal scaling). High value, self-contained.
2. **S4.1 — Provision the TimescaleDB hypertable** (migration 009 is ready) + continuous aggregates (S4.2). Unlocks the historical-analytics and the remaining Grafana panels (Redis Geo p99, chunk size).
3. **S2.3 / S2.4** — device migration to Protobuf-over-HTTP + ingest backpressure.
4. **S5 — Kafka shim** (Redpanda) once sustained load justifies it (decision gate: 25,000 vehicles per ADR-005).
5. **S6.2 — Reference C++ firmware** for the custom GPS unit (the no-smartphone path).
6. **Docs:** S1.5 capacity-planning ADR-005 + S1.6 cost model.

---

*This file is the human-readable index; the authoritative checkboxes live in `ROADMAP_100.md` and `Scale_100k_Roadmap.md`.*
