from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.core.auth import CurrentUser, optional_auth
from api.core.database import _supabase_get
from api.core.tenancy import _op_filter, _resolve_operator_id
from api.models.schemas import ScheduleResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/api/schedules/{route_id}",
    response_model=List[ScheduleResponse],
    tags=["schedules"],
)
async def get_route_schedule(
    route_id: str,
    operator: Optional[str] = Query(None, description="Operator slug"),
    current_user: Optional[CurrentUser] = Depends(optional_auth),
):
    """Get schedule for a route by day of week."""
    try:
        if current_user and current_user.role == "super_admin":
            op_id = await _resolve_operator_id(operator) if operator else None
        elif current_user and current_user.operator_id:
            op_id = current_user.operator_id
        else:
            op_id = await _resolve_operator_id(operator) if operator else None

        query = f"schedules?route_id=eq.{route_id}&select=*"
        if op_id:
            query += f"&{_op_filter(op_id)}"
        schedules = await _supabase_get(query)

        return [
            ScheduleResponse(
                id=s["id"],
                route_id=s["route_id"],
                day_of_week=s["day_of_week"],
                first_departure=s["first_departure"],
                last_departure=s["last_departure"],
                frequency_min=s["frequency_min"],
            )
            for s in schedules
        ]

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
