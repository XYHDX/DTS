import collections
import json
import os
import threading
import time

from fastapi import Request

CACHE_TTL_VEHICLES = 5
CACHE_TTL_ROUTES_STOPS = 300
CACHE_TTL_STATS = 30

CACHE_KEY_VEHICLES_LIST = "transit:vehicles:list"
CACHE_KEY_VEHICLES_POSITIONS = "transit:vehicles:positions"
CACHE_KEY_ROUTES_LIST = "transit:routes:list"
CACHE_KEY_STATS = "transit:stats"
CACHE_KEY_STOPS_LIST = "transit:stops:list"

RATE_LIMIT_LOGIN = (10, 60)
RATE_LIMIT_DRIVER_POS = (12, 60)
RATE_LIMIT_GLOBAL = (200, 60)
RATE_LIMIT_PUSH_SUB = (5, 60)
RATE_LIMIT_READ = (60, 60)
RATE_LIMIT_WRITE = (20, 60)

# Trusted proxy IPs loaded from env (comma-separated). When set, X-Forwarded-For
# is walked right-to-left: the first IP not in the trusted set is the real client.
_TRUSTED_PROXIES: frozenset[str] = frozenset(
    ip.strip() for ip in os.getenv("TRUSTED_PROXY_IPS", "").split(",") if ip.strip()
)


# In-memory rate limit fallback — used when Redis is unavailable.
# Stores a deque of request timestamps per identifier, protected by a lock.
_rl_memory: collections.defaultdict = collections.defaultdict(collections.deque)
_rl_lock: threading.Lock = threading.Lock()


def _rate_limit_check_memory(
    identifier: str, max_requests: int, window_seconds: int
) -> bool:
    """Thread-safe sliding-window rate limiter using in-process memory."""
    now = time.time()
    cutoff = now - window_seconds
    with _rl_lock:
        dq = _rl_memory[identifier]
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= max_requests:
            return False
        dq.append(now)
        return True


def _tenant_cache_key(base: str, operator_id: str) -> str:
    return f"{base}:{operator_id}"


def _get_redis_client():
    url = os.getenv("UPSTASH_REDIS_REST_URL", "")
    token = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")
    if not url or not token:
        return None
    try:
        from upstash_redis.asyncio import Redis

        return Redis(url=url, token=token)
    except Exception:
        return None


async def _cache_get(key: str):
    client = _get_redis_client()
    if client is None:
        return None
    try:
        raw = await client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        return None


async def _cache_set(key: str, value, ttl: int) -> None:
    client = _get_redis_client()
    if client is None:
        return
    try:
        await client.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception:
        pass


async def _cache_delete(*keys: str) -> None:
    client = _get_redis_client()
    if client is None:
        return
    try:
        await client.delete(*keys)
    except Exception:
        pass


async def _redis_health_check() -> bool:
    client = _get_redis_client()
    if client is None:
        return True
    try:
        await client.ping()
        return True
    except Exception:
        return False


async def _rate_limit_check(
    identifier: str, max_requests: int, window_seconds: int
) -> bool:
    client = _get_redis_client()
    if client is None:
        return _rate_limit_check_memory(identifier, max_requests, window_seconds)
    try:
        window = int(time.time()) // window_seconds
        key = f"rl:{identifier}:{window}"
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, window_seconds + 1)
        return count <= max_requests
    except Exception:
        return _rate_limit_check_memory(identifier, max_requests, window_seconds)


# ---------------------------------------------------------------------------
# Step 19 — Reusable rate-limit dependency for admin / write endpoints.
#
# Usage:
#   from fastapi import APIRouter, Depends
#   from api.core.cache import rate_limit, RATE_LIMIT_WRITE
#
#   router = APIRouter()
#
#   @router.post(
#       "/api/admin/vehicles",
#       dependencies=[Depends(rate_limit("admin:write", *RATE_LIMIT_WRITE))],
#   )
#   async def create_vehicle(...): ...
#
# The key is the bucket name; the IP is appended automatically so two writers
# at different addresses don't share the same counter.
# ---------------------------------------------------------------------------
from typing import Callable


def rate_limit(bucket: str, max_requests: int, window_seconds: int) -> Callable:
    """Return a FastAPI dependency that enforces a sliding-window rate limit.

    Backed by the same primitives as the global middleware: Upstash Redis when
    available, otherwise an in-process sliding window (ADR-003).
    """

    async def _gate(request: Request) -> None:
        ip = _get_client_ip(request)
        ok = await _rate_limit_check(
            f"rl:{bucket}:{ip}", max_requests, window_seconds
        )
        if not ok:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded for this endpoint",
                headers={"Retry-After": str(window_seconds)},
            )

    # Preserve a stable __name__ so FastAPI's dependency cache can identify it.
    _gate.__name__ = f"rate_limit_{bucket.replace(':','_')}"
    return _gate


def _get_client_ip(request: Request) -> str:
    # x-real-ip is set by Vercel/CDN and cannot be spoofed by end clients.
    # Prefer it when available.
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip

    # When TRUSTED_PROXY_IPS is configured, walk X-Forwarded-For right-to-left
    # and return the first IP that is not a known trusted proxy. This prevents
    # clients from injecting arbitrary source IPs into the leftmost position.
    if _TRUSTED_PROXIES:
        forwarded_for = request.headers.get("x-forwarded-for", "")
        if forwarded_for:
            ips = [ip.strip() for ip in forwarded_for.split(",")]
            for ip in reversed(ips):
                if ip not in _TRUSTED_PROXIES:
                    return ip

    # Fall back to the actual TCP connection IP, which cannot be spoofed.
    if request.client:
        return request.client.host
    return "unknown"
