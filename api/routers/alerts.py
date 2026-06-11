from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.core.auth import CurrentUser, optional_auth
from api.core.database import _supabase_get
from api.core.tenancy import _op_filter, resolve_read_scope
from api.models.schemas import AlertResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/alerts/active", response_model=List[AlertResponse], tags=["alerts"])
async def get_active_alerts(
    operator: Optional[str] = Query(None, description="Operator slug"),
    current_user: Optional[CurrentUser] = Depends(optional_auth),
):
    """Get all unresolved alerts."""
    try:
        # Always scoped to exactly one operator (cross-tenant leak fix).
        op_id = await resolve_read_scope(operator, current_user)

        query = "alerts?is_resolved=eq.false&select=*&order=created_at.desc"
        if op_id:
            query += f"&{_op_filter(op_id)}"
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

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
