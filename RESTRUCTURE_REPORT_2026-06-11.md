# Restructure Report — 2026-06-11

Full review + restructure of the Damascus Transit System: verification of the
previous session's work, security hardening, the new admin approval workflow,
the Sham Cash payment scaffold, navigation cleanup, and repository consolidation.
Test suite: **~360 tests passing, 0 failing** (34 of them new).

---

## 1) What I fixed

### Security vulnerabilities (10)

| # | Severity | Issue | Fix |
|---|---|---|---|
| 1 | HIGH | `/api/test` was a live, unauthenticated endpoint leaking config state + stack traces | Deleted `api/test.py` and its `vercel.json` build/route |
| 2 | HIGH | Cron secret compared with `!=` — a timing oracle could recover it byte-by-byte | `hmac.compare_digest` (`api/routers/cron.py`) |
| 3 | HIGH | Cross-tenant data leak: anonymous reads with no `?operator=` returned **every** operator's data (vehicles, alerts, stats, routes, stops, schedules, stream — 12 endpoints) | New `resolve_read_scope()` — every public read is always scoped to exactly one operator, cached to cost no extra DB round-trip (`api/core/tenancy.py`) |
| 4 | HIGH | `/api/ws/track` WebSocket was unauthenticated **and** unscoped — broadcast all operators' live fleets to anyone | Connections now carry an operator scope; broadcasts filtered per tenant (`api/routers/websocket.py`) |
| 5 | HIGH | Cross-tenant **writes**: admin mutations patched rows by bare UUID (`vehicles?id=eq.X`) — an admin of operator A could modify operator B's vehicles/users/alerts | `_own_op_filter()` appended to every mutation (`api/routers/admin.py`) |
| 6 | HIGH | Deactivated accounts could still **log in**, and disabling a user left their token valid for 24h | Login checks `is_active`; token verification now revokes inactive users within 5 seconds (`api/routers/auth.py`, `api/core/auth.py`) |
| 7 | MED | Password reset/change relied on a DB trigger to revoke old tokens — fail-open on fresh databases | App now writes `password_changed_at` explicitly as well; `schema.sql` consolidated |
| 8 | MED | Cloudflare Turnstile captcha was dead code — never called at login | Wired into `/api/auth/login` (active when `TURNSTILE_SECRET` is set) |
| 9 | MED | Push broadcast ignored tenancy (admin of A pushed to B's subscribers) | Subscriptions tagged with operator; broadcast filtered (`api/routers/push.py`) |
| 10 | LOW | Traccar webhook returned raw exception text to callers | Generic error responses; details only in logs |

Also: demo-credential rotation (migration `011`) and ops hardening (`017`) were stranded
in the unused `source/` tree — they are now in the live migration chain.

### Frontend XSS (5 sinks)

All API-fed `innerHTML` sinks now escape data: homepage route cards, passenger
nearest-stops + routes, admin alerts feed, analytics route table. The CSP in
`vercel.json` was extended from 4 path prefixes to **every page**, and allows the
Turnstile + map-tile origins it was silently missing.

### Broken / illogical functions (7)

| Issue | Fix |
|---|---|
| Telemetry persist imported `_service_post` — **which did not exist**: every MQTT/protobuf frame crashed on save | Implemented `_service_post` + `_service_patch` (`api/core/database.py`) |
| Admin vehicles list inner-joined GPS positions — **newly registered vehicles were invisible** (fatal for an approval queue) | Reads the vehicles table and merges positions on top |
| Driver console sent `lat/lon/speed` but the API requires `latitude/longitude/speed_kmh` — **every position report failed validation** | Payload fixed (`public/driver/index.html`) |
| Driver trip-start sent an empty body but `route_id` is required — **trips were never recorded server-side** (silent local fallback) | Sends the assigned route; clear Arabic error when none assigned |
| `/api/driver/incident` was called by both apps but **never existed** | Implemented — incidents create critical alerts visible on the admin dashboard |
| Dashboard KPIs read `trips_today`/`open_alerts` that the API never returned (showed "—" forever) + hardcoded fake deltas ("+٢ منذ الأمس") | Overview endpoint now returns real values; fake deltas removed |
| Analytics page showed `Math.random()` numbers to **anonymous visitors** | Auth-gated; real route-performance data; honest empty states |

Password-reset emails also pointed to `/reset-password` — a page that never existed;
they now point to the real `/admin/reset.html`, which handles all three flows
(request link / consume token / forced first-login rotation).

---

## 2) What I linked correctly (simplest user experience)

**Before:** the admin sidebar had 4 dead links (vehicles/users/routes/alerts pages
didn't exist), "forgot password" led to a 404, the privacy link was dead, every page
carried its own copy-pasted nav, and the role shown was cosmetic.

**Now — one shared shell (`/admin/_shell.js`) renders the same role-aware sidebar on
all 9 admin pages**, so a link can never go somewhere that doesn't exist:

```
Overview → Approvals* → Vehicles → Users → Routes → Alerts → Payments → Audit* → Analytics → Help
                                                            (* admin-only — operators never see them)
```

* **The approval flow is one straight line:** operator opens *Users* → creates the
  driver (email + password, forced rotation on first login) and links a vehicle in
  the same form → *Vehicles* shows the approval badge → the admin sees a live
  **pending-count badge** in the sidebar + a quick-access card on Overview →
  *Approvals* page: Approve / Reject (with reason) / Suspend / Resubmit → the driver
  console instantly reflects the result (a clear "awaiting approval" banner blocks
  trip start until approved).
* Login now fetches the real profile, so the sidebar greets the actual person and
  role; dispatchers landing on admin-only URLs are bounced politely.
* Driver console shows the vehicle code, route name, route fare, and the Sham Cash
  QR automatically once approved.
* Dead ends removed: `reset.html`, `privacy.html`, `/help/` now exist and are
  linked; the orphaned `/demo/` is reachable from the homepage footer; the 404 page
  no longer carries the old "SyriaTransit" branding.

---

## 3) How much data and space I saved

| What | Before | After |
|---|---|---|
| Working tree (code you actually maintain) | **~34 MB** | **7.8 MB** (−77%) |
| Duplicate code trees | 3 full copies (root, `source/` 14 MB, `dts-push/` 8.1 MB) | **1 canonical tree** |
| Loose snapshot files | `dts-repo.bundle` 2.7 MB + `dts-repo-files.tar.gz` 1.1 MB | folded into the archive |
| Caches/junk (`__pycache__`, `.DS_Store`, stray files) | 14 items | 0 |

Everything legacy went into **one** verified zip: `archives/legacy-snapshots-2026-06-11.zip`
(23 MB, integrity-tested, git-ignored). Move it off the repo (external disk / cloud)
and the project folder is the 7.8 MB working tree + git history.
Before archiving I verified the old git bundle contains history **not** present in
`.git` — that's why it was preserved rather than deleted.

Runtime savings too: anonymous API reads no longer trigger a per-request operator
lookup (5-minute cache), and telemetry approval checks are cached 60 s so the
100k-vehicle hot path pays ~1 extra query per vehicle per minute, not per ping.

---

## 4) What needs YOUR intervention (I cannot do these)

1. **Run migrations `010` → `020` on Supabase before deploying this code** —
   order matters; the API now references `approval_status` and `payments`.
   `docs/APPLY_MIGRATIONS.md` has the walkthrough. (`019` grandfathers your existing
   vehicles as approved — no service interruption.)
2. **Sham Cash merchant onboarding** — sign the merchant agreement and obtain
   `SHAM_CASH_MERCHANT_ID`, `SHAM_CASH_API_SECRET`, `SHAM_CASH_WEBHOOK_SECRET`,
   then set `SHAM_CASH_MODE=live` + a dedicated `QR_SIGNING_SECRET`. Until then the
   system runs in sandbox (full flow, no real money). Also confirm their actual
   deep-link/callback formats — I scaffolded to standard wallet patterns.
3. **Set new env vars in Vercel:** `DEFAULT_OPERATOR_SLUG=damascus` (+ the Sham
   Cash vars when ready; `TURNSTILE_SECRET`/`TURNSTILE_SITE_KEY` if you want the
   login captcha).
4. **Rotate the demo passwords** (migration `011` does it — but verify
   `admin@damascus-transit.demo` etc. no longer accept `damascus2025`).
5. **Apple/Google accounts** (roadmap #86–95): Firebase project, Android keystore,
   Apple Developer Program, Play Console — store rollout is paperwork only you can do.
6. **Decide the mobile track**: ship Capacitor as v1 (wraps the now-fixed PWA) and
   keep Flutter for v2 — both still live in the repo; maintaining both forever
   doubles your work. The Flutter app also needs its driver screens pointed at the
   new `/api/driver/me` bootstrap when you pick it up.
7. **Move `archives/legacy-snapshots-2026-06-11.zip` off the repo** when convenient.
8. **Email sending** (`RESEND_API_KEY`) if you want password-reset/welcome emails
   delivered rather than logged.

---

## 5) Documentation

* **`docs/ARCHITECTURE_DECISIONS.md`** — the "why" for every important choice:
  why Python/FastAPI, why Supabase/PostGIS, why TimescaleDB, why MQTT + Protobuf
  for your hardware, **why Grafana/Prometheus**, why SSE for live maps, the role
  model, the approval state machine, the Sham Cash security design, why plain
  HTML/RTL frontends, Vercel vs ministry Docker, and the repo layout.
* `PROJECT_STATUS.md` — updated with this restructure.
* `db/migrations/019_vehicle_approval.sql` / `020_payments_sham_cash.sql` — heavily
  commented, with rollback notes.
* `.env.example` — every new variable documented inline.
* Code comments at every fix site explain *what was wrong and why the fix is shaped
  that way* (search for "2026-06-11").

---

### Verification performed

Full pytest suite green (~360 tests, including 34 new ones covering the approval
state machine, dispatcher permission limits, operating-enforcement, QR forgery,
amount tampering, webhook HMAC + replay-idempotency, and sandbox gating). All 19
HTML pages parse clean. The FastAPI app boots with all 89 routes. The legacy zip
passed an integrity test before the originals were removed.
