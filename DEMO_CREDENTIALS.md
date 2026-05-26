# Damascus Transit — Demo Testing Credentials

One-stop cheat sheet for testing every part of the system end-to-end.

> ⚠ **Security update (2026-05-26):** each role now has its OWN unique
> password. The old shared `damascus2025` password was a critical privilege
> overlap (admin and operator had identical credentials). Every seeded
> account also starts with `must_change_password = true`, so the first
> successful login is REQUIRED to rotate the password before issuing a
> full-privilege JWT.
>
> Seeded by `db/supabase_bootstrap.sql` and `db/demo_accounts.sql`.
> Re-run either of those to force-rotate to these hashes.

---

## 1. Demo accounts (one password per role)

| # | Email | Initial Password | Role (DB enum) | UI to test on | Arabic name | English name |
|---|---|---|---|---|---|---|
| 0 | `superadmin@damascus-transit.demo` | `SuperAdmin#2026`     | `super_admin` | `/admin/login.html` → tab **إدارة / Admin** | مدير عام تجريبي | Demo Super Admin |
| 1 | `admin@damascus-transit.demo`      | `AdminDamascus#2026`  | `admin`       | `/admin/login.html` → tab **إدارة / Admin**      | مدير تجريبي     | Demo Admin     |
| 2 | `operator@damascus-transit.demo`   | `Dispatcher#2026`     | `dispatcher`  | `/admin/login.html` → tab **موزّع / Dispatcher** | مشغّل تجريبي    | Demo Operator  |
| 3 | `driver@damascus-transit.demo`     | `Driver#2026`         | `driver`      | `/admin/login.html` → tab **سائق / Driver** OR `/driver/` directly | سائق تجريبي    | Demo Driver    |
| 4 | `passenger@damascus-transit.demo`  | `Passenger#2026`      | `viewer`      | Not used — passengers are anonymous              | راكب تجريبي     | Demo Passenger |

> All five accounts have `must_change_password = true`. After login the
> token has limited scope and the client is required to call
> `POST /api/auth/change_password` before any privileged endpoint accepts
> the JWT.

> The "passenger" account exists in the seed but the public passenger app
> doesn't require a login at all. You can skip it. It's there for future
> use if a personal "saved routes" feature is added.

---

## 2. What each role can do

### Admin (`admin@damascus-transit.demo`)
After login lands on `/admin/`. Has access to every admin page:

| Page                    | URL                              | What to test |
|-------------------------|----------------------------------|---|
| Overview                | `/admin/`                        | Live map, KPIs (active vehicles, trips today, occupancy, open alerts), recent-alerts panel |
| Vehicles                | `/admin/vehicles.html`           | Bus list with assigned route, capacity, status pill |
| Users                   | `/admin/users.html`              | Full user list (admin-only — dispatcher won't see this page) |
| Routes                  | `/admin/routes.html`             | All 4 routes with color swatches and vehicle counts |
| Alerts                  | `/admin/alerts.html`             | All alerts + **Resolve** button on open rows |
| Analytics               | `/dashboard/analytics.html`      | Charts: trips/week, occupancy donut, route table, top incidents |
| Help                    | `/help/`                         | The user guide |

### Dispatcher (`operator@damascus-transit.demo`)
Same as admin **except**: `/admin/users.html` returns 403 (admin-only). Can resolve alerts and view all other admin screens.

### Driver (`driver@damascus-transit.demo`)
After login lands on `/driver/`. Tests:

| Feature                  | How |
|--------------------------|---|
| GPS streaming            | Allow location → green "متصل / Connected" pill |
| Start a trip             | Click **▶ بدء الرحلة** — should POST to `/api/driver/trip/start` |
| Live speed/distance/time | Counters tick while moving (or simulated) |
| Passenger count          | Increment/decrement during trip |
| Incident report          | **🚨 الإبلاغ عن حادث** — creates a critical alert that admins see |
| End a trip               | **■ إنهاء الرحلة** — POSTs to `/api/driver/trip/end` |
| Bilingual UI             | EN/AR pill in the driver-bar |

### Passenger (no account needed)
Just open `/passenger/` — no login. Tests:

| Feature                  | How |
|--------------------------|---|
| Search autocomplete      | Type "مزة" or "Bab Tuma" — dropdown appears with matching stops + routes |
| Keyboard nav             | Arrow/Enter/Escape work on the dropdown |
| Locate me                | **موقعي** button — asks for geolocation → fills "nearest stops" |
| Live map                 | Vehicle markers refresh every 5s via SSE |
| Popular routes           | Tap a route card → `/passenger/?route=<id>` |
| GTFS link                | Footer link → `/api/gtfs` (placeholder JSON) |
| Install PWA              | Banner appears on mobile/Edge → adds to home screen |
| Offline                  | Disable network → service worker serves the cached shell |

---

## 3. Quick API tests (CLI)

These run without the UI — useful for sanity checks.

### Health (no auth)
```bash
curl https://dts-brown.vercel.app/api/health
# → {"status":"ok", "config":{"supabase_configured":true,"jwt_configured":true,...}}
```

### Login (get JWT)
```bash
curl -X POST https://dts-brown.vercel.app/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@damascus-transit.demo","password":"damascus2025"}'
# → {"token":"eyJ...","user":{"id":...,"email":"admin@...","role":"admin"}}
```

Save the token then test gated endpoints:

```bash
TOKEN="eyJ..."   # paste from login response

# Admin-only — full user list
curl -H "Authorization: Bearer $TOKEN" \
  https://dts-brown.vercel.app/api/admin/users

# Dispatcher+ — alerts (try with operator@ login too)
curl -H "Authorization: Bearer $TOKEN" \
  https://dts-brown.vercel.app/api/admin/alerts?limit=10

# Resolve an alert (replace ID)
curl -X PATCH -H "Authorization: Bearer $TOKEN" \
  https://dts-brown.vercel.app/api/admin/alerts/<UUID>/resolve

# Admin-only vehicle update
curl -X PATCH -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"status":"maintenance"}' \
  https://dts-brown.vercel.app/api/admin/vehicles/<UUID>
```

### Without auth (public)
```bash
curl https://dts-brown.vercel.app/api/routes
curl https://dts-brown.vercel.app/api/stops
curl https://dts-brown.vercel.app/api/vehicles
curl https://dts-brown.vercel.app/api/stats
curl "https://dts-brown.vercel.app/api/stops/nearest?lat=33.513&lon=36.291&radius_m=1500"
```

---

## 4. Negative tests (what should fail)

| Test                                                | Expected |
|-----------------------------------------------------|----------|
| Login with wrong password                           | 401, "Invalid email or password / بيانات الدخول غير صحيحة" — same latency as wrong email (timing-safe) |
| Login 11 times in 5 minutes from one IP             | 429 "Too many requests" after the 10th |
| Call `/api/admin/users` without a JWT               | 401 "Authentication required" |
| Call `/api/admin/users` with a dispatcher's JWT     | 403 "Admin role required" |
| Call `/api/admin/alerts/not-a-uuid/resolve`         | 400 "Invalid alert id" |
| POST `/api/driver/position` with lat=99             | 400 "Coordinates outside service area" |
| POST `/api/driver/position` without JWT             | 401 "Driver login required" |
| GET `/api/health`                                   | 200 (always works) |

---

## 5. Resetting a password

Self-service password reset is **not enabled** (intentional — government-grade deployment). To rotate a demo password:

1. Generate a new bcrypt hash locally:
   ```bash
   python3 -c "import bcrypt; print(bcrypt.hashpw(b'newpassword', bcrypt.gensalt()).decode())"
   ```
2. In the Supabase SQL editor:
   ```sql
   UPDATE users
   SET password_hash = '$2b$12$NEW_HASH_HERE...'
   WHERE email = 'admin@damascus-transit.demo';
   ```

---

## 6. Production caveats

- **Never use these credentials in a real deployment.** Rotate before going live.
- The seeded password hash is publicly visible in this repo's git history.
- All four accounts belong to a single demo operator
  (`00000000-0000-0000-0000-000000000001`). Real operators get unique
  UUIDs and scoped data.
- `damascus2025` is intentionally weak so QA testers don't get locked out.
  Production accounts should use long random passwords and rotate quarterly.
