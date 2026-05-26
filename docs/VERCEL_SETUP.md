# Vercel Environment Setup — required to make the backend work

If you see this error on `/api/health` or any other API endpoint:

```
This Serverless Function has crashed.
500: INTERNAL_SERVER_ERROR — FUNCTION_INVOCATION_FAILED
```

…the FastAPI backend can't initialize because the required environment variables aren't set in Vercel. Symptoms downstream:

- **Driver page**: GPS pill stays stuck at "جاري الاتصال…" because login can't succeed → `setupGPS()` never runs.
- **Admin login**: shows "بيانات الدخول غير صحيحة" for any password — the real error is the API returning 500, not bad credentials.
- **Passenger map**: shows nothing because `/api/stream` is unreachable.

## Required env vars (minimum to boot)

Go to **Vercel → your project → Settings → Environment Variables** and add these for the **Production** scope (and optionally Preview):

| Variable | Value | Where to get it |
|---|---|---|
| `SUPABASE_URL` | `https://<project-ref>.supabase.co` | Supabase → Project Settings → API → Project URL |
| `SUPABASE_KEY` | `eyJ...` (long JWT) | Supabase → Project Settings → API → `anon` `public` key |
| `SUPABASE_ANON_KEY` | same as `SUPABASE_KEY` | same source — needed by the SDK |
| `SUPABASE_SERVICE_KEY` | `eyJ...` (different JWT) | Supabase → Project Settings → API → `service_role` `secret` key (this one is sensitive — never expose to the browser) |
| `JWT_SECRET` | random 64-char string | Generate locally: `openssl rand -hex 32` |
| `ALLOWED_ORIGINS` | `https://dts-brown.vercel.app` | Match your Vercel production domain. Add preview domains comma-separated if needed. |

## Optional env vars (features that require setup)

| Variable | Used by | Default behaviour if missing |
|---|---|---|
| `TURNSTILE_SECRET` | Cloudflare Turnstile captcha on admin login | Captcha is hidden — login still works |
| `SENTRY_DSN` | Error monitoring | Errors aren't sent anywhere (logs only) |
| `RESEND_API_KEY` | Email alerts to operators | Alerts still appear in admin dashboard, just no email |
| `UPSTASH_REDIS_REST_URL` + `UPSTASH_REDIS_REST_TOKEN` | Redis Geo cache for 100k-scale | Falls back to Postgres position queries (slower) |
| `QSTASH_TOKEN` | Scheduled background jobs | Cron jobs run via Vercel native cron only |
| `TRACCAR_WEBHOOK_SECRET` | GPS hardware tracker integration | Hardware GPS ingestion disabled |

## Step-by-step in the Vercel dashboard

1. Go to https://vercel.com/dashboard → click on your **dts** (or `dts-brown`) project.
2. Click **Settings** in the top nav.
3. Click **Environment Variables** in the left sidebar.
4. For each of the 6 required vars above:
   - **Name**: paste the variable name (e.g. `SUPABASE_URL`)
   - **Value**: paste the value from Supabase
   - **Environment**: tick **Production**, **Preview**, and **Development**
   - Click **Save**
5. After all 6 are saved, go to the **Deployments** tab → click the **⋯** on the latest deployment → **Redeploy** → confirm.
6. Wait ~30 seconds for the new build to ship.
7. Visit `https://dts-brown.vercel.app/api/health` — you should see `{"status":"ok"}` instead of the crash page.
8. Visit `https://dts-brown.vercel.app/admin/login.html` and log in with `admin@damascus-transit.demo` / `damascus2025`.

## Finding your Supabase keys

1. Supabase → your **DTSDB** project → top-left dropdown stays on DTSDB.
2. Click **Project Settings** (gear icon, bottom-left sidebar).
3. Click **API** in the left submenu.
4. Copy the three things from the right panel:
   - **Project URL** → `SUPABASE_URL`
   - **anon public** key → `SUPABASE_KEY` and `SUPABASE_ANON_KEY` (same value, two env names)
   - **service_role secret** key → `SUPABASE_SERVICE_KEY`

The service-role key bypasses RLS — keep it secret, never paste it into the frontend code, only into Vercel env vars.

## Generating a JWT secret

In a terminal:

```bash
openssl rand -hex 32
```

This produces a 64-character random string. Paste it as `JWT_SECRET`. The backend uses it to sign and verify auth tokens; if it changes, all existing logins become invalid (everyone has to log in again — that's fine for now).

## Verifying after redeploy

After redeploying with the env vars set, the following URLs should all return valid JSON instead of the Vercel crash page:

```
https://dts-brown.vercel.app/api/health      → {"status":"ok","ts":...}
https://dts-brown.vercel.app/api/routes      → [{"id":"R101",...}, ...]
https://dts-brown.vercel.app/api/stats       → {"active_vehicles":4,...}
```

If `/api/health` is fine but `/api/routes` or `/api/stats` returns an error, the env vars are set but the database connection isn't reaching Supabase — most often a stale `SUPABASE_URL` (you copied the dashboard URL `https://supabase.com/dashboard/...` instead of the project API URL `https://<ref>.supabase.co`).

## Why this isn't auto-configured

Vercel can't set these for you because:
- `SUPABASE_SERVICE_KEY` is a project-specific secret only you have
- `JWT_SECRET` is yours to generate (sharing one across projects is a security smell)
- `ALLOWED_ORIGINS` depends on your final production domain

The `.env.example` file in the repo root documents the same list with comments — use it as a checklist.
