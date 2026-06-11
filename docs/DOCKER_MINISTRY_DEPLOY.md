# DamascusTransit — Ministry self-hosted deployment

> Updated 2026-05-24 to reflect the hardened `Dockerfile.prod` and `docker-compose.prod.yml`, the new `/api/health/deep` healthcheck, nginx HTTP/3 + brotli, the design-system refresh, and the eight-workflow CI matrix.

This guide is the ground-truth procedure for running DamascusTransit on the Ministry's own servers, without any reliance on Vercel. Vercel is still supported and documented in `DEPLOY.md` — pick whichever topology fits your data-residency posture.

## Hardware baseline

| Tier | CPU | RAM | Disk | Notes |
|---|---|---|---|---|
| Pilot (≤150 vehicles) | 2 vCPU | 4 GB | 40 GB SSD | A single host running api + nginx + Postgres. |
| Production (≤500 vehicles) | 4 vCPU | 8 GB | 80 GB SSD | Postgres on a separate host or use Supabase Pro. |
| Region rollout (1 000+) | 8 vCPU + LB | 16 GB | 200 GB SSD | Add a second API host behind a load balancer. |

The reference compose file targets the pilot tier. The production tier is the same compose file with the Postgres service externalised — the API connects to `SUPABASE_URL` instead.

## Pre-flight

1. Ubuntu 22.04 LTS or Debian 12 host with `docker` and `docker compose v2`.
2. A DNS A/AAAA record pointing at the host. The Let's Encrypt cert-bot path assumes `damascustransit.example.sy`.
3. Outbound HTTPS to `fonts.googleapis.com`, `cdn.jsdelivr.net`, `tile.openstreetmap.org`, and (if used) `firebase-messaging.googleapis.com`.
4. A 64-character random `JWT_SECRET` generated with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`.

## Bring up the stack

```bash
# 1. Clone
git clone https://github.com/actuatorsos/SyrianTransitSystem.git ministry-transit
cd ministry-transit

# 2. Configure
cp .env.ministry.example .env
${EDITOR} .env       # fill: SUPABASE_*, JWT_SECRET, ALLOWED_ORIGINS, TRUSTED_PROXY_IPS

# 3. Build + run
docker compose -f docker-compose.prod.yml --env-file .env up -d --build

# 4. Verify
curl -fsS http://localhost/healthz                                       # nginx
curl -fsS http://localhost/api/health/deep | jq                          # api
```

The `/api/health/deep` probe returns 200 only when **all three** sub-checks pass: database connectivity, Redis connectivity (or in-memory fallback active), and a position update within the last 6 hours during service hours. The Docker healthcheck uses this endpoint so the orchestrator pulls a sick container out of rotation automatically.

## Required env vars

| Variable | Purpose |
|---|---|
| `SUPABASE_URL` / `SUPABASE_KEY` / `SUPABASE_SERVICE_KEY` | Database access (Supabase or your own self-hosted Postgres + PostgREST). |
| `JWT_SECRET`        | ≥ 32 random chars. Token-signing key. Rotate per `Runbook_JWT_Rotation.md`. |
| `ALLOWED_ORIGINS`   | Comma-separated. No wildcards. Your real production domain. |
| `TRUSTED_PROXY_IPS` | The nginx container's IP (`172.18.0.2` for the default compose network). Without this the rate limiter discards `X-Forwarded-For`. |

Optional but recommended:

| Variable | Purpose |
|---|---|
| `UPSTASH_REDIS_REST_URL` + `_TOKEN` | Cluster-wide rate limit counters. Without these the limiter falls back to per-process memory (ADR-003). |
| `TRACCAR_WEBHOOK_SECRET` | HMAC secret if you run a Traccar GPS server. |
| `SENTRY_DSN` | Error reporting. |
| `TURNSTILE_SECRET` | Captcha gate on `/admin/login.html`. |
| `RESEND_API_KEY` + `RESEND_FROM_EMAIL` + `ALERT_EMAIL_RECIPIENTS` | Outbound mail for critical alerts. |

## TLS

The compose file mounts `nginx/ssl/` into the nginx container. Two ways to fill it:

### Let's Encrypt (recommended)

```bash
sudo ./scripts/setup-ssl.sh damascustransit.example.sy ops@example.sy
```

This stops nginx, runs the standalone certbot ACME flow, places `fullchain.pem` and `privkey.pem` into `nginx/ssl/`, and re-up's the stack. Renewal is via a host-side cron (`certbot renew && docker compose restart nginx`) — see `scripts/setup-ssl.sh` for the exact line.

### Bring-your-own cert

Drop `fullchain.pem` and `privkey.pem` into `nginx/ssl/` before `docker compose up`. The TLS hygiene block in `nginx/nginx.conf` is set for TLSv1.2+ only.

## What the stack gives you

- **HTTP/3 over QUIC** on port 443 via Alt-Svc advertisement. Clients capable of H3 upgrade automatically; everyone else gets H2 / 1.1.
- **Brotli + gzip** compression on every static and JSON response.
- **Per-route rate limits**: `api_general` 20 r/s burst 40, `api_login` 5 r/min burst 2, `conn_per_ip` 50.
- **Tightened CSP / HSTS / COOP / CORP** headers identical to the Vercel deployment so client behaviour is identical across topologies.
- **read-only filesystem + tmpfs** on the API container. The only writable paths are `/tmp` (64 MB tmpfs) and `/dev/shm` (64 MB tmpfs for gunicorn workers).
- **non-root UID 10001** so a container escape lands on an unprivileged account.

## Sanity checks after a deploy

```bash
# All four web apps render
for path in / /passenger/ /driver/ /admin/login.html; do
  printf "%-22s " "$path"
  curl -sS -o /dev/null -w "%{http_code} %{time_total}s\n" "https://damascustransit.example.sy${path}"
done

# Deep healthcheck
curl -fsS https://damascustransit.example.sy/api/health/deep | jq

# SSE stream alive
curl -sS https://damascustransit.example.sy/api/stream \
     -H 'Accept: text/event-stream' --max-time 8 | head -c 4000

# Security headers
curl -sIX GET https://damascustransit.example.sy/ | grep -iE 'strict-transport|content-security|frame-options|cross-origin'
```

If any of these fail, follow `markdown-files/technical/Runbook_Incident_Response.md`.

## Backups

The compose stack does **not** automatically back up your Postgres. Wire one of:

1. **GitHub Actions `backup.yml` against your self-hosted DB** — set `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` secrets to point at the ministry's Postgres + PostgREST endpoint. The same workflow that backs up Supabase will work.
2. **Host-side cron** — see `markdown-files/technical/Runbook_DB_Backup_Restore.md` for the `pg_dump --format=custom` recipe and the verification job.
3. **Hot replica** — for the production tier, run a streaming replica on a second host. Failover is not in scope here.

The quarterly restore drill is mandatory regardless of topology.

## Updating

```bash
git fetch origin main
git checkout main
git pull
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```

The build is multi-stage so a typical update touches only the API layer image. nginx is rebuilt only when `nginx/nginx.conf` changes.

If you're upgrading from the April 2026 deploy you must apply database migration `007_password_changed_at.sql` before the first redeploy — see `Runbook_Hotfix_Deploy.md`'s decision tree for whether to use rollback or patch.

## Air-gapped notes

If the ministry network blocks outbound to public CDNs:

- Set `MAPLIBRE_TILE_URL` to a self-hosted tile server (e.g. a containerised `martin` instance) and tighten `nginx/nginx.conf`'s CSP `img-src` accordingly.
- Mirror `fonts.googleapis.com` and `cdn.jsdelivr.net` content into `public/lib/vendored/` and remove the external links from `public/index.html`, `public/passenger/index.html`, `public/driver/index.html`, `public/admin/login.html`, and `public/admin/index.html`.
- Disable FCM in the Flutter / Capacitor builds by omitting `google-services.json`. The push pipeline degrades cleanly.

## Cost rough-cut (single-host pilot, USD/month)

| Item | Cost |
|---|---|
| 2 vCPU / 4 GB VPS (DigitalOcean, Hetzner) | ~$24 |
| Domain + Let's Encrypt | ~$1 (domain amortised) |
| Backup storage (Supabase Storage free or S3-compatible) | $0–5 |
| **Total** | **~$25–30/month** |

The Vercel free-tier topology in `DEPLOY.md` runs the same software for **$0/month** but at the cost of US-based hosting. Pick deliberately.
