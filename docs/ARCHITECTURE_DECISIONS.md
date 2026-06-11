# Damascus Transit — Architecture Decisions (the "why" document)

**Updated:** 2026-06-11 · **Audience:** you (the owner), future engineers, ministry reviewers.
This explains *why* each technology and design exists in the project, in plain language.

---

## 1. Why Python + FastAPI for the backend

* **Async-first.** A transit API is overwhelmingly I/O-bound: hundreds of GPS pings,
  SSE streams, and database round-trips per second, each spending its time *waiting*.
  FastAPI on `asyncio` lets one cheap worker hold thousands of concurrent connections —
  exactly the workload profile here.
* **Pydantic validation as a security layer.** Every request body is validated and
  type-coerced *before* business code runs (coordinates bounded ±90/±180, fares capped,
  roles restricted to a literal list). Several injection-class bugs are simply
  impossible to reach.
* **OpenAPI for free.** `openapi.json` is generated from the code — the Flutter app and
  the web consoles develop against a contract, not against guesses.
* **Hiring reality.** Python is the most teachable mainstream language; a future
  Syrian team can maintain this without scarce Go/Rust talent.
* **Trade-off accepted:** raw throughput is lower than Go. The scale plan compensates
  architecturally (Redis hot path, MQTT ingestion, queue buffering) instead of
  rewriting the language.

## 2. Why Supabase (PostgreSQL 16 + PostGIS)

* **PostGIS is the industry's GIS engine.** Nearest-stop, route geometry, and
  geofencing are first-class SQL (`ST_DWithin`, `ST_Contains`) rather than custom code.
* **One database for everything** — fleet, users, trips, alerts, payments — with
  **Row-Level Security** as a second tenancy wall under the application's own
  operator scoping (defense in depth).
* **Free tier + EU region** keeps the demo running at zero cost while staying
  production-shaped (the same SQL runs on any self-hosted Postgres if the ministry
  later requires on-premise hosting — see `DOCKER_MINISTRY_DEPLOY.md`).

## 3. Why a time-series database (TimescaleDB, migration 009)

GPS telemetry is append-only, time-ordered, and huge: 100,000 vehicles × 1 ping/5s
≈ **1.7 billion rows/day**. A plain table dies; a *hypertable* partitions by time
("chunks"), so inserts stay fast forever and old chunks compress ~90% or drop by
retention policy. TimescaleDB is chosen over InfluxDB/ClickHouse because it **is
Postgres** — same SQL, same PostGIS joins, same backup tooling, zero new
infrastructure to learn.

## 4. Why MQTT for vehicle hardware (your GPS units)

* **Built for unreliable cellular links.** MQTT keeps one persistent TCP session per
  device with 2-byte keep-alives; HTTP would pay full TLS+headers per ping
  (~600 bytes of overhead for a 40-byte position).
* **QoS 1 + offline queueing**: a bus entering a tunnel buffers frames and replays
  them on reconnect (`is_replay` flag in the schema) — no data loss, no custom code.
* **Fan-out for later**: the broker can feed the API, Kafka, and an archiver
  simultaneously without the device knowing.
* **Protobuf payload** (`schemas/telematics.proto`): ~80% smaller than JSON — that is
  real SIM-card money at fleet scale.
* The HTTP bridge (`/api/v1/telemetry/*`) accepts the *same* signed payload so your
  firmware can migrate transport without changing its message format.
  Authentication is HMAC-SHA256 per device (`DEVICE_INGEST_SECRET`), compared in
  constant time, failing closed.

## 5. Why Grafana + Prometheus (and not a custom ops page)

* The **admin dashboard answers business questions** (fleet, trips, approvals).
  **Grafana answers engineering questions** (p95 latency, ingest rate, error spikes,
  broker backlog) — you need both, and they evolve at different speeds.
* Prometheus scrapes `/metrics` (enabled by `METRICS_ENABLED=true` on Docker
  deployments); Grafana dashboards live in `monitoring/grafana/dashboards/` as JSON —
  versioned, reviewable, reproducible on any machine with `docker-compose.scale.yml`.
* Building equivalent charts by hand would be weeks of work for a worse result;
  Grafana is the de-facto standard ops UI and free to self-host.

## 6. Why SSE for live maps (and WebSocket only where needed)

`/api/stream` uses **Server-Sent Events**: one-directional position pushes fit SSE
exactly, it traverses proxies/CDNs better, auto-reconnects natively in browsers, and
works on Vercel's serverless model. The S3.4 live bus (Redis pub/sub,
`api/core/live_bus.py`) fans one driver update out to every subscribed client without
per-client DB polling. `/api/ws/track` (WebSocket) remains for bidirectional needs
(subscribe/unsubscribe per route) and is **operator-scoped since 2026-06-11**.

## 7. Why two mobile strategies exist (and which to ship)

* `mobile/` — **Capacitor** wraps the existing PWA pages in a native shell. Cheapest
  path to the stores; one codebase for web+apps. **This is the v1 recommendation.**
* `flutter_app/` — **Flutter** native rewrite. Better offline maps, background GPS,
  and 60fps feel; it is the v2 candidate (see ADR-001 in `markdown-files/adr/`).
* Keeping both *active* triples mobile work — ship Capacitor v1, develop Flutter v2.

## 8. The role model (who can do what)

| Role | Means | Can | Cannot |
|---|---|---|---|
| `super_admin` | platform owner | everything, across operators | — |
| `admin` | transit-authority manager | **approve/reject/suspend vehicles**, create staff, manage routes/users, see audit log, broadcast push | create super_admins |
| `dispatcher` | **the operator** (company staff) | register vehicles, **create driver accounts** (username+password), assign driver↔vehicle↔route, maintain own fleet, see own payments | **approve vehicles**, create non-driver users, see audit log, touch other operators |
| `driver` | behind the wheel | log in, start/end trips, stream GPS, report incidents, show payment QR | anything administrative |
| `viewer` | public registered user | read public data | any write |

Two-person control: **the operator provisions, the admin authorises.** No single
compromised dispatcher account can put a vehicle into service.

## 9. The vehicle approval workflow (migration 019)

```
operator registers vehicle ──▶ pending ──admin──▶ approved ──admin──▶ suspended
        + creates driver           │                   ▲                  │
        + assigns driver/route     └──admin──▶ rejected ──resubmit──▶ pending
```

* Enforced **server-side** at every entry point a vehicle has into the system:
  driver trip-start, driver position, Traccar webhook, MQTT/HTTP telemetry
  (60-second cached check in the hot path), payment QR issuance, and payment
  initiation. The public map never shows unapproved vehicles.
* Every decision writes to `audit_log` with the deciding admin, old→new state, and
  note; the admin UI is `/admin/approvals.html`.
* Existing fleet was grandfathered as `approved` (decision 2026-06-11) so nothing
  stopped when the migration shipped.

## 10. Sham Cash payments — design of the scaffold (migration 020)

* **Signed QR, not a plain code.** The in-vehicle QR payload is
  `DTSPAY|v1|vehicle|operator|nonce|HMAC`. A fraudster swapping stickers to divert
  fares fails signature verification. Server-side, the vehicle must also be
  *approved* and the operator must match.
* **Fixed-fare enforcement.** For bus/microbus routes with `fare_syp`, the client
  cannot pay a different amount (taxis pass the metered amount).
* **Idempotent confirmation.** `payments.provider_ref` is UNIQUE and confirmation
  PATCHes only `status=pending` rows — a replayed webhook cannot double-credit.
  The webhook itself is HMAC-SHA256 over the raw body, constant-time compared,
  failing closed when unconfigured.
* **Sandbox mode by default.** Until you obtain merchant credentials
  (`SHAM_CASH_MERCHANT_ID`, `SHAM_CASH_API_SECRET`, `SHAM_CASH_WEBHOOK_SECRET`),
  the full passenger loop works with an admin-gated simulator
  (`POST /api/pay/sandbox/confirm`) and a clearly-labelled SBX badge in
  `/admin/payments.html`. Going live is configuration, not code.

## 11. Security model (post-restructure)

* **JWT (HS256, 24h)** with `iat`-based revocation: password change/reset bumps
  `password_changed_at` (now written by the app *and* a DB trigger) and old tokens
  die within 5 seconds; deactivating an account revokes its live tokens the same way.
  Login rejects inactive accounts and supports Cloudflare Turnstile when configured.
* **Tenancy:** every public read resolves to exactly **one** operator
  (`resolve_read_scope`, cached); every admin mutation appends an operator filter
  (`_own_op_filter`) so cross-tenant writes by UUID are impossible; WS/SSE/push are
  operator-scoped.
* **Webhooks/devices/cron:** HMAC-SHA256, constant-time compares, fail-closed.
* **Frontend:** all API-fed `innerHTML` sinks escape data (`escH`/`ADMIN_AUTH.esc`);
  CSP now covers every page; staff credentials issued by operators force
  first-login rotation.
* **Headers:** HSTS, nosniff, frame-deny, scoped CSP, Permissions-Policy in
  `vercel.json`.

## 12. Why the frontend is plain HTML/CSS/JS (no React)

The public pages are content-first, RTL Arabic, government-styled (design tokens in
`public/lib/design-system.css` — national green `#0E5650`, gold `#C9A95B`, Readex
Pro). Static files on a CDN load in well under a second on a 3G connection in
Damascus, work offline as PWAs, and have zero build chain — any editor can fix a
page. The admin console shares one shell (`/admin/_shell.js` renders the role-aware
sidebar; `_gate.js` blocks unauthenticated flashes; `_layout.css` shares the chrome),
so all nine admin pages stay visually and behaviourally identical.

## 13. Why Vercel now, Docker for the ministry later

Vercel gives free TLS, CDN, serverless API scaling, and zero ops while the project
is a demo/pilot. The same repo ships `Dockerfile.prod`, `docker-compose.prod.yml`
(nginx + API) and `docker-compose.scale.yml` (Mosquitto MQTT, Prometheus, Grafana,
Redis) for sovereign on-premise deployment — see `DOCKER_MINISTRY_DEPLOY.md`.

## 14. Why GTFS endpoints exist

`/api/gtfs/*` publishes the network in the **General Transit Feed Specification** —
the open format Google Maps and every transit app consume. The day the ministry
wants Damascus buses inside Google Maps, the feed already exists.

## 15. Repository layout (after the 2026-06-11 restructure)

```
api/            FastAPI backend (routers/, core/, models/, workers/)
db/             schema.sql + migrations/002…020 (single migration chain)
public/         web frontends (/, /passenger, /driver, /admin×9, /help, /demo)
flutter_app/    Flutter native app (v2 candidate)
mobile/         Capacitor native shell (v1)
monitoring/     Mosquitto/Prometheus/Grafana configs + dashboards
firmware/       SPEC.md for your custom GPS hardware
schemas/        telematics.proto (device wire format)
tests/          pytest suite (~360 tests) + Playwright specs
archives/       single zip of the pre-restructure source/ and dts-push/ trees
docs/           this file + setup docs
```

The previous `source/` (monolith v5.0) and `dts-push/` (GitHub snapshot) trees were
merged into the root and archived — there is now **one** canonical codebase.
