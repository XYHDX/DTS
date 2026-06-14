import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from api.core.auth import CurrentUser, optional_auth
from api.core.cache import (
    CACHE_KEY_ROUTES_LIST,
    CACHE_TTL_ROUTES_STOPS,
    RATE_LIMIT_READ,
    _cache_get,
    _cache_set,
    _get_client_ip,
    _rate_limit_check,
    _tenant_cache_key,
)
from api.core.database import _supabase_get
from api.core.geo import parse_location
from api.core.tenancy import _op_filter, resolve_read_scope
from api.models.schemas import RouteResponse, StopResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/routes", response_model=List[RouteResponse], tags=["routes"])
async def list_routes(
    raw_request: Request,
    operator: Optional[str] = Query(
        None, description="Operator slug (e.g. 'damascus')"
    ),
    current_user: Optional[CurrentUser] = Depends(optional_auth),
):
    """List all active routes with stop counts."""
    client_ip = _get_client_ip(raw_request)
    max_req, window = RATE_LIMIT_READ
    if not await _rate_limit_check(f"routes:{client_ip}", max_req, window):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Try again later.",
            headers={"Retry-After": str(window)},
        )
    try:
        # Always scoped to exactly one operator (cross-tenant leak fix).
        op_id = await resolve_read_scope(operator, current_user)

        cache_key = _tenant_cache_key(CACHE_KEY_ROUTES_LIST, op_id or "all")
        cached = await _cache_get(cache_key)
        if cached is not None:
            return cached

        query = "routes?is_active=eq.true&select=*"
        if op_id:
            query += f"&{_op_filter(op_id)}"
        routes = await _supabase_get(query)

        enriched_routes = []
        for route in routes:
            stops = await _supabase_get(
                f"route_stops?route_id=eq.{route['id']}&select=id"
            )
            enriched_routes.append(
                RouteResponse(
                    id=route["id"],
                    route_id=route["route_id"],
                    name=route["name"],
                    name_ar=route["name_ar"],
                    route_type=route["route_type"],
                    color=route.get("color"),
                    distance_km=route.get("distance_km"),
                    avg_duration_min=route.get("avg_duration_min"),
                    fare_syp=route.get("fare_syp"),
                    stop_count=len(stops),
                )
            )

        await _cache_set(
            cache_key, [r.model_dump() for r in enriched_routes], CACHE_TTL_ROUTES_STOPS
        )
        return enriched_routes

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/api/routes/{route_id}", response_model=RouteResponse, tags=["routes"])
async def get_route(
    route_id: str,
    operator: Optional[str] = Query(None, description="Operator slug"),
    current_user: Optional[CurrentUser] = Depends(optional_auth),
):
    """Get single route details."""
    try:
        # Always scoped to exactly one operator (cross-tenant leak fix).
        op_id = await resolve_read_scope(operator, current_user)

        cache_key = f"transit:routes:{route_id}:{op_id or 'all'}"
        cached = await _cache_get(cache_key)
        if cached is not None:
            return cached

        query = f"routes?id=eq.{route_id}&select=*"
        if op_id:
            query += f"&{_op_filter(op_id)}"
        routes = await _supabase_get(query)

        if not routes:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Route not found"
            )

        route = routes[0]
        stops = await _supabase_get(f"route_stops?route_id=eq.{route_id}&select=id")

        result = RouteResponse(
            id=route["id"],
            route_id=route["route_id"],
            name=route["name"],
            name_ar=route["name_ar"],
            route_type=route["route_type"],
            color=route.get("color"),
            distance_km=route.get("distance_km"),
            avg_duration_min=route.get("avg_duration_min"),
            fare_syp=route.get("fare_syp"),
            stop_count=len(stops),
        )

        await _cache_set(cache_key, result.model_dump(), CACHE_TTL_ROUTES_STOPS)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get(
    "/api/routes/{route_id}/stops",
    response_model=List[StopResponse],
    tags=["routes"],
)
async def get_route_stops(
    route_id: str,
    operator: Optional[str] = Query(None, description="Operator slug"),
    current_user: Optional[CurrentUser] = Depends(optional_auth),
):
    """Return the ordered list of stops served by a route (by stop_sequence).

    Powers the passenger route-detail view so tapping a route card opens a real
    stop list (previously a dead-end deep link).
    """
    try:
        op_id = await resolve_read_scope(operator, current_user)

        cache_key = f"transit:route_stops:{route_id}:{op_id or 'all'}"
        cached = await _cache_get(cache_key)
        if cached is not None:
            return cached

        # Embed the related stop row via the route_stops → stops FK, ordered by
        # the canonical stop_sequence so the list reads start → end.
        rows = await _supabase_get(
            f"route_stops?route_id=eq.{route_id}"
            "&select=stop_sequence,stops(id,stop_id,name,name_ar,location,has_shelter,is_active)"
            "&order=stop_sequence.asc"
        )

        result: List[StopResponse] = []
        for row in rows or []:
            stop = row.get("stops") or {}
            if not stop or stop.get("is_active") is False:
                continue
            lat, lon = parse_location(stop.get("location"))
            result.append(
                StopResponse(
                    id=stop["id"],
                    stop_id=stop["stop_id"],
                    name=stop["name"],
                    name_ar=stop["name_ar"],
                    latitude=lat,
                    longitude=lon,
                    has_shelter=stop.get("has_shelter", False),
                    is_active=stop.get("is_active", True),
                )
            )

        await _cache_set(
            cache_key, [r.model_dump() for r in result], CACHE_TTL_ROUTES_STOPS
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        # Degrade gracefully — an empty list renders an "empty" detail view
        # rather than a 500 that breaks the passenger screen.
        return []
