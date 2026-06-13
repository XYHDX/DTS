# Restore Runbook — "Operator 'damascus' not found" / login fails

**Symptom (observed 2026-06-13 on dts-brown.vercel.app):**
- `GET /api/health` → `200 healthy` (DB + Redis up) ✅
- `GET /api/stats|routes|stream|vehicles|stops` → `404 {"detail":"Operator 'damascus' not found"}`
- `POST /api/auth/login` with demo creds → `401 {"detail":"Invalid credentials"}`

**Root cause:** the backend is healthy, but the **production Supabase database is
not seeded** — the `damascus` operator row and the demo user accounts are
missing. Every operator-scoped read resolves to slug `damascus` (the app
default) and 404s; every login fails because the `users` rows don't exist.

The data was present until ~2026-06-11 (`health.last_position_update`), so a
migration/redeploy/reset most likely dropped or re-created the tables without
re-seeding.

---

## Fix (do this once, in the Supabase SQL editor)

The SQL editor runs as the **service role**, so it bypasses RLS.

1. Open Supabase → **SQL Editor** for the project this deployment points at
   (`SUPABASE_URL`).
2. **Apply migrations first** if the schema is fresh: run `db/schema.sql`, then
   each file in `db/migrations/` in numeric order (`002_…` → `020_…`).
3. **Seed the demo data:** paste and run the entire contents of
   **`db/demo_seed.sql`**. It is idempotent (safe to re-run) and resolves all
   foreign keys by business key, so pre-existing rows are reused, not collided.
4. (Optional) For a cross-operator super admin, run the two commented
   statements at the bottom of `db/demo_seed.sql` (the `ALTER TYPE … ADD VALUE`
   must run on its own, outside a transaction).

### Verify
```bash
curl https://dts-brown.vercel.app/api/stats      # → 200 with counts (not 404)
curl https://dts-brown.vercel.app/api/routes     # → 3 routes
curl https://dts-brown.vercel.app/api/vehicles   # → 4 vehicles (BUS-101 active)
curl -X POST https://dts-brown.vercel.app/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@damascus-transit.demo","password":"Damascus2026!"}'
# → 200 with access_token
```
All demo accounts use **`Damascus2026!`** (see `docs/DEMO_CREDENTIALS.md`).

---

## Defense-in-depth (already applied in this branch)

`api/core/tenancy.py :: _ensure_operator()` auto-creates the default operator
when it's missing. It previously used the **anon key**, which RLS blocks from
writing to `operators` — so the auto-seed silently failed and the 404
persisted. It now uses the **service-role key** (falling back to anon only when
no service key is configured) and upserts with `resolution=merge-duplicates`.

**Required env var for the safety net to work:** `SUPABASE_SERVICE_KEY` must be
set in the Vercel project. With it set, an anonymous hit to `/api/stats` will
self-heal the missing operator row (though routes/vehicles/positions still come
from `db/demo_seed.sql`).

---

## Prevent recurrence

- Add a post-deploy/CI check that fails if `GET /api/stats` returns 404 for the
  default operator (an unseeded-DB smoke test).
- Treat `db/demo_seed.sql` as the single source of truth for demo data; the
  older `db/demo_accounts.sql` is deprecated and now carries the same password.
- Confirm `SUPABASE_SERVICE_KEY` is present in every environment.
