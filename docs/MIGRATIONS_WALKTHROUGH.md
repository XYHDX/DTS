# Run the Supabase migrations — 5 minutes, step-by-step

> Open this in one tab, the Supabase SQL Editor in another. Follow
> the numbered steps in order.

## Step 1 — Open the SQL Editor

1. Go to <https://supabase.com/dashboard/projects> and pick the
   Damascus Transit project.
2. Left sidebar → **SQL Editor** → **+ New query**.

## Step 2 — Paste & run the bundle

Open the file `source/db/MIGRATIONS_BUNDLE.sql` from this repo. It's a
single ~800-line file that concatenates **all seven** migrations
(011 → 017) in order. Every block is idempotent (`IF NOT EXISTS`,
`ON CONFLICT DO NOTHING`, `EXCEPTION WHEN duplicate_object`), so it's
safe to re-run on a partially-applied schema.

1. **⌘A** to select all in the SQL editor.
2. Paste the bundle.
3. Click **Run** (or **⌘⏎**).
4. You should see "Success. No rows returned" within ~10 seconds.

> If you get a single red error, copy the message and tell me — the
> bundle has fallback `DO $$ … EXCEPTION WHEN others THEN NULL` blocks
> around the type-mutation statements, but Postgres versions differ
> and one of them might need a tweak.

## Step 3 — Verify

The bundle ends with **8 verification queries** but they're commented
to run separately. Click **+ New query** again, paste this block:

```sql
SELECT email, role, must_change_password
  FROM users
 WHERE email LIKE '%@damascus-transit.demo'
 ORDER BY email;

SELECT route_id, target_headway_min FROM routes ORDER BY route_id;

SELECT r.route_id, COUNT(*) AS stop_count
  FROM routes r
  JOIN route_stops rs ON rs.route_id = r.id
 GROUP BY r.route_id
 ORDER BY r.route_id;

SELECT tablename FROM pg_tables
 WHERE schemaname = 'public'
   AND tablename IN ('vehicle_geofences','headway_observations','revoked_tokens','login_attempts');
```

**Expected results:**

| Query | Should return |
|---|---|
| 1 — demo users | 5 rows: superadmin / admin / operator / driver / passenger, all `must_change_password = true` |
| 2 — target headways | R101/R102 = 8, R201/R202 = 5 |
| 3 — route_stops counts | R101 = 6, R102 = 5, R201 = 4, R202 = 5 |
| 4 — new tables | 4 rows |

The full 8-query verification block is at the end of `MIGRATIONS_BUNDLE.sql`.

## Step 4 — Push the latest code

You're 4 commits ahead of `origin/main` (geofence map drawer, white-screen
fix, wave-6 phases). Push them:

```bash
cd ~/Documents/Claude/Projects/DamascusTransitSystem
bash "./Push to GitHub.command"
```

Vercel auto-deploys within ~30 seconds.

## Step 5 — Test login with the new password

The first login on each demo account uses the per-role password from
`DEMO_CREDENTIALS.md` AND lands on `/admin/reset.html?force=1` so you
can rotate to your own password.

```bash
HOST=https://dts-brown.vercel.app

# 1. Login — expect must_change_password=true and a 15-minute token.
curl -s -X POST "$HOST/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@damascus-transit.demo","password":"AdminDamascus#2026"}' \
  | python3 -m json.tool

# 2. Save the token, then rotate the password.
TOKEN="..."  # paste from step 1
curl -s -X POST "$HOST/api/auth/change_password" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"current_password":"AdminDamascus#2026","new_password":"YourNewStrongPw-2026"}' \
  | python3 -m json.tool

# 3. The response gives you a full-scope 24h token. Use it for admin calls.
FULL="..."
curl -s -H "Authorization: Bearer $FULL" "$HOST/api/admin/headway" | python3 -m json.tool
```

If `/api/admin/headway` returns one row per route with both
`target_headway_min` AND `actual_headway_min` populated, **everything is
wired end-to-end**.

## What you can expect to start working after the migrations

- `/passenger/` popular routes show real stop counts (R101 = 6, R201 = 4, etc.)
- `/passenger/?route=R101` (with Phase D shipped) shows a stop list with live ETA
- Dispatcher console headway strip shows the green/red gauge per route
- Driver app's bunching banner activates when two vehicles on the same route get within 250 m
- `/admin/audit.html` shows every admin action + every login attempt
- Brute-force lockout (10 fails / 60 min → 30 min lock)
- Forced password rotation flow on first login

If anything still misbehaves, ping me and I'll diagnose against the
live database.
