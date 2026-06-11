# CTO Briefing — Damascus Transit System

## Technical Overview

Damascus Transit System is a real-time GPS-based public transport platform. This document contains everything you need to lead the technical team.

**Working Directory:** `/Users/yahya/Desktop/TransitSystem`
**Repository:** GitHub (access via GITHUB_TOKEN env var)
**Production:** Vercel (access via VERCEL_TOKEN env var)
**Database:** Supabase PostgreSQL + PostGIS

---

## ⚠️ Pending: Frankfurt Migration (DAM-49)

**Status:** Blocked — waiting for new Supabase project credentials

**Context:** Load test (DAM-45) confirmed the current Supabase project runs in **us-east-1**, adding 80-120ms latency for Damascus users. Migration to Frankfurt (eu-central-1) is in progress.

**Current project:** `usxcuocnvfeltcdcnqoy` (us-east-1, Vercel project `prj_YhiCddRpAglbm40Nhpe8IOxATZbT`)
**Current data:** Only seed data (no live production data) — migration is safe to proceed.

**What's ready:**
- Migration script: `db/migrate_to_frankfurt.sh` — fully automated once new project exists
- Schema: `db/schema.sql` (no pg_dump needed, already in repo)
- Seed data: `db/seed.sql` (no data export needed, seed data only)

**What's needed from you (human):**
1. Go to [supabase.com](https://supabase.com) → New Project → Region: **Frankfurt (eu-central-1)**
2. Note the new project URL, anon key, service_role key, and JWT secret
3. Fill those values into `db/migrate_to_frankfurt.sh` (top of file, 4 variables)
4. Run: `bash db/migrate_to_frankfurt.sh`

The script will automatically update Vercel env vars and trigger a redeployment.
**Alternatively**, provide a Supabase Personal Access Token (from supabase.com → Account → Access Tokens) and this can be fully automated.

---

## Available Credentials

The following are available as **Sealed environment variables**:

- **GITHUB_TOKEN** — GitHub Personal Access Token for repo access, PRs, Actions
- **VERCEL_TOKEN** — Vercel token for deployments

Pass these to any technical agent that needs GitHub or Vercel access.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python 3.11), single file `api/index.py` (2,100 lines) |
| Database | Supabase PostgreSQL 16 + PostGIS |
| Auth | JWT + RBAC (admin, dispatcher, driver, viewer) |
| Frontend | Static HTML + MapLibre GL JS (4 apps) |
| Real-time | Server-Sent Events (SSE) |
| IoT | Traccar webhook integration (HMAC signed) |
| Deployment | Vercel (serverless) + Docker (local dev) |
| Maps | MapLibre GL JS 4.0, OpenStreetMap tiles |
| Fonts | IBM Plex Sans Arabic (bilingual) |

---

## Project Structure

```
TransitSystem/
├── api/
│   ├── index.py          # Main FastAPI app (2,100 lines, 26 endpoints)
│   └── test.py           # Diagnostic endpoint
├── db/
│   ├── schema.sql        # 15 tables, PostGIS, RLS, functions (422 lines)
│   ├── seed.sql          # 42 stops, 8 routes, 24 vehicles (231 lines)
│   └── gtfs/             # GTFS feed (agency, stops, routes, trips, etc.)
├── public/
│   ├── index.html        # Main dashboard (real-time map)
│   ├── admin/index.html  # Admin panel
│   ├── passenger/        # Passenger PWA (manifest + service worker)
│   └── driver/           # Driver PWA (manifest + service worker)
├── tests/
│   ├── conftest.py       # Pytest fixtures
│   ├── test_happy_paths.py    # Integration tests
│   ├── test_api_contract.py   # Contract tests (Pact)
│   ├── stub_server.py         # Mock Supabase server
│   └── locustfile.py          # Load testing
├── lib/                  # Shared utilities
├── docker-compose.yml    # Single service: api on port 8000
├── Dockerfile            # Python 3.11-slim + uvicorn
├── vercel.json           # Vercel routing config
├── requirements.txt      # FastAPI, httpx, PyJWT, bcrypt, pydantic
├── DEPLOY.md             # Full deployment guide
├── README.md             # Project overview
└── markdown-files/       # Documentation for AI agents
```

---

## API Endpoints (26 Total)

### Health & Auth
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/health | None | Health check with DB status |
| POST | /api/auth/login | None | Login, returns JWT token |

### Public Routes & Stops
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/routes | None | List all 8 Damascus routes |
| GET | /api/routes/{route_id} | None | Single route with stops |
| GET | /api/stops | None | All 42 stops with coordinates |
| GET | /api/stops/nearest | None | Nearest stops by lat/lon (1km) |
| GET | /api/schedules/{route_id} | None | Departure times for a route |

### Vehicles & Real-Time
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/vehicles | None | All vehicles with positions |
| GET | /api/vehicles/positions | None | Raw position data |
| GET | /api/stream | None | SSE real-time position stream |

### Analytics
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/stats | None | Fleet statistics |

### Driver Mobile API
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/driver/position | driver | Update GPS coordinates |
| POST | /api/driver/trip/start | driver | Begin trip on route |
| POST | /api/driver/trip/end | driver | End trip with stats |
| POST | /api/driver/trip/passenger-count | driver | Update occupancy |

### Admin/Dispatcher
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/admin/users | admin | List all users |
| POST | /api/admin/users | admin | Create user |
| PUT | /api/admin/users/{user_id} | admin | Update user |
| GET | /api/admin/vehicles | dispatcher+ | List vehicles |
| POST | /api/admin/vehicles | dispatcher+ | Create vehicle |
| PUT | /api/admin/vehicles/{vehicle_id} | dispatcher+ | Update vehicle |
| POST | /api/admin/vehicles/{vehicle_id}/assign | dispatcher+ | Assign to driver/route |

### Alerts
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/admin/alerts | dispatcher+ | Unresolved alerts |
| PUT | /api/admin/alerts/{alert_id}/resolve | dispatcher+ | Resolve alert |

### Trips & Analytics
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/admin/trips | dispatcher+ | Historical trip data |
| GET | /api/admin/analytics/overview | admin | Dashboard summary |

### IoT Integration
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/traccar/position | HMAC | Traccar GPS webhook |
| POST | /api/traccar/event | HMAC | Traccar event webhook |

---

## Database Schema (15 Tables)

**Engine:** PostgreSQL 16 + PostGIS + UUID extensions
**File:** `db/schema.sql`

1. **users** — id, email, password_hash, full_name, full_name_ar, role (admin|dispatcher|driver|viewer), phone, is_active
2. **routes** — id, route_id, name, name_ar, route_type (bus|microbus|taxi), color, geometry (LineString), distance_km, fare_syp
3. **stops** — id, stop_id, name, name_ar, location (Point), address, address_ar, has_shelter, has_display
4. **route_stops** — route_id, stop_id, stop_sequence, distance_from_start_km, typical_arrival_offset_min
5. **vehicles** — id, vehicle_id, name, name_ar, vehicle_type, capacity, status (active|idle|maintenance|decommissioned), assigned_route_id, assigned_driver_id, gps_device_id
6. **vehicle_positions** — id, vehicle_id, location (Point), speed_kmh, heading, source (simulator|traccar|osmand), occupancy_pct, recorded_at
7. **vehicle_positions_latest** — Materialized latest positions (trigger-updated, Supabase Realtime enabled)
8. **trips** — id, vehicle_id, route_id, driver_id, status (scheduled|in_progress|completed|cancelled), passenger_count, distance_km, on_time_pct
9. **alerts** — id, vehicle_id, alert_type (speed_violation|route_deviation|geofence_exit|breakdown|delay|sos|maintenance_due|connection_lost), severity, is_resolved
10. **geofences** — id, name, geometry (Polygon), geofence_type (zone|depot|terminal), speed_limit_kmh
11. **schedules** — id, route_id, day_of_week, first_departure, last_departure, frequency_min
12. **audit_log** — id, user_id, action, entity_type, entity_id, details (JSONB), ip_address

**Row-Level Security (RLS):** Enabled. Admins=full access, dispatchers=vehicles+positions, drivers=own data, viewers=read-only public.

**Database Functions:**
- `upsert_vehicle_position()` — Insert GPS + update latest in single transaction
- `find_nearest_stops()` — ST_DWithin spatial query (1km radius)
- `estimate_arrival()` — ETA from vehicle speed + route geometry

---

## Known Technical Debt (8 Issues)

1. **Single-file API** — All 2,100 lines in `api/index.py`. Needs modular refactoring.
2. **Traccar HMAC optional** — Webhook signature verification can be skipped. Must be enforced.
3. **In-memory rate limiter** — Resets on Vercel cold starts. Needs Redis or Supabase-backed solution.
4. **CORS allows localhost** — Production config includes `localhost:3000`. Must be removed.
5. **No password complexity** — Users can set weak passwords. Need validation rules.
6. **No input sanitization** — SQL injection risk on some endpoints. Need parameterized queries audit.
7. **No API versioning** — All endpoints are unversioned. Need `/api/v1/` prefix.
8. **SSE reconnect** — 25-second timeout on Vercel serverless. Consider WebSocket upgrade.

---

## Scale Projections

| Metric | Current | 3 Months | 12 Months |
|--------|---------|----------|-----------|
| Vehicles | 24 (seeded) | 100 | 500 |
| API Requests/day | ~100 (dev) | 50,000 | 500,000 |
| Position Updates/min | ~10 | 500 | 2,500 |
| Database Size | 10 MB | 5 GB | 50 GB |
| Concurrent Users | 5 | 500 | 5,000 |

---

## Frontend Apps (4 Total)

All in `public/` directory, pure HTML + JS (no framework):

1. **Main Dashboard** (`public/index.html`) — Real-time map with MapLibre GL JS, vehicle markers, route overlays
2. **Admin Panel** (`public/admin/index.html`) — Vehicle management, alert resolution, trip analytics
3. **Passenger PWA** (`public/passenger/`) — Route tracking, stop suggestions, fare lookup, offline support
4. **Driver PWA** (`public/driver/`) — Trip controls, passenger counting, navigation

---

## Agent Hiring Plan

As CTO, you are responsible for hiring the following technical agents. For business agents (Researcher, Legal, Finance, Grant Writer, Marketing), coordinate with the CEO.

### How to Hire

Create each agent in Paperclip with the description below. All agents should use:
- **Model:** `claude-opus-4-6`
- **Working directory:** `/Users/yahya/Desktop/TransitSystem`
- **Adapter:** `claude_local`

---

### Agent 1: Apps Builder
**Role:** `engineer`

A full-stack developer that builds features for the Damascus transit platform at /Users/yahya/Desktop/TransitSystem. Implements new API endpoints in api/index.py, creates frontend components in public/, and integrates with Supabase. Read markdown-files/CTO_BRIEFING.md for architecture details.

---

### Agent 2: Debug Tester
**Role:** `engineer`

A QA engineer that writes and runs tests for the Damascus transit platform at /Users/yahya/Desktop/TransitSystem. Creates pytest tests in tests/, performs security audits, finds bugs, validates API contracts, and runs load tests with Locust. Read markdown-files/CTO_BRIEFING.md for all endpoints.

---

### Agent 3: DevOps Engineer
**Role:** `engineer`

A DevOps Engineer that manages CI/CD, Docker, infrastructure, and deployments for the transit platform at /Users/yahya/Desktop/TransitSystem. Sets up GitHub Actions workflows, manages docker-compose.yml, writes Terraform for AWS, configures Vercel deployments, and builds monitoring. Read markdown-files/CTO_BRIEFING.md for architecture details.

---

### Agent 4: Daily Reporter
**Role:** `engineer`

A reporting agent that generates end-of-day activity summaries for the Damascus transit platform at /Users/yahya/Desktop/TransitSystem. Gathers git commits, GitHub PRs/issues, checks build status, and creates a daily report as DailyReport_YYYY-MM-DD.docx in /Users/yahya/Desktop/TransitSystem/Reports/. Read markdown-files/DAILY_REPORT_AGENT.md for instructions.

---

### Agent 5: Researcher (Business — Reports to CEO)
**Role:** `researcher`

A market researcher for the Damascus transit platform. Analyzes competitors, studies MENA transit tech, gathers ridership data, evaluates technology options, and produces research reports in markdown-files/. Read markdown-files/CEO_BRIEFING.md for business context.

---

### Agent 6: Legal Advisor (Business — Reports to CEO)
**Role:** `researcher`

A legal advisor for the Damascus transit platform. Reviews Syrian transport regulations, data privacy law compliance, drafts terms of service, analyzes liability, and produces legal documents in markdown-files/legal/. Read markdown-files/CEO_BRIEFING.md for business context.

---

### Agent 7: Finance Manager (Business — Reports to CEO)
**Role:** `researcher`

A finance manager for the Damascus transit platform. Creates budgets, financial models, unit economics analysis, runway projections, and cost optimization reports in markdown-files/financial/. Read markdown-files/CEO_BRIEFING.md for business model details.

---

### Agent 8: Grant Writer (Business — Reports to CEO)
**Role:** `researcher`

A grant writer for the Damascus transit platform. Writes proposals for World Bank, UNDP, and international funding. Prepares applications, impact assessments, and funding documents in markdown-files/business/. Read markdown-files/CEO_BRIEFING.md for project context.

---

### Agent 9: Marketing & Outreach (Business — Reports to CEO)
**Role:** `researcher`

A marketing specialist for the Damascus transit platform. Creates social media content, press releases, partnership outreach materials, ministry pitch decks, and brand strategy docs in markdown-files/business/. Read markdown-files/CEO_BRIEFING.md for business context.

---

## Technical Priorities

### Immediate (Week 1)
1. Fix security vulnerabilities (CORS, HMAC enforcement, password validation)
2. Set up GitHub Actions CI/CD pipeline
3. Write comprehensive test suite for all 26 endpoints
4. Set up error monitoring and alerting

### Short-term (Weeks 2-4)
5. Refactor api/index.py into modular structure
6. Implement Redis caching for hot endpoints
7. Add API versioning (/api/v1/)
8. Build rate limiting with persistent storage
9. Improve admin dashboard with analytics charts

### Medium-term (Weeks 5-8)
10. Add WebSocket support for real-time (replace SSE)
11. Build passenger notification system (ETA alerts)
12. Implement driver performance scoring
13. Prepare GTFS feed for Google Maps submission
14. Load test to 1000 concurrent users
15. Database optimization (indexing, query tuning, connection pooling)

---

## Reference Documents

All documentation in `markdown-files/` subfolders:

- `business/` — Business Model Canvas, Competitive Analysis, Ministry Pitch, World Bank Proposal
- `legal/` — Legal Framework, Risk Assessment
- `technical/` — Technical Architecture, Hardware Requirements, Setup Guide, Research Reports
- `financial/` — Financial Plan, Scaling Cost Model
- `project-management/` — MVP Phases Tracker, Project Timeline, Roadmap, Features Summary

Read these before making architectural or staffing decisions.
