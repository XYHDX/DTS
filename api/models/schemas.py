import re
from datetime import datetime
from typing import Dict, Any, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


def _strip_html(value: Optional[str]) -> Optional[str]:
    """Strip HTML tags to prevent stored XSS."""
    if value is None:
        return None
    return re.sub(r"<[^>]+>", "", value).strip()


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    database: bool
    redis: bool
    last_position_update: Optional[str] = None
    active_vehicles: Optional[int] = None


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("Invalid email address")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str


class UserCreate(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=100)
    full_name_ar: Optional[str] = Field(None, max_length=100)
    role: Literal["admin", "dispatcher", "driver", "viewer"] = "viewer"
    phone: Optional[str] = Field(None, max_length=20)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("Invalid email address")
        return v


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    full_name_ar: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    full_name_ar: Optional[str] = None
    role: str
    phone: Optional[str] = None
    is_active: bool
    created_at: Optional[str] = None


class RegisterRequest(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=100)
    full_name_ar: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("Invalid email address")
        return v


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., max_length=254)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("Invalid email address")
        return v


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=512)
    new_password: str = Field(..., min_length=8, max_length=128)


class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    full_name_ar: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)

    @field_validator("full_name", "full_name_ar", mode="before")
    @classmethod
    def sanitize_name(cls, v):
        return _strip_html(v)


class RouteResponse(BaseModel):
    id: str
    route_id: str
    name: str
    name_ar: str
    route_type: str
    color: Optional[str] = None
    distance_km: Optional[float] = None
    avg_duration_min: Optional[int] = None
    fare_syp: Optional[float] = None
    stop_count: Optional[int] = 0


class StopResponse(BaseModel):
    id: str
    stop_id: str
    name: str
    name_ar: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    has_shelter: bool
    is_active: bool


class VehicleResponse(BaseModel):
    id: str
    vehicle_id: str
    name: str
    name_ar: str
    vehicle_type: str
    capacity: int
    status: str
    assigned_route_id: Optional[str] = None
    assigned_driver_id: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    speed_kmh: Optional[float] = None
    occupancy_pct: Optional[int] = None
    recorded_at: Optional[str] = None
    # Approval workflow (migration 019)
    approval_status: Optional[str] = None
    approved_at: Optional[str] = None
    approval_note: Optional[str] = None
    driver_name: Optional[str] = None
    driver_email: Optional[str] = None
    created_at: Optional[str] = None


class VehicleApprovalRequest(BaseModel):
    """Admin decision on whether a vehicle may operate."""

    action: Literal["approve", "reject", "suspend", "resubmit"]
    note: Optional[str] = Field(None, max_length=500)

    @field_validator("note", mode="before")
    @classmethod
    def sanitize_note(cls, v):
        return _strip_html(v)


class PositionUpdate(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    speed_kmh: Optional[float] = Field(None, ge=0)
    heading: Optional[int] = Field(None, ge=0, le=360)


class TripStart(BaseModel):
    route_id: str
    scheduled_departure: Optional[datetime] = None


class TripEnd(BaseModel):
    passenger_count: Optional[int] = Field(None, ge=0)


class PassengerCountUpdate(BaseModel):
    passenger_count: int = Field(..., ge=0)


class VehicleCreate(BaseModel):
    vehicle_id: str
    name: str
    name_ar: str
    vehicle_type: Literal["bus", "microbus", "taxi"]
    capacity: int = Field(..., ge=1)
    gps_device_id: Optional[str] = None
    is_real_gps: bool = True


class VehicleUpdate(BaseModel):
    name: Optional[str] = None
    name_ar: Optional[str] = None
    capacity: Optional[int] = None
    status: Optional[Literal["active", "idle", "maintenance", "decommissioned"]] = None


class VehicleAssign(BaseModel):
    """Either field may be omitted to leave it unchanged; explicit empty
    string clears the assignment."""

    route_id: Optional[str] = None
    driver_id: Optional[str] = None


class RouteCreate(BaseModel):
    route_id: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=120)
    name_ar: str = Field(..., min_length=1, max_length=120)
    route_type: Literal["bus", "microbus", "taxi"] = "bus"
    color: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    distance_km: Optional[float] = Field(None, ge=0, le=500)
    avg_duration_min: Optional[int] = Field(None, ge=0, le=1440)
    fare_syp: Optional[int] = Field(None, ge=0, le=1_000_000)


class RouteUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    name_ar: Optional[str] = Field(None, min_length=1, max_length=120)
    color: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    distance_km: Optional[float] = Field(None, ge=0, le=500)
    avg_duration_min: Optional[int] = Field(None, ge=0, le=1440)
    fare_syp: Optional[int] = Field(None, ge=0, le=1_000_000)
    is_active: Optional[bool] = None


class AlertResponse(BaseModel):
    id: str
    vehicle_id: str
    alert_type: str
    severity: str
    title: str
    title_ar: str
    description: Optional[str] = None
    is_resolved: bool
    created_at: str


class AlertResolve(BaseModel):
    resolved: bool = True


# ── Payments (Sham Cash) ──────────────────────────────────────────────────────


class PaymentInitiateRequest(BaseModel):
    """Passenger scanned a vehicle QR and wants to pay the fare."""

    qr: str = Field(..., min_length=16, max_length=1024)  # signed QR payload
    amount_syp: int = Field(..., gt=0, le=1_000_000)


class PaymentInitiateResponse(BaseModel):
    payment_id: str
    status: str
    amount_syp: int
    vehicle_code: Optional[str] = None
    deeplink: Optional[str] = None  # shamcash:// link or sandbox hint
    sandbox: bool = True
    expires_at: Optional[str] = None


class PaymentStatusResponse(BaseModel):
    payment_id: str
    status: str
    amount_syp: int
    confirmed_at: Optional[str] = None
    sandbox: bool = True


class ShamCashWebhookPayload(BaseModel):
    """Callback body from Sham Cash (or the sandbox simulator)."""

    payment_id: str = Field(..., min_length=8, max_length=64)
    provider_ref: str = Field(..., min_length=4, max_length=128)
    result: Literal["success", "failure"]
    amount_syp: int = Field(..., gt=0)
    payer_hint: Optional[str] = Field(None, max_length=32)


class ScheduleResponse(BaseModel):
    id: str
    route_id: str
    day_of_week: int
    first_departure: str
    last_departure: str
    frequency_min: int


class AnalyticsOverview(BaseModel):
    total_vehicles: int
    active_vehicles: int
    idle_vehicles: int
    # Fix 2026-06-11: the admin dashboard read trips_today/open_alerts/
    # pending_vehicles but the API never returned them (KPIs showed "—").
    trips_today: Optional[int] = None
    open_alerts: Optional[int] = None
    pending_vehicles: Optional[int] = None
    maintenance_vehicles: int
    total_routes: int
    active_routes: int
    total_stops: int
    total_drivers: int
    active_drivers: int
    avg_occupancy_pct: Optional[float] = None


class PositionData(BaseModel):
    vehicle_id: str
    vehicle_name: str
    vehicle_name_ar: str
    latitude: float
    longitude: float
    speed_kmh: Optional[float]
    occupancy_pct: Optional[int]
    timestamp: str


class NearestStop(BaseModel):
    id: str
    stop_id: str
    name: str
    name_ar: str
    latitude: float
    longitude: float
    distance_m: Optional[float] = None
    has_shelter: bool


class TraccarPosition(BaseModel):
    deviceId: int
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    speed: Optional[float] = None
    heading: Optional[float] = None
    accuracy: Optional[float] = None
    timestamp: int


class TraccarEvent(BaseModel):
    eventId: Optional[int] = None
    type: str
    serverTime: int
    deviceId: int
    deviceName: str
    data: dict


class OperatorCreate(BaseModel):
    slug: str
    name: str
    name_ar: Optional[str] = None
    plan: str = "basic"
    settings: Optional[Dict[str, Any]] = None


class OperatorUpdate(BaseModel):
    name: Optional[str] = None
    name_ar: Optional[str] = None
    plan: Optional[str] = None
    is_active: Optional[bool] = None
    settings: Optional[Dict[str, Any]] = None


class OperatorResponse(BaseModel):
    id: str
    slug: str
    name: str
    name_ar: Optional[str] = None
    plan: str
    is_active: bool
    settings: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None


class PushSubscription(BaseModel):
    endpoint: str
    keys: Dict[str, str]


class PushSubscribeRequest(BaseModel):
    subscription: PushSubscription
    stopIds: Optional[list] = None
    role: Optional[str] = (
        None  # "passenger" | "driver" — overridden by JWT role if present
    )
    operator: Optional[str] = Field(
        None, max_length=64
    )  # operator slug for tenant-scoped notifications


class PushBroadcastRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=1000)
    icon: Optional[str] = Field(None, max_length=500)
    role: Optional[str] = None  # broadcast only to this role; None = all
    data: Optional[Dict[str, Any]] = None

    @field_validator("title", "body", mode="before")
    @classmethod
    def sanitize_text(cls, v):
        return _strip_html(v)


class NotificationTestRequest(BaseModel):
    email: str = Field(..., max_length=254)
    kind: Literal["alert", "welcome"] = "alert"

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("Invalid email address")
        return v


class FeedbackCreate(BaseModel):
    trip_id: str = Field(..., min_length=1, max_length=36)
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=2000)
    categories: Optional[List[str]] = None
    is_anonymous: bool = False

    @field_validator("comment", mode="before")
    @classmethod
    def sanitize_comment(cls, v):
        return _strip_html(v)


class FeedbackResponse(BaseModel):
    id: str
    trip_id: str
    driver_id: Optional[str] = None
    passenger_id: Optional[str] = None
    rating: int
    comment: Optional[str] = None
    categories: List[str] = []
    is_anonymous: bool
    created_at: Optional[str] = None


class DriverRatingSummary(BaseModel):
    driver_id: str
    total_reviews: int
    average_rating: Optional[float] = None
    five_star: int = 0
    four_star: int = 0
    three_star: int = 0
    two_star: int = 0
    one_star: int = 0
    last_reviewed_at: Optional[str] = None


class ETAArrival(BaseModel):
    vehicle_id: str
    vehicle_name: str
    vehicle_name_ar: str
    route_name: Optional[str] = None
    route_name_ar: Optional[str] = None
    eta_minutes: int
    distance_km: float
    speed_kmh: Optional[float] = None
    source: str = "estimated"  # "real" | "estimated"


class StopETAResponse(BaseModel):
    stop_id: str
    stop_name: str
    stop_name_ar: str
    arrivals: List[ETAArrival]
    updated_at: str


# ── Generic response models for endpoints returning simple dicts ─────────────


class StatusTimestampResponse(BaseModel):
    status: str
    timestamp: str


class TripActionResponse(BaseModel):
    status: str
    trip_id: Optional[str] = None
    timestamp: str


class MessageResponse(BaseModel):
    message: str


class WebhookResponse(BaseModel):
    status: str
    timestamp: Optional[str] = None
    reason: Optional[str] = None
    detail: Optional[str] = None


class VapidKeyResponse(BaseModel):
    publicKey: str
    enabled: bool


class PushSubscribeResponse(BaseModel):
    status: str
    endpoint: str
    role: str


class PushUnsubscribeResponse(BaseModel):
    status: str


class PushBroadcastResponse(BaseModel):
    sent: int
    failed: int
    skipped: int


class PushTestResponse(BaseModel):
    status: str
    count: Optional[int] = None
    message: Optional[str] = None


class WsStatsResponse(BaseModel):
    active_connections: int
