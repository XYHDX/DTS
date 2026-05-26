from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.core.auth import CurrentUser, optional_auth
from api.core.cache import (
    CACHE_KEY_STATS,
    CACHE_TTL_STATS,
    _cache_get,
    _cache_set,
    _tenant_cache_key,
)
from api.core.database import _supabase_get
from api.core.tenancy import _op_filter, _resolve_operator_id
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/stats", response_model=dict, tags=["stats"])
async def get_fleet_stats(
    operator: Optional[str] = Query(None, description="Operator slug"),
    current_user: Optional[CurrentUser] = Depends(optional_auth),
):
    """Get fleet statistics and real-time metrics."""
    try:
        if current_user and current_user.role == "super_admin":
            op_id = await _resolve_operator_id(operator) if operator else None
        elif current_user and current_user.operator_id:
            op_id = current_user.operator_id
        else:
            op_id = await _resolve_operator_id(operator) if operator else None

        cache_key = _tenant_cache_key(CACHE_KEY_STATS, op_id or "all")
        cached = await _cache_get(cache_key)
        if cached is not None:
            return cached

        op_suffix = f"&{_op_filter(op_id)}" if op_id else ""

        vehicles = await _supabase_get(
            f"vehicles?is_active=eq.true&select=id,status{op_suffix}"
        )
        active_count = (
            len([v for v in vehicles if v.get("status") == "active"]) if vehicles else 0
        )
        idle_count = (
            len([v for v in vehicles if v.get("status") == "idle"]) if vehicles else 0
        )
        maintenance_count = (
            len([v for v in vehicles if v.get("status") == "maintenance"])
            if vehicles
            else 0
        )

        routes = await _supabase_get(f"routes?is_active=eq.true&select=id{op_suffix}")
        stops = await _supabase_get(f"stops?is_active=eq.true&select=id{op_suffix}")
        drivers = await _supabase_get(
            f"users?role=eq.driver&select=id,is_active{op_suffix}"
        )
        active_drivers = (
            len([d for d in drivers if d.get("is_active")]) if drivers else 0
        )

        positions = await _supabase_get(
            f"vehicle_positions_latest?select=occupancy_pct{op_suffix}"
        )
        occupancy_values = [
            p["occupancy_pct"] for p in positions if p.get("occupancy_pct") is not None
        ]
        avg_occupancy = (
            sum(occupancy_values) / len(occupancy_values) if occupancy_values else None
        )

        result = {
            "total_vehicles": len(vehicles),
            "active_vehicles": active_count,
            "idle_vehicles": idle_count,
            "maintenance_vehicles": maintenance_count,
            "total_routes": len(routes),
            "total_stops": len(stops),
            "total_drivers": len(drivers),
            "active_drivers": active_drivers,
            "avg_occupancy_pct": round(avg_occupancy, 1) if avg_occupancy else None,
            "timestamp": datetime.utcnow().isoformat(),
        }

        await _cache_set(cache_key, result, CACHE_TTL_STATS)
        return result

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


def _build_driver_metrics(
    driver: dict, driver_trips: list, positions_by_vehicle: dict
) -> dict:
    """Compute per-driver metrics from trip and position data."""
    on_time_values = [
        t["on_time_pct"] for t in driver_trips if t.get("on_time_pct") is not None
    ]
    speed_values = [
        t["speed_kmh"] for t in driver_trips if t.get("speed_kmh") is not None
    ]
    total_distance = round(sum(t.get("distance_km") or 0 for t in driver_trips), 1)

    # Active hours: sum of trip durations derived from actual_start / actual_end
    active_seconds = 0
    for t in driver_trips:
        if t.get("actual_start") and t.get("actual_end"):
            try:
                s = datetime.fromisoformat(t["actual_start"].replace("Z", "+00:00"))
                e = datetime.fromisoformat(t["actual_end"].replace("Z", "+00:00"))
                active_seconds += max(0, (e - s).total_seconds())
            except (ValueError, AttributeError):
                pass

    # Live position speed for current idle vs active inference
    vehicle_id = driver.get("vehicle_id")
    live_pos = positions_by_vehicle.get(vehicle_id) if vehicle_id else None
    live_speed = live_pos.get("speed_kmh") if live_pos else None

    return {
        "driver_id": driver["id"],
        "name": driver.get("full_name_ar") or driver.get("full_name"),
        "is_active": driver.get("is_active", False),
        "total_trips": len(driver_trips),
        "on_time_pct": round(sum(on_time_values) / len(on_time_values), 1)
        if on_time_values
        else None,
        "avg_speed_kmh": round(sum(speed_values) / len(speed_values), 1)
        if speed_values
        else None,
        "total_distance_km": total_distance,
        "active_hours": round(active_seconds / 3600, 1),
        "current_speed_kmh": live_speed,
    }


@router.get("/api/stats/drivers", response_model=list, tags=["stats"])
async def get_driver_stats(
    operator: Optional[str] = Query(None, description="Operator slug"),
    days: int = Query(30, ge=1, le=90, description="Lookback window in days"),
    current_user: Optional[CurrentUser] = Depends(optional_auth),
):
    """Get per-driver performance metrics (public read access)."""
    try:
        if current_user and current_user.role == "super_admin":
            op_id = await _resolve_operator_id(operator) if operator else None
        elif current_user and current_user.operator_id:
            op_id = current_user.operator_id
        else:
            op_id = await _resolve_operator_id(operator) if operator else None

        op_suffix = f"&{_op_filter(op_id)}" if op_id else ""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        drivers, trips, positions = await _gather_driver_data(op_suffix, cutoff)

        positions_by_vehicle = {
            p["vehicle_id"]: p for p in positions if p.get("vehicle_id")
        }

        # Enrich drivers with their assigned vehicle id from positions lookup
        vehicle_rows = await _supabase_get(
            f"vehicles?select=id,assigned_driver_id{op_suffix}"
        )
        vehicle_by_driver = {
            v["assigned_driver_id"]: v["id"]
            for v in vehicle_rows
            if v.get("assigned_driver_id")
        }
        for d in drivers:
            d["vehicle_id"] = vehicle_by_driver.get(d["id"])

        trip_map: dict = defaultdict(list)
        for t in trips:
            if t.get("driver_id"):
                trip_map[t["driver_id"]].append(t)

        result = [
            _build_driver_metrics(d, trip_map.get(d["id"], []), positions_by_vehicle)
            for d in drivers
        ]
        result.sort(key=lambda x: x["total_trips"], reverse=True)
        return result

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/api/stats/drivers/{driver_id}", response_model=dict, tags=["stats"])
async def get_driver_detail(
    driver_id: str,
    operator: Optional[str] = Query(None, description="Operator slug"),
    current_user: Optional[CurrentUser] = Depends(optional_auth),
):
    """Get detailed performance metrics for a single driver."""
    try:
        if current_user and current_user.role == "super_admin":
            op_id = await _resolve_operator_id(operator) if operator else None
        elif current_user and current_user.operator_id:
            op_id = current_user.operator_id
        else:
            op_id = await _resolve_operator_id(operator) if operator else None

        op_suffix = f"&{_op_filter(op_id)}" if op_id else ""

        driver_rows = await _supabase_get(
            f"users?id=eq.{driver_id}&role=eq.driver&select=id,full_name,full_name_ar,is_active{op_suffix}"
        )
        if not driver_rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found"
            )
        driver = driver_rows[0]

        # Fetch trips for last 30 days (detail view)
        cutoff_30 = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        trips_30 = await _supabase_get(
            f"trips?driver_id=eq.{driver_id}&status=eq.completed&actual_start=gte.{cutoff_30}"
            f"&select=id,on_time_pct,distance_km,speed_kmh,actual_start,actual_end{op_suffix}"
        )

        # Fetch daily trip counts for last 30 days (sparkline data)
        daily_counts: dict = defaultdict(int)
        for t in trips_30:
            if t.get("actual_start"):
                try:
                    day = t["actual_start"][:10]
                    daily_counts[day] += 1
                except Exception:
                    pass

        sparkline_30 = []
        today = datetime.now(timezone.utc).date()
        for i in range(30):
            day = (today - timedelta(days=29 - i)).isoformat()
            sparkline_30.append({"date": day, "trips": daily_counts.get(day, 0)})

        # 7-day sparkline subset
        sparkline_7 = sparkline_30[-7:]

        # Get live position
        vehicle_rows = await _supabase_get(
            f"vehicles?assigned_driver_id=eq.{driver_id}&select=id{op_suffix}"
        )
        vehicle_id = vehicle_rows[0]["id"] if vehicle_rows else None
        driver["vehicle_id"] = vehicle_id

        positions = (
            await _supabase_get(
                f"vehicle_positions_latest?select=vehicle_id,speed_kmh{op_suffix}"
            )
            if vehicle_id
            else []
        )
        positions_by_vehicle = {
            p["vehicle_id"]: p for p in positions if p.get("vehicle_id")
        }

        metrics = _build_driver_metrics(driver, trips_30, positions_by_vehicle)
        metrics["sparkline_7d"] = sparkline_7
        metrics["sparkline_30d"] = sparkline_30
        return metrics

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


async def _gather_driver_data(op_suffix: str, cutoff: str):
    """Fetch drivers, trips, and live positions concurrently."""
    import asyncio

    drivers_task = _supabase_get(
        f"users?role=eq.driver&select=id,full_name,full_name_ar,is_active{op_suffix}"
    )
    trips_task = _supabase_get(
        f"trips?status=eq.completed&actual_start=gte.{cutoff}"
        f"&select=driver_id,on_time_pct,distance_km,speed_kmh,actual_start,actual_end{op_suffix}"
    )
    positions_task = _supabase_get(
        f"vehicle_positions_latest?select=vehicle_id,speed_kmh{op_suffix}"
    )
    drivers, trips, positions = await asyncio.gather(
        drivers_task, trips_task, positions_task
    )
    return drivers or [], trips or [], positions or []
