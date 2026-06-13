# Damascus Transit — Demo Testing Credentials

One-stop cheat sheet for testing every part of the system end-to-end.

> ✅ **Canonical seed (2026-06-13):** the single source of truth for demo
> data is **`db/demo_seed.sql`**. Run it in the Supabase SQL editor (it runs
> as the service role, bypassing RLS) to create the `damascus` operator, all
> demo accounts, a testable fleet, and seed live positions. See
> **`db/RESTORE_RUNBOOK.md`** for the full restore procedure.
>
> **Password for ALL demo accounts: `Damascus2026!`** (verified against the
> bcrypt hashes in `db/demo_seed.sql`).
>
> ⚠ The older `db/demo_accounts.sql` (password `damascus2025`) and any
> per-role `#2026` passwords are **deprecated** — they do not match the
> deployed seed and were the cause of "Invalid credentials" at login.

---

## 1. Demo accounts — one shared password

| # | Email | Password | Role (DB enum) | UI to test on |
|---|---|---|---|---|
| 1 | `admin@damascus-transit.demo`      | `Damascus2026!` | `admin`      | `/admin/login.html` → tab **إدارة / Admin** |
| 2 | `operator@damascus-transit.demo`   | `Damascus2026!` | `dispatcher` | `/admin/login.html` → tab **موزّع / Operator** |
| 3 | `driver@damascus-transit.demo`     | `Damascus2026!` | `driver`     | `/admin/login.html` → tab **سائق / Driver**, or `/driver/` directly |
| 4 | `driver2@damascus-transit.demo`    | `Damascus2026!` | `driver`     | `/driver/` (second driver, bound to MIC-014) |
| 5 | `passenger@damascus-transit.demo`  | `Damascus2026!` | `viewer`     | Not required — the passenger app is anonymous |

`driver@damascus-transit.demo` is bound to **BUS-101** on route **R001
(Marjeh → Mezzeh)**, so you can start a trip and stream GPS.

> A `super_admin` cross-operator account is **optional** — see the commented
> block at the bottom of `db/demo_seed.sql` (it needs an enum value added
> first, which can't run inside a transaction).

---

## 2. What each role can do

### Admin (`admin@damascus-transit.demo`)
After login lands on `/admin/`. Has access to every admin page:

| Page      | URL                          | What to test |
|-----------|------------------------------|---|
| Overview  | `/admin/`                    | Live map, KPIs (active vehicles, trips today, occupancy, open alerts), recent-alerts panel |
| Vehicles  | `/admin/vehicles.html`       | Fleet list with assigned route, capacity, status pill |
| Users     | `/admin/users.html`          | Full user list (admin-only — dispatcher gets 403) |
| Routes    | `/admin/routes.html`         | Routes with color swatches and vehicle counts |
| Alerts    | `/admin/alerts.html`         | All alerts + **Resolve** button on open rows |
| Approvals | `/admin/approvals.html`      | Vehicle approval workflow (migration 019) |
| Payments  | `/admin/payments.html`       | Sham-cash payment records (migration 020) |
| Audit     | `/admin/audit.html`          | Audit log |
| Analytics | `/dashboard/analytics.html`  | Charts: trips/week, occupancy donut, route table, top incidents |

### Dispatcher / Operator (`operator@damascus-transit.demo`)
Same as admin **except** `/admin/users.html` returns 403 (admin-only). Can resolve alerts and view the other admin screens.

### Driver (`driver@damascus-transit.demo`)
After login lands on `/driver/`. Tests:

| Feature                  | How |
|--------------------------|---|
| GPS streaming            | Allow location → green "متصل / Connected" pill |
| Start a trip             | **▶ بدء الرحلة** → POST `/api/driver/trip/start` |
| Live speed/distance/time | Counters tick while moving (or simulated) |
| Passenger count          | Increment/decrement during trip |
| Incident report          | **🚨 الإبلاغ عن حادث** → creates a critical alert admins see |
| End a trip               | **■ إنهاء الرحلة** → POST `/api/driver/trip/end` |
| Bilingual UI             | EN/AR pill in the driver bar |

### Passenger (no account needed)
Open `/passenger/` — no login. Search, locate-me, live map, popular routes, PWA install, offline shell.

---

## 3. Quick API tests (CLI)

### Health (no auth)
```bash
curl https://dts-brown.vercel.app/api/health
# → {"status":"healthy","database":true,"redis":true,"active_vehicles":...}
```

### Login (get JWT)
```bash
curl -X POST https://dts-brown.vercel.app/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@damascus-transit.demo","password":"Damascus2026!"}'
# → {"access_token":"eyJ...","user_id":"...","role":"admin"}
```

Save the token then test gated endpoints:

```bash
TOKEN="eyJ..."   # paste from login response
curl -H "Authorization: Bearer $TOKEN" https://dts-brown.vercel.app/api/auth/me
curl -H "Authorization: Bearer $TOKEN" https://dts-brown.vercel.app/api/admin/alerts?limit=10
```

### Public (after seeding)
```bash
curl https://dts-brown.vercel.app/api/routes      # → 3 routes
curl https://dts-brown.vercel.app/api/stops        # → 6 stops
curl https://dts-brown.vercel.app/api/vehicles     # → 4 vehicles
curl https://dts-brown.vercel.app/api/stats
curl "https://dts-brown.vercel.app/api/stops/nearest?lat=33.513&lon=36.291&radius_m=1500"
```

---

## 4. Negative tests (what should fail)

| Test | Expected |
|------|----------|
| Login with wrong password | 401 "Invalid credentials" |
| Login 11 times in 5 min from one IP | 429 after the 10th |
| `/api/admin/users` without a JWT | 401 |
| `/api/admin/users` with a dispatcher JWT | 403 |
| `/api/driver/position` with lat=99 | 422 (out of range) |
| `/api/health` | 200 (always) |

---

## 5. Rotating a demo password

```bash
python3 -c "import bcrypt; print(bcrypt.hashpw(b'NewPass!', bcrypt.gensalt()).decode())"
```
```sql
UPDATE public.users
SET password_hash = '$2b$12$NEW_HASH_HERE...'
WHERE email = 'admin@damascus-transit.demo';
```

---

## 6. Production caveats

- **Never use these credentials in a real deployment.** Rotate or delete them before going live (a clean-up block is at the bottom of `db/demo_seed.sql`).
- The seeded hashes are public in this repo's git history.
- All demo accounts belong to one demo operator (`00000000-0000-0000-0000-000000000001`). Real operators get unique UUIDs and scoped data.
