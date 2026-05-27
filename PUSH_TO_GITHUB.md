# Push to https://github.com/XYHDX/DTS

> **Current state (2026-05-26):** Both repos are committed on `main`.
> The work just needs to be pushed from your Mac — the sandbox where it
> was prepared is firewalled from github.com.
>
> | Repo            | Branch | Last commit                                           |
> |-----------------|--------|-------------------------------------------------------|
> | `source/`       | `main` | `74142d1 feat(track-c): headway control + bunching alerts` |
> | top-level       | `main` | `8018092 feat(track-c): headway control + bunching alerts` |
>
> Older runs of this doc described a `dts-repo.bundle` / tarball flow.
> Those are obsolete — the actual git history is now in the working
> folders. Use **Option A** below.

---

## Option A — Push the two working repos (recommended, ~10 seconds)

Open Terminal on your Mac:

```bash
cd ~/Documents/Claude/Projects/DamascusTransitSystem

# OPTIONAL but recommended: clear the stub files the sandbox left behind
# (broken refs, *.bak files from sed). Safe to skip if you don't see
# "ignoring broken ref" warnings.
bash CLEANUP.command

# 1. Push the actual code repo (api + db + public).
cd source
git remote -v   # verify origin points at the right GitHub repo
# If origin is missing:
#   git remote add origin https://github.com/XYHDX/DTS.git
git push -u origin main

# 2. Push the top-level project repo (docs + bundle artifacts).
cd ..
git remote -v
# If origin is missing:
#   git remote add origin https://github.com/XYHDX/DTS-meta.git   # or whatever you call the wrapper repo
git push -u origin main
```

> If GitHub asks for credentials, use a **Personal Access Token** (not your
> password) — generate one at <https://github.com/settings/tokens?type=beta>
> with **Contents: read & write** scope, paste it as the password.

---

## What's in this push

This push contains every change made in the last two days:

### v5.0 hardening (H1–H10) — commit `f3375c1` / `7511bb3`
- **H1:** rotated the shared `damascus2025` bcrypt hash; 35 unique
  hashes across all seed files. `must_change_password = true` on
  every seeded account.
- **H2:** added `super_admin` role + strict per-operator isolation on
  every admin endpoint.
- **H3:** vehicle CRUD with fixed `vehicle_status` enum
  (`active|idle|maintenance|decommissioned`) and `vehicle_type` ↔
  route `route_type` cross-check.
- **H4:** routes & stops CRUD with GeoJSON validation (Syria bbox).
- **H5:** users CRUD with role-rank guard (no privilege escalation).
- **H6:** geofence CRUD + hard cap on `max_vehicles` enforced in
  `/api/driver/position`.
- **H7:** atomic `POST /api/admin/vehicles/register` linking flow.
- **H8:** trip-end ownership, alert-resolve operator scope,
  passenger-count actually persists, login precedence bug, JWT_SECRET
  32-char minimum, audit_log on every admin mutation.
- **H9:** Add/Edit forms on every admin page; new geofences page;
  forced password rotation flow.
- **H10:** 47 endpoints; full verification report in `FIXES_APPLIED.md`.

### Track A — Trip dispatch & operator console — same commit
- POST/GET/PATCH/DELETE `/api/admin/trips` with the
  `scheduled → dispatched → acked → in_progress → completed | cancelled`
  lifecycle.
- New `/admin/dispatch.html` Dispatcher Console (status pills,
  Schedule modal, Push/Cancel actions, 20-second auto-refresh).
- `/api/driver/me`, `/api/driver/me/next_trip`,
  `POST /api/driver/trip/{id}/ack`. Driver app shows a banner with
  Acknowledge button when a trip is queued.
- `Start Trip` now promotes a queued trip instead of always creating
  ad-hoc.

### Track C — Headway control + bunching alerts — commit `74142d1` / `8018092`
- New `routes.target_headway_min` column, `alert_type` value
  `bus_bunching`, `headway_observations` append-only table,
  `route_headway_status()` and `detect_bunching()` RPCs.
- `GET /api/admin/headway` for the new console gauge.
- `/api/driver/position` runs the bunching detector; deduped
  `bus_bunching` alerts; response surface `hold_seconds + gap_m +
  other_vehicle_id`.
- Driver UI: amber **hold banner** with live countdown.
- Dispatcher Console: per-route headway strip (target ↔ actual, with
  green/red/amber/grey status).

### Visible-bug fixes (folded into the v5.0 commit)
- `/api/routes` `stops_count` now hydrated from `route_stops`.
- Missing i18n keys for `idle` / `decommissioned` status pills added.
- Footer `v4.0` → `v5.0`.
- New `_gate.js` eliminates the flash-of-empty-admin-shell.
- Hardcoded fake KPI deltas replaced with computed values.
- `critical_alerts` exposed on `/api/admin/analytics/overview`.

### New migrations to apply (run in order)

```
db/migrations/011_rotate_demo_credentials.sql
db/migrations/012_geofence_capacity_and_links.sql
db/migrations/013_trip_dispatch.sql
db/migrations/014_headway_control.sql
```

---

## After the push — deploy to Vercel + Supabase

1. **Vercel:** if the project is already connected to the GitHub repo,
   the push triggers an automatic deploy. Otherwise, in the dashboard:
   - Import Project → pick the XYHDX/DTS repository.
   - Framework preset: "Other" (Vercel will detect `vercel.json`).
   - Environment variables (minimum):
     - `SUPABASE_URL`
     - `SUPABASE_KEY` (anon public key)
     - `SUPABASE_SERVICE_KEY` (service-role secret)
     - `JWT_SECRET` — **must be ≥32 chars** (the v5.0 backend will return
       503 otherwise). Generate one with:
       ```bash
       python3 -c "import secrets; print(secrets.token_urlsafe(48))"
       ```
     - `ALLOWED_ORIGINS` (your production hostname)

2. **Supabase:** open the SQL Editor and run the four migrations in
   order: `011`, `012`, `013`, `014`. They are idempotent — safe to
   re-run.

3. **Verify the deploy** — hit `https://dts-brown.vercel.app/api/health`
   (or your own host) and confirm the response shows:
   ```json
   {"status":"ok","version":"5.0.0","config":{"jwt_configured":true,"jwt_secret_min_len":32, …}}
   ```
   If you see `4.1.0` the new build hasn't gone live yet.

4. **Rotate demo credentials.** The new demo passwords are documented
   in `DEMO_CREDENTIALS.md`. Every seeded account starts with
   `must_change_password = true`, so the first login will be forced
   through `/admin/reset.html?force=1` before any privileged endpoint
   accepts the JWT.

---

## After-deploy smoke checks

```bash
HOST=https://dts-brown.vercel.app

# 1. Health, should report 5.0.0 with jwt_secret_min_len = 32
curl -s "$HOST/api/health" | python3 -m json.tool

# 2. Login as admin — must_change_password=true expected on the first one.
curl -s -X POST "$HOST/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@damascus-transit.demo","password":"AdminDamascus#2026"}' \
  | python3 -m json.tool

# 3. Routes endpoint — confirm stops_count is no longer null.
curl -s "$HOST/api/routes" | python3 -m json.tool | head -40
```

---

## Troubleshooting

### "stale info" or "non-fast-forward" (push rejected)

Means the remote `main` has commits your local doesn't. The script
prints both sides of the diff so you can see what's about to happen,
then offers three recovery modes — pick based on what the diff shows:

```bash
# RECOMMENDED for "switching deployment generations" — the remote
# has the v4.x history (design system, deploy fixes, wave2/3, etc.)
# and your local is the fresh v5.0 / Track A / Track C work that
# replaces almost everything. This soft-resets to origin/main and
# lands your entire working tree as ONE new commit on top, so the
# remote history is preserved AND your new tree becomes HEAD.
# Zero conflicts.
cd ~/Documents/Claude/Projects/DamascusTransitSystem
PUSH_MERGE=1 bash "./Push to GitHub.command"

# Alternative — replay your local commits on top of origin/main,
# auto-resolving conflicts in favor of your changes (-X theirs):
PUSH_REBASE=1 bash "./Push to GitHub.command"

# DESTRUCTIVE — overwrite the remote with the local history. You
# lose every commit listed in "REMOTE has but LOCAL doesn't". Only
# use on a personal / throwaway repo:
PUSH_FORCE=1 bash "./Push to GitHub.command"
```

To inspect without pushing, run this from Terminal:

```bash
cd ~/Documents/Claude/Projects/DamascusTransitSystem/source
git fetch origin
echo "== LOCAL has, REMOTE doesn't:" ; git log --oneline origin/main..main
echo "== REMOTE has, LOCAL doesn't:" ; git log --oneline main..origin/main
```

- **"Permission denied (publickey)"** — switch the remote URL from
  `git@github.com:…` to `https://github.com/XYHDX/DTS.git`:

  ```bash
  cd source
  git remote set-url origin https://github.com/XYHDX/DTS.git
  ```

- **`fatal: cannot lock ref 'HEAD'`** — re-run `bash CLEANUP.command`,
  it clears the stale `.git/HEAD.lock` / `.git/index.lock` files left
  behind by the sandbox.

- **Asked for username/password** — paste your GitHub username and a
  Personal Access Token (NOT your account password). Generate one at
  <https://github.com/settings/tokens?type=beta> with **Contents:
  read & write** scope. The macOS keychain helper remembers it.
