"""
Passenger feedback router — driver ratings and trip reviews.

Endpoints:
  POST /api/feedback              — submit feedback for a completed trip
  GET  /api/feedback/trip/{id}   — list reviews for a trip (public)
  GET  /api/feedback/driver/{id} — driver rating summary (public)
  GET  /api/admin/feedback        — all feedback (admin/dispatcher only)
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from api.core.auth import CurrentUser, optional_auth, require_role
from api.core.cache import (
    RATE_LIMIT_WRITE,
    _get_client_ip,
    _rate_limit_check,
)
from api.core.database import (
    _supabase_get,
    _supabase_post,
)
from api.models.schemas import (
    DriverRatingSummary,
    FeedbackCreate,
    FeedbackResponse,
)

router = APIRouter()


# ── Submit feedback ──────────────────────────────────────────────────────────


@router.post(
    "/api/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["feedback"],
)
async def submit_feedback(
    raw_request: Request,
    payload: FeedbackCreate,
    current_user: Optional[CurrentUser] = Depends(optional_auth),
):
    """
    Submit feedback for a completed trip.

    Authentication is optional — anonymous submissions are accepted.
    A logged-in passenger may only submit one review per trip.
    """
    client_ip = _get_client_ip(raw_request)
    max_req, window = RATE_LIMIT_WRITE
    if not await _rate_limit_check(f"feedback:{client_ip}", max_req, window):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Try again later.",
            headers={"Retry-After": str(window)},
        )
    # Verify the trip exists and is completed
    trips = await _supabase_get(
        f"trips?id=eq.{payload.trip_id}&select=id,driver_id,status,operator_id"
    )
    if not trips:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found"
        )

    trip = trips[0]
    if trip["status"] != "completed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Feedback can only be submitted for completed trips",
        )

    passenger_id: Optional[str] = None
    is_anonymous = payload.is_anonymous

    if current_user:
        if not is_anonymous:
            passenger_id = current_user.user_id
        # Check for duplicate (only for logged-in, non-anonymous users)
        if passenger_id:
            existing = await _supabase_get(
                f"trip_feedback?trip_id=eq.{payload.trip_id}&passenger_id=eq.{passenger_id}&select=id"
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="You have already submitted feedback for this trip",
                )
    else:
        # No JWT — treat as anonymous regardless of payload flag
        is_anonymous = True

    record = {
        "trip_id": payload.trip_id,
        "driver_id": trip.get("driver_id"),
        "passenger_id": passenger_id,
        "rating": payload.rating,
        "comment": payload.comment,
        "categories": payload.categories or [],
        "is_anonymous": is_anonymous,
        "operator_id": trip.get("operator_id"),
    }

    created = await _supabase_post("trip_feedback", record)

    return FeedbackResponse(
        id=created["id"],
        trip_id=created["trip_id"],
        driver_id=created.get("driver_id"),
        passenger_id=created.get("passenger_id"),
        rating=created["rating"],
        comment=created.get("comment"),
        categories=created.get("categories") or [],
        is_anonymous=created["is_anonymous"],
        created_at=created.get("created_at"),
    )


# ── Trip reviews (public) ────────────────────────────────────────────────────


@router.get(
    "/api/feedback/trip/{trip_id}",
    response_model=List[FeedbackResponse],
    tags=["feedback"],
)
async def get_trip_feedback(
    trip_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List reviews for a specific trip (non-anonymous only)."""
    rows = await _supabase_get(
        f"trip_feedback?trip_id=eq.{trip_id}"
        f"&is_anonymous=eq.false"
        f"&order=created_at.desc"
        f"&limit={limit}&offset={offset}"
        f"&select=id,trip_id,driver_id,passenger_id,rating,comment,categories,is_anonymous,created_at"
    )
    return [
        FeedbackResponse(
            id=r["id"],
            trip_id=r["trip_id"],
            driver_id=r.get("driver_id"),
            passenger_id=r.get("passenger_id"),
            rating=r["rating"],
            comment=r.get("comment"),
            categories=r.get("categories") or [],
            is_anonymous=r["is_anonymous"],
            created_at=r.get("created_at"),
        )
        for r in rows
    ]


# ── Driver rating summary (public) ──────────────────────────────────────────


@router.get(
    "/api/feedback/driver/{driver_id}/rating",
    response_model=DriverRatingSummary,
    tags=["feedback"],
)
async def get_driver_rating(driver_id: str):
    """Return aggregated rating summary for a driver."""
    rows = await _supabase_get(
        f"driver_rating_summary?driver_id=eq.{driver_id}&select=*"
    )
    if not rows:
        # Driver exists but has no reviews yet — return zeroed summary
        users = await _supabase_get(f"users?id=eq.{driver_id}&role=eq.driver&select=id")
        if not users:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found"
            )
        return DriverRatingSummary(
            driver_id=driver_id,
            total_reviews=0,
            average_rating=None,
            five_star=0,
            four_star=0,
            three_star=0,
            two_star=0,
            one_star=0,
            last_reviewed_at=None,
        )

    r = rows[0]
    return DriverRatingSummary(
        driver_id=r["driver_id"],
        total_reviews=r["total_reviews"],
        average_rating=float(r["average_rating"]) if r.get("average_rating") else None,
        five_star=r.get("five_star", 0),
        four_star=r.get("four_star", 0),
        three_star=r.get("three_star", 0),
        two_star=r.get("two_star", 0),
        one_star=r.get("one_star", 0),
        last_reviewed_at=r.get("last_reviewed_at"),
    )


# ── Admin: list all feedback ─────────────────────────────────────────────────


@router.get(
    "/api/admin/feedback",
    response_model=List[FeedbackResponse],
    tags=["feedback", "admin"],
)
async def list_all_feedback(
    driver_id: Optional[str] = Query(None),
    trip_id: Optional[str] = Query(None),
    min_rating: Optional[int] = Query(None, ge=1, le=5),
    max_rating: Optional[int] = Query(None, ge=1, le=5),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: CurrentUser = Depends(
        require_role("admin", "dispatcher", "super_admin")
    ),
):
    """List all feedback. Admins and dispatchers only."""
    query = (
        "trip_feedback?select=id,trip_id,driver_id,passenger_id,rating,"
        "comment,categories,is_anonymous,created_at"
        f"&order=created_at.desc&limit={limit}&offset={offset}"
    )
    if driver_id:
        query += f"&driver_id=eq.{driver_id}"
    if trip_id:
        query += f"&trip_id=eq.{trip_id}"
    if min_rating is not None:
        query += f"&rating=gte.{min_rating}"
    if max_rating is not None:
        query += f"&rating=lte.{max_rating}"

    # Scope to operator for non-super-admin users
    if current_user.role != "super_admin" and current_user.operator_id:
        query += f"&operator_id=eq.{current_user.operator_id}"

    rows = await _supabase_get(query)
    return [
        FeedbackResponse(
            id=r["id"],
            trip_id=r["trip_id"],
            driver_id=r.get("driver_id"),
            passenger_id=r.get("passenger_id"),
            rating=r["rating"],
            comment=r.get("comment"),
            categories=r.get("categories") or [],
            is_anonymous=r["is_anonymous"],
            created_at=r.get("created_at"),
        )
        for r in rows
    ]
