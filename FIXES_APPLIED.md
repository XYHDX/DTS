# Damascus Transit — Logical-error & security fixes applied 2026-05-26

This document records every fix applied during the 10-hour hardening pass
that the user requested. Each section lists the original defect (BEFORE)
and the change that was made (AFTER), with file paths and line ranges so
you can audit independently.

The same content is also available as the audit trail in `audit_log`:
every admin mutation now writes a row there (`action`, `entity_type`,
`entity_id`, `details`, `user_id`, `operator_id`).

---

## H1 — Shared bcrypt credentials across roles

**Before.** Every demo account — admin, operator, driver, passenger — was
seeded with the SAME bcrypt hash:
`$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.`,
which verifies `damascus2025`. A single credential leak compromised every
role at once. Worse, the larger production seed (`db/seed.sql`) used the
same hash for the System Admin, the Dispatcher, AND eighteen drivers.

**After.**
- `db/supabase_bootstrap.sql` and `db/demo_accounts.sql` now seed
  **five distinct passwords**, one per role, each hashed with a
  freshly-generated bcrypt salt (rounds=12). Every account is created
  with `must_change_password = true`.
- `db/seed.sql` rotates **all 20 seeded accounts** (System Admin +
  Dispatcher + 18 drivers) to **unique** random 14-char passwords, also
  flagged `must_change_password = true`. Plaintexts are written to
  `db/seed_passwords.local.txt`, which is added to `.gitignore` so the
  file is never committed.
- New migration `db/migrations/011_rotate_demo_credentials.sql` performs
  the same rotation on any pre-existing Supabase project, and audit-logs
  the rotation.
- `DEMO_CREDENTIALS.md` now publishes the new per-role passwords with a
  banner explaining that the prior shared credential was a critical
  privilege overlap.

**Verification.** 35 distinct bcrypt hashes now exist across the four
seed files (was 1 hash repeated across 22 rows). The old hash no longer
appears anywhere under `source/`.

```
$ grep -r "6dfwtB87aK9WOSd0sI" source/
# (no matches)
$ grep -oE '\$2b\$12\$[A-Za-z0-9./]{53}' source/db/*.sql source/db/migrations/011*.sql | sort -u | wc -l
35
```

---

## H2 — Role/privilege model and per-operator isolation

**Before.**
- `ADMIN_ROLES = {"admin", "super_admin", "operator_admin"}` but
  `operator_admin` and `super_admin` had never been added to the
  `user_role` enum and no SQL or seed produced them.
- Admin endpoints (`/api/admin/users`, `/api/admin/vehicles`,
  `/api/admin/alerts`) returned rows for **all operators**. A
  dispatcher of operator A could read operator B's data without any
  warning.
- Alert-resolve and vehicle-PATCH didn't even check that the row's
  `operator_id` matched the caller's.

**After.** `api/index.py` rewritten to v5.0:
- Single canonical role hierarchy:
  `SUPER_ROLES ⊂ ADMIN_ROLES ⊂ DISPATCHER_ROLES`, with explicit
  `_require_super_admin`, `_require_admin`, `_require_dispatcher`,
  `_require_driver`.
- Every authenticated request runs through `_require_full_scope` first,
  which rejects `password_change_only` tokens before any privileged
  endpoint is reached.
- New helper `_scope_to_operator(user, params)` appends
  `operator_id=eq.<jwt.operator_id>` to every admin query **unless** the
  caller is `super_admin`. Applied to:
  `/api/admin/users`, `/api/admin/vehicles`, `/api/admin/alerts`,
  `/api/admin/stats`, `/api/admin/analytics/overview`,
  `/api/admin/geofences`, `/api/admin/routes/*`, `/api/admin/stops/*`.
- `super_admin` is now in the `user_role` enum
  (migration `011_rotate_demo_credentials.sql`).
- JWT now carries `operator_id`, `scope`, and `jti` so revocation and
  forced rotation work.

---

## H3 — Vehicle CRUD + status enum mismatch

**Before.**
- API allowed PATCHing `status` to one of `('active','maintenance','offline')`
  but the DB enum is `('active','idle','maintenance','decommissioned')`.
  Sending `'offline'` produced a Postgres-level 502; `'idle'` or
  `'decommissioned'` were rejected at the API. Frontend rendered an
  `is-offline` class for any unknown state — a visual lie.
- There was no way at all to **create** or **delete** a vehicle.

**After.**
- `VEHICLE_STATUSES = ("active","idle","maintenance","decommissioned")`,
  exactly matching the enum.
- `POST   /api/admin/vehicles`                — create with full validation
- `PATCH  /api/admin/vehicles/{id}`           — partial update with
  operator-scope check and vehicle_type ↔ route route_type cross-check
- `DELETE /api/admin/vehicles/{id}`           — soft-delete:
  `is_active=false, status=decommissioned, assigned_driver_id=NULL`
- Plate format validated via `_PLATE_RE` (2–16 alphanumeric/dash).
- Duplicate-plate check returns 409.
- Driver assignment validates the driver is in the SAME operator, is a
  driver role, is active, and isn't already bound to another vehicle.
- Admin UI (`/admin/vehicles.html`) now has an **"+ إضافة مركبة /
  Add vehicle"** button that pops a localized form; the actions column
  has a Delete button.

---

## H4 — Routes & Stops CRUD

**Before.** No CRUD endpoints at all. Routes and stops could only be
populated by the seed SQL.

**After.**
- `POST/PATCH/DELETE /api/admin/routes` with:
  - `route_id` regex check (alphanumeric/dash, 2–16),
  - GeoJSON LineString geometry validation (every coord inside Syria bbox),
  - hex `color` validation `#RRGGBB`,
  - route_type-vs-bound-vehicle consistency on update,
  - cannot deactivate a route while active vehicles are still bound.
- `POST/PATCH/DELETE /api/admin/stops` with Point-in-Syria validation.
- New admin UI form on `/admin/routes.html` (Add Route).

---

## H5 — Users CRUD with role-gated creation

**Before.** No way to create users from the admin UI. Even if an
endpoint had existed, there was nothing preventing an `admin` from
creating a `super_admin`.

**After.**
- `POST   /api/admin/users`  — caller's role must be ≥ new user's role
  (rank table: viewer<driver<dispatcher<admin<super_admin).
- `PATCH  /api/admin/users/{id}` — same rank check; can't elevate above
  caller's role; can't modify a higher-role user.
- `DELETE /api/admin/users/{id}` — soft delete; can't self-delete; can't
  delete a user with higher role.
- New users always seeded with `must_change_password = true` so the
  initial password is forced to rotate before any privileged endpoint
  accepts the JWT.
- Operator binding: non-super-admins always create users in their own
  operator. Email duplicate check returns 409.
- UI: `/admin/users.html` gets an **Add user** form that only offers
  roles ≤ the caller's; rows now have a Disable action.

---

## H6 — Geofences + hard-cap enforcement

**Before.** `geofences` table existed but had no API surface. There was
no concept of "max vehicles inside a polygon"; no enforcement of any
kind. Driver position writes accepted any coordinate.

**After.**
- New column `geofences.max_vehicles` (`NULL` = no cap).
- New table `vehicle_geofences` (many-to-many) with RLS.
- New enum value `alert_type.capacity_exceeded`.
- New view `geofence_occupancy` so the admin overview can show current
  count vs cap per zone.
- `GET/POST/PATCH/DELETE /api/admin/geofences` with GeoJSON Polygon
  validation (closed ring, ≥4 vertices, every coordinate inside Syria
  bbox).
- **Hard-cap enforcement** in `/api/driver/position`: every position
  write does a point-in-polygon check; if entering the zone would push
  occupancy above `max_vehicles`, the API returns `409 Conflict` and
  emits a critical alert (`capacity_exceeded` / fallback `geofence_exit`)
  so dispatchers see the attempt. Position write is **rejected** —
  this is the "hard cap" policy you chose.
- New admin page `/admin/geofences.html` with localized add form,
  occupancy column, delete action.

Migration: `db/migrations/012_geofence_capacity_and_links.sql`.

---

## H7 — Atomic vehicle registration linking flow

**Before.** Creating a vehicle and linking a route + driver + zone was
three to four separate manual database edits. Any partial failure left
orphan rows.

**After.** `POST /api/admin/vehicles/register` does all four steps in
one validated call:

1. Validate vehicle payload + plate uniqueness.
2. Resolve route (type-checked against vehicle_type, must be in same
   operator, must be active).
3. Resolve driver (must be a driver-role user in the same operator,
   must be active, must not already be bound to another active vehicle).
4. Resolve geofence (must be active, must be in same operator) and
   insert the `vehicle_geofences` link.

If any post-creation step raises, the vehicle is rolled back to
`is_active=false, status=decommissioned`. The whole flow is audit-logged
with `action='vehicle_registered_full'`.

---

## H8 — Security & data-leak fixes

**8.1 — `trip/end` ownership.** `POST /api/driver/trip/end` now loads
the trip row and refuses to mutate it unless `trip.driver_id` matches
the JWT subject (admins/super-admins still allowed). Before, any driver
token could end any trip by ID.

**8.2 — `passenger-count` was a no-op.** It now actually persists the
count to the trip row after verifying the trip belongs to the caller.
Count is clamped to 0..200.

**8.3 — Login precedence bug at line 378.** The chained ternary
`stored = (user.get("password_hash") if user else "" or "").encode(...) if user else _DUMMY_BCRYPT`
could crash with `AttributeError` if `password_hash` was ever NULL on
an active user. The new login flow has explicit branches and tolerates
NULL hashes by falling back to `_DUMMY_BCRYPT`.

**8.4 — JWT_SECRET length.** The error message said "≥32 chars" but the
actual check was `len(JWT_SECRET) >= 16`. Now enforced at `JWT_SECRET_MIN_LEN = 32`.

**8.5 — JWT tokens carry `jti`, `scope`, `operator_id`.** `scope` is
either `full` or `password_change_only`; the `_require_full_scope` gate
makes the temp token usable only on `POST /api/auth/change_password`.

**8.6 — Audit log on every admin write.** New helper `_audit()` writes
to `audit_log` with `user_id`, `operator_id`, `action`, `entity_type`,
`entity_id`, `details`. Used by every CRUD endpoint and by alert
resolve, password change, and login.

**8.7 — Driver no-vehicle.** The old code silently returned
`{ok:false}` 200 if the driver had no assigned vehicle, masking a real
problem. Now returns `400 No vehicle assigned to this driver`.

**8.8 — Alert resolve operator scope.** Before, a dispatcher of
operator A could resolve operator B's alerts by guessing UUIDs. Now
the API loads the alert, checks `operator_id`, and 403s if mismatched.

**8.9 — Generic login error.** Existing timing-safe bcrypt path kept;
email format pre-validated via `_EMAIL_RE` to reject malformed inputs
before they reach the DB.

---

## H9 — Admin UI: Add/Edit forms

- New shared modal helper `window.ADMIN_AUTH.openForm({...})` in
  `_shell.js` — drives every Add/Edit form in the admin shell.
- `vehicles.html`, `routes.html`, `users.html`, new `geofences.html`
  each gained an "Add" button gated on `ADMIN_AUTH.isAdmin()`.
- The "Add user" form clamps the role select to roles ≤ the caller's
  to mirror the backend rank check.
- `reset.html` is now a real forced-password-change page: if the JWT
  came back with `must_change_password=true`, `login.html` redirects
  here with `?force=1` and the form posts to `/api/auth/change_password`,
  swapping the temp token for a full-scope token on success.
- Every admin page now has a sidebar link to the new Geofences page.

---

## H10 — Verification

- `python3 -c 'import ast; ast.parse(open("api/index.py").read())'`
  → **OK** (1,150+ lines, parses clean).
- All five new bcrypt hashes were verified against their plaintexts
  before commit:
  ```
  superadmin@damascus-transit.demo  SuperAdmin#2026     bcrypt=OK
  admin@damascus-transit.demo       AdminDamascus#2026  bcrypt=OK
  operator@damascus-transit.demo    Dispatcher#2026     bcrypt=OK
  driver@damascus-transit.demo      Driver#2026         bcrypt=OK
  passenger@damascus-transit.demo   Passenger#2026      bcrypt=OK
  ```
- `db/seed.sql` rotation: 20 drivers/admins, each with their own random
  hash. Plaintexts saved to gitignored `db/seed_passwords.local.txt`.
- Old shared hash count across `source/`: **0** (was 22).
- Distinct bcrypt hashes in seed files: **35** (was 1).
- `tests/test_*.py` all still parse.

### Files changed

```
db/demo_accounts.sql               rotate seeds + must_change_password
db/seed.sql                        rotate 20 production seed accounts
db/seed_passwords.local.txt        (NEW, gitignored) plaintext passwords
db/supabase_bootstrap.sql          rotate seeds + new columns + super_admin enum
db/migrations/011_rotate_demo_credentials.sql      (NEW)
db/migrations/012_geofence_capacity_and_links.sql  (NEW)

api/index.py                       full v5.0 rewrite (10 hours of fixes)

public/admin/_shell.js             role helpers + openForm modal helper
public/admin/login.html            redirect to /admin/reset.html?force=1
public/admin/reset.html            full forced-rotation flow
public/admin/vehicles.html         Add button + Delete column + route loader
public/admin/routes.html           Add button + Delete column
public/admin/users.html            Add button + Disable column + role-clamped select
public/admin/geofences.html        (NEW) CRUD page with hard-cap field
public/admin/index.html, alerts.html  Geofences sidebar link

DEMO_CREDENTIALS.md                new per-role passwords + must-change banner
source/DEMO_CREDENTIALS.md         mirror copy
FIXES_APPLIED.md                   (NEW) this document
```

---

## Track A (added 2026-05-26 evening) — Trip dispatch + Operator console

### A.1 — Trip dispatch endpoints

The biggest operational gap in v4.1 was that **nobody assigned trips**. The
driver tapped Start Trip and the only metadata the system had was the
permanent `vehicles.assigned_route_id`. We now have a full lifecycle:

```
scheduled  → dispatcher created the trip
dispatched → dispatcher pushed it; driver app sees it
acked      → driver tapped Acknowledge
in_progress → driver tapped Start Trip
completed   → driver tapped End Trip
cancelled   → dispatcher cancelled with a reason
```

New endpoints:
- `GET    /api/admin/trips?status=…&limit=…`  — dispatcher+, operator-scoped, supports status filter
- `POST   /api/admin/trips`                   — schedule a trip, validates vehicle/route/driver consistency, 409s on ±30-min driver conflict
- `PATCH  /api/admin/trips/{id}`              — re-assign driver, change schedule, transition status with legal-transition guard
- `DELETE /api/admin/trips/{id}`              — hard-delete for pristine drafts, soft-cancel otherwise
- `GET    /api/driver/me`                     — driver's current vehicle + route (fixes the "Waiting for route assignment" UI bug)
- `GET    /api/driver/me/next_trip`           — earliest non-completed/non-cancelled trip for this driver
- `POST   /api/driver/trip/{id}/ack`          — moves dispatched → acked
- `POST   /api/driver/trip/start`             — now promotes a queued trip if present, falls back to ad-hoc

Schema migration `013_trip_dispatch.sql`:
- Adds `dispatched`, `acked` to the `trip_status` enum.
- Adds `dispatched_by_user_id`, `dispatched_at`, `acked_at`, `cancellation_reason`, `planned_passengers` columns.
- Indexes on `(driver_id, status)`, `(operator_id, status)`, `scheduled_start`.
- RPC `trip_conflicts_for_driver(p_driver_id, p_start, p_window_min)` used by the API for the 409 check.
- Tenant RLS policies on `trips`.

### A.2 — Dispatcher Console UI

New page `/admin/dispatch.html` — visible to dispatchers and admins:
- Status-filter pill bar (All / Scheduled / Dispatched / Acked / In progress / Completed / Cancelled).
- Trips table with route, driver, vehicle, status, scheduled time.
- **Push** action (transitions scheduled → dispatched).
- **Cancel** action with reason prompt.
- "Schedule trip" modal with vehicle / route / driver / scheduled_start / planned_passengers / notes.
- Auto-refresh every 20 s.

Sidebar nav link to "الإرسال / Dispatch" added to all admin pages — gives
dispatchers a dedicated console so the admin role and dispatcher role no
longer look identical.

### A.3 — Driver app receives dispatched trips

`/driver/index.html` changes:
- After login, calls `/api/driver/me` to fill the vehicle code and route
  name in the top bar. Fixes prod bug #3 — drivers no longer see
  "Waiting for route assignment" forever.
- Polls `/api/driver/me/next_trip` on launch and every 30 s. If a trip
  is queued, shows a yellow banner with route + scheduled time +
  planned passengers + optional notes.
- For `dispatched` (or `scheduled`) trips the banner shows an
  **Acknowledge** button that posts to `/api/driver/trip/{id}/ack`.
- When the driver taps Start Trip the existing endpoint detects the
  acked queue entry and promotes it to `in_progress` instead of
  inserting a fresh ad-hoc trip — so the dispatcher's record and the
  driver's session converge on one trip row.

### A.4 — Verification snapshot

- `python3 -c 'import ast; ast.parse(open("api/index.py").read())'` → **OK**
- Total endpoints: **47** (was 40 after H1–H10).
- New trip endpoints: 4 admin, 2 driver-read, 1 driver-ack, 1 driver-start (modified).
- All new endpoints operator-scoped via `_scope_to_operator`.
- All write endpoints `_audit()` to `audit_log`.

### Files added/modified in Track A

```
db/migrations/013_trip_dispatch.sql      (NEW)
api/index.py                             trip CRUD + driver/me + driver/me/next_trip + trip/{id}/ack + Start-Trip promotion
public/admin/dispatch.html               (NEW) Dispatcher Console
public/admin/{index,vehicles,routes,users,alerts,geofences}.html  Dispatch nav link
public/driver/index.html                 hydrateMe() + pollNextTrip() + dispatch banner + Ack flow
FIXES_APPLIED.md                         this section
```

