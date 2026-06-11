"""Protobuf-over-HTTP bridge endpoint.

Phase S2.1 of Scale_100k_Roadmap.md.

This router accepts the *exact* wire format the MQTT broker will eventually
deliver, but over HTTPS. It lets the firmware switch to the production
Protobuf payload **before** the MQTT broker exists, so the cutover later is
purely a transport change.

Endpoints
---------
  POST /api/v1/telemetry/protobuf
      Body: a single VehicleStatus protobuf message OR a VehicleStatusBatch.
      Content-Type: application/x-protobuf
      Auth: HMAC signature header X-Device-Signature (same scheme as Traccar).
      Returns: 204 on success.

  POST /api/v1/telemetry/json
      Same payload but JSON-encoded — for the dev console and integration
      tests. Disabled in production via DEV_INGEST_ENABLED.

Hot path
--------
  1. Verify the HMAC.
  2. Decode the Protobuf.
  3. Update Redis Geo for live-map (sub-ms).
  4. EMA-smooth fuel level if the device didn't.
  5. Detect refuel / theft (api.core.ema.classify_fuel_step).
  6. Persist to `vehicle_positions` (which is a TimescaleDB hypertable
     once migration 009 has been applied).

Once a Kafka producer is wired, the persist step (6) moves into a
background consumer and this handler returns immediately after step 3.
"""

from __future__ import annotations

import hmac
import hashlib
import os
import time
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel

from api.core.cache import RATE_LIMIT_DRIVER_POS, rate_limit
from api.core.ema import EMAFilter, classify_fuel_step
from api.core.geo_cache import update_position as geo_update
from api.core import live_bus
from api.core.logging import logger

router = APIRouter(prefix="/api/v1/telemetry", tags=["telemetry"])

# In-process EMA filter dict. At 100k vehicles this dict is bounded by the
# vehicle count seen by *this* worker; pruned every hour by a small task.
_ema_filters: dict[tuple[str, str], EMAFilter] = {}
_last_fuel_smoothed: dict[str, float] = {}


# ── HMAC verification ───────────────────────────────────────────────────
def _ingest_secret() -> Optional[str]:
    return os.getenv("DEVICE_INGEST_SECRET", "").strip() or None


def _verify_signature(body: bytes, header_value: Optional[str]) -> bool:
    """HMAC-SHA256 verification with constant-time compare. Same shape as
    the Traccar webhook check in api/routers/traccar.py."""
    secret = _ingest_secret()
    if secret is None:
        # Misconfigured — the route refuses every request. This is the
        # safest fail-mode (vs the H2 fail-open the audit caught).
        return False
    if not header_value:
        return False
    try:
        expected = hmac.new(
            secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, header_value.strip().lower())
    except Exception:
        return False


# ── Lightweight pure-python protobuf decoder ────────────────────────────
#
# We don't ship protoc-generated bindings yet (that requires a build step
# we're deliberately keeping out of the API for now). Instead we accept
# JSON as the canonical dev format and treat Protobuf as opaque bytes
# that get forwarded to a Kafka topic once that exists.
#
# When the firmware reference code lands and produces real Protobuf, we
# swap this decode for the generated Python class. The router contract
# does not change.
class _PartialDecode(BaseModel):
    """JSON shape that mirrors telematics.proto VehicleStatus 1:1.
    Names are snake_case to match the proto field names."""

    vehicle_id: str
    timestamp: int  # ms since epoch
    latitude: float
    longitude: float
    speed_kph: float = 0.0
    heading: float = 0.0
    engine_state: bool = False
    fuel_level: Optional[float] = None
    trigger_event: int = 0
    operator_id: Optional[str] = None
    route_id: Optional[str] = None
    driver_id: Optional[str] = None
    trip_id: Optional[str] = None
    satellite_count: Optional[int] = None
    hdop: Optional[float] = None
    cell_signal_dbm: Optional[int] = None
    firmware_version: Optional[int] = None
    battery_mv: Optional[int] = None
    is_replay: bool = False


def _smooth_fuel(vehicle_id: str, raw: Optional[float]) -> Optional[float]:
    """Edge devices SHOULD smooth on-device. This is the safety net."""
    if raw is None:
        return None
    key = (vehicle_id, "fuel")
    f = _ema_filters.get(key)
    if f is None:
        f = EMAFilter()
        _ema_filters[key] = f
    return f.push(raw)


async def _persist(decoded: _PartialDecode, *, fuel_smoothed: Optional[float]) -> None:
    """Write to the hypertable. Lazy-import to avoid coupling at startup."""
    from api.core.database import _service_post  # type: ignore

    row = {
        "vehicle_id": decoded.vehicle_id,
        "operator_id": decoded.operator_id,
        "route_id": decoded.route_id,
        "ts":  # ms → ISO 8601 UTC
        time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(decoded.timestamp / 1000.0))
        + "Z",
        "lat": decoded.latitude,
        "lon": decoded.longitude,
        "speed": decoded.speed_kph,
        "heading": decoded.heading,
        "engine_state": decoded.engine_state,
        "fuel_level": fuel_smoothed,
        "trigger_event": decoded.trigger_event,
        "satellite_count": decoded.satellite_count,
        "hdop": decoded.hdop,
        "cell_signal_dbm": decoded.cell_signal_dbm,
        "firmware_version": decoded.firmware_version,
        "battery_mv": decoded.battery_mv,
        "is_replay": decoded.is_replay,
    }
    try:
        await _service_post("vehicle_positions", row)
    except Exception as e:
        # The MQTT path will move this into a background consumer; until
        # then a Postgres blip drops the frame on the floor. We log,
        # never crash.
        logger.warning(
            "telemetry_persist_failed",
            extra={"vehicle_id": decoded.vehicle_id, "err": str(e)[:200]},
        )


def _maybe_fuel_event(
    vehicle_id: str, before: Optional[float], after: Optional[float], engine_state: bool
) -> None:
    if before is None or after is None:
        return
    ev = classify_fuel_step(before, after, engine_state=engine_state)
    if ev is None:
        return
    logger.info(
        "fuel_event",
        extra={
            "vehicle_id": vehicle_id,
            "kind": ev.kind,
            "delta_pct": ev.delta_pct,
            "before": ev.smoothed_before,
            "after": ev.smoothed_after,
        },
    )
    # TODO when /api/admin/alerts has a kind="refuel"/"theft", emit there.


@router.post(
    "/json",
    status_code=204,
    summary="Telemetry frame (JSON form of telematics.proto VehicleStatus)",
    dependencies=[Depends(rate_limit("telemetry", *RATE_LIMIT_DRIVER_POS))],
)
async def telemetry_json(
    payload: _PartialDecode,
    request: Request,
    x_device_signature: Optional[str] = Header(default=None),
) -> Response:
    """JSON variant — handy for dev + integration tests. In production the
    Protobuf endpoint is preferred for the 80% bandwidth saving."""
    if (
        os.getenv("DEV_INGEST_ENABLED", "").lower() not in {"1", "true", "yes"}
        and os.getenv("VERCEL_ENV", "").lower() == "production"
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    body = await request.body()
    if not _verify_signature(body, x_device_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid device signature"
        )
    await _ingest(payload)
    return Response(status_code=204)


@router.post(
    "/protobuf",
    status_code=204,
    summary="Telemetry frame (Protobuf VehicleStatus or VehicleStatusBatch)",
    dependencies=[Depends(rate_limit("telemetry", *RATE_LIMIT_DRIVER_POS))],
)
async def telemetry_protobuf(
    request: Request,
    x_device_signature: Optional[str] = Header(default=None),
) -> Response:
    """Protobuf variant — production target.

    Body decoding is currently a placeholder: we accept any opaque payload,
    verify the HMAC, and return 204. Once the protoc-generated bindings
    land in api/proto/telematics_pb2.py, this handler parses the body,
    runs the same `_ingest` pipeline, and returns the same 204.
    """
    body = await request.body()
    if not _verify_signature(body, x_device_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid device signature"
        )
    # Placeholder: count frame, log size, no decode yet.
    logger.info("telemetry_protobuf_received", extra={"bytes": len(body)})
    return Response(status_code=204)


# ── Approval gate (migration 019) ───────────────────────────────────────
# 60-second in-process TTL cache so the 100k-vehicle hot path costs at most
# one approval lookup per vehicle per minute, not one per frame.
_approval_cache: dict[str, tuple[float, bool]] = {}
_APPROVAL_TTL = 60.0


async def _vehicle_approved(vehicle_id: str) -> bool:
    cached = _approval_cache.get(vehicle_id)
    now = time.monotonic()
    if cached is not None and (now - cached[0]) < _APPROVAL_TTL:
        return cached[1]
    approved = True  # fail-open for transport errors / pre-migration DBs
    try:
        from api.core.database import _service_get  # type: ignore

        rows = await _service_get(
            f"vehicles?id=eq.{vehicle_id}&select=approval_status,is_active"
        )
        if rows:
            v = rows[0]
            approved = v.get("is_active") is not False and (
                v.get("approval_status") is None or v["approval_status"] == "approved"
            )
        else:
            approved = False  # definitive answer: unknown vehicle
    except Exception:
        approved = True
    _approval_cache[vehicle_id] = (now, approved)
    return approved


async def _ingest(decoded: _PartialDecode) -> None:
    """Hot path: approval gate → geo cache → EMA → persist."""
    if not await _vehicle_approved(decoded.vehicle_id):
        logger.info(
            "telemetry_dropped_unapproved",
            extra={"vehicle_id": decoded.vehicle_id},
        )
        return
    if decoded.operator_id:
        await geo_update(
            operator_id=decoded.operator_id,
            vehicle_id=decoded.vehicle_id,
            lat=decoded.latitude,
            lon=decoded.longitude,
        )
    before = _last_fuel_smoothed.get(decoded.vehicle_id)
    smoothed = _smooth_fuel(decoded.vehicle_id, decoded.fuel_level)
    if smoothed is not None:
        _last_fuel_smoothed[decoded.vehicle_id] = smoothed
    _maybe_fuel_event(decoded.vehicle_id, before, smoothed, decoded.engine_state)
    await _persist(decoded, fuel_smoothed=smoothed)

    # S3.4 — fan the accepted frame out to /api/stream subscribers via the live
    # bus (no-op unless a pub/sub backend is configured). Best-effort.
    try:
        ts_iso = (
            time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(decoded.timestamp / 1000.0))
            + "Z"
        )
        await live_bus.publish(
            operator_id=decoded.operator_id,
            payload={
                "vehicle_id": decoded.vehicle_id,
                "vehicle_name": "",
                "vehicle_name_ar": "",
                "latitude": decoded.latitude,
                "longitude": decoded.longitude,
                "speed_kmh": decoded.speed_kph,
                "occupancy_pct": None,
                "timestamp": ts_iso,
            },
        )
    except Exception:
        pass
