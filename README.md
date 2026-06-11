<p align="center">
  <h1 align="center">DamascusTransit</h1>
  <p align="center">
    Real-time GPS tracking, fleet management, and QR fare payment for public transit in Syria
    <br />
    <strong>نظام النقل العام في دمشق — تتبع مباشر، إدارة أسطول، ودفع بمسح الرمز</strong>
  </p>
  <p align="center">
    <a href="#quick-start">Quick Start</a> ·
    <a href="#architecture">Architecture</a> ·
    <a href="instructions/README.md">Instructions (admin / operator / driver / hardware)</a> ·
    <a href="docs/DEPLOY.md">Deploy</a> ·
    <a href="docs/ARCHITECTURE_DECISIONS.md">Why it's built this way</a>
  </p>
</p>

---

DamascusTransit is an open-source platform for Syrian public transit — buses,
microbuses, and taxis. Passengers see vehicles live and pay fares by scanning a
**Sham Cash QR**; drivers run trips from a phone; **operators** register vehicles
and issue driver credentials; the **transit-authority admin approves every
vehicle before it may operate**. GPS comes from custom in-vehicle hardware
(MQTT/Protobuf) or the driver app.

## Status (11 June 2026)

| Component | State |
|---|---|
| Backend (`api/`) | FastAPI · 89 routes · JWT + RBAC + revocation · per-operator tenancy on reads **and** writes · vehicle approval workflow · Sham Cash payment scaffold (sandbox) |
| Database (`db/`) | PostgreSQL 16 + PostGIS · migration chain `002→020` (019 approvals, 020 payments) · TimescaleDB hypertable for telemetry |
| Web (`public/`) | Landing + passenger PWA + driver console + **9-page admin console** (approvals, vehicles, users, routes, alerts, payments, audit, analytics) — RTL-first, unified design system |
| Mobile (`flutter_app/`) | **The official iOS + Android app** (Flutter 3.22, Riverpod, MapLibre, SSE) |
| Hardware (`firmware/`, `schemas/`) | Edge-unit spec (ESP32/STM32 + SIM900A→BG95) · Protobuf wire format · HMAC-signed ingest over HTTPS or MQTT |
| Observability (`monitoring/`) | Prometheus `/metrics` + auto-provisioned Grafana dashboards + Mosquitto dev broker (`docker-compose.scale.yml`) |
| Tests | ~360 pytest tests green + Playwright specs |

> **Deploy note:** apply DB migrations **through `020`** before deploying this
> code — `docs/APPLY_MIGRATIONS.md`.

## The operating model — نموذج التشغيل

```
operator (المشغّل)                    admin (الإدارة)              driver (السائق)
  registers vehicle  ──▶  pending ──▶  APPROVES on /admin/approvals  ──▶  drives, streams GPS,
  creates driver login                 (or rejects / suspends)            collects QR fares
```

No vehicle starts a trip, lands on the map, or collects a fare before approval —
enforced server-side at every entry point. Per-role walkthroughs:
**[instructions/](instructions/README.md)**.

## Architecture

```
┌─────────────┐   ┌──────────────────────────────────────────────┐
│ Passengers  │──▶│ Vercel / Docker (static + serverless API)    │
│ Drivers     │   │  ├── /            public live map            │
│ Operators   │   │  ├── /passenger/  PWA (stops, ETA, pay-QR)   │
│ Admins      │   │  ├── /driver/     console (trips, GPS, QR)   │
└─────────────┘   │  └── /admin/      9-page console + approvals │
┌─────────────┐   │                                              │
│ Flutter app │──▶│  /api/*  FastAPI · JWT · SSE · GTFS · pay    │
│ iOS+Android │   └────────────┬─────────────────────────────────┘
└─────────────┘                │
                    ┌──────────▼────────────────────────────────┐
                    │ Supabase — PostgreSQL 16 + PostGIS + RLS  │
                    │  TimescaleDB hypertable (telemetry)       │
                    └──────────┬────────────────────────────────┘
                               │                    ┌────────────┐
┌──────────────┐   MQTT/HTTPS  │   Redis (live bus) │ Prometheus │
│ GPS hardware │──HMAC-signed──┤                    │  + Grafana │
│ (your units) │   Protobuf    │                    └────────────┘
└──────────────┘   vehicles/<id>/status
```

Every "why" (FastAPI, Supabase, TimescaleDB, MQTT, Grafana, SSE, Flutter, the
approval workflow, the payment security design):
**[docs/ARCHITECTURE_DECISIONS.md](docs/ARCHITECTURE_DECISIONS.md)**.

## Tech stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python 3.12), Pydantic 2, httpx |
| Database | Supabase PostgreSQL 16 + PostGIS + TimescaleDB |
| Auth | JWT (HS256) + bcrypt + RBAC + iat/is_active revocation |
| Payments | Sham Cash QR scaffold — HMAC-signed payloads, idempotent webhook, sandbox mode |
| Real-time | SSE (`/api/stream`) + Redis pub/sub live bus; WebSocket for route subscriptions |
| Device ingest | MQTT (Mosquitto dev / EMQX prod) or HTTPS bridge · Protobuf (`schemas/telematics.proto`) · HMAC-SHA256 |
| Web frontend | Static HTML + MapLibre GL · RTL Arabic-first design system (`public/lib/design-system.css`) |
| Mobile | Flutter 3.22 (Riverpod, go_router, Dio, drift, flutter_map) |
| Monitoring | Prometheus + Grafana + Sentry |

## Quick start

```bash
# 1. Clone
git clone https://github.com/actuatorsos/SyrianTransitSystem.git
cd SyrianTransitSystem

# 2. Configure
cp .env.example .env       # Supabase creds + JWT_SECRET (≥32 chars) — every var documented inline

# 3. Apply DB schema + migrations (db/schema.sql, then db/migrations/ in order)
#    walkthrough: docs/APPLY_MIGRATIONS.md

# 4. Run the API
pip install -r requirements.txt
uvicorn api.index:app --reload --port 8000

# 5. Open the apps
open http://localhost:8000/             # public live map
open http://localhost:8000/passenger/   # passenger PWA
open http://localhost:8000/driver/      # driver console
open http://localhost:8000/admin/       # staff console (login: docs/DEMO_ACCOUNTS.md)
```

Optional dev stack (MQTT broker + Prometheus + Grafana + Redis):

```bash
docker compose -f docker-compose.scale.yml up -d
```

## Mobile (iOS + Android)

The official app is **Flutter** (`flutter_app/`):

```bash
cd flutter_app
flutter pub get
flutter run --dart-define=API_BASE=http://10.0.2.2:8000   # Android emulator → local API
```

Full path from a bare GPS unit to seeing the bus move in the app:
**[instructions/GPS_TO_APP_ROADMAP.md](instructions/GPS_TO_APP_ROADMAP.md)**.
(The earlier Capacitor shell was retired on 2026-06-11 — see
[ADR-001](docs/adr/ADR-001-mobile-shell.md); it lives in `archives/` if ever needed.)

## Hardware (your GPS units)

* Edge firmware spec: [`firmware/SPEC.md`](firmware/SPEC.md) — MCU/modem/GPS BOM,
  adaptive heartbeat, offline FIFO, watchdog.
* Wire contract + broker topics + monitoring:
  [`instructions/HARDWARE_SETUP.md`](instructions/HARDWARE_SETUP.md).
* Frames are HMAC-signed per device and **dropped unless the vehicle is
  admin-approved**.

## Security posture

Hardened 2026-06-11 (see [`RESTRUCTURE_REPORT_2026-06-11.md`](RESTRUCTURE_REPORT_2026-06-11.md)):

- Tenant isolation on every public read, admin write, WebSocket, and push broadcast.
- Vehicle approval gate enforced at trips, GPS ingest (driver app, Traccar, MQTT/HTTP), QR issuance, and payment initiation.
- JWT revocation on password change **and** account deactivation (≤ 5 s).
- Constant-time secret compares everywhere (cron, devices, webhooks); fail-closed webhooks.
- All API-fed `innerHTML` escaped; CSP on every page; staff passwords force first-login rotation.
- Payments: signed QR (anti-counterfeit), fixed-fare enforcement, idempotent confirmation (no double-credit).

## Repository layout

```
api/             FastAPI backend (routers/, core/, models/, workers/)
db/              schema.sql + migrations 002→020
public/          web apps (landing, passenger, driver, admin×9, help, demo)
flutter_app/     official iOS+Android app
firmware/        GPS edge-unit spec        schemas/   Protobuf wire format
monitoring/      Grafana/Prometheus/Mosquitto configs
instructions/    how to USE the system (admin/operator/driver/hardware/roadmap)
docs/            how it's BUILT (decisions, deploy, migrations, ADRs, runbooks)
business/        ministry pitch package, financial/legal docs
tests/           pytest (~360) + Playwright
archives/        zipped legacy snapshots (git-ignored)
```

## CI

| Workflow | Purpose |
|---|---|
| `ci.yml` | Ruff lint + pytest with coverage |
| `flutter.yml` | `flutter analyze` + tests + debug APK |
| `security-scan.yml` | `pip-audit`, gitleaks, Flutter deps |
| `codeql.yml` | static security analysis |
| `openapi-lint.yml` | Spectral lint of `openapi.json` |
| `gtfs-validate.yml` | validates the GTFS export |
| `backup.yml` | scheduled DB backup |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Roadmaps: [`ROADMAP_100.md`](ROADMAP_100.md)
(revival — complete except store rollout) and
[`Scale_100k_Roadmap.md`](Scale_100k_Roadmap.md) (scale track — in progress).

## License

MIT — see [LICENSE](LICENSE).
