import math
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from api.core.auth import CurrentUser, optional_auth
from api.core.cache import (
    CACHE_KEY_STOPS_LIST,
    CACHE_TTL_ROUTES_STOPS,
    RATE_LIMIT_READ,
    _cache_get,
    _cache_set,
    _get_client_ip,
    _rate_limit_check,
    _tenant_cache_key,
)
from api.core.database import _supabase_get, _supabase_rpc
from api.core.geo import parse_location
from api.core.tenancy import _op_filter, _resolve_operator_id
from api.models.schemas import ETAArrival, NearestStop, StopETAResponse, StopResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

_CITY_AVG_SPEED_KMH = 25.0  # fallback when vehicle is stationary or speed unavailable


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in km between two lat/lon points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@router.get("/api/stops", response_model=List[StopResponse], tags=["stops"])
async def list_stops(
    operator: Optional[str] = Query(None, description="Operator slug"),
    current_user: Optional[CurrentUser] = Depends(optional_auth),
):
    """List all active stops."""
    try:
        if current_user and current_user.role == "super_admin":
            op_id = await _resolve_operator_id(operator) if operator else None
        elif current_user and current_user.operator_id:
            op_id = current_user.operator_id
        else:
            op_id = await _resolve_operator_id(operator) if operator else None

        cache_key = _tenant_cache_key(CACHE_KEY_STOPS_LIST, op_id or "all")
        cached = await _cache_get(cache_key)
        if cached is not None:
            return cached

        query = "stops?is_active=eq.true&select=*"
        if op_id:
            query += f"&{_op_filter(op_id)}"
        stops = await _supabase_get(query)

        result = []
        for stop in stops:
            lat, lon = parse_location(stop.get("location"))
            result.append(
                StopResponse(
                    id=stop["id"],
                    stop_id=stop["stop_id"],
                    name=stop["name"],
                    name_ar=stop["name_ar"],
                    latitude=lat,
                    longitude=lon,
                    has_shelter=stop.get("has_shelter", False),
                    is_active=stop["is_active"],
                )
            )

        await _cache_set(
            cache_key, [r.model_dump() for r in result], CACHE_TTL_ROUTES_STOPS
        )
        return result

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/api/stops/nearest", response_model=List[NearestStop], tags=["stops"])
async def find_nearest_stops(
    raw_request: Request,
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius: int = Query(1000, ge=100, le=5000),
    limit: int = Query(10, ge=1, le=50),
):
    """Find nearest stops using PostGIS RPC."""
    client_ip = _get_client_ip(raw_request)
    max_req, window = RATE_LIMIT_READ
    if not await _rate_limit_check(f"stops_nearest:{client_ip}", max_req, window):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Try again later.",
            headers={"Retry-After": str(window)},
        )
    try:
        stops = await _supabase_rpc(
            "find_nearest_stops",
            {"p_lat": lat, "p_lon": lon, "p_limit": limit, "p_radius_m": radius},
        )

        stops = stops if isinstance(stops, list) else [stops] if stops else []

        return [
            NearestStop(
                id=stop.get("id"),
                stop_id=stop["stop_id"],
                name=stop["name"],
                name_ar=stop["name_ar"],
                latitude=stop.get("lat"),
                longitude=stop.get("lon"),
                distance_m=stop.get("distance_m"),
                has_shelter=stop.get("has_shelter", False),
            )
            for stop in stops
        ]

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/api/stops/{stop_id}/eta", response_model=StopETAResponse, tags=["stops"])
async def get_stop_eta(
    stop_id: str,
    limit: int = Query(3, ge=1, le=10, description="Max arrivals to return"),
    operator: Optional[str] = Query(None, description="Operator slug"),
    current_user: Optional[CurrentUser] = Depends(optional_auth),
):
    """Return upcoming bus arrivals with ETA for a specific stop.

    ETA is calculated from live vehicle GPS positions using Haversine distance
    and current speed. Falls back to city-average speed (25 km/h) when a
    vehicle is stationary or speed data is unavailable.
    """
    try:
        if current_user and current_user.role == "super_admin":
            op_id = await _resolve_operator_id(operator) if operator else None
        elif current_user and current_user.operator_id:
            op_id = current_user.operator_id
        else:
            op_id = await _resolve_operator_id(operator) if operator else None

        # 1. Resolve the stop — accept UUID (id) or stop_id string
        stop_query = f"stops?id=eq.{stop_id}&select=*"
        if op_id:
            stop_query += f"&{_op_filter(op_id)}"
        stops = await _supabase_get(stop_query)

        if not stops:
            # Try matching by stop_id string field
            alt_query = f"stops?stop_id=eq.{stop_id}&select=*"
            if op_id:
                alt_query += f"&{_op_filter(op_id)}"
            stops = await _supabase_get(alt_query)

        if not stops:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stop '{stop_id}' not found",
            )

        stop = stops[0]
        stop_uuid = stop["id"]
        stop_lat, stop_lon = parse_location(stop.get("location"))

        if stop_lat is None or stop_lon is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Stop has no valid GPS location",
            )

        # 2. Find routes that serve this stop via route_stops table
        route_stop_rows = await _supabase_get(
            f"route_stops?stop_id=eq.{stop_uuid}&select=route_id"
        )
        route_ids = [r["route_id"] for r in (route_stop_rows or [])]

        # 3. Fetch all active vehicle positions
        pos_query = (
            "vehicle_positions_latest"
            "?select=vehicle_id,location,speed_kmh,source,recorded_at"
            ",vehicles(id,vehicle_id,name,name_ar,assigned_route_id,status)"
        )
        if op_id:
            pos_query += f"&{_op_filter(op_id)}"
        positions = await _supabase_get(pos_query)

        # Fetch route name info for routes serving this stop
        route_info: dict = {}
        if route_ids:
            routes_query = (
                "routes?id=in.(" + ",".join(route_ids) + ")&select=id,name,name_ar"
            )
            route_rows = await _supabase_get(routes_query)
            for r in route_rows or []:
                route_info[r["id"]] = r

        # 4. Calculate ETA for each vehicle with a valid position
        arrivals: List[ETAArrival] = []
        for pos in positions or []:
            vlat, vlon = parse_location(pos.get("location"))
            if vlat is None or vlon is None:
                continue

            vehicle = pos.get("vehicles") or {}
            if vehicle.get("status") == "decommissioned":
                continue

            dist_km = _haversine_km(vlat, vlon, stop_lat, stop_lon)
            raw_speed = pos.get("speed_kmh")
            speed = raw_speed if raw_speed and raw_speed > 3 else _CITY_AVG_SPEED_KMH
            eta_min = max(1, round((dist_km / speed) * 60))

            assigned_route_id = vehicle.get("assigned_route_id")
            route = route_info.get(assigned_route_id, {}) if assigned_route_id else {}

            arrivals.append(
                ETAArrival(
                    vehicle_id=vehicle.get("vehicle_id") or pos.get("vehicle_id", ""),
                    vehicle_name=vehicle.get("name", ""),
                    vehicle_name_ar=vehicle.get("name_ar", ""),
                    route_name=route.get("name"),
                    route_name_ar=route.get("name_ar"),
                    eta_minutes=eta_min,
                    distance_km=round(dist_km, 2),
                    speed_kmh=raw_speed,
                    source="real" if pos.get("source") == "traccar" else "estimated",
                )
            )

        # Sort: vehicles on routes serving this stop first, then by ETA ascending
        arrivals.sort(key=lambda a: (0 if a.route_name else 1, a.eta_minutes))

        return StopETAResponse(
            stop_id=stop["stop_id"],
            stop_name=stop["name"],
            stop_name_ar=stop["name_ar"],
            arrivals=arrivals[:limit],
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
