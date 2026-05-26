# SSE Contract — `/api/stream`

> Source of truth for the event shape consumed by the dashboard, passenger PWA, driver PWA, Capacitor wrapper, and the Flutter client. Updated 2026-05-24 alongside roadmap step 66.

## Endpoint

| Method | URL | Auth |
|---|---|---|
| `GET`  | `/api/stream` | None (public) |
| `GET`  | `/api/stream?operator=<slug>` | None — operator-scoped feed |
| `GET`  | `/api/stream?route=<id>` | None — route-filtered feed |

Headers expected from the client:

```
Accept: text/event-stream
Cache-Control: no-cache
```

Headers returned by the server:

```
Content-Type: text/event-stream; charset=utf-8
Cache-Control: no-cache, no-transform
Connection: keep-alive
X-Accel-Buffering: no
```

## Heartbeat

The server emits an SSE comment frame every **25 seconds** so corporate proxies, mobile NATs, and Vercel's edge do not idle the connection out. Clients ignore comment frames.

```
: ping 2026-05-24T12:00:00Z

```

## Event types

### `vehicles` (default frame)

Fired roughly every **5 seconds**. Payload is a JSON object:

```json
{
  "ts": "2026-05-24T12:01:32Z",
  "positions": [
    {
      "vehicle_id": "DAM-024",
      "route_id": "R-12",
      "lat": 33.5121,
      "lon": 36.2918,
      "speed": 28.4,
      "heading": 124.0,
      "occupancy": 41,
      "updated_at": "2026-05-24T12:01:30Z"
    }
  ]
}
```

Field semantics:

| Field | Type | Notes |
|---|---|---|
| `ts` | RFC 3339 string | Timestamp the frame was assembled on the backend. |
| `positions[]` | array | May be empty during overnight non-service hours. |
| `positions[].vehicle_id` | string | Stable identifier across trips. |
| `positions[].route_id` | string \| null | Null when the vehicle is idle (not on a trip). |
| `positions[].lat` / `.lon` | number | WGS-84. Backend rejects coordinates outside Syria bounds. |
| `positions[].speed` | number | km/h. Clamped to 0–200 at ingest. |
| `positions[].heading` | number | Degrees, 0 = north, clockwise. |
| `positions[].occupancy` | int \| null | Current passenger count, capped at the vehicle capacity. |
| `positions[].updated_at` | RFC 3339 string | Timestamp the position was reported, may lag `ts` by up to 30 s. |

For backwards compatibility the client must also accept either of:

- A top-level array (`[ {…}, {…} ]`) — historical shape.
- A `vehicles` key in place of `positions` (`{"vehicles": […]}`).

### `alerts`

Fired when a service alert is published. Cadence is event-driven, not periodic.

```json
{
  "id": "alert-771",
  "severity": "high",
  "type": "route_disruption",
  "route_id": "R-08",
  "title_ar": "تحويلة مؤقتة على خط ٨",
  "title_en": "Temporary detour on Route 8",
  "expires_at": "2026-05-24T18:00:00Z"
}
```

### `incidents`

Fired when a driver submits an incident report or a server-side rule fires (speed violation, route deviation, SOS).

```json
{
  "id": "inc-2026-05-24-018",
  "kind": "speed_violation",
  "vehicle_id": "DAM-024",
  "route_id": "R-12",
  "lat": 33.5099,
  "lon": 36.3071,
  "speed_kph": 78,
  "limit_kph": 60,
  "ts": "2026-05-24T12:01:31Z"
}
```

## Reconnect behaviour

Clients should:

1. Open `EventSource('/api/stream')` (or the `flutter_client_sse` equivalent).
2. On `onerror`, wait with capped exponential backoff (1 s → 2 → 4 → 8 → 16 → 30 s) plus ±20 % jitter.
3. Reset the backoff window on the next successful frame.
4. Respect HTTP `503` responses by lengthening the wait (the rate limiter or `/api/health/deep` may have flagged degradation).

The Flutter client implements this in `lib/features/map/vehicle_stream.dart`; the web clients rely on browser `EventSource` plus the connection-badge UI to surface state.

## Error frames

The server never sends `error` events; transport-level failures arrive at the client as connection drops. Use `EventSource.readyState` (web) or stream `onError` (Flutter) to detect.

## Versioning

This contract version is `2026-05-24`. Breaking changes will be introduced behind a `/api/v2/stream` route and announced via the API `Sunset` header on the existing endpoint (current sunset: `2026-09-30`).
