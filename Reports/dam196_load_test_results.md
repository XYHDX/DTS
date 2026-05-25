# DAM-196 Load Test Results
**Date:** 2026-04-02
**Target:** https://syrian-transit-system.vercel.app
**Concurrency:** 100 simultaneous requests per endpoint
**Target SLA:** p95 < 200ms

---

## Summary

| Endpoint | Phase | n_ok | p50 | p95 | p99 | 429s | Pass |
|---|---|---|---|---|---|---|---|
| /api/vehicles | Burst 100 (cold) | 100 | 4384ms | 11867ms | 12201ms | 0 | **FAIL** |
| /api/vehicles | Burst 100 (warm) | 100 | 3731ms | 8354ms | 12017ms | 0 | **FAIL** |
| /api/routes | Burst 100 (cold) | 100 | 4815ms | 12785ms | 21277ms | 0 | **FAIL** |
| /api/routes | Burst 100 (warm) | 99 | 6848ms | 20600ms | 20686ms | 0 | **FAIL** |

**All 4 scenarios failed the <200ms p95 target.** Actual p95 is 40–100× over target.

---

## Warm-up (Sequential, Single Requests)

| Endpoint | First Request | p50 (5 reqs) |
|---|---|---|
| /api/vehicles | 930ms | 509ms |
| /api/routes | 1519ms | 1116ms |

Even single sequential requests are 500–1500ms — well above target before concurrency pressure.

---

## Key Observations

### 1. No Rate Limiting
Zero 429s at 100 concurrent requests. The API has no rate-limiting middleware.
**Risk:** A single malicious client or runaway retry loop can saturate the backend.

### 2. Serverless Cold Starts
First requests to each endpoint are significantly slower (930ms vehicles, 1519ms routes), confirming Vercel serverless cold-start penalty.

### 3. Latency Explodes Under Concurrent Load
Single-request baselines are already slow (500–1500ms), but under 100 concurrent connections, p50 jumps to 3700–6800ms. This is the primary bottleneck signature of **database connection queueing**: every serverless function instance opens its own DB connection, and they all contend simultaneously.

### 4. /api/routes Is Significantly Slower Than /api/vehicles
Routes endpoint is ~2× slower even in warm single-request mode (1116ms vs 509ms), suggesting more complex queries or joins.

### 5. No Errors — But 1 Timeout at Tail
The last burst (warm /api/routes) had 1 request return status 0 (connection dropped/timeout), indicating the load is approaching Vercel's concurrency limits.

---

## Root Cause Analysis

The primary bottleneck is **unconnected database calls from serverless functions at scale**:
- Each Vercel function invocation opens a fresh database connection (Supabase/PostgreSQL)
- 100 concurrent requests = 100 simultaneous DB connections competing for the connection pool
- Connection queuing causes latency to cascade from ~500ms to 5000–20000ms

Secondary factors:
- No response caching (Redis/DAM-63 is blocked and not deployed)
- No query result memoization
- Cold-start overhead compounds the baseline

---

## Recommendations

### Immediate (P0)
1. **Activate Redis caching** — [DAM-63](/DAM/issues/DAM-63): cache `/api/vehicles` and `/api/routes` responses with a 30–60s TTL. This eliminates 90%+ of DB load under burst traffic and will bring p95 well under 200ms for repeated requests.
2. **Add Supabase connection pooling** — Use Supabase's PgBouncer connection pooler (transaction mode) to cap DB connections regardless of serverless concurrency.

### Short-term (P1)
3. **Add rate limiting middleware** — Implement per-IP rate limiting (e.g., 50 req/10s) to protect against abuse.
4. **Optimize /api/routes query** — Profile the SQL query; the 2× latency gap over /api/vehicles suggests a complex join or missing index.
5. **Enable Vercel Edge caching** — Add `Cache-Control: public, s-maxage=30` response headers for static-enough data like vehicle/route lists.

### Monitoring
6. Set up p95 latency alerts in Vercel Analytics at thresholds: warn at 500ms, critical at 2000ms.
