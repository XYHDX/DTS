# Demo accounts — DamascusTransit

> Seeded by `scripts/seed_demo_data.py` against a Supabase project that has run migration `007_password_changed_at.sql`. **Never** seed these against production — the script refuses by default; you'd have to pass `--force`.

All demo accounts share the operator **damascus** (slug) and the same password.

| Email | Role | What they see |
|---|---|---|
| `demo-admin@example.com`      | `admin`      | Full admin panel — users, vehicles, routes, alerts, analytics |
| `demo-dispatcher@example.com` | `dispatcher` | Live map, alert resolution, trip history |
| `demo-driver1@example.com`    | `driver`     | Driver PWA / Flutter app — assigned to demo route R01 |
| `demo-driver2@example.com`    | `driver`     | Driver PWA / Flutter app — assigned to demo route R02 |
| `demo-viewer@example.com`     | `viewer`     | Read-only dashboards |

**Password:** `demo1234`

The bcrypt hash for this password is pinned in the seed script. If you rotate the password you must rebuild the hash and update `scripts/seed_demo_data.py`'s `DEMO_HASH` constant.

## Seeding

```bash
# Reads SUPABASE_URL + SUPABASE_SERVICE_KEY from your environment.
python scripts/seed_demo_data.py --operator damascus --routes 8 --stops-per-route 6
```

Idempotent — re-running is safe and updates rather than duplicates.

## Logging in

### Web

- Public dashboard: <http://localhost:8000/>
- Passenger PWA:    <http://localhost:8000/passenger/>
- Driver PWA:       <http://localhost:8000/driver/>  → log in with `demo-driver1@example.com`
- Admin panel:      <http://localhost:8000/admin/login.html>  → log in with `demo-admin@example.com`

### Flutter app

```bash
cd flutter_app
flutter run --dart-define=API_BASE=http://10.0.2.2:8000   # Android emulator
flutter run --dart-define=API_BASE=http://localhost:8000  # iOS simulator
```

Use any of the emails above. The onboarding screen appears once; after that the app remembers and skips it.

### Capacitor wrapper

```bash
cd mobile
npm install
npx cap sync android
cd android && ./gradlew installDebug
```

The wrapper reuses the existing `public/driver/` and `public/passenger/` codebase, so the same accounts work.

## What you'll see when seeded

| Surface | Count |
|---|---|
| Operators | 1 (damascus) |
| Users     | 5 |
| Routes    | 8 (`R01`–`R08`, radiating from Umayyad Square) |
| Stops     | 6 per route = 48 total |
| Vehicles  | 2 (`DEMO-001`, `DEMO-002`) |
| Trips     | 0 (created live by the driver app) |
| Alerts    | 0 (created when an incident is reported) |

## Resetting

To wipe all demo data without nuking the project:

```sql
-- Run in Supabase SQL editor. Only operates on the demo operator.
BEGIN;
WITH op AS (SELECT id FROM operators WHERE slug = 'damascus')
DELETE FROM vehicle_positions WHERE vehicle_id IN
  (SELECT id FROM vehicles WHERE operator_id IN (SELECT id FROM op));
DELETE FROM trips    WHERE operator_id IN (SELECT id FROM operators WHERE slug='damascus');
DELETE FROM vehicles WHERE operator_id IN (SELECT id FROM operators WHERE slug='damascus');
DELETE FROM stops    WHERE operator_id IN (SELECT id FROM operators WHERE slug='damascus');
DELETE FROM routes   WHERE operator_id IN (SELECT id FROM operators WHERE slug='damascus');
DELETE FROM users    WHERE email LIKE 'demo-%@example.com';
COMMIT;
```

Then re-run the seeder.

## Notes for contributors

- These accounts are **insecure by design**. The password is committed to the repo. Do not enable them on any host that's reachable from the public internet.
- For staging / production use real bcrypt passwords with at least 12 random characters per user.
- If you're testing JWT revocation (M1) the seed accounts have `password_changed_at = NOW()` from the trigger in migration 007. To simulate a leaked-token scenario, bump that column:
  ```sql
  UPDATE users SET password_changed_at = NOW() WHERE email = 'demo-driver1@example.com';
  ```
  All issued tokens for that user should immediately fail with 401.
