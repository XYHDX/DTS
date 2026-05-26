import asyncio
import json
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from api.core.auth import CurrentUser, optional_auth
from api.core.database import _supabase_get
from api.core.geo import parse_location
from api.core.tenancy import _op_filter, _resolve_operator_id
from api.models.schemas import PositionData

router = APIRouter()


@router.get("/api/stream", tags=["stream"])
async def stream_positions(
    operator: Optional[str] = Query(None, description="Operator slug"),
    current_user: Optional[CurrentUser] = Depends(optional_auth),
):
    """Server-sent events (SSE) stream of vehicle position updates."""
    if current_user and current_user.role == "super_admin":
        op_id = await _resolve_operator_id(operator) if operator else None
    elif current_user and current_user.operator_id:
        op_id = current_user.operator_id
    else:
        op_id = await _resolve_operator_id(operator) if operator else None

    async def generate():
        start_time = time.time()
        max_duration = 25  # Vercel hobby timeout

        while time.time() - start_time < max_duration:
            try:
                query = "vehicle_positions_latest?select=*,vehicles(name,name_ar)"
                if op_id:
                    query += f"&{_op_filter(op_id)}"
                positions = await _supabase_get(query)

                for pos in positions or []:
                    vehicle = pos.get("vehicles", {})
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
                    )
                    yield f"data: {data.model_dump_json()}\n\n"

                await asyncio.sleep(2)

            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                await asyncio.sleep(2)

    return StreamingResponse(generate(), media_type="text/event-stream")
