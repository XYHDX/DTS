"""
DamascusTransit FastAPI Backend — Modular edition.
This file is the thin app factory; all business logic lives in api/routers/*.
"""

import asyncio
import os
import sys
import time
import uuid
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv()

# ── Structured logging ───────────────────────────────────────────────────────
from api.core.logging import setup_logging  # noqa: E402

setup_logging()

from api.core.logging import logger  # noqa: E402

# ── Sentry (optional) ────────────────────────────────────────────────────────
_SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if _SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.httpx import HttpxIntegration

    sentry_sdk.init(
        dsn=_SENTRY_DSN,
        integrations=[FastApiIntegration(), HttpxIntegration()],
        traces_sample_rate=0.1,
        profiles_sample_rate=0.0,
        environment=os.getenv("VERCEL_ENV", "development"),
        release=os.getenv("APP_RELEASE") or "damascustransit@1.0.0",
        send_default_pii=False,
    )
    logger.info("Sentry error tracking initialised")
else:
    logger.info("SENTRY_DSN not set — error tracking disabled")

# ── OpenAPI tag metadata ─────────────────────────────────────────────────────
_OPENAPI_TAGS = [
    {
        "name": "health",
        "description": "Service health and status checks. No authentication required.",
    },
    {"name": "auth", "description": "User authentication. Returns a JWT bearer token."},
    {
        "name": "routes",
        "description": "Transit route data. Public read access; no authentication required.",
    },
    {
        "name": "stops",
        "description": "Bus stop locations and nearest-stop lookup. Public read access.",
    },
    {
        "name": "vehicles",
        "description": "Real-time vehicle positions and fleet list. Public read access.",
    },
    {
        "name": "stream",
        "description": "Server-Sent Events (SSE) stream for live vehicle updates. Public.",
    },
    {
        "name": "websocket",
        "description": "WebSocket real-time vehicle tracking with route subscriptions.",
    },
    {"name": "stats", "description": "Aggregate fleet statistics. Public read access."},
    {
        "name": "schedules",
        "description": "Route schedules and timetables. Public read access.",
    },
    {
        "name": "alerts",
        "description": "Passenger-facing service alerts. Public read access.",
    },
    {
        "name": "driver",
        "description": "Driver-only endpoints. Requires `driver` role JWT.",
    },
    {
        "name": "admin",
        "description": "Admin and dispatcher endpoints. Requires `admin` or `dispatcher` role JWT.",
    },
    {
        "name": "traccar",
        "description": "Traccar GPS device webhooks. Secured by HMAC signature header.",
    },
    {
        "name": "gtfs",
        "description": "GTFS static and realtime feeds for Google Maps / transit apps.",
    },
    {
        "name": "operators",
        "description": "Fleet operator (tenant) management. super_admin role required for most operations.",
    },
    {"name": "push", "description": "Web Push notification subscriptions."},
    {"name": "cron", "description": "Scheduled background jobs. Bearer-token secured."},
    {
        "name": "feedback",
        "description": "Passenger feedback submission and driver rating summaries.",
    },
    {
        "name": "payments",
        "description": "Sham Cash fare payments — signed vehicle QR, initiate/status, "
        "HMAC-verified webhook, sandbox simulator. See docs/ARCHITECTURE_DECISIONS.md §10.",
    },
    {
        "name": "telemetry",
        "description": (
            "Protobuf-over-HTTP bridge endpoints that accept the same wire format "
            "the MQTT broker will eventually deliver. Phase S2 of Scale_100k_Roadmap.md. "
            "Authenticated by HMAC device signature, NOT JWT."
        ),
    },
]

app = FastAPI(
    title="DamascusTransit API",
    description=(
        "Real-time transit tracking and fleet management — multi-tenant SaaS edition.\n\n"
        "## Authentication\n\n"
        "Most read endpoints are public but require an `?operator=<slug>` query parameter.\n"
        "1. **POST /api/v1/auth/login** — exchange email/password for a JWT token\n"
        "2. Include the token as `Authorization: Bearer <token>` on protected endpoints\n\n"
        "Roles: `super_admin` · `admin` · `dispatcher` · `driver` · `viewer`\n\n"
        "Tokens expire after 24 hours."
    ),
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    contact={
        "name": "Damascus Transit System",
        "email": "support@damascustransit.com",
    },
    license_info={
        "name": "MIT",
    },
    openapi_tags=_OPENAPI_TAGS,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
_cors_origins_env = os.getenv("ALLOWED_ORIGINS", "")
_allowed_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
if not _allowed_origins:
    raise RuntimeError(
        "ALLOWED_ORIGINS env var must be set to a comma-separated list of allowed origins"
    )
if "*" in _allowed_origins:
    raise RuntimeError(
        "Wildcard '*' is not permitted in ALLOWED_ORIGINS — specify explicit origins only"
    )
_is_production = os.getenv("VERCEL_ENV", "").lower() == "production"
if _is_production:
    _allowed_origins = [
        o for o in _allowed_origins if "localhost" not in o and "127.0.0.1" not in o
    ]
    if not _allowed_origins:
        raise RuntimeError(
            "All ALLOWED_ORIGINS are localhost — no valid origins remain for production"
        )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# ── Middleware ────────────────────────────────────────────────────────────────
from api.core.cache import RATE_LIMIT_GLOBAL, _get_client_ip, _rate_limit_check  # noqa: E402

_GLOBAL_RATE_LIMIT_SKIP = frozenset(
    {"/api/health", "/", "/api/docs", "/api/openapi.json", "/api/redoc"}
)

_API_V1_PREFIX = "/api/v1"
_API_PREFIX = "/api"
_SUNSET_DATE = "2026-09-30"


@app.middleware("http")
async def _global_rate_limit_middleware(request: Request, call_next):
    if request.url.path not in _GLOBAL_RATE_LIMIT_SKIP:
        client_ip = _get_client_ip(request)
        max_req, window = RATE_LIMIT_GLOBAL
        if not await _rate_limit_check(f"global:{client_ip}", max_req, window):
            logger.warning(
                "global_rate_limit_exceeded",
                extra={"client_ip": client_ip, "path": request.url.path},
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please slow down.",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                headers={"Retry-After": str(window)},
            )
    return await call_next(request)


@app.middleware("http")
async def _request_logging_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    logger.info(
        "request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    response.headers["X-Request-Id"] = request_id
    return response


@app.middleware("http")
async def _security_headers_middleware(request: Request, call_next):
    """Step 16 — tighten security headers across every response.

    CSP is intentionally permissive for the embedded MapLibre + OSM tiles but
    blocks inline event handlers and arbitrary remote scripts.
    """
    response = await call_next(request)
    response.headers.setdefault(
        "Strict-Transport-Security",
        "max-age=63072000; includeSubDomains; preload",
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(self), microphone=(), geolocation=(self), payment=()",
    )
    # CSP is only applied to HTML responses; JSON / SSE keep their own headers.
    ctype = response.headers.get("content-type", "")
    if "text/html" in ctype:
        response.headers.setdefault(
            "Content-Security-Policy",
            (
                "default-src 'self'; "
                "img-src 'self' data: https://tile.openstreetmap.org https://*.tile.openstreetmap.org; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
                "font-src 'self' https://fonts.gstatic.com; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "connect-src 'self' https://tile.openstreetmap.org https://*.upstash.io https://*.supabase.co; "
                "worker-src 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'self';"
            ),
        )
    return response


@app.middleware("http")
async def _api_versioning_middleware(request: Request, call_next):
    original_path = request.url.path
    if (
        original_path.startswith(_API_V1_PREFIX + "/")
        or original_path == _API_V1_PREFIX
    ):
        new_path = _API_PREFIX + original_path[len(_API_V1_PREFIX) :]
        if not new_path:
            new_path = _API_PREFIX
        request.scope["path"] = new_path
        response = await call_next(request)
        response.headers["X-API-Version"] = "v1"
        return response
    if original_path.startswith(_API_PREFIX + "/") or original_path == _API_PREFIX:
        response = await call_next(request)
        v1_path = _API_V1_PREFIX + original_path[len(_API_PREFIX) :]
        response.headers["X-API-Version"] = "v1"
        response.headers["Deprecation"] = "true"
        response.headers["Sunset"] = _SUNSET_DATE
        response.headers["Link"] = f'<{v1_path}>; rel="successor-version"'
        return response
    return await call_next(request)


# ── Routers ───────────────────────────────────────────────────────────────────
from api.routers import (  # noqa: E402
    admin,
    alerts,
    auth,
    client_log,
    cron,
    driver,
    gtfs,
    health,
    mqtt_ingest,
    operators,
    push,
    routes,
    schedules,
    stats,
    stops,
    payments,
    stream,
    traccar,
    vehicles,
    websocket,
)

for _router in [
    health.router,
    client_log.router,
    auth.router,
    routes.router,
    stops.router,
    vehicles.router,
    stream.router,
    websocket.router,
    stats.router,
    schedules.router,
    alerts.router,
    driver.router,
    admin.router,
    cron.router,
    traccar.router,
    gtfs.router,
    push.router,
    operators.router,
    mqtt_ingest.router,
    payments.router,
]:
    app.include_router(_router)


# ── Prometheus metrics (optional; self-hosted / Docker deployment) ────────────
# Phase S7.2 of Scale_100k_Roadmap.md. Disabled on serverless (Vercel), where a
# scraped /metrics endpoint has no persistent process to scrape; enable it on
# the Docker deployment with METRICS_ENABLED=true. See docker-compose.scale.yml.
if os.getenv("METRICS_ENABLED", "").lower() in {"1", "true", "yes"}:
    try:
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator(
            excluded_handlers=["/metrics", "/api/health", "/api/health/deep"],
        ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
        logger.info("Prometheus metrics enabled at /metrics")
    except Exception as _metrics_exc:  # never let metrics break startup
        logger.warning(f"metrics_init_failed: {_metrics_exc}")


# ── Startup event ─────────────────────────────────────────────────────────────
async def _seed_default_operator():
    """Ensure the default 'damascus' operator exists in the database."""
    from api.core.database import _service_get, _supabase_headers, _supabase_url

    try:
        rows = await _service_get("operators?slug=eq.damascus&select=id,is_active")
        if rows and rows[0].get("is_active"):
            logger.info("Default operator 'damascus' exists and is active")
            return
        # Insert or reactivate
        import httpx as _httpx

        headers = _supabase_headers(use_service_key=True)
        headers["Prefer"] = "return=representation"
        async with _httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                _supabase_url("operators?on_conflict=slug"),
                headers=headers,
                json={
                    "id": "00000000-0000-0000-0000-000000000001",
                    "slug": "damascus",
                    "name": "Damascus Transit Authority",
                    "name_ar": "\u0647\u064a\u0626\u0629 \u0646\u0642\u0644 \u062f\u0645\u0634\u0642",
                    "is_active": True,
                },
            )
            resp.raise_for_status()
        logger.info("Default operator 'damascus' seeded/reactivated successfully")
    except Exception as e:
        logger.critical(f"Failed to seed default operator: {e}")


@app.on_event("startup")
async def _startup():
    await _seed_default_operator()
    asyncio.create_task(websocket._ws_broadcast_loop())


# ── Exception handlers ────────────────────────────────────────────────────────
from fastapi import HTTPException  # noqa: E402


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "timestamp": datetime.utcnow().isoformat()},
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@app.get("/", tags=["health"])
async def root():
    return {"message": "DamascusTransit API", "docs": "/docs", "health": "/api/health"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
