# DamascusTransit — Disaster Recovery Runbook

**Last updated:** 2026-03-30
**Owner:** Platform Engineer
**Scope:** Supabase (PostgreSQL) + Vercel (API + frontend)

---

## RTO / RPO Targets

| Tier | Scenario | RTO | RPO |
|------|----------|-----|-----|
| P0 | Full DB loss | 2 hours | 24 hours (last nightly backup) |
| P1 | Vercel deployment broken | 15 minutes | 0 (instant rollback) |
| P2 | Single table corrupted | 30 minutes | 24 hours |

---

## Backup Schedule

Automated via GitHub Actions (`.github/workflows/backup.yml`):

| Frequency | Retention | Storage |
|-----------|-----------|---------|
| Nightly at 01:00 UTC | 7 days | GitHub Actions artifacts |
| Monthly (1st of month) | 90 days | GitHub Release asset |

### What Is Backed Up

- All 12 Supabase tables exported as JSON via REST API
- Vercel env var names (not values) + recent deployment list
- Schema and seed SQL files are version-controlled in `db/`

### What Is NOT Backed Up Automatically

- Supabase env var **values** (stored in Vercel — use dashboard export)
- Supabase project settings / connection pooling config
- Custom RLS policies beyond what is in `db/schema.sql`

---

## Playbook 1 — Database Partial Corruption

A table has bad data (e.g., accidental bulk delete).

```bash
# 1. Download latest backup artifact from GitHub Actions
#    Actions → Workflow runs → "Disaster Recovery — Automated DB Backup" → Artifacts

# 2. Unpack
tar -xzf damascus-transit-backup-YYYY-MM-DD.tar.gz

# 3. Dry-run to confirm backup is valid
SUPABASE_URL=https://... SUPABASE_SERVICE_KEY=eyJ... \
  python scripts/restore-db.py --backup-dir ./backup-<run-id> --tables routes,stops --dry-run

# 4. Restore specific table(s)
SUPABASE_URL=https://... SUPABASE_SERVICE_KEY=eyJ... \
  python scripts/restore-db.py --backup-dir ./backup-<run-id> --tables routes,stops
```

The restore script **upserts** — existing rows with matching PKs are overwritten.
It does **not** delete rows not in the backup.

---

## Playbook 2 — Full Database Loss

Supabase project is deleted or data is wiped.

```bash
# Step 1: Create a new Supabase project
#   Dashboard → New Project → Frankfurt (eu-central-1)
#   Save: SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY, JWT secret

# Step 2: Apply schema (enables PostGIS, creates all tables, indexes, RLS)
#   Supabase SQL Editor → paste contents of db/schema.sql → Run

# Step 3: Apply seed data (routes, stops, schedules, demo vehicles)
#   Supabase SQL Editor → paste contents of db/seed.sql → Run

# Step 4: Restore live data from latest backup
SUPABASE_URL=https://new-project.supabase.co SUPABASE_SERVICE_KEY=eyJ... \
  python scripts/restore-db.py --backup-dir ./backup-<run-id>

# Step 5: Update Vercel env vars to point to new project
vercel env rm SUPABASE_URL production --yes
vercel env add SUPABASE_URL production   # paste new URL
vercel env rm SUPABASE_KEY production --yes
vercel env add SUPABASE_KEY production
vercel env rm SUPABASE_SERVICE_KEY production --yes
vercel env add SUPABASE_SERVICE_KEY production

# Step 6: Trigger redeploy
vercel --prod --yes

# Step 7: Smoke test
curl https://syrian-transit-system.vercel.app/api/health
```

---

## Playbook 3 — Vercel Deployment Broken

A bad deploy is serving errors.

```bash
# Option A: Instant rollback via Vercel CLI (recommended)
vercel rollback --token "$VERCEL_TOKEN"

# Option B: Rollback via dashboard
#   Vercel dashboard → Deployments → find last good deploy → "..." → Promote to Production

# Verify
curl https://syrian-transit-system.vercel.app/api/health
```

---

## Playbook 4 — Manual Backup (On-Demand)

Before a risky migration or schema change:

```bash
# Run backup locally
SUPABASE_URL=https://... SUPABASE_SERVICE_KEY=eyJ... \
  python scripts/backup-db.py --output-dir ./backup-$(date +%Y%m%d-%H%M)

# Compress
tar -czf pre-migration-backup-$(date +%Y%m%d).tar.gz ./backup-$(date +%Y%m%d-)*/
```

Or trigger the GitHub Actions workflow manually:
Actions → "Disaster Recovery — Automated DB Backup" → Run workflow.

---

## Playbook 5 — Vercel Env Var Recovery

All env var keys and their types are captured in nightly backup artifacts
(`vercel-env-manifest-YYYY-MM-DD.txt`). **Values are not stored.**

To recover values:
1. Vercel dashboard → Settings → Environment Variables → Export (XLSX/JSON)
2. Or check with the board for secrets stored in password manager / vault

---

## Secrets Inventory

| Secret | Used By | Recovery Path |
|--------|---------|---------------|
| `SUPABASE_URL` | Vercel, GitHub Actions | Supabase dashboard → Settings → API |
| `SUPABASE_KEY` (anon) | Vercel | Supabase dashboard → Settings → API |
| `SUPABASE_SERVICE_KEY` | Vercel, GitHub Actions (backup) | Supabase dashboard → Settings → API |
| `JWT_SECRET` | Vercel | Rotate via `openssl rand -hex 32`, update in Vercel + any issued tokens invalidated |
| `VERCEL_TOKEN` | GitHub Actions (CI/CD) | Vercel dashboard → Account → Tokens |
| `VERCEL_ORG_ID` | GitHub Actions | Vercel dashboard → Settings → General |
| `VERCEL_PROJECT_ID` | GitHub Actions | Vercel dashboard → Project Settings |
| `UPSTASH_REDIS_REST_URL` | Vercel (optional cache) | Upstash console |
| `UPSTASH_REDIS_REST_TOKEN` | Vercel (optional cache) | Upstash console |

---

## GitHub Actions Setup (Required Secrets)

Add these secrets to the GitHub repo (Settings → Secrets and variables → Actions):

```
SUPABASE_URL            https://your-project.supabase.co
SUPABASE_SERVICE_KEY    eyJ...service-role-key
VERCEL_TOKEN            your-vercel-token
VERCEL_ORG_ID           your-org-id
VERCEL_PROJECT_ID       your-project-id
```

The backup workflow will fail silently (artifact upload still works) if Vercel secrets
are missing — only the env manifest step is skipped.

---

## Testing the Backup/Restore Pipeline

Run after any infrastructure change:

```bash
# 1. Take a fresh backup
SUPABASE_URL=https://... SUPABASE_SERVICE_KEY=eyJ... \
  python scripts/backup-db.py --output-dir ./test-backup

# 2. Dry-run restore to validate all files
SUPABASE_URL=https://... SUPABASE_SERVICE_KEY=eyJ... \
  python scripts/restore-db.py --backup-dir ./test-backup --dry-run

# Expected output: all tables listed with row counts, no errors
```

Test against production quarterly or after any major schema migration.
