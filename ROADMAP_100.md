# DamascusTransit — 100-Step Revival Roadmap

> Authored 24 May 2026. Each step is concrete and verifiable. Mark `[x]` when done with a one-line evidence note.
> Items marked **(user)** require human action (signing, store submission, hardware) and cannot be done from this environment.

---

## Phase A — Project hygiene (1–10)

- [x] **1.** Stage `main` snapshot into workspace as the working copy — `source/` populated.
- [x] **2.** Document branch-of-truth decision (main beats feat-dashboard-deploy) — captured in `Revival_Analysis_2026-05-24.docx`.
- [x] **3.** Apply H1 trusted-proxy fix in `api/core/cache.py` — verified already present.
- [x] **4.** Apply H2 rate-limiter fail-closed in `api/core/cache.py` — verified already present.
- [x] **5.** Add `iat` to JWTs + revocation helper for M1 — done in `api/core/auth.py`.
- [x] **6.** Unified CSS design system at `public/lib/design-system.css` — refreshed with Claude design language: warm cream surface, coral accent, serif display for Latin headings, generous whitespace, calm density. Flutter `theme.dart` mirrors the same tokens.
- [x] **7.** Redesign public landing `public/index.html`.
- [x] **8.** Redesign passenger PWA `public/passenger/index.html`.
- [x] **9.** Redesign driver PWA `public/driver/index.html`.
- [x] **10.** Redesign admin login `public/admin/login.html` — done with role pills + show/hide password.

## Phase B — Admin & ops UI (11–20)

- [x] **11.** Redesign admin dashboard `public/admin/index.html` — sidebar nav, KPI tiles, alerts panel, live map.
- [x] **12.** Redesign analytics page `public/dashboard/analytics.html` — SVG bars + donut + route table + filter pills.
- [x] **13.** Add SQL migration `007_password_changed_at.sql` for M1 revocation — column + trigger landed.
- [x] **14.** `get_current_user` now consults `_lookup_password_changed_at` with a 5-sec TTL cache and rejects revoked tokens with 401.
- [x] **15.** `ensure_operator_scope()` helper landed in `api/core/tenancy.py`; super_admin bypass + 400/403 distinctions.
- [x] **16.** Tighten CSP header in `api/index.py` — HSTS + X-Frame-Options + Permissions-Policy + HTML-only CSP allowlist.
- [x] **17.** Add `/api/health/deep` — DB/Redis/position-freshness probe, returns 503 if any fail.
- [x] **18.** Verified — `_request_logging_middleware` in `api/index.py` emits a structured log line per request (request_id + method + path + status + duration_ms) and adds `X-Request-Id` to every response.
- [x] **19.** `rate_limit(bucket, max, window)` FastAPI dependency added to `api/core/cache.py` — IP-keyed sliding window, 429 with `Retry-After` on overflow, drop-in usage via `dependencies=[Depends(rate_limit(…))]`.
- [x] **20.** Verified — 17 OpenAPI tag entries with descriptions live in `api/index.py` `_OPENAPI_TAGS` (health, auth, routes, stops, vehicles, stream, websocket, stats, schedules, alerts, driver, admin, traccar, gtfs, operators, push, cron).

## Phase C — Flutter app expansion (21–40)

- [x] **21.** Drift schema landed: `CachedRoutes`, `CachedStops`, `CachedPositions` in `lib/core/offline/database.dart`. Generated file needs `dart run build_runner build`.
- [x] **22.** `OfflineRouteRepository` — API-first with Drift fallback; warms cache on every successful API call. Drop-in providers `offlineRoutesListProvider` and `offlineStopsProvider`.
- [x] **23.** `SyncController` landed: `syncAll`, `syncRoutes`, `rememberPositions` with capped fan-out (12 routes) and soft-fail.
- [x] **24.** `NearestStopsScreen` — Claude-styled list, serif distance anchor, ETA pill, RefreshIndicator, skeleton + error + empty states.
- [x] **25.** `ScheduleScreen` — Claude-styled departure board with serif "next departure" callout, relative time, soft "now" indicator, hairline list of upcoming departures.
- [x] **26.** `AccountScreen` — Claude-styled identity block, role chips, spec list, sign-out.
- [x] **27.** `SettingsScreen` — Claude-styled with quiet sections, ChoiceChip radio rows, SharedPreferences persistence.
- [x] **28.** ARB files landed: `lib/l10n/app_en.arb` + `app_ar.arb` + `l10n.yaml` for `flutter gen-l10n`.
- [x] **29.** `PushService` in `lib/features/push/push_service.dart`; auto-paired on login + token-refresh listener.
- [x] **30.** Deep-link handling — `damascustransit://` custom scheme + Android App Links + iOS associated-domains landed in manifest + Info.plist.
- [x] **31.** `ErrorBoundary` widget hooks `FlutterError.onError`; Claude-styled fallback with retry; debug-mode rethrows for stack visibility, release shows polite UI.
- [x] **32.** `BackgroundGps` façade landed (`flutter_app/lib/features/driver/background_gps.dart`) — `flutter_background_geolocation` (transistorsoft) in `pubspec.yaml`, idempotent configure, ready/start/stop API, foreground-service notification copy.
- [x] **33.** Capped exponential backoff with ±20 % jitter in `vehicle_stream.dart` (1 s → 30 s; resets on first good frame).
- [x] **34.** Two-layer polyline polish in `route_detail_screen.dart` — cream halo (10 px) + coral spine (5 px) so the route reads clearly even on light raster tiles.
- [x] **35.** Reusable `EtaCard` widget + `EmptyState` widget — Claude-styled, serif numeric anchor, route chip, "now"-state variant, friendly empty illustrations.
- [x] **36.** `IncidentReportScreen` — three-step Claude-styled flow (kind → note → confirm) with progress dots, ChoiceChips, summary spec list, GPS auto-attach, soft-fail submission.
- [x] **37.** `ShiftSummaryScreen` — Claude-styled with serif passenger-count display, spec rows for distance/duration/peak/on-time/incidents, reflective copy that adapts to outcome.
- [x] **38.** `sentry_flutter` wired in `main.dart`; activates only when `--dart-define=SENTRY_DSN=…` is set; release + env tagged.
- [x] **39.** Unit tests landed: `test/auth_controller_test.dart`, `test/route_repository_test.dart`, plus Python `tests/test_jwt_revocation.py`.
- [x] **40.** Widget tests landed for `EmptyState` (3 cases) and `EtaCard` (3 cases) in `test/empty_state_widget_test.dart`.

## Phase D — CI & quality gates (41–55)

- [x] **41.** Add GitHub Actions job: `flutter-analyze` + `flutter-test` + debug APK upload — `.github/workflows/flutter.yml`.
- [ ] **42.** Add GitHub Actions job: build debug Android APK on every PR.
- [x] **43.** `flutter.yml` gained Gradle + Android-SDK caches keyed on `build.gradle*` hash; pub already cached via `subosito/flutter-action`.
- [x] **44.** Add Dependabot config — `.github/dependabot.yml` covers pip, pub, npm (Capacitor), and GitHub Actions.
- [x] **45.** `.pre-commit-config.yaml` — ruff, bandit, prettier, gitleaks, dart-format, flutter-analyze, conventional-pre-commit (commit-msg).
- [x] **46.** `tests/passenger_flow.spec.js` — RTL assertion, hero copy, stats grid, map presence, lang toggle, axe-core a11y scan.
- [x] **47.** `tests/driver_flow.spec.js` — login pane, failing-login error visibility, GPS pill + vehicle badge presence, axe-core scan.
- [x] **48.** `tests/load_sse.js` — k6 with three profiles (smoke/soak/spike), counts `event: vehicles` frames, asserts connect rate ≥97% and median ≥1 event/sec.
- [x] **49.** `security-scan.yml` extended — `npm-audit` job for `mobile/` + `flutter-deps` job for pub outdated; existing `pip-audit` retained.
- [x] **50.** `.github/workflows/lighthouse.yml` — audits /, /passenger/, /driver/, /admin/login.html; a11y ≥0.9 (fail), perf ≥0.85 (warn).
- [x] **51.** axe-core wired into both Playwright specs — asserts zero critical/serious WCAG 2 A + AA violations on the landing, passenger, and driver pages.
- [x] **52.** `openapi-lint.yml` — Spectral 6.x with custom ruleset; fails on missing tags/operations + error-severity drift.
- [x] **53.** Conventional Commits enforced in CI via `.github/workflows/commit-style.yml` (PR title + every commit through commitlint) **and** locally via the existing pre-commit hook. `.commitlintrc.json` shares the same type list.
- [x] **54.** `release-please.yml` workflow + `.github/release-please-config.json` + manifest — sectioned changelog (Features / Bug Fixes / Security / Performance / Dependencies).
- [x] **55.** `codeql.yml` workflow — Python + JS/TS matrix, security-extended + security-and-quality queries, weekly cron.

## Phase E — Documentation (56–70)

- [x] **56.** New `README.md` reflecting the post-revival architecture — Status table, dual-mobile section, security posture.
- [x] **57.** ADR-001: Capacitor v1.0, Flutter v2.0 — landed at `markdown-files/adr/ADR-001-mobile-shell.md` with explicit trigger metrics.
- [x] **58.** ADR-002 written — but re-scoped from PostGIS to SSE-vs-WebSocket (PostGIS deferred to ADR-004). See `markdown-files/adr/ADR-002-sse-vs-websocket.md`.
- [x] **59.** ADR-003 written — rate-limiter fail-closed semantics; `markdown-files/adr/ADR-003-rate-limit-fail-closed.md`.
- [x] **60.** Runbook for hotfix deploy: pre-flight → patch → deploy → verify → post-incident. `Runbook_Hotfix_Deploy.md`.
- [x] **61.** Runbook for JWT rotation: dual-secret overlap window + 24 h wait + backout. `Runbook_JWT_Rotation.md`.
- [x] **62.** `Runbook_DB_Backup_Restore.md` — pg_dump custom format, restore drill with §0–§5 phases, RPO 24h / RTO 60min targets, quarterly drill template.
- [x] **63.** `docs/DEPLOY.md` rewritten — two topologies (Vercel free, Docker ministry), full env-var table with `TRUSTED_PROXY_IPS` / `TURNSTILE_SECRET` / `JWT_SECRET_PREVIOUS`, eight-workflow CI checklist, what-changed-in-this-revision section.
- [x] **64.** `DOCKER_MINISTRY_docs/DEPLOY.md` rewritten — hardware baseline table, three deploy tiers, full env-var table including `TRUSTED_PROXY_IPS`, sanity-check curls, air-gapped notes, cost rough-cut.
- [x] **65.** `docs/DEMO_ACCOUNTS.md` rewritten — 5 demo users, password `demo1234`, seeding instructions, reset SQL, M1 testing notes.
- [x] **66.** SSE contract documented: heartbeat, event types (vehicles/alerts/incidents), payload schemas, reconnect rules — `markdown-files/technical/SSE_Contract.md`.
- [x] **67.** Flutter architecture documented: layering, state model, build flags, offline plan — `flutter_app/ARCHITECTURE.md`.
- [x] **68.** `Push_Notification_Flow.md` — token lifecycle, send pipeline, Android channels, iOS specifics, observability, threat model.
- [x] **69.** `Runbook_Incident_Response.md` — SEV-1/2/3 classification, IC/Operator/Communicator roles, 10-min stabilise target, blameless postmortem template.
- [x] **70.** `CONTRIBUTING.md` rewritten — first-time setup, Conventional Commits, the eight CI workflows, language-specific style rules, reviewer expectations, security disclosure.

## Phase F — Infrastructure & DevOps (71–85)

- [x] **71.** `requirements.txt` bumped — fastapi ≥0.136, pydantic ≥2.13, sentry-sdk ≥2.58, upstash-redis ≥1.7, pywebpush ≥2.3. Majors (bcrypt 5, gtfs-realtime 2) deferred.
- [x] **72.** Pin Python version in `Dockerfile.prod` to 3.12-slim — verified: both builder + runtime stages use `python:3.12-slim-bookworm` (landed with step 73). _(2026-06-02)_
- [x] **73.** `Dockerfile.prod` rewritten — Python 3.12-slim multi-stage, tini PID 1, non-root UID 10001, /api/health/deep healthcheck, --worker-tmp-dir=/dev/shm.
- [x] **74.** `docker-compose.prod.yml` hardened — /api/health/deep healthcheck on API, /healthz on nginx, read_only fs + tmpfs for /tmp + /dev/shm, no-new-privileges security_opt, memory reservations.
- [x] **75.** `scripts/wait_for_db.sh` — portable bash, parses Postgres URL, two-phase probe (TCP + trivial psql query if available), configurable `TIMEOUT` + `INTERVAL`.
- [x] **76.** `scripts/seed_demo_data.py` — idempotent, refuses production-named projects without --force, upserts 1 operator + 5 users + N routes + M stops + vehicles via PostgREST.
- [x] **77.** `scripts/gtfs_export.sh` — pulls `/api/gtfs`, sanity-checks size, uploads daily archive + rolling `latest.zip` + appends to a `checksums.sha256` log in Supabase Storage.
- [x] **78.** `nginx/nginx.conf` rewritten — HTTP/3 via QUIC + Alt-Svc advertisement, brotli + gzip, per-route rate-limit zones, structured JSON access log, immutable cache for static assets, SSE-friendly `proxy_buffering off` on /api/.
- [x] **79.** `vercel.json` headers — HSTS preload, X-Frame-Options DENY, COOP same-origin, CORP same-site, consolidated CSP for /dashboard|admin|driver|passenger, edge-cache rules for static assets, no-store for /api/*.
- [x] **80.** Add `Sentry.init` to FastAPI startup with release env var — `api/index.py` initialises Sentry when `SENTRY_DSN` is set, with `release` from `APP_RELEASE` (default `damascustransit@1.0.0`) and `environment` from `VERCEL_ENV`. _(2026-06-02)_
- [x] **81.** `api/core/queue.py` — Upstash QStash wrapper with `enqueue()` (delayed publish + dedup id) and `schedule_cron()` (recurring jobs); soft no-op when `QSTASH_TOKEN` unset.
- [x] **82.** `vercel.json` gained a `/tiles/(.*)` rule — `max-age=604800` + `stale-while-revalidate=86400` + `immutable` + `Access-Control-Allow-Origin: *` + `Cross-Origin-Resource-Policy: cross-origin`.
- [x] **83.** `Postgres_Pooling.md` — Supavisor transaction-mode recipe, httpx Limits config, server-side `statement_timeout` + `idle_in_transaction_session_timeout`, required indexes including PostGIS GiST, capacity-headroom table.
- [x] **84.** `verify-backup` job added to `backup.yml` — pulls live row counts, diffs against the previous baseline, fails CI if any table drops more than 20%. New baseline uploaded as a 30-day artifact.
- [x] **85.** Cloudflare Turnstile wired — `api/core/turnstile.py` verifies via siteverify endpoint, soft-fails open if CF unreachable; admin login HTML loads the widget when `window.TURNSTILE_SITE_KEY` is set.

## Phase G — Release prep (86–95)

- [ ] **86.** **(user)** Create Firebase project; download `google-services.json` + `GoogleService-Info.plist`.
- [ ] **87.** **(user)** Generate Android signing keystore; store in 1Password or HCV.
- [x] **88.** `mobile/android/app/build.gradle.snippet` documents the env-var-driven `signingConfigs.release` block + graceful fallback to debug signing when keystore env vars are missing.
- [ ] **89.** **(user)** Enrol in Apple Developer Program (or partner via MENA entity).
- [ ] **90.** **(user)** Enrol in Google Play Console.
- [x] **91.** Play Store assets drafted as SVG in `mobile/store-assets/` — `feature-graphic.svg` (1024×500) + three 1080×2400 screenshot mockups (live map, driver summary, onboarding). Rendered to PNG via LibreOffice for preview; production render via Inkscape recommended.
- [x] **92.** Same SVG mockups serve App Store at 6.5"/6.7" — the 1080×2400 source canvas is the iPhone 14 Pro Max display.
- [x] **93.** `PLAY_STORE_LISTING.md` refreshed — Claude UI mention, what's-new for v1.0.0, screenshot order, feature graphic spec, privacy section, release-channel cadence.
- [ ] **94.** Internal-test rollout via Play Console internal track (Capacitor build).
- [ ] **95.** TestFlight rollout (Capacitor build) once Apple membership is active.

## Phase H — Launch + sustain (96–100)

- [x] **96.** `Launch_Announcement.md` — blog (AR + EN), Twitter thread, LinkedIn post, WhatsApp broadcast, press FAQ.
- [x] **97.** `ISSUE_TEMPLATE/good-first-issue.md` + `.github/labels.yml` — 25-label taxonomy across kind/area/priority/status + contributor signals; sync via `github-label-sync`.
- [x] **98.** `sentry-digest.yml` workflow — weekly Mon 06:00 UTC pulls top 10 unresolved issues; posts to Slack and emails via Resend; uploads digest as 30-day artifact.
- [x] **99.** `regression-report.yml` workflow — monthly 1st 08:00 UTC runs Lighthouse + Playwright (with axe-core) + k6 smoke and opens / updates a tracking issue with the combined report.
- [x] **100.** `Flutter_V2_Migration_Plan.md` — opens-when triggers from ADR-001, parity + build + verification + store-transition checklists, ~9-week effort estimate, `gh api` command to materialise the GitHub milestone.

---

## Out-of-band additions

These were added during the work but did not have a slot in the original 100:

- [x] **N1.** Onboarding screen — 3 calm intro slides with inline-painted Claude illustrations, `SharedPreferences` "seen" flag, skip button always visible.
- [x] **N2.** Alerts inbox screen — Claude-styled service-alert list with severity-tinted chips, friendly empty + offline states.
- [x] **N3.** Deep-link verification assets — `public/.well-known/assetlinks.json` (Android App Links) + `apple-app-site-association` (iOS Universal Links). Replace the placeholder fingerprints with real keystore SHA + Apple Team ID before going live.
- [x] **N4.** Migration `008_user_devices.sql` — table + indexes + auto-touch trigger + RLS policies for the push-notification flow documented in `Push_Notification_Flow.md`.
- [x] **N5.** Flutter integration test stub — `integration_test/passenger_smoke_test.dart` covers onboarding render + advance + skip-persists-flag against a `SharedPreferences` mock.

## Progress log

| Date | Step(s) | Notes |
|---|---|---|
| 2026-05-24 | 1–9 | Project hygiene + design system + 3 web pages redesigned + JWT iat. |
| 2026-05-24 | 10–13, 16–17, 41, 44, 56–57, 71 | Admin login + admin dashboard + analytics + SQL migration 007 + security headers + /api/health/deep + Flutter CI + Dependabot + new README + ADR-001 + requirements bump. |
| 2026-05-24 | 14–15, 28–29, 33, 38–39, 58–59, 66–67 | JWT-revocation lookup wired; operator-scope guard; AR/EN ARB localisation; FCM token registration; SSE backoff with jitter; Sentry in Flutter; auth + route-repo + JWT-revocation tests; ADR-002 (SSE), ADR-003 (rate-limit); SSE contract doc; Flutter ARCHITECTURE.md. |
| 2026-05-24 | 6 (revised), 21, 23, 24, 26, 27, 37, 60–61, 73, 79 | Claude design refresh applied to CSS + Flutter theme; Drift database + SyncController; NearestStops/Account/Settings/ShiftSummary screens (all Claude-styled); hotfix + JWT rotation runbooks; multi-stage Dockerfile; vercel.json security headers + caching. |
| 2026-05-24 | 22, 25, 31, 36, 45, 49–50, 52, 62, 70, 74, 76 | OfflineRouteRepository (API→Drift fallback); ScheduleScreen + ErrorBoundary + IncidentReportScreen (Claude-styled); pre-commit-config.yaml; security-scan extended with npm audit + flutter pub outdated; Lighthouse CI; Spectral OpenAPI lint; DB backup/restore runbook; CONTRIBUTING.md rewrite; docker-compose hardened; idempotent seed script. |
| 2026-05-24 | 35, 40, 54–55, 65, 68–69, 78, 85, 93, N1–N2 | EtaCard + EmptyState widgets (Claude design); widget tests; release-please workflow + config; CodeQL workflow; DEMO_ACCOUNTS rewrite; Push_Notification_Flow.md; Runbook_Incident_Response.md; nginx HTTP/3+brotli; Cloudflare Turnstile (server + client); Play Store listing refresh; onboarding screen; alerts inbox screen. |
| 2026-05-24 | 30, 32, 46–48, 51, 53, 63, 75, 77, 82, 84 | Deep-link manifest (Android App Links + iOS associated-domains); background_gps.dart façade over transistorsoft plugin; Playwright passenger + driver flows with axe-core a11y; k6 SSE load test (smoke/soak/spike); Conventional Commits enforced in CI (commitlint + PR-title check); docs/DEPLOY.md rewrite; wait_for_db.sh; gtfs_export.sh; CDN tile cache headers; backup-row-count verifier. |
| 2026-05-24 | 19, 43, 64, 81, 83, 88, 96–100 | rate_limit() dependency; gradle + Android-SDK caches in CI; DOCKER_MINISTRY_DEPLOY rewrite; QStash wrapper; Postgres pooling guide; Android env-var signing snippet; AR+EN launch announcement; good-first-issue template + 25-label taxonomy; weekly Sentry digest; monthly regression report; Flutter v2.0 migration plan. |
| 2026-05-24 | 18, 20, 34, 91, 92, N3–N5 | Verified existing logging + OpenAPI tag work; two-layer polyline polish; SVG store assets (feature graphic + 3 phone screenshots); assetlinks.json + apple-app-site-association; migration 008_user_devices.sql; Flutter integration_test stub. |
| 2026-06-02 | 72, 80 | Verified Python 3.12-slim pin and Sentry release tag — both already satisfied in code; marked done. Scale-track work this session is logged in `Scale_100k_Roadmap.md` (S2.2, S7.2). |
| (remaining) | 42 (overlap), 86–87, 89–90, 94–95 | Firebase project creation + Apple Developer + Google Play Console enrolment (**USER actions, not codeable from here**); internal-test rollout + TestFlight rollout. **All codeable ROADMAP_100 items are now complete.** |
