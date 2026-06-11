# Runbook — Supabase backup and restore

> Two stories: nightly automated backups (always-on), and a restore drill that we exercise quarterly. Both share the same primitives. Target time for a full restore from cold: **45 minutes**.

## What's backed up

| Surface | Mechanism | Frequency | Retention |
|---|---|---|---|
| Postgres schema + data | `pg_dump --format=custom`, stored in Supabase Storage bucket `backups/` | Nightly 02:30 UTC via `.github/workflows/backup.yml` | 14 days rolling, 1 monthly snapshot per month for 12 months |
| Storage objects (incident photos) | Supabase native object-store replication | Continuous | Per Supabase free tier policy |
| Auth metadata (users.* PostgREST tables) | Part of the pg_dump above | Same | Same |
| Edge config (Vercel env vars) | Encrypted JSON in 1Password vault | After each rotation | Indefinite |

What is **not** backed up: Sentry event data, Upstash Redis (it is a cache by design and can be cold-started), `scripts/simulate_gps.py` runtime state.

## Take a backup right now

```bash
# Requires: a service-role connection string in SUPABASE_DB_URL.
# Generate one in Supabase → Settings → Database → Connection string (URI).

OUT="dam_backup_$(date -u +%Y%m%dT%H%M%SZ).dump"
pg_dump "$SUPABASE_DB_URL" \
        --format=custom \
        --no-owner --no-privileges \
        --jobs=4 \
        -f "$OUT"
ls -lh "$OUT"
```

The custom format is required by `pg_restore`. Plain SQL backups also work but are about 4× larger and slower to restore.

Upload to the `backups/` bucket:

```bash
curl -X POST "$SUPABASE_URL/storage/v1/object/backups/$(basename $OUT)" \
     -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" \
     -H "Content-Type: application/octet-stream" \
     --data-binary @"$OUT"
```

## Restore into a fresh project

This is the procedure to use during a real incident or during the quarterly drill.

### 0. Stand up a fresh Supabase project (5 min)

- New project: same region (eu-central-1) and same plan tier.
- Enable PostGIS in the SQL editor: `CREATE EXTENSION IF NOT EXISTS postgis;`
- Run `db/schema.sql` first **only** when restoring into a totally clean DB. If `pg_restore` will recreate everything, skip this.

### 1. Pull the latest backup (5 min)

```bash
LATEST=$(curl -sS "$SUPABASE_URL/storage/v1/object/list/backups" \
           -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" \
         | jq -r 'sort_by(.updated_at) | reverse | .[0].name')
curl -sS "$SUPABASE_URL/storage/v1/object/backups/$LATEST" \
     -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" \
     -o "$LATEST"
```

Verify the file size matches what was uploaded (CloudWatch / Supabase audit log).

### 2. Restore (15 min)

```bash
pg_restore --dbname "$NEW_SUPABASE_DB_URL" \
           --clean --if-exists --no-owner --no-privileges \
           --jobs=4 \
           "$LATEST"
```

Common gotchas:

- `pg_restore: error: could not execute query: ERROR: extension "postgis" must be installed` → run the `CREATE EXTENSION` step from §0 first.
- `permission denied for schema public` → ensure `$NEW_SUPABASE_DB_URL` uses the service-role connection string, not the anon one.
- Row counts mismatch with production → check if anything was written to production after the backup ran; the dump is consistent at the moment of pg_dump only.

### 3. Verify (10 min)

```sql
-- Counts should be within 1% of yesterday's baseline. Update the baseline in Health_Log.md.
SELECT 'routes',  COUNT(*) FROM routes;
SELECT 'stops',   COUNT(*) FROM stops;
SELECT 'vehicles', COUNT(*) FROM vehicles;
SELECT 'trips',   COUNT(*) FROM trips;
SELECT 'users',   COUNT(*) FROM users;

-- Spot-check PostGIS data
SELECT id, ST_AsText(geometry) FROM routes LIMIT 3;

-- Confirm RLS policies survived
SELECT schemaname, tablename, policyname FROM pg_policies WHERE schemaname = 'public';
```

Also hit the API health endpoint against the restored DB:

```bash
SUPABASE_URL="https://<new>.supabase.co" \
SUPABASE_KEY="<new-anon-key>" \
SUPABASE_SERVICE_KEY="<new-service-key>" \
  uvicorn api.index:app --port 8001 &

curl -sS http://localhost:8001/api/health/deep
```

Expect `status: healthy` and `position_fresh_6h: false` (the restored DB has stale positions, which is correct after a 24h-old dump).

### 4. Cut over (5 min)

Only after §3 passes:

- Update Vercel env vars `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_KEY` to the new project.
- Redeploy.
- Run `scripts/smoke_test_production.py` against the live URL.
- Announce on Slack / status page.

### 5. Decommission the old project (when safe)

Wait at least 7 days before deleting the old project — keep an escape hatch in case the restore turned out to be incomplete.

## Quarterly drill

Schedule the drill into the calendar at the end of each quarter. Use a throwaway Supabase project. Time the full §1 → §3 cycle and write the result into `Health_Log.md`:

```
## YYYY-MM-DD — Backup restore drill
- Backup vintage: 2026-MM-DD 02:30 UTC
- Restored into: <project-id>
- Total time: 38 min
- Verification: row counts within 0.4% of production; /api/health/deep returns 200
- Issues found: none
- Drilled by: <name>
```

If the drill takes more than 60 minutes, file a follow-up task — a slow restore is itself an incident waiting to happen.

## Recovery objectives

| Objective | Target |
|---|---|
| RPO (recovery point) | 24 h — we accept losing at most one day of data on a cold restore |
| RTO (recovery time) | 60 min from "we need to restore" to "service is live on the restored DB" |
| Drill cadence | Quarterly, mandatory |
| Backup verification | Automated row-count diff against the prior backup runs nightly in `.github/workflows/backup.yml` |
