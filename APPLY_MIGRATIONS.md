# Apply Supabase migrations (one-time, ~5 minutes)

> **Status check.** As of 2026-05-27, the Vercel deploy is at API
> **v5.0.0** but the Supabase schema is still at v4.1 (the migrations
> below have NOT been applied yet). The API is resilient to this — it
> retries queries when columns or enum values are missing — but you
> get the full v5.0 behavior (forced password rotation, geofence caps,
> trip dispatch lifecycle, headway control) only AFTER these run.
>
> **Verify** the current schema state with `/api/health` (already
> reports `version: 5.0.0`) and the smoke checks at the bottom of this
> doc.

---

## Steps

### 1. Open the Supabase SQL Editor

1. Go to <https://supabase.com/dashboard/projects>.
2. Pick the Damascus Transit project (the one whose URL is in
   Vercel's `SUPABASE_URL` env var).
3. Left sidebar → **SQL Editor** → **+ New query**.

### 2. Run the four migrations in order

Each file is **idempotent** — safe to re-run. Paste the entire file
into the editor and click **Run** (or ⌘⏎). Wait for the green
"Success. No rows returned" toast, then load the next file.

| # | File | What it does |
|---|---|---|
| 1 | `source/db/migrations/011_rotate_demo_credentials.sql` | Adds `super_admin` to `user_role` enum. Adds `users.must_change_password`, `password_changed_at`, `last_seen_at` columns. Rotates the five demo accounts to per-role bcrypt hashes; sets `must_change_password = true` on all of them. Audit-logs the rotation. |
| 2 | `source/db/migrations/012_geofence_capacity_and_links.sql` | Adds `geofences.max_vehicles` column. New `vehicle_geofences` link table (tenant-RLS'd). New `alert_type` enum value `capacity_exceeded`. New `geofence_occupancy` view (current vs cap per zone). |
| 3 | `source/db/migrations/013_trip_dispatch.sql` | Adds `dispatched` + `acked` enum values to `trip_status`. Adds `dispatched_by_user_id`, `dispatched_at`, `acked_at`, `cancellation_reason`, `planned_passengers` columns to `trips`. New indexes for the dispatcher console. New `trip_conflicts_for_driver` RPC. Tenant-RLS policies. |
| 4 | `source/db/migrations/014_headway_control.sql` | Adds `routes.target_headway_min`. Adds `bus_bunching` to `alert_type`. New `headway_observations` table (append-only, tenant-RLS'd). New `route_headway_status` and `detect_bunching` RPCs. Seeds target headways for the demo routes (R101/R102 = 8 min, R201/R202 = 5 min). |
| 5 | `source/db/migrations/015_route_stops_seed.sql` | Seeds the empty `route_stops` join table so each demo route has its real stop sequence. Computes `distance_from_start_km` via PostGIS for each stop. After this, `/api/routes` returns real `stops_count` values and the passenger UI no longer shows "0 stops". |
| 6 | `source/db/migrations/016_edge_case_fixes.sql` | Phase 6.2 fixes. Adds `one_active_vehicle_per_driver` unique index (prevents concurrent-create race), `users.session_invalidate_after` column (so demote/deactivate kills tokens immediately), `cancel_active_trips_for_vehicle` RPC, plus a comment documenting `max_vehicles=0` as a no-entry zone. |
| 7 | `source/db/migrations/017_ops_hardening.sql` | Phase 6.3 ops layer. Adds `revoked_tokens` table (admins can kill a JWT mid-life), `login_attempts` audit log, `users.locked_until` for brute-force lockout, `failed_login_count` RPC. Admin endpoints `/api/admin/audit_log`, `/login_attempts`, `/tokens/revoke`, `/users/{id}/revoke_sessions`, `/users/{id}/unlock` start working after this. |

> **A note on `ALTER TYPE ... ADD VALUE`** — Postgres requires this to
> run **outside a transaction** in some versions. The migrations wrap
> it in `DO $$ … EXCEPTION WHEN others THEN NULL; END $$;` so a
> "cannot run inside a transaction block" error is caught and the
> rest of the migration continues. If you see that warning, it's
> safe to ignore — the enum value was added either earlier or by the
> defensive block.

### 3. Verify each migration applied

Paste this into the SQL Editor and run after all four migrations are
done:

```sql
-- Expect: 5 users, all with must_change_password=true
SELECT email, role, must_change_password
  FROM users
 WHERE email LIKE '%@damascus-transit.demo'
 ORDER BY email;

-- Expect: geofences table has max_vehicles column
SELECT column_name FROM information_schema.columns
 WHERE table_name = 'geofences' AND column_name = 'max_vehicles';

-- Expect: trips table has dispatched_at column
SELECT column_name FROM information_schema.columns
 WHERE table_name = 'trips' AND column_name = 'dispatched_at';

-- Expect: routes have target_headway_min set (8 for buses, 5 for microbuses)
SELECT route_id, route_type, target_headway_min FROM routes ORDER BY route_id;

-- Expect: super_admin is now in the user_role enum
SELECT enumlabel FROM pg_enum
  JOIN pg_type ON pg_type.oid = enumtypid
 WHERE typname = 'user_role'
 ORDER BY enumsortorder;

-- Expect: dispatched and acked appear in trip_status
SELECT enumlabel FROM pg_enum
  JOIN pg_type ON pg_type.oid = enumtypid
 WHERE typname = 'trip_status'
 ORDER BY enumsortorder;
```

If everything returns the expected rows, you're done.

### 4. After-migration smoke test

```bash
HOST=https://dts-brown.vercel.app

# 1. Login with the NEW demo password. Expect a 200 with
#    must_change_password=true and a short-lived token.
curl -s -X POST "$HOST/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@damascus-transit.demo","password":"AdminDamascus#2026"}' \
  | python3 -m json.tool

# 2. The temp token can ONLY call /api/auth/change_password.
#    Replace TOKEN with the value from step 1.
TOKEN="..."
curl -s -X POST "$HOST/api/auth/change_password" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"current_password":"AdminDamascus#2026","new_password":"Whatever-Strong-Pw-2026"}' \
  | python3 -m json.tool

# 3. Use the full-scope token returned by step 2 to hit an admin endpoint.
FULL="..."
curl -s -H "Authorization: Bearer $FULL" "$HOST/api/admin/headway" | python3 -m json.tool
```

If `/api/admin/headway` returns the per-route gauge data (one row per
route with `target_headway_min` and `actual_headway_min`), the v5.0
backend is fully wired end-to-end.

---

## Rollback (only if something goes very wrong)

The migrations are additive — they don't drop existing columns or
break the v4.1 API. If you need to revert the Vercel deploy:

1. Vercel dashboard → **Deployments** → pick the last good v4.1
   deployment → **Promote to Production**.
2. Leave the Supabase schema as-is. The v4.1 API ignores the new
   columns; nothing breaks.

If you want to also revert the demo-credential rotation, run:

```sql
-- Restores the shared damascus2025 bcrypt hash. WARNING — undoes the
-- H1 credential rotation.
UPDATE users
   SET password_hash = '$2b$12$6dfwtB87aK9WOSd0sI/Ixe/X8d45kroxYrMXblEo6dwCOqu/vY8p.',
       must_change_password = false
 WHERE email LIKE '%@damascus-transit.demo';
```

(Don't do this in production unless you have a specific reason.)

---

## What changes for users after the migrations run

- The first login on each demo account uses the new password
  (documented in `DEMO_CREDENTIALS.md`) AND lands on
  `/admin/reset.html?force=1`. The user must rotate the password
  before any privileged endpoint accepts the JWT.
- Operators of geofences with `max_vehicles` set start seeing
  capacity-exceeded alerts when a driver's GPS heartbeat would push
  the zone over capacity. The position write itself is rejected
  (409).
- The Dispatcher Console (`/admin/dispatch.html`) shows the headway
  gauge for every active route. Trip scheduling works end-to-end.
- The driver app shows an amber hold banner when bunching is
  detected on the same route within 250 m.

After verification, you can safely delete this file.
