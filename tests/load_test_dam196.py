"""
DAM-196 Load Test — 100 concurrent requests, p50/p95/p99 latency
Target: <200ms p95 on /api/vehicles and /api/routes
"""

import asyncio
import statistics
import time
import sys
from typing import Optional

try:
    import httpx
except ImportError:
    print("httpx not installed: pip install httpx")
    sys.exit(1)

BASE_URL = "https://syrian-transit-system.vercel.app"
CONCURRENCY = 100
WARMUP_REQUESTS = 5  # cold-start warm-up

ENDPOINTS = [
    "/api/vehicles",
    "/api/routes",
]


async def single_request(
    client: httpx.AsyncClient,
    url: str,
    results: list,
    idx: int,
):
    start = time.perf_counter()
    status = 0
    error: Optional[str] = None
    try:
        resp = await client.get(url, timeout=30.0)
        status = resp.status_code
    except Exception as e:
        error = str(e)
    elapsed_ms = (time.perf_counter() - start) * 1000
    results.append({"ms": elapsed_ms, "status": status, "error": error, "idx": idx})


async def run_concurrent_burst(endpoint: str, concurrency: int, label: str):
    url = BASE_URL + endpoint
    results = []
    print(f"\n  {label} — {concurrency} concurrent requests to {url}")

    limits = httpx.Limits(
        max_connections=concurrency + 10, max_keepalive_connections=concurrency
    )
    async with httpx.AsyncClient(limits=limits, follow_redirects=True) as client:
        tasks = [
            asyncio.create_task(single_request(client, url, results, i))
            for i in range(concurrency)
        ]
        await asyncio.gather(*tasks)

    latencies = [r["ms"] for r in results if r["status"] == 200]
    statuses = [r["status"] for r in results]
    errors = [r for r in results if r["error"]]

    status_counts: dict = {}
    for s in statuses:
        status_counts[s] = status_counts.get(s, 0) + 1

    if latencies:
        sorted_lat = sorted(latencies)
        p50 = statistics.median(latencies)
        p95 = sorted_lat[int(len(sorted_lat) * 0.95)]
        p99 = sorted_lat[int(len(sorted_lat) * 0.99)]
        p_min = sorted_lat[0]
        p_max = sorted_lat[-1]
        p_mean = statistics.mean(latencies)
    else:
        p50 = p95 = p99 = p_min = p_max = p_mean = 0.0

    rate_limited = status_counts.get(429, 0)
    ok_count = status_counts.get(200, 0)

    print(f"    Responses: {status_counts}")
    print(f"    Errors:    {len(errors)}")
    print(f"    Latency (200s only, n={ok_count}):")
    print(
        f"      min={p_min:.0f}ms  mean={p_mean:.0f}ms  p50={p50:.0f}ms  p95={p95:.0f}ms  p99={p99:.0f}ms  max={p_max:.0f}ms"
    )
    print(f"    Rate limited (429): {rate_limited}")
    target_ok = p95 < 200 if latencies else False
    print(f"    Target <200ms p95: {'PASS ✓' if target_ok else 'FAIL ✗'}")

    return {
        "endpoint": endpoint,
        "label": label,
        "n_total": concurrency,
        "n_ok": ok_count,
        "n_errors": len(errors),
        "n_429": rate_limited,
        "min_ms": round(p_min),
        "mean_ms": round(p_mean),
        "p50_ms": round(p50),
        "p95_ms": round(p95),
        "p99_ms": round(p99),
        "max_ms": round(p_max),
        "target_pass": target_ok,
    }


async def warmup(endpoint: str):
    url = BASE_URL + endpoint
    print(f"  Warming up {url} ({WARMUP_REQUESTS} sequential requests)…")
    times = []
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for _ in range(WARMUP_REQUESTS):
            start = time.perf_counter()
            try:
                r = await client.get(url, timeout=30.0)
                ms = (time.perf_counter() - start) * 1000
                times.append(ms)
                print(f"    {r.status_code} {ms:.0f}ms")
            except Exception as e:
                print(f"    ERROR: {e}")
    if times:
        print(f"  Warm-up p50: {statistics.median(times):.0f}ms")
    return times


async def main():
    print("=" * 64)
    print("DAM-196 Load Test — DamascusTransit Production API")
    print(f"Target: {BASE_URL}")
    print(f"Concurrency: {CONCURRENCY} simultaneous requests per endpoint")
    print("=" * 64)

    all_results = []

    for endpoint in ENDPOINTS:
        print(f"\n{'─' * 60}")
        print(f"Endpoint: {endpoint}")
        print(f"{'─' * 60}")

        # Warm-up (cold-start measurement)
        print("\n[1] Cold-start / warm-up phase:")
        await warmup(endpoint)

        # Brief pause
        await asyncio.sleep(2)

        # Main burst
        print("\n[2] Burst: 100 concurrent requests:")
        result = await run_concurrent_burst(endpoint, CONCURRENCY, "Burst 100")
        all_results.append(result)

        # Second burst (warm)
        await asyncio.sleep(1)
        print("\n[3] Second burst (warm serverless):")
        result2 = await run_concurrent_burst(endpoint, CONCURRENCY, "Burst 100 (warm)")
        all_results.append(result2)

        await asyncio.sleep(3)

    print("\n" + "=" * 64)
    print("SUMMARY")
    print("=" * 64)
    print(
        f"{'Endpoint':<25} {'Phase':<20} {'n_ok':>5} {'p50':>6} {'p95':>6} {'p99':>6} {'429':>5} {'Pass':>5}"
    )
    print("-" * 80)
    for r in all_results:
        status = "PASS" if r["target_pass"] else "FAIL"
        print(
            f"{r['endpoint']:<25} {r['label']:<20} {r['n_ok']:>5} "
            f"{r['p50_ms']:>5}ms {r['p95_ms']:>5}ms {r['p99_ms']:>5}ms "
            f"{r['n_429']:>5} {status:>5}"
        )

    print("\nDone.")
    return all_results


if __name__ == "__main__":
    asyncio.run(main())
