import asyncio
import csv
import io
import math
import os
import random
import sys
import time
import urllib.parse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from api.core.auth import CurrentUser, hash_password, require_role
from api.core.database import (
    _service_get,
    _service_rpc,
    _supabase_get,
    _supabase_patch,
    _supabase_post,
)
from api.core.geo import parse_location
from api.core.tenancy import _op_filter
from api.models.schemas import (
    AlertResponse,
    AlertResolve,
    AnalyticsOverview,
    NotificationTestRequest,
    StatusTimestampResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
    VehicleAssign,
    VehicleCreate,
    VehicleResponse,
    VehicleUpdate,
)
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
try:
    from lib.email import _alert_html, _send, send_alert_email, send_welcome_email

    _email_available = True
except ImportError:
    _email_available = False

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Users ──────────────────────────────────────────────────────────────────────


@router.get("/api/admin/users", response_model=List[UserResponse], tags=["admin"])
async def list_users(
    current_user: CurrentUser = Depends(
        require_role("admin", "dispatcher", "super_admin")
    ),
):
    """List all users scoped to the current operator."""
    try:
        query = "users?select=*"
        if current_user.role != "super_admin" and current_user.operator_id:
            query += f"&{_op_filter(current_user.operator_id)}"
        users = await _supabase_get(query)

        return [
            UserResponse(
                id=u["id"],
                email=u["email"],
                full_name=u["full_name"],
                full_name_ar=u.get("full_name_ar"),
                role=u["role"],
                phone=u.get("phone"),
                is_active=u["is_active"],
                created_at=u.get("created_at"),
            )
            for u in users
        ]

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/api/admin/users", response_model=UserResponse, tags=["admin"])
async def create_user(
    user_data: UserCreate,
    current_user: CurrentUser = Depends(require_role("admin")),
):
    """Create a new user (admin only)."""
    try:
        existing = await _supabase_get(
            f"users?email=eq.{urllib.parse.quote(user_data.email, safe='')}&select=id"
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Email already exists"
            )

        new_user = {
            "email": user_data.email,
            "password_hash": hash_password(user_data.password),
            "full_name": user_data.full_name,
            "full_name_ar": user_data.full_name_ar,
            "role": user_data.role,
            "phone": user_data.phone,
            "is_active": True,
            "operator_id": current_user.operator_id,
        }

        result = await _supabase_post("users", new_user)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user",
            )

        created_user = (
            result if isinstance(result, dict) else result[0] if result else {}
        )

        if _email_available:
            asyncio.create_task(
                send_welcome_email(
                    full_name=created_user.get("full_name", ""),
                    email=created_user.get("email", ""),
                    role=created_user.get("role", ""),
                )
            )

        return UserResponse(
            id=created_user.get("id"),
            email=created_user.get("email"),
            full_name=created_user.get("full_name"),
            full_name_ar=created_user.get("full_name_ar"),
            role=created_user.get("role"),
            phone=created_user.get("phone"),
            is_active=created_user.get("is_active"),
        )

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put("/api/admin/users/{user_id}", response_model=UserResponse, tags=["admin"])
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    current_user: CurrentUser = Depends(require_role("admin")),
):
    """Update user details."""
    try:
        update_dict = {}
        if user_data.full_name is not None:
            update_dict["full_name"] = user_data.full_name
        if user_data.full_name_ar is not None:
            update_dict["full_name_ar"] = user_data.full_name_ar
        if user_data.phone is not None:
            update_dict["phone"] = user_data.phone
        if user_data.is_active is not None:
            update_dict["is_active"] = user_data.is_active

        if not update_dict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update"
            )

        result = await _supabase_patch(f"users?id=eq.{user_id}", update_dict)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        updated_user = result[0] if result else {}
        return UserResponse(
            id=updated_user.get("id"),
            email=updated_user.get("email"),
            full_name=updated_user.get("full_name"),
            full_name_ar=updated_user.get("full_name_ar"),
            role=updated_user.get("role"),
            phone=updated_user.get("phone"),
            is_active=updated_user.get("is_active"),
        )

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ── Vehicles ───────────────────────────────────────────────────────────────────


@router.get("/api/admin/vehicles", response_model=List[VehicleResponse], tags=["admin"])
async def list_all_vehicles(
    current_user: CurrentUser = Depends(
        require_role("admin", "dispatcher", "super_admin")
    ),
):
    """List all vehicles including inactive ones, scoped to current operator."""
    try:
        query = "vehicle_positions_latest?select=*,vehicles(*)"
        if current_user.role != "super_admin" and current_user.operator_id:
            query += f"&{_op_filter(current_user.operator_id)}"
        positions = await _supabase_get(query)

        result = []
        for v in positions or []:
            if not v.get("vehicles"):
                continue
            lat, lon = parse_location(v.get("location"))
            result.append(
                VehicleResponse(
                    id=v["vehicles"]["id"],
                    vehicle_id=v["vehicles"]["vehicle_id"],
                    name=v["vehicles"]["name"],
                    name_ar=v["vehicles"]["name_ar"],
                    vehicle_type=v["vehicles"]["vehicle_type"],
                    capacity=v["vehicles"]["capacity"],
                    status=v["vehicles"]["status"],
                    assigned_route_id=v["vehicles"].get("assigned_route_id"),
                    latitude=lat,
                    longitude=lon,
                    speed_kmh=v.get("speed_kmh"),
                    occupancy_pct=v.get("occupancy_pct"),
                    recorded_at=v.get("recorded_at"),
                )
            )
        return result

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/api/admin/vehicles", response_model=VehicleResponse, tags=["admin"])
async def create_vehicle(
    vehicle_data: VehicleCreate,
    current_user: CurrentUser = Depends(require_role("admin")),
):
    """Create a new vehicle."""
    try:
        new_vehicle = {
            "vehicle_id": vehicle_data.vehicle_id,
            "name": vehicle_data.name,
            "name_ar": vehicle_data.name_ar,
            "vehicle_type": vehicle_data.vehicle_type,
            "capacity": vehicle_data.capacity,
            "status": "idle",
            "gps_device_id": vehicle_data.gps_device_id,
            "is_real_gps": vehicle_data.is_real_gps,
            "is_active": True,
            "operator_id": current_user.operator_id,
        }

        result = await _supabase_post("vehicles", new_vehicle)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create vehicle",
            )

        created = result if isinstance(result, dict) else result[0] if result else {}
        return VehicleResponse(
            id=created.get("id"),
            vehicle_id=created.get("vehicle_id"),
            name=created.get("name"),
            name_ar=created.get("name_ar"),
            vehicle_type=created.get("vehicle_type"),
            capacity=created.get("capacity"),
            status=created.get("status"),
        )

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put(
    "/api/admin/vehicles/{vehicle_id}", response_model=VehicleResponse, tags=["admin"]
)
async def update_vehicle(
    vehicle_id: str,
    vehicle_data: VehicleUpdate,
    current_user: CurrentUser = Depends(require_role("admin")),
):
    """Update vehicle details."""
    try:
        update_dict = {}
        if vehicle_data.name is not None:
            update_dict["name"] = vehicle_data.name
        if vehicle_data.name_ar is not None:
            update_dict["name_ar"] = vehicle_data.name_ar
        if vehicle_data.capacity is not None:
            update_dict["capacity"] = vehicle_data.capacity
        if vehicle_data.status is not None:
            update_dict["status"] = vehicle_data.status

        if not update_dict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update"
            )

        result = await _supabase_patch(f"vehicles?id=eq.{vehicle_id}", update_dict)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found"
            )

        updated = result[0] if result else {}
        return VehicleResponse(
            id=updated.get("id"),
            vehicle_id=updated.get("vehicle_id"),
            name=updated.get("name"),
            name_ar=updated.get("name_ar"),
            vehicle_type=updated.get("vehicle_type"),
            capacity=updated.get("capacity"),
            status=updated.get("status"),
        )

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/api/admin/vehicles/{vehicle_id}/assign",
    response_model=StatusTimestampResponse,
    tags=["admin"],
)
async def assign_vehicle(
    vehicle_id: str,
    assignment: VehicleAssign,
    current_user: CurrentUser = Depends(require_role("admin", "dispatcher")),
):
    """Assign vehicle to route and driver."""
    try:
        update_data = {
            "assigned_route_id": assignment.route_id,
            "assigned_driver_id": assignment.driver_id,
        }
        result = await _supabase_patch(f"vehicles?id=eq.{vehicle_id}", update_data)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found"
            )

        audit_entry = {
            "admin_id": current_user.user_id,
            "action": "vehicle_assigned",
            "details": f"Vehicle {vehicle_id} assigned to route {assignment.route_id}, driver {assignment.driver_id}",
        }
        await _supabase_post("audit_log", audit_entry)

        return {"status": "success", "timestamp": datetime.utcnow().isoformat()}

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ── Alerts ─────────────────────────────────────────────────────────────────────


@router.get("/api/admin/alerts", response_model=List[AlertResponse], tags=["admin"])
async def list_all_alerts(
    current_user: CurrentUser = Depends(
        require_role("admin", "dispatcher", "super_admin")
    ),
):
    """Get all alerts (resolved and unresolved), scoped to current operator."""
    try:
        query = "alerts?select=*&order=created_at.desc"
        if current_user.role != "super_admin" and current_user.operator_id:
            query += f"&{_op_filter(current_user.operator_id)}"
        alerts = await _supabase_get(query)

        return [
            AlertResponse(
                id=a["id"],
                vehicle_id=a["vehicle_id"],
                alert_type=a["alert_type"],
                severity=a["severity"],
                title=a["title"],
                title_ar=a["title_ar"],
                description=a.get("description"),
                is_resolved=a["is_resolved"],
                created_at=a["created_at"],
            )
            for a in alerts
        ]

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put(
    "/api/admin/alerts/{alert_id}/resolve",
    response_model=StatusTimestampResponse,
    tags=["admin"],
)
async def resolve_alert(
    alert_id: str,
    alert_data: AlertResolve,
    current_user: CurrentUser = Depends(require_role("admin", "dispatcher")),
):
    """Resolve or unresolve an alert."""
    try:
        update_data = {
            "is_resolved": alert_data.resolved,
            "resolved_at": datetime.utcnow().isoformat()
            if alert_data.resolved
            else None,
        }
        result = await _supabase_patch(f"alerts?id=eq.{alert_id}", update_data)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found"
            )

        return {"status": "success", "timestamp": datetime.utcnow().isoformat()}

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ── Trips ──────────────────────────────────────────────────────────────────────


@router.get("/api/admin/trips", response_model=List[dict], tags=["admin"])
async def list_trips(
    vehicle_id: Optional[str] = None,
    driver_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    current_user: CurrentUser = Depends(
        require_role("admin", "dispatcher", "super_admin")
    ),
):
    """List trips with optional filtering, scoped to current operator."""
    try:
        params = []
        if vehicle_id:
            params.append(f"vehicle_id=eq.{urllib.parse.quote(vehicle_id, safe='')}")
        if driver_id:
            params.append(f"driver_id=eq.{urllib.parse.quote(driver_id, safe='')}")
        if status_filter:
            params.append(f"status=eq.{urllib.parse.quote(status_filter, safe='')}")
        if current_user.role != "super_admin" and current_user.operator_id:
            params.append(_op_filter(current_user.operator_id))

        query = "trips?select=*&order=created_at.desc"
        if params:
            query = f"trips?{'&'.join(params)}&select=*&order=created_at.desc"

        result = await _supabase_get(query)
        return result or []

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ── Analytics ──────────────────────────────────────────────────────────────────


@router.get(
    "/api/admin/analytics/overview", response_model=AnalyticsOverview, tags=["admin"]
)
async def get_analytics_overview(
    current_user: CurrentUser = Depends(
        require_role("admin", "dispatcher", "super_admin")
    ),
):
    """Get fleet analytics overview for dashboard."""
    try:
        op_suffix = (
            f"&{_op_filter(current_user.operator_id)}"
            if current_user.role != "super_admin" and current_user.operator_id
            else ""
        )

        vehicles = await _supabase_get(f"vehicles?select=status{op_suffix}")
        active_vehicles = len([v for v in vehicles if v.get("status") == "active"])
        idle_vehicles = len([v for v in vehicles if v.get("status") == "idle"])
        maintenance_vehicles = len(
            [v for v in vehicles if v.get("status") == "maintenance"]
        )

        routes = await _supabase_get(f"routes?is_active=eq.true&select=id{op_suffix}")
        stops = await _supabase_get(f"stops?is_active=eq.true&select=id{op_suffix}")
        drivers = await _supabase_get(
            f"users?role=eq.driver&select=is_active{op_suffix}"
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

        return AnalyticsOverview(
            total_vehicles=len(vehicles),
            active_vehicles=active_vehicles,
            idle_vehicles=idle_vehicles,
            maintenance_vehicles=maintenance_vehicles,
            total_routes=len(routes),
            active_routes=len(routes),
            total_stops=len(stops),
            total_drivers=len(drivers),
            active_drivers=active_drivers,
            avg_occupancy_pct=round(avg_occupancy, 1) if avg_occupancy else None,
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/api/admin/analytics/fleet-utilization", tags=["admin"])
async def get_fleet_utilization(
    current_user: CurrentUser = Depends(
        require_role("admin", "dispatcher", "super_admin")
    ),
):
    """Get fleet utilization over the last 24 hours, bucketed by hour."""
    try:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=24)

        op_suffix = (
            f"&{_op_filter(current_user.operator_id)}"
            if current_user.role != "super_admin" and current_user.operator_id
            else ""
        )

        vehicles = await _supabase_get(f"vehicles?select=id,status{op_suffix}")
        total_vehicles = len(vehicles)

        trips = await _supabase_get(
            f"trips?actual_start=gte.{cutoff.isoformat()}&select=actual_start,actual_end,vehicle_id{op_suffix}"
        )

        hours = []
        for h in range(23, -1, -1):
            bucket_start = now - timedelta(hours=h + 1)
            bucket_end = now - timedelta(hours=h)
            label = bucket_start.strftime("%H:%M")

            active_ids = set()
            for t in trips:
                t_start_str = t.get("actual_start")
                t_end_str = t.get("actual_end")
                if not t_start_str:
                    continue
                try:
                    t_start = datetime.fromisoformat(t_start_str.replace("Z", "+00:00"))
                    t_end = (
                        datetime.fromisoformat(t_end_str.replace("Z", "+00:00"))
                        if t_end_str
                        else now
                    )
                    if t_start < bucket_end and t_end > bucket_start:
                        active_ids.add(t.get("vehicle_id"))
                except (ValueError, TypeError):
                    continue

            active = len(active_ids)
            idle = max(0, total_vehicles - active)
            hours.append({"hour": label, "active": active, "idle": idle})

        return {"hours": hours, "total": total_vehicles}

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/api/admin/analytics/route-performance", tags=["admin"])
async def get_route_performance(
    current_user: CurrentUser = Depends(
        require_role("admin", "dispatcher", "super_admin")
    ),
):
    """Get per-route performance based on completed trips in the last 7 days."""
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

        op_suffix = (
            f"&{_op_filter(current_user.operator_id)}"
            if current_user.role != "super_admin" and current_user.operator_id
            else ""
        )

        routes = await _supabase_get(
            f"routes?is_active=eq.true&select=id,name,name_ar,distance_km{op_suffix}"
        )
        trips = await _supabase_get(
            f"trips?status=eq.completed&actual_start=gte.{cutoff}"
            f"&select=route_id,on_time_pct,scheduled_start,actual_start{op_suffix}"
        )

        route_trips: dict = defaultdict(list)
        for t in trips:
            route_trips[t["route_id"]].append(t)

        result = []
        for r in routes:
            rt = route_trips.get(r["id"], [])
            trip_count = len(rt)

            on_time_values = [
                t["on_time_pct"] for t in rt if t.get("on_time_pct") is not None
            ]
            avg_on_time = (
                round(sum(on_time_values) / len(on_time_values), 1)
                if on_time_values
                else None
            )

            delays = []
            for t in rt:
                if t.get("scheduled_start") and t.get("actual_start"):
                    try:
                        sched = datetime.fromisoformat(
                            t["scheduled_start"].replace("Z", "+00:00")
                        )
                        actual = datetime.fromisoformat(
                            t["actual_start"].replace("Z", "+00:00")
                        )
                        delays.append((actual - sched).total_seconds() / 60)
                    except (ValueError, TypeError):
                        pass

            avg_delay = round(sum(delays) / len(delays), 1) if delays else None

            result.append(
                {
                    "route_id": r["id"],
                    "name": r.get("name_ar") or r.get("name"),
                    "trip_count": trip_count,
                    "on_time_pct": avg_on_time,
                    "avg_delay_min": avg_delay,
                    "distance_km": r.get("distance_km"),
                }
            )

        result.sort(key=lambda x: x["trip_count"], reverse=True)
        return result

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/api/admin/analytics/driver-scoreboard", tags=["admin"])
async def get_driver_scoreboard(
    current_user: CurrentUser = Depends(
        require_role("admin", "dispatcher", "super_admin")
    ),
):
    """Get driver scoreboard based on completed trips in the last 30 days."""
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

        op_suffix = (
            f"&{_op_filter(current_user.operator_id)}"
            if current_user.role != "super_admin" and current_user.operator_id
            else ""
        )

        drivers = await _supabase_get(
            f"users?role=eq.driver&select=id,full_name,full_name_ar,is_active{op_suffix}"
        )
        trips = await _supabase_get(
            f"trips?status=eq.completed&actual_start=gte.{cutoff}"
            f"&select=driver_id,on_time_pct,distance_km{op_suffix}"
        )

        driver_trips: dict = defaultdict(list)
        for t in trips:
            if t.get("driver_id"):
                driver_trips[t["driver_id"]].append(t)

        result = []
        for d in drivers:
            dt = driver_trips.get(d["id"], [])
            on_time_values = [
                t["on_time_pct"] for t in dt if t.get("on_time_pct") is not None
            ]
            avg_adherence = (
                round(sum(on_time_values) / len(on_time_values), 1)
                if on_time_values
                else None
            )
            total_km = round(sum(t.get("distance_km") or 0 for t in dt), 1)

            result.append(
                {
                    "driver_id": d["id"],
                    "name": d.get("full_name_ar") or d.get("full_name"),
                    "is_active": d.get("is_active", False),
                    "trips_completed": len(dt),
                    "avg_adherence_pct": avg_adherence,
                    "total_km": total_km,
                }
            )

        result.sort(key=lambda x: x["trips_completed"], reverse=True)
        return result

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/api/admin/analytics/gps-heatmap", tags=["admin"])
async def get_gps_heatmap(
    current_user: CurrentUser = Depends(
        require_role("admin", "dispatcher", "super_admin")
    ),
):
    """Get GPS position data for heatmap visualization."""
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

        op_suffix = (
            f"&{_op_filter(current_user.operator_id)}"
            if current_user.role != "super_admin" and current_user.operator_id
            else ""
        )

        positions = await _supabase_get(
            f"vehicle_positions?recorded_at=gte.{cutoff}"
            f"&select=location,speed_kmh&order=recorded_at.desc&limit=2000{op_suffix}"
        )

        features = []

        def _parse_loc(loc, weight):
            if isinstance(loc, dict):
                coords = loc.get("coordinates", [])
                if len(coords) >= 2:
                    return {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [coords[0], coords[1]],
                        },
                        "properties": {"weight": weight},
                    }
            elif isinstance(loc, str) and loc.startswith("POINT"):
                inner = loc.replace("POINT(", "").replace(")", "").strip()
                parts = inner.split()
                if len(parts) == 2:
                    return {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [float(parts[0]), float(parts[1])],
                        },
                        "properties": {"weight": weight},
                    }
            return None

        for p in positions:
            loc = p.get("location")
            if not loc:
                continue
            try:
                feat = _parse_loc(loc, 1)
                if feat:
                    features.append(feat)
            except (ValueError, TypeError, AttributeError):
                continue

        latest = await _supabase_get(
            f"vehicle_positions_latest?select=location,speed_kmh{op_suffix}"
        )
        for p in latest:
            loc = p.get("location")
            if not loc:
                continue
            try:
                feat = _parse_loc(loc, 3)
                if feat:
                    features.append(feat)
            except (ValueError, TypeError, AttributeError):
                continue

        return {
            "type": "FeatureCollection",
            "features": features,
            "count": len(features),
        }

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ── Simulator ──────────────────────────────────────────────────────────────────


def _interpolate_position(stops: list, progress: float) -> tuple:
    """Interpolate lat/lon/heading along a sequence of stop coordinates."""
    if not stops or len(stops) < 2:
        return (33.5105, 36.3025, 0)

    if progress > 1.0:
        progress = 2.0 - progress
        stops = list(reversed(stops))

    n_segments = len(stops) - 1
    seg_progress = progress * n_segments
    seg_idx = min(int(seg_progress), n_segments - 1)
    t = seg_progress - seg_idx

    a, b = stops[seg_idx], stops[seg_idx + 1]
    lat = a["lat"] + (b["lat"] - a["lat"]) * t
    lon = a["lon"] + (b["lon"] - a["lon"]) * t

    lat += random.uniform(-0.00015, 0.00015)
    lon += random.uniform(-0.00015, 0.00015)

    d_lon = b["lon"] - a["lon"]
    d_lat = b["lat"] - a["lat"]
    heading = math.degrees(math.atan2(d_lon, d_lat)) % 360

    return (round(lat, 6), round(lon, 6), round(heading, 1))


async def _run_simulation() -> dict:
    """Core simulation logic — generates positions for all active vehicles."""
    vehicles = await _service_get(
        "vehicles?status=in.(active,idle)&assigned_route_id=not.is.null"
        "&select=id,vehicle_id,assigned_route_id,vehicle_type"
    )

    if not vehicles:
        return {"status": "no_vehicles", "updated": 0}

    route_ids = list({v["assigned_route_id"] for v in vehicles})

    route_stops_map: dict = {}
    for rid in route_ids:
        rows = await _service_get(
            f"route_stops?route_id=eq.{rid}"
            f"&select=stop_sequence,stops(stop_id,location)"
            f"&order=stop_sequence.asc"
        )
        stops = []
        for row in rows:
            stop_data = row.get("stops")
            if not stop_data:
                continue
            loc = stop_data.get("location")
            if not loc:
                continue
            lat, lon = None, None
            if isinstance(loc, dict):
                coords = loc.get("coordinates", [])
                if len(coords) >= 2:
                    lon, lat = coords[0], coords[1]
            elif isinstance(loc, str) and "POINT" in loc:
                inner = loc.replace("POINT(", "").replace(")", "").strip()
                parts = inner.split()
                if len(parts) == 2:
                    lon, lat = float(parts[0]), float(parts[1])
            if lat is not None and lon is not None:
                stops.append({"lat": lat, "lon": lon})
        route_stops_map[rid] = stops

    now = time.time()
    cycle_seconds = 1800
    updated = []

    for i, vehicle in enumerate(vehicles):
        rid = vehicle["assigned_route_id"]
        stops = route_stops_map.get(rid, [])
        if len(stops) < 2:
            continue

        phase = (i * 137) % cycle_seconds
        progress = ((now + phase) % cycle_seconds) / (cycle_seconds / 2)
        progress = progress % 2.0

        lat, lon, heading = _interpolate_position(stops, progress)

        base_speed = {"bus": 30, "microbus": 25, "taxi": 40}.get(
            vehicle.get("vehicle_type", "bus"), 30
        )
        speed = round(base_speed + random.uniform(-5, 5), 1)
        occupancy = random.randint(15, 85)

        await _service_rpc(
            "upsert_vehicle_position",
            {
                "p_vehicle_id": vehicle["id"],
                "p_lat": lat,
                "p_lon": lon,
                "p_speed": speed,
                "p_heading": heading,
                "p_source": "simulator",
                "p_route_id": rid,
                "p_occupancy": occupancy,
            },
        )

        updated.append(
            {
                "vehicle_id": vehicle["vehicle_id"],
                "lat": lat,
                "lon": lon,
                "speed_kmh": speed,
                "heading": heading,
            }
        )

    return {
        "status": "success",
        "updated": len(updated),
        "vehicles": updated,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post(
    "/api/admin/simulate", response_model=StatusTimestampResponse, tags=["admin"]
)
async def simulate_vehicle_positions(
    current_user: CurrentUser = Depends(require_role("admin", "super_admin")),
):
    """Generate simulated GPS positions (admin JWT auth)."""
    return await _run_simulation()


# ── Data Exports ───────────────────────────────────────────────────────────────


def _csv_response(rows: list, filename: str) -> StreamingResponse:
    """Build a streaming CSV response from a list of dicts."""
    if not rows:
        output = io.StringIO()
        output.write("")
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/api/admin/export/vehicles.csv", tags=["admin"])
async def export_vehicles_csv(
    current_user: CurrentUser = Depends(
        require_role("admin", "dispatcher", "super_admin")
    ),
):
    """Export all vehicles as CSV."""
    try:
        op_suffix = (
            f"&{_op_filter(current_user.operator_id)}"
            if current_user.role != "super_admin" and current_user.operator_id
            else ""
        )
        vehicles = await _supabase_get(f"vehicles?select=*{op_suffix}")
        rows = [
            {
                "vehicle_id": v.get("vehicle_id", ""),
                "name": v.get("name", ""),
                "name_ar": v.get("name_ar", ""),
                "vehicle_type": v.get("vehicle_type", ""),
                "capacity": v.get("capacity", ""),
                "status": v.get("status", ""),
                "assigned_route_id": v.get("assigned_route_id", ""),
                "gps_device_id": v.get("gps_device_id", ""),
                "is_active": v.get("is_active", ""),
                "created_at": v.get("created_at", ""),
            }
            for v in (vehicles or [])
        ]
        return _csv_response(rows, "vehicles.csv")
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/admin/export/trips.csv", tags=["admin"])
async def export_trips_csv(
    current_user: CurrentUser = Depends(
        require_role("admin", "dispatcher", "super_admin")
    ),
):
    """Export trips from the last 30 days as CSV."""
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        op_suffix = (
            f"&{_op_filter(current_user.operator_id)}"
            if current_user.role != "super_admin" and current_user.operator_id
            else ""
        )
        trips = await _supabase_get(
            f"trips?actual_start=gte.{cutoff}&select=*&order=actual_start.desc{op_suffix}"
        )
        rows = [
            {
                "id": t.get("id", ""),
                "vehicle_id": t.get("vehicle_id", ""),
                "driver_id": t.get("driver_id", ""),
                "route_id": t.get("route_id", ""),
                "status": t.get("status", ""),
                "scheduled_start": t.get("scheduled_start", ""),
                "actual_start": t.get("actual_start", ""),
                "actual_end": t.get("actual_end", ""),
                "distance_km": t.get("distance_km", ""),
                "on_time_pct": t.get("on_time_pct", ""),
                "passenger_count": t.get("passenger_count", ""),
                "created_at": t.get("created_at", ""),
            }
            for t in (trips or [])
        ]
        return _csv_response(rows, "trips.csv")
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/admin/export/alerts.csv", tags=["admin"])
async def export_alerts_csv(
    current_user: CurrentUser = Depends(
        require_role("admin", "dispatcher", "super_admin")
    ),
):
    """Export all alerts as CSV."""
    try:
        op_suffix = (
            f"&{_op_filter(current_user.operator_id)}"
            if current_user.role != "super_admin" and current_user.operator_id
            else ""
        )
        alerts = await _supabase_get(
            f"alerts?select=*&order=created_at.desc{op_suffix}"
        )
        rows = [
            {
                "id": a.get("id", ""),
                "vehicle_id": a.get("vehicle_id", ""),
                "alert_type": a.get("alert_type", ""),
                "severity": a.get("severity", ""),
                "title": a.get("title", ""),
                "description": a.get("description", ""),
                "is_resolved": a.get("is_resolved", ""),
                "resolved_at": a.get("resolved_at", ""),
                "created_at": a.get("created_at", ""),
            }
            for a in (alerts or [])
        ]
        return _csv_response(rows, "alerts.csv")
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/admin/export/drivers.csv", tags=["admin"])
async def export_drivers_csv(
    current_user: CurrentUser = Depends(
        require_role("admin", "dispatcher", "super_admin")
    ),
):
    """Export all drivers as CSV."""
    try:
        op_suffix = (
            f"&{_op_filter(current_user.operator_id)}"
            if current_user.role != "super_admin" and current_user.operator_id
            else ""
        )
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        drivers = await _supabase_get(
            f"users?role=eq.driver&select=id,full_name,full_name_ar,email,phone,is_active,created_at{op_suffix}"
        )
        trips = await _supabase_get(
            f"trips?status=eq.completed&actual_start=gte.{cutoff}"
            f"&select=driver_id,on_time_pct,distance_km{op_suffix}"
        )
        driver_trips: dict = defaultdict(list)
        for t in trips or []:
            if t.get("driver_id"):
                driver_trips[t["driver_id"]].append(t)

        rows = []
        for d in drivers or []:
            dt = driver_trips.get(d["id"], [])
            on_time_values = [
                t["on_time_pct"] for t in dt if t.get("on_time_pct") is not None
            ]
            avg_adherence = (
                round(sum(on_time_values) / len(on_time_values), 1)
                if on_time_values
                else None
            )
            total_km = round(sum(t.get("distance_km") or 0 for t in dt), 1)
            rows.append(
                {
                    "id": d.get("id", ""),
                    "full_name": d.get("full_name", ""),
                    "full_name_ar": d.get("full_name_ar", ""),
                    "email": d.get("email", ""),
                    "phone": d.get("phone", ""),
                    "is_active": d.get("is_active", ""),
                    "trips_completed_30d": len(dt),
                    "avg_adherence_pct_30d": avg_adherence
                    if avg_adherence is not None
                    else "",
                    "total_km_30d": total_km,
                    "created_at": d.get("created_at", ""),
                }
            )
        return _csv_response(rows, "drivers.csv")
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/admin/export/route-performance.csv", tags=["admin"])
async def export_route_performance_csv(
    current_user: CurrentUser = Depends(
        require_role("admin", "dispatcher", "super_admin")
    ),
):
    """Export route performance (last 7 days) as CSV."""
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        op_suffix = (
            f"&{_op_filter(current_user.operator_id)}"
            if current_user.role != "super_admin" and current_user.operator_id
            else ""
        )
        routes = await _supabase_get(
            f"routes?is_active=eq.true&select=id,name,name_ar,distance_km{op_suffix}"
        )
        trips = await _supabase_get(
            f"trips?status=eq.completed&actual_start=gte.{cutoff}"
            f"&select=route_id,on_time_pct,scheduled_start,actual_start{op_suffix}"
        )
        route_trips: dict = defaultdict(list)
        for t in trips or []:
            route_trips[t["route_id"]].append(t)

        rows = []
        for r in routes or []:
            rt = route_trips.get(r["id"], [])
            on_time_values = [
                t["on_time_pct"] for t in rt if t.get("on_time_pct") is not None
            ]
            avg_on_time = (
                round(sum(on_time_values) / len(on_time_values), 1)
                if on_time_values
                else None
            )
            delays = []
            for t in rt:
                if t.get("scheduled_start") and t.get("actual_start"):
                    try:
                        sched = datetime.fromisoformat(
                            t["scheduled_start"].replace("Z", "+00:00")
                        )
                        actual = datetime.fromisoformat(
                            t["actual_start"].replace("Z", "+00:00")
                        )
                        delays.append((actual - sched).total_seconds() / 60)
                    except (ValueError, TypeError):
                        pass
            avg_delay = round(sum(delays) / len(delays), 1) if delays else None
            rows.append(
                {
                    "route_id": r.get("id", ""),
                    "name": r.get("name", ""),
                    "name_ar": r.get("name_ar", ""),
                    "distance_km": r.get("distance_km", ""),
                    "trip_count_7d": len(rt),
                    "avg_on_time_pct_7d": avg_on_time
                    if avg_on_time is not None
                    else "",
                    "avg_delay_min_7d": avg_delay if avg_delay is not None else "",
                }
            )
        rows.sort(key=lambda x: x["trip_count_7d"], reverse=True)
        return _csv_response(rows, "route-performance.csv")
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/admin/notifications/test", tags=["admin"])
async def test_notification(
    body: NotificationTestRequest,
    current_user: CurrentUser = Depends(require_role("admin")),
):
    """Send a test email to verify Resend integration is configured."""
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RESEND_API_KEY is not configured on this server.",
        )

    if not _email_available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email library not available.",
        )

    from datetime import datetime as _dt

    if body.kind == "welcome":
        ok = await send_welcome_email(
            full_name="Test User",
            email=body.email,
            role="admin",
        )
    else:
        ok = await send_alert_email(
            alert_type="overspeed",
            severity="high",
            title="Test Alert — Overspeed",
            vehicle_id="test-vehicle-001",
            description="This is a test notification from the Damascus Transit Platform.",
            created_at=_dt.utcnow().isoformat(),
        )
        if not ok:
            html = _alert_html(
                alert_type="overspeed",
                severity="high",
                title="Test Alert — Overspeed",
                vehicle_id="test-vehicle-001",
                description="This is a test notification from the Damascus Transit Platform.",
                created_at=_dt.utcnow().isoformat(),
            )
            ok = await _send(
                to=[body.email],
                subject="[TEST] Transit Alert — Overspeed",
                html=html,
            )

    return {
        "status": "sent" if ok else "failed",
        "kind": body.kind,
        "recipient": body.email,
        "timestamp": _dt.utcnow().isoformat(),
    }
