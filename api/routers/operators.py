import urllib.parse
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from api.core.auth import CurrentUser, get_current_user, require_role
from api.core.database import _supabase_get, _supabase_patch, _supabase_post
from api.models.schemas import OperatorCreate, OperatorResponse, OperatorUpdate
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/operators", response_model=List[OperatorResponse], tags=["operators"])
async def list_operators(
    current_user: CurrentUser = Depends(require_role("super_admin")),
):
    """List all fleet operators (super_admin only)."""
    try:
        operators = await _supabase_get("operators?select=*&order=created_at.asc")
        return [
            OperatorResponse(
                id=o["id"],
                slug=o["slug"],
                name=o["name"],
                name_ar=o.get("name_ar"),
                plan=o["plan"],
                is_active=o["is_active"],
                settings=o.get("settings"),
                created_at=o.get("created_at"),
            )
            for o in operators
        ]
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/api/operators/me", response_model=OperatorResponse, tags=["operators"])
async def get_my_operator(
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get the current user's operator profile."""
    try:
        if not current_user.operator_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No operator associated with this account",
            )
        operators = await _supabase_get(
            f"operators?id=eq.{current_user.operator_id}&select=*"
        )
        if not operators:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Operator not found"
            )
        o = operators[0]
        return OperatorResponse(
            id=o["id"],
            slug=o["slug"],
            name=o["name"],
            name_ar=o.get("name_ar"),
            plan=o["plan"],
            is_active=o["is_active"],
            settings=o.get("settings"),
            created_at=o.get("created_at"),
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/api/operators", response_model=OperatorResponse, tags=["operators"])
async def create_operator(
    data: OperatorCreate,
    current_user: CurrentUser = Depends(require_role("super_admin")),
):
    """Register a new fleet operator (super_admin only)."""
    try:
        existing = await _supabase_get(
            f"operators?slug=eq.{urllib.parse.quote(data.slug, safe='')}&select=id"
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Operator slug '{data.slug}' already exists",
            )

        payload: dict = {
            "slug": data.slug,
            "name": data.name,
            "name_ar": data.name_ar,
            "plan": data.plan,
            "is_active": True,
        }
        if data.settings is not None:
            payload["settings"] = data.settings

        result = await _supabase_post("operators", payload)
        created = result if isinstance(result, dict) else result[0] if result else {}

        return OperatorResponse(
            id=created["id"],
            slug=created["slug"],
            name=created["name"],
            name_ar=created.get("name_ar"),
            plan=created["plan"],
            is_active=created["is_active"],
            settings=created.get("settings"),
            created_at=created.get("created_at"),
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put(
    "/api/operators/{operator_id}", response_model=OperatorResponse, tags=["operators"]
)
async def update_operator(
    operator_id: str,
    data: OperatorUpdate,
    current_user: CurrentUser = Depends(require_role("super_admin")),
):
    """Update an operator's details (super_admin only)."""
    try:
        update_dict: dict = {}
        if data.name is not None:
            update_dict["name"] = data.name
        if data.name_ar is not None:
            update_dict["name_ar"] = data.name_ar
        if data.plan is not None:
            update_dict["plan"] = data.plan
        if data.is_active is not None:
            update_dict["is_active"] = data.is_active
        if data.settings is not None:
            update_dict["settings"] = data.settings

        if not update_dict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update"
            )

        result = await _supabase_patch(f"operators?id=eq.{operator_id}", update_dict)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Operator not found"
            )

        o = result[0]
        return OperatorResponse(
            id=o["id"],
            slug=o["slug"],
            name=o["name"],
            name_ar=o.get("name_ar"),
            plan=o["plan"],
            is_active=o["is_active"],
            settings=o.get("settings"),
            created_at=o.get("created_at"),
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
