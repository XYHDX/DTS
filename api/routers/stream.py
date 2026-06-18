import asyncio
import json
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from api.core import live_bus
from api.core.auth import CurrentUser, optional_auth
from api.core.database import _service_get
from api.core.geo import parse_location
from api.core.tenancy import _op_filter, resolve_read_scope
from api.models.schemas import PositionData

router = APIRouter()

# How long a single SSE connection lives before the client reconnects. Kept at
# the Vercel hobby function timeout so behaviour is identical on serverless and
# self-hosted deployments.
_MAX_DURATION_S = 25
# Idle gap after which we emit an SSE comment so proxies/clients keep the socket
# open even when no vehicle has moved.
_HEARTBEAT_S = 15
# Legacy poll interval (only used when no pub/sub backend is configured).
_POLL_INTERVAL_S = 2


async def _snapshot_frames(op_id: Optional[str]) -> list[str]:
    """Build the current set of SSE `data:` frames from the latest-position view.

    Used for the legacy poll loop and for the one-shot snapshot a bus subscriber
    receives on connect (so a freshly-opened stream is never blank).
    """
    query = (
        "vehicle_positions_latest?select=*,"
        "vehicles(vehicle_id,name,name_ar,gps_device_id,assigned_driver_id)"
    )
    if op_id:
        query += f"&{_op_filter(op_id)}"
    positions = await _service_get(query)

    # Resolve assigned-driver names in one batch (service key → RLS-safe), so the
    # live-map hover card can show who is driving each bus.
    driver_ids = sorted(
        {(p.get("vehicles") or {}).get("assigned_driver_id") for p in (positions or [])}
        - {None}
    )
    drivers_by_id: dict[str, dict] = {}
    if driver_ids:
        rows = await _service_get(
            f"users?id=in.({','.join(driver_ids)})&select=id,full_name,full_name_ar"
        )
        drivers_by_id = {d["id"]: d for d in (rows or [])}

    frames: list[str] = []
    for pos in positions or []:
        vehicle = pos.get("vehicles") or {}
        drv = drivers_by_id.get(vehicle.get("assigned_driver_id")) or {}
        lat, lon = parse_location(pos.get("location"))
        data = PositionData(
            vehicle_id=pos.get("vehicle_id"),
            vehicle_name=vehicle.get("name", ""),
            vehicle_name_ar=vehicle.get("name_ar", ""),
            latitude=lat or 0,
            longitude=lon or 0,
            speed_kmh=pos.get("speed_kmh"),
            occupancy_pct=pos.get("occupancy_pct"),
            timestamp=pos.get("recorded_at", datetime.utcnow().isoformat()),
            fleet_code=vehicle.get("vehicle_id"),
            gps_device_id=vehicle.get("gps_device_id"),
            driver_name=drv.get("full_name"),
            driver_name_ar=drv.get("full_name_ar"),
        )
        frames.append(f"data: {data.model_dump_json()}\n\n")
    return frames


@router.get("/api/stream", tags=["stream"])
async def stream_positions(
    operator: Optional[str] = Query(None, description="Operator slug"),
    current_user: Optional[CurrentUser] = Depends(optional_auth),
):
    """Server-sent events (SSE) stream of vehicle position updates.

    Two delivery modes, transparent to the client:

    * **Pub/sub (S3.4)** — when a live-bus backend is configured
      (``REDIS_PUBSUB_URL`` / ``LIVE_BUS_BACKEND``), the connection sends one
      snapshot then relays updates pushed by the ingest path. No per-client
      database polling and no in-process state, so any web process can serve any
      client and the service scales horizontally without sticky sessions.
    * **Poll (legacy)** — with no backend configured (e.g. serverless without a
      TCP Redis), it falls back to the original 2-second Supabase poll, so the
      existing deployment is unchanged.
    """
    # Always scoped to exactly one operator (cross-tenant leak fix).
    op_id = await resolve_read_scope(operator, current_user)

    async def generate():
        start_time = time.time()

        # ── Pub/sub path — generation happens off this process ────────────────
        if live_bus.configured():
            try:
                for frame in await _snapshot_frames(op_id):
                    yield frame
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

            updates = live_bus.subscribe(operator_id=op_id)
            iterator = updates.__aiter__()
            try:
                while time.time() - start_time < _MAX_DURATION_S:
                    try:
                        item = await asyncio.wait_for(
                            iterator.__anext__(), timeout=_HEARTBEAT_S
                        )
                    except asyncio.TimeoutError:
                        yield ": keep-alive\n\n"  # SSE comment — ignored by clients
                        continue
                    except StopAsyncIteration:
                        break
                    yield f"data: {json.dumps(item)}\n\n"
            finally:
                await updates.aclose()
            return

        # ── Legacy poll path (unchanged) ──────────────────────────────────────
        while time.time() - start_time < _MAX_DURATION_S:
            try:
                for frame in await _snapshot_frames(op_id):
                    yield frame
                await asyncio.sleep(_POLL_INTERVAL_S)
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                await asyncio.sleep(_POLL_INTERVAL_S)

    return StreamingResponse(generate(), media_type="text/event-stream")
