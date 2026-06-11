# ADR-002 — Real-time channel: Server-Sent Events over WebSocket

- **Status:** Accepted (ratifying the existing implementation)
- **Date:** 2026-05-24
- **Deciders:** 3dtitans, Claude (advisory)
- **Supersedes:** —

## Context

DamascusTransit pushes vehicle positions from the backend to passenger and driver clients at a 1–5 Hz cadence. The choice of transport affects:

- Compatibility with serverless platforms (the API runs on Vercel functions).
- Behaviour on cellular networks with NAT timeouts.
- Client implementation surface for web, Capacitor WebView, and Flutter.
- Bidirectional vs. unidirectional traffic.

The implementation already uses SSE (`/api/stream`, router `api/routers/stream.py`) and provides an optional WebSocket endpoint (`/api/ws/...`, router `api/routers/websocket.py`) as a complement.

## Decision

Make **Server-Sent Events the primary real-time channel** for vehicle positions. WebSocket remains available for two-way dispatcher and ops cases.

Rationale:

- SSE travels over plain HTTPS; it crosses every corporate proxy, mobile carrier NAT, and CDN that already handles our REST traffic.
- All four clients (web dashboard, Capacitor WebView, Flutter via `flutter_client_sse`, optional native iOS via `URLSession`) have stable SSE support.
- The traffic shape is push-only fleet → clients; bidirectional WebSocket framing buys nothing for that pattern.
- Browser `EventSource` reconnects automatically with the `Last-Event-ID` header, simplifying the client.
- Vercel's serverless functions support streaming responses; long-running WebSocket connections would need a separate always-on host.

## Consequences

### Positive

- One transport for the public bus-tracking experience; one CDN-friendly URL.
- Trivial to load-balance — every SSE connection is just an HTTP/2 stream.
- Authentication piggy-backs on standard JWT-bearer headers; no special handshake.
- Clients implement no message protocol of their own.

### Negative

- One-way only. Dispatcher push-to-driver chat needs WebSocket or short polling, and we keep `websocket.py` for that.
- Some legacy mobile proxies kill long-lived HTTP connections; the SSE backoff handler in `flutter_app/lib/features/map/vehicle_stream.dart` mitigates with capped exponential reconnects.
- Browser limit of 6 open SSE connections per origin under HTTP/1.1. We require HTTP/2 in production (`vercel.json`).

## Operational notes

- Heartbeat: server emits a `: ping` comment every 25 seconds to keep proxies open.
- Event names: `vehicles`, `alerts`, `incidents`. See `SSE_Contract.md` for payloads.
- Client backoff: capped at 30 seconds with ±20 % jitter (`vehicle_stream.dart` step 33).

## Alternatives considered

- **WebSocket-first.** Rejected for the public passenger use case on the grounds above. Retained for dispatcher tooling.
- **Polling at 1 Hz.** Trivially simple but burns request budget on the serverless plan and produces visible jitter on the map.
- **MQTT-over-WebSocket.** Overkill for one-way push of small JSON payloads.
