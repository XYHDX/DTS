<p align="center">
  <h1 align="center">DamascusTransit</h1>
  <p align="center">
    Real-time GPS tracking and fleet management for public transit in Damascus, Syria
    <br />
    <strong>نظام النقل العام في دمشق</strong>
  </p>
  <p align="center">
    <a href="#quick-start">Quick Start</a> ·
    <a href="#architecture">Architecture</a> ·
    <a href="#mobile">Mobile</a> ·
    <a href="DEPLOY.md">Deploy</a> ·
    <a href="../ROADMAP_100.md">100-Step Roadmap</a>
  </p>
</p>

---

DamascusTransit is an open-source platform for real-time vehicle tracking, route management, and fleet analytics in Damascus. It runs on free-tier infrastructure and scales to 500+ vehicles.

The platform covers the full transit lifecycle: passengers find routes and track buses in real time, drivers manage trips from a mobile app, dispatchers monitor the fleet and respond to alerts, and administrators manage users, vehicles, and analytics.

## Status (24 May 2026)

| Component | State |
|---|---|
| Backend (`api/`) | 26 endpoints. JWT + RBAC + iat-based revocation. Security HIGHs cleared (H1, H2). MEDIUMs M1 hook landed; wiring in progress (M3 next). |
| Database (`db/`) | 15 tables + PostGIS + 7 migrations (007 adds `password_changed_at`). |
| Web (`public/`) | Dashboard, admin, passenger, driver — all rewritten on a unified design system (`public/lib/design-system.css`). RTL-first, dark-mode aware, ≥AA contrast. |
| Mobile shell A: Capacitor 6 (`mobile/`) | 70 % scaffolded; bridge wired; native projects ready. Targeted v1.0. |
| Mobile shell B: Flutter 3.22 (`flutter_app/`) | Runnable scaffold. Live SSE, JWT, MapLibre via `flutter_map`. Held as v2.0 candidate. See ADR-001. |
| CI (`.github/workflows/`) | Lint + tests + coverage + security-scan + db backup + gtfs-validate + **flutter** + Dependabot. |
| Tests | 307 / 307 last green run (Apr 18). Re-verify after deps refresh. |

## Architecture

```
┌─────────────┐   ┌─────────────────────────────────────────────┐
│ Passengers  │──▶│ Vercel (Frontend)                            │
│ Drivers     │   │  ├── /             Dashboard                 │
│ Dispatchers │   │  ├── /passenger/   PWA                       │
└─────────────┘   │  ├── /driver/      PWA                       │
                   │  └── /admin/       Operations + analytics    │
┌─────────────┐   │                                              │
│ Native apps │──▶│ Vercel (Serverless API)                      │
│ Capacitor/  │   │   /api/*   FastAPI · JWT · SSE · GTFS · …    │
│ Flutter     │   └────────────┬────────────────────────────────┘
└─────────────┘                │
                    ┌──────────▼────────────────────────────────┐
                    │ Supabase                                  │
                    │  · PostgreSQL 16 + PostGIS                │
                    │  · 15 tables + RLS                        │
                    │  · Realtime + Supavisor pooler            │
                    └──────────┬────────────────────────────────┘
                               │
┌─────────────┐    ┌──────────▼──────────┐
│ GPS devices │───▶│ Traccar  ──HMAC──▶ /api/traccar/position    │
└─────────────┘    └─────────────────────┘
```

## Tech stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python 3.12), Pydantic 2.13, httpx |
| Database | Supabase PostgreSQL 16 + PostGIS |
| Auth | JWT (PyJWT) + bcrypt + RBAC + iat-revocation |
| Web frontend | Static HTML + MapLibre GL JS 4.7 + unified CSS design system |
| Real-time | Server-Sent Events |
| Caching / Rate-limit | Upstash Redis with in-memory fail-closed fallback |
| Native shell A | Capacitor 6 (Android + iOS) |
| Native shell B | Flutter 3.22 (Android + iOS) — see `flutter_app/` |
| Monitoring | Sentry SDK ≥2.58 |
| Maps | OpenStreetMap raster tiles |

## Quick start

```bash
# 1. Clone
git clone https://github.com/actuatorsos/SyrianTransitSystem.git
cd SyrianTransitSystem

# 2. Configure
cp .env.example .env       # fill in Supabase creds + JWT_SECRET (≥32 chars)

# 3. Run backend
docker compose up --build  # serves http://localhost:8000

# 4. Open the web apps
open http://localhost:8000/             # public dashboard
open http://localhost:8000/passenger/   # passenger PWA
open http://localhost:8000/driver/      # driver PWA
open http://localhost:8000/admin/       # admin panel
```

## Mobile

Two shells exist; see [ADR-001](markdown-files/adr/ADR-001-mobile-shell.md) for why.

### Capacitor (v1.0 path)

```bash
cd mobile
npm install
npx cap sync android
cd android && ./gradlew assembleDebug    # APK on a connected device
```

The web assets it wraps live in `public/` — change them once, ship to web and native.

### Flutter (v2.0 candidate)

```bash
cd ../flutter_app
flutter pub get
flutter run --dart-define=API_BASE=http://10.0.2.2:8000
```

Architecture documented in `flutter_app/README.md`. CI builds a debug APK on every PR.

## Security posture

Cleared this revival (May 2026):

- **H1** Rate-limit bypass via `X-Forwarded-For` spoofing — `_get_client_ip` walks trusted proxies right-to-left, falls back to TCP source.
- **H2** Rate limiter fails open when Redis unreachable — replaced with thread-safe in-memory sliding window (`_rate_limit_check_memory`).
- **M1** JWT revocation on password change — `iat` claim added; `is_token_revoked_by_password_change()` helper added; migration `007_password_changed_at.sql` adds the column + trigger.
- **Security headers** — HSTS, X-CTO, X-Frame-Options, Referrer-Policy, Permissions-Policy, CSP on HTML responses.

Open (M3, M4, L1–L4): see `markdown-files/technical/Security_Scan_*.md`.

## CI

All workflows live in `.github/workflows/`:

| Workflow | Purpose |
|---|---|
| `ci.yml` | Ruff lint, pytest + coverage, smoke test |
| `flutter.yml` | `flutter analyze` + `flutter test` + debug APK build |
| `security-scan.yml` | `pip-audit` + custom scanner |
| `gtfs-validate.yml` | Validates the GTFS export feed |
| `backup.yml` | Scheduled Supabase backup |

Dependabot is configured for Python, Flutter (pub), Capacitor (npm), and GitHub Actions.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The 100-step revival roadmap is in [`ROADMAP_100.md`](../ROADMAP_100.md) — pick an unticked item and submit a PR referencing its number.

## License

MIT — see [LICENSE](LICENSE).
