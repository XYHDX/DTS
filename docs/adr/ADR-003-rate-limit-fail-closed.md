# ADR-003 — Rate limiter fail-closed semantics

- **Status:** Accepted
- **Date:** 2026-05-24
- **Deciders:** 3dtitans, Claude (advisory)
- **Supersedes:** Implicit prior behaviour patched as H2 in the April security scan.

## Context

The rate limiter (`api/core/cache.py:_rate_limit_check`) is the only line of defence on `/api/auth/login`, `/api/auth/reset`, and the public webhook endpoints. The original implementation used Upstash Redis exclusively; when Redis was unreachable the function returned `True` (request allowed), silently disabling all brute-force protection during a Redis outage.

The April 2026 security audit (H2) flagged this as a HIGH risk. We need a deterministic, configurable behaviour.

## Decision

When the Redis backend is unreachable the rate limiter **falls back to a process-local, thread-safe sliding-window** (`_rate_limit_check_memory`). It does not fail open.

Concretely:

- Upstash Redis is the canonical store. Successful path: increment a key `rl:<ident>:<window>` and compare to the limit.
- On any Redis exception, the request is checked against the in-process `_rl_memory` deque guarded by `_rl_lock`. The window length and limit are identical to the Redis path.
- A 503 is **not** returned. We accept that two FastAPI workers seeing the same client cannot coordinate during an outage; in that worst-case the effective limit is `N_workers × configured_limit`, which is still bounded and still attacker-unfriendly.

## Consequences

### Positive

- Brute-force protection survives a Redis incident.
- No new dependency; the fallback is pure Python.
- Limit semantics are unchanged in the happy path.

### Negative

- Per-worker memory means the limit is approximate during outages. We surface this in the logs as `rate_limit_redis_fallback`.
- Long-running outages cause `_rl_memory` to grow; we use a `defaultdict(deque)` and prune entries older than the window on every lookup, so steady-state memory is bounded.
- We do not communicate "service degraded" to clients during an outage. Clients see normal 200/429 responses.

## Operational notes

- Configure trusted proxy IPs via `TRUSTED_PROXY_IPS` (comma-separated). Without this, X-Forwarded-For values are ignored to prevent H1.
- The rate-limit middleware is bypassed for `/`, `/api/health`, `/api/docs`, `/api/openapi.json`, `/api/redoc` — these endpoints must remain available even during attack.
- `/api/health/deep` (introduced as roadmap step 17) returns 503 if Redis is unreachable, giving load balancers a signal independent of rate-limit success.

## Alternatives considered

- **Fail open.** The original behaviour. Rejected as documented in the audit.
- **Fail closed with 503.** Considered. Rejected because a Redis outage would take the entire API offline, which is a higher-impact incident than a temporary reduction in brute-force protection.
- **Dedicated rate-limit microservice.** Rejected as over-engineering for the current scale (24 vehicles, low write rate).
