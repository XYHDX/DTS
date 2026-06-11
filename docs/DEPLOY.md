# DamascusTransit — Deployment guide

> Updated 2026-05-24 to reflect the new env vars (`TRUSTED_PROXY_IPS`, `TURNSTILE_SECRET`, `JWT_SECRET_PREVIOUS`), the eight CI workflows, and the hardened `vercel.json`. Two deployment topologies are supported. Pick one.

| Topology | Best for | Total cost |
|---|---|---|
| **A. Vercel + Supabase free tier** | A pilot up to ~150 vehicles | **$0/month** |
| **B. Self-hosted Docker (ministry)** | Large operator / strict data residency | Hardware + Supabase paid tier |

Both topologies use the same code, the same `.env`, and the same database schema. They differ only in the runtime envelope.

---

## A. Vercel + Supabase (default)

### 1. Provision Supabase (10 minutes)

1. Create a free Supabase project. Pick the region nearest your users — for Damascus, **eu-central-1 (Frankfurt)** has the lowest median RTT.
2. Open SQL editor and run `db/schema.sql`. This creates 15 tables, RLS policies, and PostGIS functions.
3. Run every file in `db/migrations/` in order. Migration `007_password_changed_at.sql` is **required** for the M1 token-revocation path to work.
4. Run `db/seed.sql` to load a tiny default operator.
5. (Optional) `python scripts/seed_demo_data.py --operator damascus --routes 8` for a richer dev dataset.

Capture the four credentials Supabase shows you:
`SUPABASE_URL`, `SUPABASE_KEY` (anon), `SUPABASE_ANON_KEY` (alias of anon), `SUPABASE_SERVICE_KEY` (service role).

### 2. Provision Upstash Redis (optional but recommended)

Free tier is enough for the pilot. The rate limiter falls back to an in-process memory window if Redis is unavailable (see ADR-003), so a missing Upstash project does not break logins — just makes the limiter weaker.

Capture `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN`.

### 3. (Optional) Provision Cloudflare Turnstile

Adds a captcha gate on the admin login. Sign up at <https://dash.cloudflare.com/?to=/:account/turnstile>, create a site, copy the site key and secret. Set:

- `TURNSTILE_SECRET` (Vercel env) — used by `api/core/turnstile.py` for `siteverify`.
- Inject the site key into `public/admin/login.html` as `window.TURNSTILE_SITE_KEY` (e.g. via a small `<script>` tag included from a Vercel rewrite).

The integration soft-fails if Cloudflare is unreachable — the FastAPI rate limiter remains the second line of defence.

### 4. Connect Vercel

```bash
npm install -g vercel
vercel link             # paste the project id from vercel.com
vercel env pull .env    # pulls down any env vars you've already set
```

Add every variable from the table below in Vercel → Settings → Environment Variables → **Production**.

| Variable | Required | Notes |
|---|---|---|
| `SUPABASE_URL`                  | yes | From step 1 |
| `SUPABASE_KEY` / `SUPABASE_ANON_KEY` | yes | anon key |
| `SUPABASE_SERVICE_KEY`          | yes | service role; never expose to clients |
| `JWT_SECRET`                    | yes | ≥32 chars, random, never commit |
| `JWT_SECRET_PREVIOUS`           | rotation only | see `Runbook_JWT_Rotation.md` |
| `ALLOWED_ORIGINS`               | yes | comma-separated; no `*` allowed |
| `TRUSTED_PROXY_IPS`             | yes | Vercel edge IP CIDRs (H1 fix). Without this, X-Forwarded-For values are ignored. |
| `UPSTASH_REDIS_REST_URL`        | optional | enables Redis caching + rate-limit |
| `UPSTASH_REDIS_REST_TOKEN`      | optional | pair with the URL |
| `TRACCAR_WEBHOOK_SECRET`        | optional | HMAC secret for the GPS webhook |
| `SENTRY_DSN`                    | optional | enables error reporting |
| `TURNSTILE_SECRET`              | optional | captcha gate on admin login |
| `RESEND_API_KEY`                | optional | transactional email |
| `RESEND_FROM_EMAIL`             | optional | pair with the API key |
| `ALERT_EMAIL_RECIPIENTS`        | optional | comma-separated; receives critical alerts |
| `VERCEL_TOKEN` / `VERCEL_ORG_ID` / `VERCEL_PROJECT_ID` | CI only | used by `.github/workflows/backup.yml` to enumerate deployments |

Deploy:

```bash
vercel --prod
```

### 5. Smoke-test the live deploy

```bash
curl -sS https://<your-project>.vercel.app/api/health/deep | jq
# Expect status 200 and "status": "healthy" with database + redis both true.

python scripts/smoke_test_production.py
# Hits the canonical endpoints with the demo accounts.
```

The Playwright tests in `tests/passenger_flow.spec.js` and `tests/driver_flow.spec.js` can also be pointed at the live URL with `BASE_URL=https://<your-project>.vercel.app npx playwright test`.

### 6. CI sanity

After the first deploy, push a no-op commit to `main` and watch:

- `ci.yml` — lint + pytest must be green.
- `flutter.yml` — analyze + test + debug APK build.
- `security-scan.yml` — pip-audit + npm audit + gitleaks all clean.
- `lighthouse.yml` — perf ≥0.85, a11y ≥0.9.
- `openapi-lint.yml` — Spectral has no errors.
- `backup.yml` — first scheduled run is within 24h; you can also trigger it manually.
- `codeql.yml` — Python + JS/TS analysis is green.
- `release-please.yml` — opens a release PR if there are unreleased conventional commits.

---

## B. Self-hosted Docker (ministry)

See `DOCKER_MINISTRY_DEPLOY.md` for the long form. The short version:

```bash
cp .env.ministry.example .env
# Edit .env with your DB credentials, JWT secret, and ALLOWED_ORIGINS.
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```

The compose file:

- Uses the multi-stage `Dockerfile.prod` (Python 3.12-slim, tini PID 1, non-root UID 10001, `read_only: true` filesystem, tmpfs for /tmp + /dev/shm, no-new-privileges).
- Healthcheck hits `/api/health/deep` so the orchestrator pulls the container out of rotation on DB or Redis outage.
- Nginx fronts it on 80/443 with HTTP/3 (QUIC) advertised via Alt-Svc, brotli + gzip compression, per-route rate-limit zones.

Before exposing publicly, double-check:

- `nginx/ssl/fullchain.pem` and `privkey.pem` exist (Let's Encrypt via certbot is wired in compose).
- `ALLOWED_ORIGINS` lists **only** your production origin(s).
- `TRUSTED_PROXY_IPS` lists nginx's container IP so the rate limiter trusts the proxy hop.

---

## Backups + DR

The DR story is documented in `markdown-files/technical/Runbook_DB_Backup_Restore.md`. Every night `.github/workflows/backup.yml` exports a custom-format `pg_dump`, verifies the row counts haven't dropped more than 20%, and stores the artifact for 7 days; the first of every month is pinned as a GitHub release for 90 days.

A quarterly restore drill is mandatory — track it in `Health_Log.md`.

## Incident response

When prod breaks, follow `markdown-files/technical/Runbook_Incident_Response.md`. The TL;DR:

1. Acknowledge the Sentry page.
2. Hit `/api/health/deep` and identify which sub-check failed.
3. Rollback before debugging if the incident started during/after a deploy: `vercel rollback`.
4. Communicate every 30 minutes for SEV-1.
5. Postmortem within 5 working days, blameless, action items into `ROADMAP_100.md`.

## What changed in this revision

- New: `TRUSTED_PROXY_IPS`, `TURNSTILE_SECRET`, `JWT_SECRET_PREVIOUS` env vars.
- New: eight-workflow CI matrix (was four).
- New: HTTP/3 + brotli on the self-hosted nginx.
- New: `/api/health/deep` with three-way probe (DB + Redis + position freshness).
- Tightened: vercel.json security headers (HSTS preload, COOP, CORP, CSP per surface).
- Hardened: docker-compose.prod with read-only fs, tmpfs mounts, no-new-privileges.

If you're upgrading from the April 2026 deploy, the only **breaking** change is migration `007_password_changed_at.sql`. Run it before the first redeploy.
