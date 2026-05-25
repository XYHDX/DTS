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
    _supabase_get,
    _supabase_patch,
    _supabase_post,
    _supabase_rpc,
)
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


@router.post(
    "/api/driver/position", response_model=StatusTimestampResponse, tags=["driver"]
)
async def report_driver_position(
    position: PositionUpdate,
    current_user: CurrentUser = Depends(require_role("driver")),
):
    """Report driver's current position."""
    max_req, window = RATE_LIMIT_DRIVER_POS
    if not await _rate_limit_check(f"drvpos:{current_user.user_id}", max_req, window):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Position update rate limit exceeded.",
        )
    try:
        if current_user.vehicle_id:
            db_vehicle_id = current_user.vehicle_id
            route_id = current_user.vehicle_route_id
        else:
            vehicles = await _supabase_get(
                f"vehicles?assigned_driver_id=eq.{current_user.user_id}&select=id,assigned_route_id"
            )
            if not vehicles:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="No vehicle assigned"
                )
            db_vehicle_id = vehicles[0]["id"]
            route_id = vehicles[0].get("assigned_route_id")

        try:
            await _supabase_rpc(
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
    """Start a new trip for the driver."""
    try:
        vehicles = await _supabase_get(
            f"vehicles?assigned_driver_id=eq.{current_user.user_id}&select=id"
        )
        if not vehicles:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No vehicle assigned"
            )

        vehicle_id = vehicles[0]["id"]
        trip_data = {
            "vehicle_id": vehicle_id,
            "route_id": trip.route_id,
            "driver_id": current_user.user_id,
            "status": "in_progress",
            "scheduled_start": trip.scheduled_departure,
            "actual_start": datetime.utcnow().isoformat(),
            "operator_id": current_user.operator_id,
        }

        result = await _supabase_post("trips", trip_data)
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
        trips = await _supabase_get(
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
        await _supabase_patch(f"trips?id=eq.{trip_id}", update_data)

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
        trips = await _supabase_get(
            f"trips?driver_id=eq.{current_user.user_id}&status=eq.in_progress&select=id"
        )
        if not trips:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No active trip"
            )

        trip_id = trips[0]["id"]
        await _supabase_patch(
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
