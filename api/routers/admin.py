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

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from api.core.auth import CurrentUser, hash_password, require_role
from api.core.database import (
    _service_get,
    _service_patch,
    _service_post,
    _service_rpc,
)
from api.core.geo import parse_location
from api.core.tenancy import _op_filter, ensure_operator_scope
from api.models.schemas import (
    AlertResponse,
    AlertResolve,
    AnalyticsOverview,
    NotificationTestRequest,
    StatusTimestampResponse,
    UserCreate,
    UserResponse,
    RouteCreate,
    RouteUpdate,
    ShamCashSettingsUpdate,
    TripCancel,
    TripDispatch,
    UserUpdate,
    VehicleApprovalRequest,
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


def _own_op_filter(current_user: CurrentUser) -> str:
    """Mutation guard: restrict a PATCH/DELETE to the caller's own tenant.

    Security fix (2026-06-11): admin mutations previously patched rows by
    bare id (`vehicles?id=eq.X`), letting an admin of operator A modify
    operator B's rows by UUID. Every mutation now appends this filter
    (super_admin is exempt).
    """
    if current_user.role != "super_admin" and current_user.operator_id:
        return f"&{_op_filter(current_user.operator_id)}"
    return ""


async def _count_pending_vehicles(op_suffix: str) -> int:
    """Count vehicles awaiting approval, tolerating a pre-migration-019 DB.

    If the `approval_status` column does not exist yet (migration 019 not
    applied), the query errors — we treat that as 'no pending vehicles' so
    the admin dashboard keeps working instead of returning 500.
    """
    try:
        rows = await _service_get(
            f"vehicles?approval_status=eq.pending&select=id{op_suffix}"
        )
        return len(rows or [])
    except Exception:
        return 0


# ── Users ──────────────────────────────────────────────────────────────────────


# Columns added by later DB migrations that an out-of-date database may not
# have yet. If an INSERT fails *because* one of these is missing, we drop it
# and retry so creating a user keeps working (the same graceful degradation
# already used for operators.settings and vehicles.approval_status). All three
# are nullable / defaulted, so omitting one only loses that single attribute.
_USER_OPTIONAL_COLUMNS = ("must_change_password", "full_name_ar", "phone")


def _humanize_db_error(body: str) -> str:
    """Turn a raw PostgREST/Postgres error body into an actionable message."""
    low = (body or "").lower()
    if "duplicate key" in low or "already exists" in low:
        return "Email already exists."
    if "foreign key" in low and "operator" in low:
        return (
            "Your admin account isn't linked to a valid operator, so the new "
            "user can't be saved. Check the account's operator and try again."
        )
    if "invalid input value for enum" in low or "user_role" in low:
        return "Invalid role for the new user."
    reason = (body or "").strip().replace("\n", " ")
    if reason:
        return f"Database rejected the new user: {reason[:200]}"
    return "Database rejected the new user."


async def _insert_user_row(new_user: dict) -> dict:
    """INSERT a user, tolerating an out-of-date database schema.

    On a "column does not exist" error we strip that (optional) column and
    retry, logging a warning so the operator knows a migration is pending.
    Any other DB error is surfaced with its real reason — callers must never
    collapse it into an opaque 500.
    """
    payload = dict(new_user)
    last_body = ""
    for _ in range(len(_USER_OPTIONAL_COLUMNS) + 1):
        try:
            return await _service_post("users", payload)
        except httpx.HTTPStatusError as exc:
            last_body = getattr(exc.response, "text", "") or str(exc)
            missing = next(
                (c for c in _USER_OPTIONAL_COLUMNS if c in payload and c in last_body),
                None,
            )
            if missing is None:
                logger.error("users INSERT failed: %s", last_body[:500])
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=_humanize_db_error(last_body),
                )
            payload.pop(missing, None)
            logger.warning(
                "users INSERT: column %r missing — retrying without it; apply "
                "the pending DB migration. Detail: %s",
                missing,
                last_body[:200],
            )
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=_humanize_db_error(last_body),
    )


@router.get("/api/admin/users", tags=["admin"])
async def list_users(
    page: int | None = None,
    page_size: int = 15,
    current_user: CurrentUser = Depends(
        require_role("admin", "dispatcher", "super_admin")
    ),
):
    """List users scoped to the current operator.

    Without ``page`` it returns the full array (kept for the vehicle form's
    driver dropdown). With ``page`` it returns ONE page only —
    ``{items, page, page_size, has_more}`` — so the Users table never pulls
    the whole table at once.
    """
    try:
        base = "users?select=*"
        if current_user.role != "super_admin" and current_user.operator_id:
            base += f"&{_op_filter(current_user.operator_id)}"
        base += "&order=created_at.desc"

        def _resp(u):
            return UserResponse(
                id=u["id"],
                email=u["email"],
                full_name=u["full_name"],
                full_name_ar=u.get("full_name_ar"),
                role=u["role"],
                phone=u.get("phone"),
                is_active=u["is_active"],
                created_at=u.get("created_at"),
            )

        if page is None:
            users = await _service_get(base)
            return [_resp(u) for u in users]

        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        offset = (page - 1) * page_size
        # Fetch one extra row to learn whether a next page exists (no COUNT).
        rows = await _service_get(base + f"&limit={page_size + 1}&offset={offset}")
        has_more = len(rows) > page_size
        return {
            "items": [_resp(u) for u in rows[:page_size]],
            "page": page,
            "page_size": page_size,
            "has_more": has_more,
        }

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/api/admin/settings", tags=["admin"])
async def get_settings(
    current_user: CurrentUser = Depends(require_role("admin", "super_admin")),
):
    """Dashboard settings (Sham Cash mode + merchant) for the current operator.

    The real secrets live only in server env vars and are never returned; we
    report whether each is present so the UI can warn before switching to live.
    """
    sham = {"mode": "sandbox", "merchant_id": ""}
    if current_user.operator_id:
        # select=* (not select=settings) so a DB without the optional settings
        # column degrades to defaults instead of erroring.
        rows = await _service_get(
            f"operators?id=eq.{urllib.parse.quote(current_user.operator_id, safe='')}&select=*"
        )
        sc = ((rows or [{}])[0].get("settings") or {}).get("sham_cash") or {}
        sham["mode"] = sc.get("mode") or "sandbox"
        sham["merchant_id"] = sc.get("merchant_id") or ""
    return {
        "sham_cash": sham,
        "secrets_present": {
            "qr_signing_secret": bool(os.getenv("QR_SIGNING_SECRET")),
            "api_secret": bool(os.getenv("SHAM_CASH_API_SECRET")),
            "webhook_secret": bool(os.getenv("SHAM_CASH_WEBHOOK_SECRET")),
        },
    }


@router.put("/api/admin/settings", tags=["admin"])
async def update_settings(
    body: ShamCashSettingsUpdate,
    current_user: CurrentUser = Depends(require_role("admin", "super_admin")),
):
    """Persist the Sham Cash mode + merchant ID on the operator (JSONB settings)."""
    if not current_user.operator_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No operator scope for settings.",
        )
    quoted = urllib.parse.quote(current_user.operator_id, safe="")
    rows = await _service_get(f"operators?id=eq.{quoted}&select=*")
    settings = (rows or [{}])[0].get("settings") or {}
    if not isinstance(settings, dict):
        settings = {}
    settings["sham_cash"] = {
        "mode": body.mode,
        "merchant_id": (body.merchant_id or "").strip(),
    }
    try:
        await _service_patch(f"operators?id=eq.{quoted}", {"settings": settings})
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Settings storage isn't available yet. Apply DB migration 023 "
                "(operators.settings column) in Supabase, then save again."
            ),
        )
    return {"status": "saved", "sham_cash": settings["sham_cash"]}


@router.post("/api/admin/users", response_model=UserResponse, tags=["admin"])
async def create_user(
    user_data: UserCreate,
    current_user: CurrentUser = Depends(require_role("admin", "dispatcher")),
):
    """Create a new user.

    Roles: admin may create any non-super_admin account. A dispatcher
    (operator staff) may ONLY create driver accounts — this implements the
    operating model where the operator issues each driver's username and
    password, and the admin later approves the vehicle itself.
    """
    try:
        if current_user.role == "dispatcher" and user_data.role != "driver":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operators (dispatchers) can only create driver accounts.",
            )
        # Defense-in-depth: tie the new account to the caller's tenant.
        ensure_operator_scope(
            current_user.operator_id, current_user.operator_id, current_user.role
        )

        existing = await _service_get(
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
            # Credentials issued by staff must be rotated on first login.
            "must_change_password": True,
        }

        result = await _insert_user_row(new_user)
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
        # Log the real cause so "Internal server error" is never a dead end.
        logger.exception("create_user failed unexpectedly")
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

        result = await _service_patch(
            f"users?id=eq.{urllib.parse.quote(user_id, safe='')}"
            f"{_own_op_filter(current_user)}",
            update_dict,
        )
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
    approval: Optional[str] = None,
    current_user: CurrentUser = Depends(
        require_role("admin", "dispatcher", "super_admin")
    ),
):
    """List all vehicles including inactive ones, scoped to current operator.

    Logic fix (2026-06-11): this used to inner-join from
    vehicle_positions_latest, so vehicles with no GPS fix yet (e.g. every
    newly registered vehicle awaiting approval) were invisible to admins.
    It now reads the vehicles base table and merges positions on top.

    Optional `?approval=pending|approved|rejected|suspended` filter feeds
    the admin approvals queue.
    """
    try:
        op_suffix = ""
        if current_user.role != "super_admin" and current_user.operator_id:
            op_suffix = f"&{_op_filter(current_user.operator_id)}"

        veh_query = "vehicles?select=*&order=created_at.desc" + op_suffix
        if approval in ("pending", "approved", "rejected", "suspended"):
            veh_query += f"&approval_status=eq.{approval}"
        vehicles = await _service_get(veh_query)

        positions = await _service_get(
            "vehicle_positions_latest?select=vehicle_id,location,speed_kmh,"
            "occupancy_pct,recorded_at" + op_suffix
        )
        pos_by_id = {p["vehicle_id"]: p for p in (positions or [])}

        # Resolve assigned drivers in one query (name + email shown in the
        # approvals queue so the admin can verify who the operator assigned).
        driver_ids = [
            v["assigned_driver_id"]
            for v in (vehicles or [])
            if v.get("assigned_driver_id")
        ]
        drivers_by_id = {}
        if driver_ids:
            uniq = ",".join(sorted(set(driver_ids)))
            drivers = await _service_get(
                f"users?id=in.({uniq})&select=id,full_name,full_name_ar,email"
            )
            drivers_by_id = {d["id"]: d for d in (drivers or [])}

        result = []
        for v in vehicles or []:
            pos = pos_by_id.get(v["id"], {})
            lat, lon = parse_location(pos.get("location")) if pos else (None, None)
            drv = drivers_by_id.get(v.get("assigned_driver_id"), {})
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
                    assigned_driver_id=v.get("assigned_driver_id"),
                    latitude=lat,
                    longitude=lon,
                    speed_kmh=pos.get("speed_kmh"),
                    occupancy_pct=pos.get("occupancy_pct"),
                    recorded_at=pos.get("recorded_at"),
                    gps_device_id=v.get("gps_device_id"),
                    is_real_gps=v.get("is_real_gps"),
                    approval_status=v.get("approval_status"),
                    approved_at=v.get("approved_at"),
                    approval_note=v.get("approval_note"),
                    driver_name=drv.get("full_name_ar") or drv.get("full_name"),
                    driver_email=drv.get("email"),
                    created_at=v.get("created_at"),
                )
            )
        return result

    except Exception:
        logger.error("list_all_vehicles failed", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/api/admin/vehicles", response_model=VehicleResponse, tags=["admin"])
async def create_vehicle(
    vehicle_data: VehicleCreate,
    current_user: CurrentUser = Depends(require_role("admin", "dispatcher")),
):
    """Register a new vehicle (bus / microbus / taxi).

    Approval workflow (migration 019): vehicles registered by an operator
    (dispatcher) start as `pending` and cannot operate until an admin
    approves them on /admin/approvals.html. Vehicles created directly by an
    admin are approved immediately (the admin IS the approver).
    """
    try:
        ensure_operator_scope(
            current_user.operator_id, current_user.operator_id, current_user.role
        )

        # Duplicate fleet code check (was previously a raw 500).
        existing = await _service_get(
            f"vehicles?vehicle_id=eq.{urllib.parse.quote(vehicle_data.vehicle_id, safe='')}"
            f"&select=id&{_op_filter(current_user.operator_id)}"
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A vehicle with this fleet code already exists.",
            )

        # Duplicate GPS device id check. A physical tracker maps to exactly one
        # vehicle; if two vehicles share a gps_device_id the Traccar webhook
        # attaches fixes to whichever row sorts first (the "wrong bus" bug).
        # Checked globally — a device belongs to one vehicle across the system.
        if vehicle_data.gps_device_id:
            device_dupe = await _service_get(
                f"vehicles?gps_device_id=eq.{urllib.parse.quote(vehicle_data.gps_device_id, safe='')}"
                "&select=id,vehicle_id"
            )
            if device_dupe:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"GPS device id '{vehicle_data.gps_device_id}' is already "
                        f"paired to vehicle {device_dupe[0].get('vehicle_id')}. "
                        "Unpair it there first."
                    ),
                )

        is_admin = current_user.role in ("admin", "super_admin")
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
            "approval_status": "approved" if is_admin else "pending",
            "created_by": current_user.user_id,
        }
        if is_admin:
            new_vehicle["approved_by"] = current_user.user_id
            new_vehicle["approved_at"] = datetime.utcnow().isoformat()

        result = await _service_post("vehicles", new_vehicle)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create vehicle",
            )

        created = result if isinstance(result, dict) else result[0] if result else {}

        await _service_post(
            "audit_log",
            {
                "admin_id": current_user.user_id,
                "action": "vehicle_created",
                "details": (
                    f"Vehicle {vehicle_data.vehicle_id} ({vehicle_data.vehicle_type}) "
                    f"registered by {current_user.role}; approval_status="
                    f"{new_vehicle['approval_status']}"
                ),
                "operator_id": current_user.operator_id,
            },
        )

        return VehicleResponse(
            id=created.get("id"),
            vehicle_id=created.get("vehicle_id"),
            name=created.get("name"),
            name_ar=created.get("name_ar"),
            vehicle_type=created.get("vehicle_type"),
            capacity=created.get("capacity"),
            status=created.get("status"),
            approval_status=created.get("approval_status"),
            created_at=created.get("created_at"),
        )

    except HTTPException:
        raise
    except Exception:
        logger.error("create_vehicle failed", exc_info=True)
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
    current_user: CurrentUser = Depends(require_role("admin", "dispatcher")),
):
    """Update vehicle details (operator staff may maintain their own fleet)."""
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
        if vehicle_data.is_real_gps is not None:
            update_dict["is_real_gps"] = vehicle_data.is_real_gps

        # Tracker (GPS device) pairing, editable from the admin UI so an admin
        # never has to touch the database to pair/unpair a tracker.
        if vehicle_data.gps_device_id is not None:
            device = vehicle_data.gps_device_id.strip()
            if not device:
                # Unpair: clear the device and the real-GPS flag together.
                update_dict["gps_device_id"] = None
                update_dict["is_real_gps"] = False
            else:
                # A device belongs to exactly one vehicle (also DB-guarded by
                # migration 027); reject pairing one already used elsewhere.
                clash = await _service_get(
                    f"vehicles?gps_device_id=eq.{urllib.parse.quote(device, safe='')}"
                    f"&id=neq.{urllib.parse.quote(vehicle_id, safe='')}"
                    "&select=id,vehicle_id"
                )
                if clash:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            f"GPS device id '{device}' is already paired to "
                            f"vehicle {clash[0].get('vehicle_id')}. Unpair it there first."
                        ),
                    )
                update_dict["gps_device_id"] = device

        if not update_dict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update"
            )

        result = await _service_patch(
            f"vehicles?id=eq.{urllib.parse.quote(vehicle_id, safe='')}"
            f"{_own_op_filter(current_user)}",
            update_dict,
        )
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
    """Assign vehicle to route and/or driver.

    Assignment is allowed while the vehicle is still pending — the operator
    links the driver (with their issued username/password) FIRST, and the
    admin's approval afterwards is what authorises the vehicle to operate.
    The driver must belong to the same operator as the vehicle. Omitted
    fields are left unchanged; empty strings clear the assignment.
    """
    try:
        update_data = {}
        if assignment.driver_id is not None:
            if assignment.driver_id == "":
                update_data["assigned_driver_id"] = None
            else:
                # The assigned driver must be an active driver of the same tenant.
                drivers = await _service_get(
                    f"users?id=eq.{urllib.parse.quote(assignment.driver_id, safe='')}"
                    f"&role=eq.driver&is_active=eq.true&select=id"
                    f"{_own_op_filter(current_user)}"
                )
                if not drivers:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Driver not found in your operator (must be an active driver account).",
                    )
                update_data["assigned_driver_id"] = assignment.driver_id
        if assignment.route_id is not None:
            update_data["assigned_route_id"] = assignment.route_id or None
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide route_id and/or driver_id.",
            )
        result = await _service_patch(
            f"vehicles?id=eq.{urllib.parse.quote(vehicle_id, safe='')}"
            f"{_own_op_filter(current_user)}",
            update_data,
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found"
            )

        audit_entry = {
            "admin_id": current_user.user_id,
            "action": "vehicle_assigned",
            "details": f"Vehicle {vehicle_id} assigned to route {assignment.route_id}, driver {assignment.driver_id}",
            "operator_id": current_user.operator_id,
        }
        await _service_post("audit_log", audit_entry)

        return {"status": "success", "timestamp": datetime.utcnow().isoformat()}

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete(
    "/api/admin/vehicles/{vehicle_id}",
    response_model=StatusTimestampResponse,
    tags=["admin"],
)
async def decommission_vehicle(
    vehicle_id: str,
    current_user: CurrentUser = Depends(require_role("admin", "super_admin")),
):
    """Soft-delete: mark a vehicle decommissioned + inactive (audit-logged).

    Hard deletes would orphan trips/positions history, so the row is kept.
    """
    try:
        result = await _service_patch(
            f"vehicles?id=eq.{urllib.parse.quote(vehicle_id, safe='')}"
            f"{_own_op_filter(current_user)}",
            {
                "status": "decommissioned",
                "is_active": False,
                "assigned_driver_id": None,
                "assigned_route_id": None,
            },
        )
        if not result:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        await _service_post(
            "audit_log",
            {
                "admin_id": current_user.user_id,
                "action": "vehicle_decommissioned",
                "details": f"Vehicle {vehicle_id} decommissioned",
                "operator_id": current_user.operator_id,
            },
        )
        return {"status": "success", "timestamp": datetime.utcnow().isoformat()}
    except HTTPException:
        raise
    except Exception:
        logger.error("decommission_vehicle failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Routes CRUD (admin) ────────────────────────────────────────────────────────
# Minimal management endpoints for /admin/routes.html. Geometry (the map
# polyline) is intentionally NOT editable here — it comes from the GTFS
# pipeline / GIS tooling; these endpoints handle the business fields only.


@router.get("/api/admin/routes", tags=["admin"])
async def admin_list_routes(
    current_user: CurrentUser = Depends(
        require_role("admin", "dispatcher", "super_admin")
    ),
):
    """All routes (including inactive), scoped to the operator."""
    try:
        op_suffix = ""
        if current_user.role != "super_admin" and current_user.operator_id:
            op_suffix = f"&{_op_filter(current_user.operator_id)}"
        rows = await _service_get(
            "routes?select=id,route_id,name,name_ar,route_type,color,distance_km,"
            f"avg_duration_min,fare_syp,is_active,created_at&order=route_id.asc{op_suffix}"
        )
        return rows or []
    except Exception:
        logger.error("admin_list_routes failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/admin/routes", tags=["admin"])
async def admin_create_route(
    body: RouteCreate,
    current_user: CurrentUser = Depends(require_role("admin", "dispatcher")),
):
    """Create a route (business fields; geometry added later via GIS)."""
    try:
        existing = await _service_get(
            f"routes?route_id=eq.{urllib.parse.quote(body.route_id, safe='')}&select=id"
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A route with this code already exists.",
            )
        new_route = {
            "route_id": body.route_id,
            "name": body.name,
            "name_ar": body.name_ar,
            "route_type": body.route_type,
            "distance_km": body.distance_km,
            "avg_duration_min": body.avg_duration_min,
            "fare_syp": body.fare_syp,
            "is_active": True,
            "operator_id": current_user.operator_id,
        }
        if body.color:
            new_route["color"] = body.color
        created = await _service_post("routes", new_route)
        created = (
            created if isinstance(created, dict) else (created[0] if created else {})
        )
        await _service_post(
            "audit_log",
            {
                "admin_id": current_user.user_id,
                "action": "route_created",
                "details": f"Route {body.route_id} ({body.route_type}) created",
                "operator_id": current_user.operator_id,
            },
        )
        return created
    except HTTPException:
        raise
    except Exception:
        logger.error("admin_create_route failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/api/admin/routes/{route_pk}", tags=["admin"])
async def admin_update_route(
    route_pk: str,
    body: RouteUpdate,
    current_user: CurrentUser = Depends(require_role("admin", "dispatcher")),
):
    """Update a route's business fields (fare, names, timing, active flag)."""
    try:
        update = {k: v for k, v in body.model_dump().items() if v is not None}
        if not update:
            raise HTTPException(status_code=400, detail="No fields to update")
        result = await _service_patch(
            f"routes?id=eq.{urllib.parse.quote(route_pk, safe='')}"
            f"{_own_op_filter(current_user)}",
            update,
        )
        if not result:
            raise HTTPException(status_code=404, detail="Route not found")
        return result[0]
    except HTTPException:
        raise
    except Exception:
        logger.error("admin_update_route failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Vehicle approval (migration 019) ──────────────────────────────────────────


@router.get("/api/admin/vehicles/pending-count", tags=["admin"])
async def pending_vehicle_count(
    current_user: CurrentUser = Depends(
        require_role("admin", "dispatcher", "super_admin")
    ),
):
    """Number of vehicles awaiting approval (drives the sidebar badge)."""
    try:
        op_suffix = ""
        if current_user.role != "super_admin" and current_user.operator_id:
            op_suffix = f"&{_op_filter(current_user.operator_id)}"
        return {"pending": await _count_pending_vehicles(op_suffix)}
    except Exception:
        logger.error("pending_vehicle_count failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/api/admin/vehicles/{vehicle_id}/approval",
    response_model=StatusTimestampResponse,
    tags=["admin"],
)
async def decide_vehicle_approval(
    vehicle_id: str,
    decision: VehicleApprovalRequest,
    current_user: CurrentUser = Depends(require_role("admin", "super_admin")),
):
    """ADMIN ONLY — approve / reject / suspend a vehicle, or send it back to
    pending (`resubmit`). Operators (dispatchers) cannot call this: the whole
    point of the workflow is that the operator registers the vehicle + driver
    credentials and a separate, higher-privileged admin authorises it.

    Allowed transitions:
        pending   -> approved | rejected
        approved  -> suspended
        rejected  -> pending   (resubmit)
        suspended -> approved | pending (resubmit)
    Every decision is written to audit_log.
    """
    try:
        rows = await _service_get(
            f"vehicles?id=eq.{urllib.parse.quote(vehicle_id, safe='')}"
            f"&select=id,vehicle_id,approval_status{_own_op_filter(current_user)}"
        )
        if not rows:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        vehicle = rows[0]
        current = vehicle.get("approval_status") or "pending"

        transitions = {
            "approve": ({"pending", "suspended"}, "approved"),
            "reject": ({"pending"}, "rejected"),
            "suspend": ({"approved"}, "suspended"),
            "resubmit": ({"rejected", "suspended"}, "pending"),
        }
        allowed_from, new_status = transitions[decision.action]
        if current not in allowed_from:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot {decision.action} a vehicle in state '{current}'.",
            )

        update = {
            "approval_status": new_status,
            "approval_note": decision.note,
        }
        if new_status == "approved":
            update["approved_by"] = current_user.user_id
            update["approved_at"] = datetime.utcnow().isoformat()
        else:
            update["approved_by"] = None
            update["approved_at"] = None

        # Compare-and-set: only flip the row if it is STILL in the state we
        # read above, so two concurrent approve/suspend calls cannot both win
        # (TOCTOU). An empty result means another request changed it first.
        result = await _service_patch(
            f"vehicles?id=eq.{urllib.parse.quote(vehicle_id, safe='')}"
            f"&approval_status=eq.{current}{_own_op_filter(current_user)}",
            update,
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Vehicle state changed concurrently; reload and retry.",
            )

        await _service_post(
            "audit_log",
            {
                "admin_id": current_user.user_id,
                "action": f"vehicle_{new_status if decision.action != 'resubmit' else 'resubmitted'}",
                "details": (
                    f"Vehicle {vehicle.get('vehicle_id')} ({vehicle_id}): "
                    f"{current} -> {new_status}"
                    + (f" — note: {decision.note}" if decision.note else "")
                ),
                "operator_id": current_user.operator_id,
            },
        )

        return {"status": new_status, "timestamp": datetime.utcnow().isoformat()}

    except HTTPException:
        raise
    except Exception:
        logger.error("decide_vehicle_approval failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/admin/audit-log", tags=["admin"])
async def list_audit_log(
    limit: int = 50,
    current_user: CurrentUser = Depends(require_role("admin", "super_admin")),
):
    """Most recent audit-log entries (approvals, assignments, creations)."""
    try:
        limit = max(1, min(limit, 200))
        op_suffix = ""
        if current_user.role != "super_admin" and current_user.operator_id:
            op_suffix = f"&{_op_filter(current_user.operator_id)}"
        rows = await _service_get(
            f"audit_log?select=id,admin_id,action,details,created_at"
            f"&order=created_at.desc&limit={limit}{op_suffix}"
        )
        return rows or []
    except Exception:
        logger.error("list_audit_log failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


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
        alerts = await _service_get(query)

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
        result = await _service_patch(
            f"alerts?id=eq.{urllib.parse.quote(alert_id, safe='')}"
            f"{_own_op_filter(current_user)}",
            update_data,
        )
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

        result = await _service_get(query)
        return result or []

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ── Trip dispatch (operator → driver) ───────────────────────────────────────────


@router.get("/api/admin/trips/upcoming", response_model=List[dict], tags=["admin"])
async def list_upcoming_trips(
    current_user: CurrentUser = Depends(
        require_role("admin", "dispatcher", "super_admin")
    ),
):
    """Dispatch queue: scheduled/dispatched/acked trips for the operator,
    enriched with route, vehicle, and driver labels for the console."""
    try:
        op_suffix = ""
        if current_user.role != "super_admin" and current_user.operator_id:
            op_suffix = f"&{_op_filter(current_user.operator_id)}"
        trips = await _service_get(
            "trips?status=in.(scheduled,dispatched,acked)"
            "&select=id,status,route_id,vehicle_id,driver_id,scheduled_start,"
            "planned_passengers,notes,dispatched_at,acked_at"
            "&order=scheduled_start.asc.nullslast" + op_suffix
        )
        if not trips:
            return []

        def _ids(key):
            return {t[key] for t in trips if t.get(key)}

        routes, vehicles, drivers = {}, {}, {}
        rid, vid, did = _ids("route_id"), _ids("vehicle_id"), _ids("driver_id")
        if rid:
            for r in await _service_get(
                f"routes?id=in.({','.join(rid)})&select=id,route_id,name,name_ar"
            ):
                routes[r["id"]] = r
        if vid:
            for v in await _service_get(
                f"vehicles?id=in.({','.join(vid)})&select=id,vehicle_id,name,name_ar"
            ):
                vehicles[v["id"]] = v
        if did:
            for u in await _service_get(
                f"users?id=in.({','.join(did)})&select=id,full_name,full_name_ar,email"
            ):
                drivers[u["id"]] = u
        for t in trips:
            t["route"] = routes.get(t.get("route_id"))
            t["vehicle"] = vehicles.get(t.get("vehicle_id"))
            t["driver"] = drivers.get(t.get("driver_id"))
        return trips
    except Exception:
        logger.error("list_upcoming_trips failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/admin/trips/dispatch", response_model=dict, tags=["admin"])
async def dispatch_trip(
    body: TripDispatch,
    current_user: CurrentUser = Depends(require_role("admin", "dispatcher")),
):
    """Schedule + push a trip to a driver.

    Resolves the route/driver from the vehicle when not supplied, refuses to
    double-book a driver within ±30 minutes, and records the trip as
    `dispatched` so the driver console shows the acknowledge banner.
    """
    try:
        veh = await _service_get(
            f"vehicles?id=eq.{urllib.parse.quote(body.vehicle_id, safe='')}"
            "&select=id,vehicle_id,assigned_driver_id,assigned_route_id,"
            "approval_status,is_active"
            f"{_own_op_filter(current_user)}"
        )
        if not veh:
            raise HTTPException(
                status_code=404, detail="Vehicle not found in your operator."
            )
        v = veh[0]
        if v.get("is_active") is False or (
            v.get("approval_status") and v["approval_status"] != "approved"
        ):
            raise HTTPException(
                status_code=422, detail="Vehicle is not approved/active to operate."
            )
        route_id = body.route_id or v.get("assigned_route_id")
        driver_id = body.driver_id or v.get("assigned_driver_id")
        if not route_id:
            raise HTTPException(
                status_code=422,
                detail="No route given and the vehicle has no assigned route.",
            )
        if not driver_id:
            raise HTTPException(
                status_code=422,
                detail="No driver given and the vehicle has no assigned driver.",
            )

        # Double-booking guard: same driver within ±30 min of an open trip.
        lo = (body.scheduled_start - timedelta(minutes=30)).isoformat()
        hi = (body.scheduled_start + timedelta(minutes=30)).isoformat()
        conflicts = await _service_get(
            f"trips?driver_id=eq.{urllib.parse.quote(driver_id, safe='')}"
            "&status=in.(scheduled,dispatched,acked,in_progress)"
            f"&scheduled_start=gte.{urllib.parse.quote(lo, safe='')}"
            f"&scheduled_start=lte.{urllib.parse.quote(hi, safe='')}"
            "&select=id"
        )
        if conflicts:
            raise HTTPException(
                status_code=409,
                detail="That driver already has a trip within 30 minutes of this time.",
            )

        now = datetime.utcnow().isoformat()
        trip = {
            "vehicle_id": v["id"],
            "route_id": route_id,
            "driver_id": driver_id,
            "status": "dispatched",
            "scheduled_start": body.scheduled_start.isoformat(),
            "planned_passengers": body.planned_passengers,
            "notes": body.notes,
            "dispatched_by_user_id": current_user.user_id,
            "dispatched_at": now,
            "operator_id": current_user.operator_id,
        }
        created = await _service_post("trips", trip)
        created = (
            created if isinstance(created, dict) else (created[0] if created else {})
        )
        if not created:
            raise HTTPException(status_code=500, detail="Failed to create trip")

        await _service_post(
            "audit_log",
            {
                "admin_id": current_user.user_id,
                "action": "trip_dispatched",
                "details": (
                    f"Trip dispatched: vehicle {v.get('vehicle_id')} → driver "
                    f"{driver_id} on route {route_id} at "
                    f"{body.scheduled_start.isoformat()}"
                ),
                "operator_id": current_user.operator_id,
            },
        )
        return created
    except HTTPException:
        raise
    except Exception:
        logger.error("dispatch_trip failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/api/admin/trips/{trip_id}/cancel",
    response_model=StatusTimestampResponse,
    tags=["admin"],
)
async def cancel_trip(
    trip_id: str,
    body: TripCancel,
    current_user: CurrentUser = Depends(require_role("admin", "dispatcher")),
):
    """Cancel a not-yet-started trip (scheduled/dispatched/acked)."""
    try:
        rows = await _service_get(
            f"trips?id=eq.{urllib.parse.quote(trip_id, safe='')}"
            "&select=id,status"
            f"{_own_op_filter(current_user)}"
        )
        if not rows:
            raise HTTPException(status_code=404, detail="Trip not found")
        if rows[0].get("status") in ("in_progress", "completed", "cancelled"):
            raise HTTPException(
                status_code=422,
                detail="Only a trip that hasn't started can be cancelled.",
            )
        await _service_patch(
            f"trips?id=eq.{urllib.parse.quote(trip_id, safe='')}"
            f"{_own_op_filter(current_user)}",
            {"status": "cancelled", "cancellation_reason": body.reason},
        )
        await _service_post(
            "audit_log",
            {
                "admin_id": current_user.user_id,
                "action": "trip_cancelled",
                "details": f"Trip {trip_id} cancelled"
                + (f": {body.reason}" if body.reason else ""),
                "operator_id": current_user.operator_id,
            },
        )
        return {"status": "success", "timestamp": datetime.utcnow().isoformat()}
    except HTTPException:
        raise
    except Exception:
        logger.error("cancel_trip failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


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

        vehicles = await _service_get(f"vehicles?select=status{op_suffix}")
        active_vehicles = len([v for v in vehicles if v.get("status") == "active"])
        idle_vehicles = len([v for v in vehicles if v.get("status") == "idle"])
        maintenance_vehicles = len(
            [v for v in vehicles if v.get("status") == "maintenance"]
        )

        routes = await _service_get(f"routes?is_active=eq.true&select=id{op_suffix}")
        stops = await _service_get(f"stops?is_active=eq.true&select=id{op_suffix}")
        drivers = await _service_get(
            f"users?role=eq.driver&select=is_active{op_suffix}"
        )
        active_drivers = (
            len([d for d in drivers if d.get("is_active")]) if drivers else 0
        )

        today = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00+00:00")
        trips_today_rows = await _service_get(
            f"trips?actual_start=gte.{urllib.parse.quote(today, safe='')}&select=id{op_suffix}"
        )
        open_alerts_rows = await _service_get(
            f"alerts?is_resolved=eq.false&select=id,alert_type{op_suffix}"
        )
        silent_buses = len(
            [
                a
                for a in (open_alerts_rows or [])
                if a.get("alert_type") == "connection_lost"
            ]
        )
        pending_count = await _count_pending_vehicles(op_suffix)

        positions = await _service_get(
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
            trips_today=len(trips_today_rows or []),
            open_alerts=len(open_alerts_rows or []),
            silent_buses=silent_buses,
            pending_vehicles=pending_count,
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

        vehicles = await _service_get(f"vehicles?select=id,status{op_suffix}")
        total_vehicles = len(vehicles)

        trips = await _service_get(
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

        routes = await _service_get(
            f"routes?is_active=eq.true&select=id,name,name_ar,distance_km{op_suffix}"
        )
        trips = await _service_get(
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

        drivers = await _service_get(
            f"users?role=eq.driver&select=id,full_name,full_name_ar,is_active{op_suffix}"
        )
        trips = await _service_get(
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

        positions = await _service_get(
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

        latest = await _service_get(
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
        vehicles = await _service_get(f"vehicles?select=*{op_suffix}")
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
        trips = await _service_get(
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
        alerts = await _service_get(f"alerts?select=*&order=created_at.desc{op_suffix}")
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
        drivers = await _service_get(
            f"users?role=eq.driver&select=id,full_name,full_name_ar,email,phone,is_active,created_at{op_suffix}"
        )
        trips = await _service_get(
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
        routes = await _service_get(
            f"routes?is_active=eq.true&select=id,name,name_ar,distance_km{op_suffix}"
        )
        trips = await _service_get(
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
