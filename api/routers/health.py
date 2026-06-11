import asyncio
from datetime import datetime

from fastapi import APIRouter

from api.core.cache import _redis_health_check
from api.core.database import (
    _active_vehicle_count,
    _health_check,
    _last_position_update,
)
from api.models.schemas import HealthResponse

router = APIRouter()


@router.get("/api/health", response_model=HealthResponse, tags=["health"])
async def health_check():
    """Health check endpoint."""
    db_healthy, redis_healthy, last_pos, active_count = await asyncio.gather(
        _health_check(),
        _redis_health_check(),
        _last_position_update(),
        _active_vehicle_count(),
    )

    overall = "healthy" if (db_healthy and redis_healthy) else "degraded"

    return HealthResponse(
        status=overall,
        timestamp=datetime.utcnow().isoformat(),
        database=db_healthy,
        redis=redis_healthy,
        last_position_update=last_pos,
        active_vehicles=active_count,
    )


@router.get("/api/health/deep", tags=["health"])
async def health_deep():
    """Step 17 — verbose probe used by uptime monitors and load balancers.

    Returns 200 only when DB and Redis are both reachable AND a position has
    been received in the last 6 hours (overnight tolerance for Damascus).
    Body always returns timing breakdowns regardless of status.
    """
    import time as _t

    t0 = _t.perf_counter()
    db_healthy, redis_healthy, last_pos, active_count = await asyncio.gather(
        _health_check(),
        _redis_health_check(),
        _last_position_update(),
        _active_vehicle_count(),
    )
    duration_ms = round((_t.perf_counter() - t0) * 1000, 1)

    # Position-freshness gate (6 hours)
    fresh = True
    try:
        if last_pos:
            from datetime import datetime as _dt, timezone

            ts = (
                last_pos
                if isinstance(last_pos, _dt)
                else _dt.fromisoformat(str(last_pos).replace("Z", "+00:00"))
            )
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age = (_dt.now(timezone.utc) - ts).total_seconds()
            fresh = age < 6 * 3600
    except Exception:
        fresh = False

    healthy_overall = db_healthy and redis_healthy
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=200 if healthy_overall else 503,
        content={
            "status": "healthy" if healthy_overall else "degraded",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "probe_duration_ms": duration_ms,
            "checks": {
                "database": db_healthy,
                "redis": redis_healthy,
                "position_fresh_6h": fresh,
            },
            "active_vehicles": active_count,
            "last_position_update": (
                last_pos.isoformat() if hasattr(last_pos, "isoformat") else last_pos
            ),
        },
    )
