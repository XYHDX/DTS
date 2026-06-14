from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from api.core.auth import CurrentUser, require_role
from api.core.cache import (
    CACHE_KEY_VEHICLES_LIST,
    CACHE_KEY_VEHICLES_POSITIONS,
    RATE_LIMIT_DRIVER_POS,
    _cache_delete,
    _rate_limit_check,
    _tenant_cache_key,
)
from api.core.database import (
    _service_get,
    _service_patch,
    _service_post,
    _service_rpc,
)
from api.core import live_bus
import logging

from api.models.schemas import (
    PassengerCountUpdate,
    PositionUpdate,
    StatusTimestampResponse,
    TripActionResponse,
    TripEnd,
    TripStart,
)

logger = logging.getLogger(__name__)

router = APIRouter()

APPROVAL_BLOCKED_DETAIL = (
    "Vehicle is not approved to operate. "
    "المركبة غير معتمدة للعمل بعد — بانتظار موافقة الإدارة."
)


async def _require_approved_vehicle(driver_user_id: str, vehicle_id: str = None):
    """Approval-workflow gate (migration 019).

    Looks up the driver's vehicle and rejects with 403 unless
    approval_status == 'approved' AND is_active. Returns
    (vehicle_uuid, assigned_route_id). Missing approval_status column
    (migration not applied yet) counts as approved for backward compat.
    """
    vehicles = None
    if vehicle_id:
        vehicles = await _service_get(
            f"vehicles?id=eq.{vehicle_id}&select=id,assigned_route_id,approval_status,is_active"
        )
    if not vehicles:
        # No vehicle_id claim, or the token's vehicle was deleted/reassigned —
        # fall back to the live assignment instead of failing on a stale token.
        vehicles = await _service_get(
            f"vehicles?assigned_driver_id=eq.{driver_user_id}"
            f"&select=id,assigned_route_id,approval_status,is_active"
        )
    if not vehicles:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No vehicle assigned"
        )
    v = vehicles[0]
    if v.get("is_active") is False or (
        v.get("approval_status") is not None and v["approval_status"] != "approved"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=APPROVAL_BLOCKED_DETAIL
        )
    return v["id"], v.get("assigned_route_id")


@router.get("/api/driver/me", tags=["driver"])
async def driver_me(
    current_user: CurrentUser = Depends(require_role("driver")),
):
    """Driver session bootstrap: my vehicle, its approval state, and route.

    Added 2026-06-11 — the driver console previously had no way to learn
    its vehicle code / route, so the header showed em-dashes forever.
    """
    try:
        vehicles = await _service_get(
            f"vehicles?assigned_driver_id=eq.{current_user.user_id}"
            f"&select=id,vehicle_id,name,name_ar,vehicle_type,approval_status,is_active,assigned_route_id"
        )
        if not vehicles:
            return {"vehicle": None, "route": None}
        v = vehicles[0]
        route = None
        if v.get("assigned_route_id"):
            routes = await _service_get(
                f"routes?id=eq.{v['assigned_route_id']}&select=id,route_id,name,name_ar,fare_syp"
            )
            route = routes[0] if routes else None
        return {
            "vehicle": {
                "id": v["id"],
                "code": v.get("vehicle_id"),
                "name": v.get("name"),
                "name_ar": v.get("name_ar"),
                "type": v.get("vehicle_type"),
                "approval_status": v.get("approval_status") or "approved",
                "is_active": v.get("is_active", True),
            },
            "route": route,
        }
    except Exception:
        logger.error("driver_me failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/driver/me/next_trip", tags=["driver"])
async def driver_next_trip(
    current_user: CurrentUser = Depends(require_role("driver")),
):
    """The driver's next not-yet-started trip, for the dispatch banner.

    Returns ``{"trip": <trip>|None}``. A trip appears here once a dispatcher
    has scheduled/pushed it (status scheduled|dispatched|acked) but before the
    driver presses Start. This endpoint is read-only and best-effort: any
    failure (e.g. the trip-dispatch columns/enum from migration 013 are not
    present on this database yet) yields ``{"trip": None}`` rather than a 500,
    because the banner is an optional enhancement and must never break the
    console. Uses the service role so it is unaffected by trips-table RLS.
    """
    try:
        trips = await _service_get(
            f"trips?driver_id=eq.{current_user.user_id}"
            "&status=in.(scheduled,dispatched,acked)"
            "&select=id,status,route_id,scheduled_start,planned_passengers,notes"
            "&order=scheduled_start.asc.nullslast&limit=1"
        )
        if not trips:
            return {"trip": None}
        t = trips[0]
        if t.get("route_id"):
            routes = await _service_get(
                f"routes?id=eq.{t['route_id']}&select=id,route_id,name,name_ar,fare_syp"
            )
            t["route"] = routes[0] if routes else None
        else:
            t["route"] = None
        return {"trip": t}
    except Exception:
        # Dispatch schema may not be migrated yet, or RLS/permissions hiccup —
        # the banner is optional, so degrade silently instead of 500-ing.
        logger.info("driver_next_trip: no dispatch data (returning null)")
        return {"trip": None}


@router.post(
    "/api/driver/incident", response_model=StatusTimestampResponse, tags=["driver"]
)
async def report_incident(
    body: dict,
    current_user: CurrentUser = Depends(require_role("driver")),
):
    """Driver SOS / incident report → creates a critical alert for dispatch.

    Added 2026-06-11 — the driver console and Flutter app both POSTed here
    but the endpoint never existed (silent failure). Uses the existing
    alerts pipeline so incidents appear on the admin dashboard immediately.
    Photo payloads are accepted but only persisted when storage is
    configured (see migration 018 / incident photos bucket).
    """
    try:
        vehicle_uuid, _ = await _require_approved_vehicle(
            current_user.user_id, current_user.vehicle_id
        )
        kind = str(body.get("kind") or "sos")
        if kind not in ("sos", "breakdown", "delay"):
            kind = "sos"
        note = str(body.get("note") or "")[:300]
        lat, lon = body.get("lat"), body.get("lon")
        loc_txt = (
            f" @({float(lat):.5f},{float(lon):.5f})"
            if isinstance(lat, (int, float)) and isinstance(lon, (int, float))
            else ""
        )
        alert = {
            "vehicle_id": vehicle_uuid,
            "alert_type": kind,
            "severity": "critical",
            "title": f"Driver incident report ({kind})",
            "title_ar": "بلاغ سائق — حادث" if kind == "sos" else "بلاغ سائق",
            "description": (note + loc_txt).strip() or None,
            "is_resolved": False,
            "operator_id": current_user.operator_id,
        }
        await _service_post("alerts", alert)
        return {"status": "success", "timestamp": datetime.utcnow().isoformat()}
    except HTTPException:
        raise
    except Exception:
        logger.error("report_incident failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/api/driver/position", response_model=StatusTimestampResponse, tags=["driver"]
)
async def report_driver_position(
    position: PositionUpdate,
    current_user: CurrentUser = Depends(require_role("driver")),
):
    """Report driver's current position (vehicle must be admin-approved)."""
    max_req, window = RATE_LIMIT_DRIVER_POS
    if not await _rate_limit_check(f"drvpos:{current_user.user_id}", max_req, window):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Position update rate limit exceeded.",
        )
    try:
        db_vehicle_id, route_id = await _require_approved_vehicle(
            current_user.user_id, current_user.vehicle_id
        )

        try:
            await _service_rpc(
                "upsert_vehicle_position",
                {
                    "p_vehicle_id": db_vehicle_id,
                    "p_lat": position.latitude,
                    "p_lon": position.longitude,
                    "p_speed": position.speed_kmh or 0,
                    "p_heading": position.heading or 0,
                    "p_source": "driver_app",
                    "p_route_id": route_id,
                    "p_occupancy": None,
                },
            )
        except HTTPException as rpc_err:
            detail = str(rpc_err.detail)
            if current_user.vehicle_id and (
                "23503" in detail or "foreign key" in detail.lower()
            ):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Vehicle assignment has changed. Please log in again to refresh your session.",
                )
            raise

        if current_user.operator_id:
            await _cache_delete(
                _tenant_cache_key(CACHE_KEY_VEHICLES_LIST, current_user.operator_id),
                _tenant_cache_key(
                    CACHE_KEY_VEHICLES_POSITIONS, current_user.operator_id
                ),
            )
        else:
            await _cache_delete(CACHE_KEY_VEHICLES_LIST, CACHE_KEY_VEHICLES_POSITIONS)

        # S3.4 — fan this update out to /api/stream subscribers via the live bus
        # (no-op unless a pub/sub backend is configured). Best-effort: a bus
        # failure must never fail a driver's position report.
        try:
            await live_bus.publish(
                operator_id=current_user.operator_id,
                payload={
                    "vehicle_id": db_vehicle_id,
                    "vehicle_name": "",
                    "vehicle_name_ar": "",
                    "latitude": position.latitude,
                    "longitude": position.longitude,
                    "speed_kmh": position.speed_kmh,
                    "occupancy_pct": None,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
        except Exception:
            pass

        return {"status": "success", "timestamp": datetime.utcnow().isoformat()}

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/api/driver/trip/start", response_model=TripActionResponse, tags=["driver"]
)
async def start_trip(
    trip: TripStart,
    current_user: CurrentUser = Depends(require_role("driver")),
):
    """Start a new trip for the driver (vehicle must be admin-approved)."""
    try:
        vehicle_id, _ = await _require_approved_vehicle(current_user.user_id)
        trip_data = {
            "vehicle_id": vehicle_id,
            "route_id": trip.route_id,
            "driver_id": current_user.user_id,
            "status": "in_progress",
            "scheduled_start": trip.scheduled_departure,
            "actual_start": datetime.utcnow().isoformat(),
            "operator_id": current_user.operator_id,
        }

        result = await _service_post("trips", trip_data)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create trip",
            )

        return {
            "status": "success",
            "trip_id": result.get("id"),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/api/driver/trip/end", response_model=TripActionResponse, tags=["driver"])
async def end_trip(
    trip_data: TripEnd,
    current_user: CurrentUser = Depends(require_role("driver")),
):
    """End the driver's current trip."""
    try:
        trips = await _service_get(
            f"trips?driver_id=eq.{current_user.user_id}&status=eq.in_progress&select=id"
        )
        if not trips:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No active trip"
            )

        trip_id = trips[0]["id"]
        update_data = {
            "status": "completed",
            "actual_end": datetime.utcnow().isoformat(),
            "passenger_count": trip_data.passenger_count,
        }
        await _service_patch(f"trips?id=eq.{trip_id}", update_data)

        return {
            "status": "success",
            "trip_id": trip_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/api/driver/trip/passenger-count",
    response_model=StatusTimestampResponse,
    tags=["driver"],
)
async def update_passenger_count(
    data: PassengerCountUpdate,
    current_user: CurrentUser = Depends(require_role("driver")),
):
    """Update passenger count for current trip."""
    try:
        trips = await _service_get(
            f"trips?driver_id=eq.{current_user.user_id}&status=eq.in_progress&select=id"
        )
        if not trips:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No active trip"
            )

        trip_id = trips[0]["id"]
        await _service_patch(
            f"trips?id=eq.{trip_id}", {"passenger_count": data.passenger_count}
        )

        return {"status": "success", "timestamp": datetime.utcnow().isoformat()}

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/api/driver/trip/{trip_id}/ack",
    response_model=TripActionResponse,
    tags=["driver"],
)
async def ack_trip(
    trip_id: str,
    current_user: CurrentUser = Depends(require_role("driver")),
):
    """Driver acknowledges a dispatched/scheduled trip (banner 'Acknowledge').

    Moves the trip to ``acked`` so dispatch knows the driver has seen it. Scoped
    to the driver's OWN trip; 404 if it isn't theirs. Pairs with
    ``GET /api/driver/me/next_trip`` and migration 013's dispatch workflow.
    """
    try:
        rows = await _service_get(
            f"trips?id=eq.{trip_id}&driver_id=eq.{current_user.user_id}&select=id,status"
        )
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found"
            )
        await _service_patch(
            f"trips?id=eq.{trip_id}",
            {"status": "acked", "acked_at": datetime.utcnow().isoformat()},
        )
        return {
            "status": "success",
            "trip_id": trip_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception:
        logger.error("ack_trip failed", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
