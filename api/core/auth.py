import asyncio
import contextvars
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel

JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Name of the httpOnly cookie that carries the JWT for browser clients.
# Native (Capacitor) and any header-based client keep using the
# `Authorization: Bearer` scheme; web clients use this cookie so the token is
# never readable from JavaScript (mitigates XSS token theft).
AUTH_COOKIE_NAME = "dt_token"

security = HTTPBearer(auto_error=False)
optional_security = HTTPBearer(auto_error=False)


def _token_from_request(request: Request) -> Optional[str]:
    """Extract the JWT from either the Authorization header or the auth cookie.

    Preference order: a well-formed ``Authorization: Bearer <token>`` header
    (used by the native driver app and API clients) first, then the
    ``dt_token`` httpOnly cookie (used by the browser admin console). A literal
    ``Bearer null`` / empty header is ignored so the cookie can still win.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        candidate = auth_header[len("Bearer ") :].strip()
        if candidate and candidate.lower() != "null":
            return candidate
    cookie_token = request.cookies.get(AUTH_COOKIE_NAME)
    if cookie_token and cookie_token.strip():
        return cookie_token.strip()
    return None


UserRole = Literal["admin", "dispatcher", "driver", "viewer", "super_admin"]

current_user_token = contextvars.ContextVar("current_user_token", default=None)

_PLACEHOLDER_JWT_SECRETS = {"change-me-to-a-random-64-char-string", "secret", ""}


def _get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "")
    if not secret or secret in _PLACEHOLDER_JWT_SECRETS or len(secret) < 32:
        raise HTTPException(
            status_code=500,
            detail="JWT_SECRET is not configured or is too weak (minimum 32 characters required)",
        )
    return secret


class TokenPayload(BaseModel):
    user_id: str
    email: str
    role: UserRole
    exp: datetime
    iat: Optional[datetime] = None
    operator_id: Optional[str] = None
    vehicle_id: Optional[str] = None
    vehicle_route_id: Optional[str] = None


class CurrentUser(BaseModel):
    user_id: str
    email: str
    role: UserRole
    operator_id: Optional[str] = None
    vehicle_id: Optional[str] = None
    vehicle_route_id: Optional[str] = None


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
    except (ValueError, TypeError):
        return False


def create_access_token(
    user_id: str,
    email: str,
    role: UserRole,
    expires_delta: Optional[timedelta] = None,
    operator_id: Optional[str] = None,
    vehicle_id: Optional[str] = None,
    vehicle_route_id: Optional[str] = None,
) -> str:
    if expires_delta is None:
        expires_delta = timedelta(hours=JWT_EXPIRATION_HOURS)

    now = datetime.utcnow()
    expire = now + expires_delta
    # iat enables password-change revocation: tokens issued before
    # users.password_changed_at can be rejected at verify time.
    to_encode: dict = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "exp": expire,
        "iat": now,
    }

    if operator_id is not None:
        to_encode["operator_id"] = operator_id
    if vehicle_id is not None:
        to_encode["vehicle_id"] = vehicle_id
    if vehicle_route_id is not None:
        to_encode["vehicle_route_id"] = vehicle_route_id

    return jwt.encode(to_encode, _get_jwt_secret(), algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> TokenPayload:
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("user_id")
        email: str = payload.get("email")
        role: str = payload.get("role")

        if user_id is None or email is None or role is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload"
            )

        return TokenPayload(
            user_id=user_id,
            email=email,
            role=role,
            exp=payload.get("exp"),
            iat=payload.get("iat"),
            operator_id=payload.get("operator_id"),
            vehicle_id=payload.get("vehicle_id"),
            vehicle_route_id=payload.get("vehicle_route_id"),
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )


# ---------------------------------------------------------------------------
# M1 — per-user revocation-state TTL cache (password_changed_at + is_active).
#
# We never want to hit Supabase on every authenticated request, so cache the
# user's revocation state for `_REVOCATION_CACHE_TTL` seconds. The cache is
# protected by an asyncio lock to coalesce concurrent lookups for the same user.
# ---------------------------------------------------------------------------
_REVOCATION_CACHE_TTL = 5  # seconds
# user_id -> (cached_at_monotonic, password_changed_at, is_active)
_revocation_cache: dict[str, tuple[float, Optional[datetime], Optional[bool]]] = {}
_revocation_lock = asyncio.Lock()


async def _lookup_revocation_state(
    user_id: str,
) -> tuple[Optional[datetime], Optional[bool]]:
    """Best-effort fetch of users.(password_changed_at, is_active), cached briefly.

    Returns (None, None) when the database is unreachable. Transport failures
    soft-fail (delayed revocation, never unauthenticated access). When the DB
    answers and the user row is missing, is_active resolves to False so
    deleted users are rejected (fail-closed on a definitive answer).
    """
    now = time.monotonic()
    cached = _revocation_cache.get(user_id)
    if cached is not None and (now - cached[0]) < _REVOCATION_CACHE_TTL:
        return cached[1], cached[2]

    async with _revocation_lock:
        cached = _revocation_cache.get(user_id)
        if (
            cached is not None
            and (time.monotonic() - cached[0]) < _REVOCATION_CACHE_TTL
        ):
            return cached[1], cached[2]
        password_changed_at: Optional[datetime] = None
        is_active: Optional[bool] = None
        try:
            # Lazy import to avoid a circular dep at module load time.
            from api.core.database import _service_get  # type: ignore

            rows = await _service_get(
                f"users?id=eq.{user_id}&select=password_changed_at,is_active"
            )
            if rows:
                raw = rows[0].get("password_changed_at")
                if raw:
                    password_changed_at = datetime.fromisoformat(
                        raw.replace("Z", "+00:00")
                    )
                is_active = bool(rows[0].get("is_active", True))
            else:
                # Definitive DB answer: the user no longer exists.
                is_active = False
        except Exception:
            # Soft-fail on transport errors — treated as not revoked.
            password_changed_at = None
            is_active = None
        _revocation_cache[user_id] = (time.monotonic(), password_changed_at, is_active)
        return password_changed_at, is_active


async def _lookup_password_changed_at(user_id: str) -> Optional[datetime]:
    """Backward-compatible wrapper kept for existing tests/callers."""
    pwd_changed_at, _ = await _lookup_revocation_state(user_id)
    return pwd_changed_at


async def get_current_user(request: Request) -> CurrentUser:
    token = _token_from_request(request)
    if not token:
        # No credentials at all → 401 Unauthorized (an authenticated user with
        # the wrong role gets 403 from require_role instead).
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    current_user_token.set(token)
    token_payload = verify_token(token)

    pwd_changed_at, is_active = await _lookup_revocation_state(token_payload.user_id)

    # Security fix (2026-06-11): deactivating an account now revokes its
    # live tokens within _REVOCATION_CACHE_TTL seconds (previously a disabled
    # user kept a valid token for up to 24 hours).
    if is_active is False:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated.",
        )

    # M1 — reject tokens issued before the user's last password change.
    if token_payload.iat is not None and is_token_revoked_by_password_change(
        token_payload.iat, pwd_changed_at
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token revoked — password was changed after this token was issued",
        )

    return CurrentUser(
        user_id=token_payload.user_id,
        email=token_payload.email,
        role=token_payload.role,
        operator_id=token_payload.operator_id,
        vehicle_id=token_payload.vehicle_id,
        vehicle_route_id=token_payload.vehicle_route_id,
    )


def is_token_revoked_by_password_change(
    token_iat: Optional[datetime], password_changed_at: Optional[datetime]
) -> bool:
    """M1 fix: tokens issued before the user's last password change are revoked.

    Call this from authenticated request handlers after looking up the user's
    password_changed_at column. Returns True if the caller should reject the token.
    Both sides are normalised to UTC-aware datetimes to avoid TypeError when one
    side is naive (Pydantic-decoded JWT iat) and the other is aware (Supabase).
    """
    if password_changed_at is None or token_iat is None:
        return False

    def _utc(dt: datetime) -> datetime:
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

    return _utc(token_iat) < _utc(password_changed_at)


def require_role(*allowed_roles: UserRole):
    async def role_checker(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {', '.join(allowed_roles)}",
            )
        return current_user

    return role_checker


def optional_auth(request: Request) -> Optional[CurrentUser]:
    token = _token_from_request(request)
    if token is None:
        current_user_token.set(None)
        return None
    current_user_token.set(token)
    token_payload = verify_token(token)
    return CurrentUser(
        user_id=token_payload.user_id,
        email=token_payload.email,
        role=token_payload.role,
        operator_id=token_payload.operator_id,
        vehicle_id=token_payload.vehicle_id,
        vehicle_route_id=token_payload.vehicle_route_id,
    )
