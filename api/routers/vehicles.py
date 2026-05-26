from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from api.core.auth import CurrentUser, optional_auth
from api.core.cache import (
    CACHE_KEY_VEHICLES_LIST,
    CACHE_KEY_VEHICLES_POSITIONS,
    CACHE_TTL_VEHICLES,
    RATE_LIMIT_READ,
    _cache_get,
    _cache_set,
    _get_client_ip,
    _rate_limit_check,
    _tenant_cache_key,
)
from api.core.database import _supabase_get
from api.core.geo import parse_location
from api.core.tenancy import _op_filter, _resolve_operator_id
from api.models.schemas import VehicleResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/vehicles", response_model=List[VehicleResponse], tags=["vehicles"])
async def list_vehicles(
    raw_request: Request,
    operator: Optional[str] = Query(None, description="Operator slug"),
    current_user: Optional[CurrentUser] = Depends(optional_auth),
):
    """List all active vehicles with latest positions."""
    client_ip = _get_client_ip(raw_request)
    max_req, window = RATE_LIMIT_READ
    if not await _rate_limit_check(f"vehicles:{client_ip}", max_req, window):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Try again later.",
            headers={"Retry-After": str(window)},
        )
    try:
        if current_user and current_user.role == "super_admin":
            op_id = await _resolve_operator_id(operator) if operator else None
        elif current_user and current_user.operator_id:
            op_id = current_user.operator_id
        else:
            op_id = await _resolve_operator_id(operator) if operator else None

        cache_key = _tenant_cache_key(CACHE_KEY_VEHICLES_LIST, op_id or "all")
        cached = await _cache_get(cache_key)
        if cached is not None:
            return cached

        # Query vehicles table directly (base table) so all vehicles are
        # returned even when the PostgREST embed on vehicle_positions_latest
        # fails or no position data exists yet.
        vehicles_query = (
            "vehicles?select=id,vehicle_id,name,name_ar,vehicle_type,"
            "capacity,status,assigned_route_id"
            "&status=neq.decommissioned"
        )
        if op_id:
            vehicles_query += f"&{_op_filter(op_id)}"
        vehicles = await _supabase_get(vehicles_query)

        # Fetch latest positions separately and merge by vehicle UUID.
        # The table stores coords as PostGIS geometry(Point,4326) in
        # a "location" column — parse it to extract lat/lon.
        pos_query = (
            "vehicle_positions_latest?select=vehicle_id,location,"
            "speed_kmh,occupancy_pct,recorded_at"
        )
        if op_id:
            pos_query += f"&{_op_filter(op_id)}"
        positions = await _supabase_get(pos_query)

        pos_by_id = {p["vehicle_id"]: p for p in (positions or [])}

        result = []
        for v in vehicles or []:
            pos = pos_by_id.get(v["id"], {})
            lat, lon = parse_location(pos.get("location"))
            result.append(
                VehicleResponse(
                    id=v["id"],
                    vehicle_id=v["vehicle_id"],
                    name=v["name"],
                    name_ar=v.get("name_ar", ""),
                    vehicle_type=v["vehicle_type"],
                    capacity=v["capacity"],
                    status=v["status"],
                    assigned_route_id=v.get("assigned_route_id"),
                    latitude=lat,
                    longitude=lon,
                    speed_kmh=pos.get("speed_kmh"),
                    occupancy_pct=pos.get("occupancy_pct"),
                    recorded_at=pos.get("recorded_at"),
                )
            )

        await _cache_set(
            cache_key, [r.model_dump() for r in result], CACHE_TTL_VEHICLES
        )
        return result

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/api/vehicles/positions", response_model=List[dict], tags=["vehicles"])
async def get_vehicle_positions(
    operator: Optional[str] = Query(None, description="Operator slug"),
    current_user: Optional[CurrentUser] = Depends(optional_auth),
):
    """Get latest vehicle positions only (lightweight endpoint)."""
    try:
        if current_user and current_user.role == "super_admin":
            op_id = await _resolve_operator_id(operator) if operator else None
        elif current_user and current_user.operator_id:
            op_id = current_user.operator_id
        else:
            op_id = await _resolve_operator_id(operator) if operator else None

        cache_key = _tenant_cache_key(CACHE_KEY_VEHICLES_POSITIONS, op_id or "all")
        cached = await _cache_get(cache_key)
        if cached is not None:
            return cached

        # Query all non-decommissioned vehicles that have position data.
        # Vehicles without a position (null lat/lon simulator stubs) are
        # intentionally excluded — DAM-449.
        veh_query = (
            "vehicles?select=id,vehicle_id,vehicle_type,name,name_ar,assigned_route_id"
            "&status=neq.decommissioned"
        )
        if op_id:
            veh_query += f"&{_op_filter(op_id)}"
        vehicles = await _supabase_get(veh_query)

        # Fetch latest positions and index by vehicle UUID.
        pos_query = (
            "vehicle_positions_latest"
            "?select=vehicle_id,location,speed_kmh,heading,source,"
            "occupancy_pct,recorded_at"
        )
        if op_id:
            pos_query += f"&{_op_filter(op_id)}"
        raw = await _supabase_get(pos_query)
        pos_by_id = {p["vehicle_id"]: p for p in (raw or [])}

        result = []
        for vehicle in vehicles or []:
            pos = pos_by_id.get(vehicle["id"], {})
            lat, lon = parse_location(pos.get("location")) if pos else (None, None)
            # Skip vehicles with no position data — DAM-449.
            if lat is None or lon is None:
                continue
            result.append(
                {
                    "vehicle_id": vehicle.get("vehicle_id"),
                    "vehicle_type": vehicle.get("vehicle_type", "bus"),
                    "vehicle_name": vehicle.get("name", ""),
                    "vehicle_name_ar": vehicle.get("name_ar", ""),
                    "route_name": vehicle.get("assigned_route_id"),
                    "lat": lat,
                    "lon": lon,
                    "heading": pos.get("heading", 0),
                    "source": pos.get("source", "simulator"),
                    "speed_kmh": pos.get("speed_kmh"),
                    "occupancy_pct": pos.get("occupancy_pct"),
                    "recorded_at": pos.get("recorded_at"),
                }
            )

        await _cache_set(cache_key, result, CACHE_TTL_VEHICLES)
        return result

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
