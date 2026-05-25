# Supabase Security Advisor — Known False Positives

After running `db/supabase_bootstrap.sql` against a fresh Supabase Cloud project, the **Security Advisor** dashboard will still show **1 error + 7 warnings**. All of them point at PostGIS objects that Supabase Cloud doesn't let customers modify. This document explains why each one is benign and what (if anything) you can do about it.

## The remaining findings

| # | Type | Entity | Reason it can't be cleared |
|---|---|---|---|
| 1 | Error — RLS Disabled | `public.spatial_ref_sys` | Table owned by `supabase_admin`. Both SQL editor and dashboard UI return `42501: must be owner of table spatial_ref_sys`. |
| 2 | Warning — Extension in Public | `public.postgis` | Supabase's default install location for PostGIS. Moving it requires schema-qualifying every PostGIS call in the API code — not worth it. |
| 3–5 | Warning — Public Can Execute SECURITY DEFINER | `public.st_estimatedextent(text,text)`, `(text,text,text)`, `(text,text,text,boolean)` | All three overloads owned by `supabase_admin`. `REVOKE EXECUTE` from `postgres` role fails with same ownership error. |
| 6–8 | Warning — Signed-In Users Can Execute | Same three `st_estimatedextent` overloads | Same ownership barrier. |

## Why your data is still secure

The advisor checks whether *any* table in `public` has RLS disabled. It flags `spatial_ref_sys` because PostGIS installs it there, but the table contains only public EPSG reference data (coordinate system definitions used by `ST_Transform()` etc.) — it has no user data, no PII, nothing sensitive. The same is true of the `st_estimatedextent` function — it estimates the geographic extent of a column, which a curious user can already determine by running `SELECT min(lat), max(lat) FROM ...`.

The 10 application tables you actually care about (`operators`, `users`, `routes`, `stops`, `route_stops`, `vehicles`, `vehicle_positions`, `vehicle_positions_latest`, `trips`, `alerts`) **all have RLS enabled**, with carefully scoped policies:

- **Read-allowed for anon role** (passenger app): `routes`, `stops`, `route_stops`, `vehicles`, `vehicle_positions_latest`
- **Service-role only** (FastAPI backend bypasses RLS): `users`, `vehicle_positions`, `trips`, `operators`, `alerts`

Every CRUD operation goes through one of those two roles. The PostGIS reference tables/functions don't expose any pathway around them.

## Why neither SQL nor the dashboard UI can fix this

Supabase Cloud runs your database with you connected as the `postgres` role — a customer-facing power user, but not the actual superuser. Genuine superuser (`supabase_admin`) is reserved for the platform itself so it can run migrations, manage backups, etc. PostGIS installs `spatial_ref_sys` and its helper functions under `supabase_admin` ownership, and only the owner can `ALTER` or `REVOKE` on those objects.

I confirmed this in two ways while bootstrapping the project:
1. SQL Editor: `ALTER TABLE public.spatial_ref_sys ENABLE ROW LEVEL SECURITY` returns `ERROR: 42501: must be owner of table spatial_ref_sys`.
2. Database → Tables → Edit table → tick "Enable RLS" → Save: returns the **exact same** `42501` error in a toast notification.

Even Supabase's own internal dashboard tooling uses a customer-tier connection and hits the same wall.

## Three options if you really want them gone

### Option A — Accept as documented (recommended)
Every Supabase Cloud project that uses PostGIS has these exact same findings. The Supabase community treats them as documented false positives. Your real security posture is determined by your 10 app-table RLS policies, which are correct.

### Option B — Open a Supabase Support ticket
Ask the support team to either:
- Grant your `postgres` role temporary ownership of `spatial_ref_sys` so you can run the `ALTER` once, or
- Suppress those specific lint findings on your project.

They usually respond in 1–2 business days. Use this ticket template:

> **Subject:** Suppress benign PostGIS lint findings on project `<your-ref>`
>
> Project: `jcmwavmascyddpigayyp`
>
> The Security Advisor reports 1 error (RLS on `spatial_ref_sys`) and 6 warnings (3 × `st_estimatedextent` overloads × 2 visibility checks) plus 1 "Extension in Public" warning for `postgis`. All of these point at PostGIS objects owned by `supabase_admin`, so I cannot clear them from the SQL editor or the Tables UI (both return `42501: must be owner`).
>
> Could you either suppress these specific Splinter rules on my project, or grant my `postgres` role temporary ownership of `spatial_ref_sys` so I can enable RLS on it? My own 10 application tables all have RLS + scoped policies enabled.
>
> Thanks.

### Option C — Migrate off PostGIS (not recommended)
Replace `GEOMETRY` / `GEOGRAPHY` columns with plain `numeric` lat/lon pairs. Eliminates the warnings but kills `ST_DWithin`, `ST_Distance`, `ST_Within`, `ST_Transform`, the GIST spatial index on positions — i.e. all the "nearest stops within 1.5km" and "vehicles on this route segment" queries. The whole transit-app value proposition depends on those.

## Re-runnability of the bootstrap

`db/supabase_bootstrap.sql` is fully idempotent on a clean project:

- `CREATE EXTENSION IF NOT EXISTS` for both extensions
- `CREATE TYPE … IF NOT EXISTS`-equivalent via `DO $$ BEGIN … EXCEPTION WHEN duplicate_object THEN NULL; END $$`
- `CREATE TABLE IF NOT EXISTS` on every table
- `INSERT … ON CONFLICT DO NOTHING` for seed data
- `DROP POLICY IF EXISTS` before `CREATE POLICY` so re-runs don't leave duplicates
- PostGIS-ownership-protected sections wrapped in `EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE`

You can safely re-run the whole file at any time. The final verification SELECT should print:

```
operators=1, users=4, routes=4, stops=12, vehicles=6, active_vehicles=4, positions_latest=4
```

If your advisor shows anything different from the 1 error + 7 warnings catalogued above, **that's** worth investigating.
