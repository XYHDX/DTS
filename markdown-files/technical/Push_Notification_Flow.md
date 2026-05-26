# Push notification flow — end to end

> How a token gets from the driver's phone into our backend, and how a stop-proximity push gets back out. Updated 2026-05-24.

## High-level

```
┌─ Driver app (Flutter or Capacitor)
│   1. PushService.registerToken()  →  FCM SDK fetches token
│
└──HTTP POST /api/push/register  { token, platform }
                                          │
                                          ▼
                          ┌────────────────────────────────┐
                          │ FastAPI /api/push (router)     │
                          │  · validates JWT                │
                          │  · upserts user_devices(token) │
                          └──────────────┬─────────────────┘
                                          │
                                  ┌──────▼───────┐
                                  │  Supabase    │
                                  │ user_devices │
                                  └──────────────┘

Later, a backend job (stop proximity, schedule change, incident):

  /api/push/send  →  Firebase Admin SDK  →  FCM/APNs  →  device
```

## Tables

### `user_devices`

| Column | Type | Notes |
|---|---|---|
| `id` | uuid pk | generated |
| `user_id` | uuid fk users(id) | owner |
| `operator_id` | uuid fk operators(id) | tenant scoping |
| `token` | text | FCM registration token |
| `platform` | text | `'android' \| 'ios' \| 'web'` |
| `created_at` | timestamptz | `now()` |
| `updated_at` | timestamptz | bumped on token refresh |
| `last_seen_at` | timestamptz | updated on successful send |
| `is_active` | bool | flipped to false after 3 consecutive UNREGISTERED responses |

Index on `(operator_id, user_id)` for tenant lookups; partial index on `is_active = true` for the broadcast path.

A migration `008_user_devices.sql` is reserved for this — not in the repo yet. Add it before wiring `/api/push/send` for real.

## Token lifecycle

### Registration

The Flutter app calls `PushService.registerToken()` after a successful login (see `lib/features/push/push_service.dart`). The Capacitor wrapper calls the equivalent through `capacitor-bridge.js`. Both POST the same body to `/api/push/register`:

```json
{ "token": "fU8…", "platform": "android" }
```

The backend:

1. Verifies the JWT.
2. Upserts `user_devices` on `(user_id, token)`.
3. Returns 204.

### Token refresh

FCM rotates tokens silently. Both clients listen to `FirebaseMessaging.onTokenRefresh` and re-post the new token to `/api/push/register`. The backend treats this as a normal upsert.

### Unregister on logout

On explicit logout the client calls `/api/push/unregister` with the current token. The backend flips `is_active` to false; the row is kept for audit. After 30 days an inactive row is hard-deleted by a nightly job (`backup.yml` extension — TODO).

### Token death

FCM/APNs returns `UNREGISTERED` or `NotRegistered` when the user uninstalls the app. The send pipeline catches that and flips `is_active = false` on the third such response (one retry tolerates transient blips).

## Sending

### Backend trigger sources

| Source | Trigger | Audience |
|---|---|---|
| Stop-proximity worker | `/api/cron/proximity` (Vercel cron) | Passengers subscribed to a route |
| Schedule-change worker | Admin saves a schedule edit | Operator's passengers |
| Incident alert worker | Driver submits an incident or speed/route alert fires | Operator's drivers + dispatchers |
| Manual broadcast | Admin endpoint `/api/admin/push/broadcast` | Filter by operator + role |

### Payload

The backend builds a Firebase Admin payload:

```json
{
  "topic": "operator-<slug>",
  "notification": {
    "title": "🚌 الحافلة قادمة",
    "body": "حافلة R-12 تبعد دقيقتين عن ساحة الأمويين"
  },
  "data": {
    "kind": "proximity",
    "route_id": "R-12",
    "stop_id": "S-77",
    "deeplink": "damascustransit://routes/R-12"
  },
  "android": {
    "priority": "HIGH",
    "notification": { "channel_id": "proximity" }
  },
  "apns": {
    "headers": { "apns-priority": "10" },
    "payload": { "aps": { "interruption-level": "time-sensitive" } }
  }
}
```

The `data.deeplink` field is consumed by `lib/core/router.dart` (Flutter) and `capacitor-bridge.js` (Capacitor) to navigate after the user taps.

### Rate limiting

`/api/push/register` and `/api/push/send` are rate-limited (see `api/core/cache.py`, constants `RATE_LIMIT_PUSH_SUB` and `RATE_LIMIT_WRITE`). Broadcasts are sharded into batches of 500 with 1-second delays so we never push more than 500 messages per second per operator.

## Channels (Android)

| Channel | Importance | Use |
|---|---|---|
| `proximity` | HIGH (heads-up) | Bus arriving / approaching |
| `schedule` | DEFAULT | Today's schedule changed |
| `incident` | HIGH | SOS / accident from a driver |
| `marketing` | LOW | Optional, opt-in only |

The channels are created on first run of the app (`channel_id` references). Users can disable any channel from system settings — the backend respects that by retrying delivery only once before giving up.

## iOS specifics

- `interruption-level: time-sensitive` is reserved for proximity and incident. Schedule changes use `active`.
- `mutable-content: 1` is set so the iOS notification service extension can localise on the device.
- APNs sandbox vs production keys are env-var gated (`APNS_ENV=production`).

## Observability

- Every send is logged with `request_id`, FCM message_id, target user_id, and outcome (sent / unregistered / rate_limited / error).
- A daily Sentry breadcrumb summary aggregates failures by reason.
- The Grafana dashboard (TBD) charts: sends per minute per operator, success-rate by platform, time-to-deliver p50/p95.

## Testing locally

```bash
# 1. Get a token from the Flutter app debug console — it's printed on boot
#    when SENTRY_DSN is empty.
export FCM_TOKEN="fU8…"

# 2. POST to the backend
curl -X POST http://localhost:8000/api/push/register \
     -H "Authorization: Bearer $JWT" \
     -H "Content-Type: application/json" \
     -d "{\"token\":\"$FCM_TOKEN\",\"platform\":\"android\"}"

# 3. Send to yourself via the admin endpoint
curl -X POST http://localhost:8000/api/admin/push/broadcast \
     -H "Authorization: Bearer $JWT" \
     -H "Content-Type: application/json" \
     -d '{"target":{"user_ids":["<your-uuid>"]},"title":"تجربة","body":"رسالة تجريبية"}'
```

The notification should arrive on your dev device within 2–3 seconds for Android, slightly longer on iOS through the APNs sandbox.

## Threat model + privacy

- We **do not** ship the user's name or any PII in `notification.body`. Stops and routes are referenced by code only.
- Tokens are hashed (`sha256`) before being indexed for analytics; the raw token never leaves the database.
- Marketing pushes are opt-in. Default `is_subscribed_marketing = false`.
- For drivers, the proximity channel is forced on — disabling it would break the trip flow — and this is disclosed in onboarding.
