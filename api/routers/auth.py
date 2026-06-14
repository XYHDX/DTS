import asyncio
import hashlib
import logging
import os
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from api.core.auth import (
    AUTH_COOKIE_NAME,
    JWT_EXPIRATION_HOURS,
    CurrentUser,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from api.core.cache import RATE_LIMIT_LOGIN, _rate_limit_check
from api.core.database import (
    _service_get,
    _supabase_get,
    _supabase_patch,
    _supabase_post,
)
from api.core.turnstile import verify_turnstile
from api.models.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    ProfileUpdateRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/auth/login", response_model=TokenResponse, tags=["auth"])
async def login(request: LoginRequest, raw_request: Request, response: Response):
    """Authenticate user and return JWT token.

    The token is returned in the body (for native/Capacitor and API clients
    that use the ``Authorization: Bearer`` scheme) AND set as an httpOnly
    cookie (for the browser admin console, so the token is never readable from
    JavaScript). Either transport is accepted on subsequent requests.
    """
    client_ip = raw_request.client.host if raw_request.client else "unknown"
    max_req, window = RATE_LIMIT_LOGIN
    if not await _rate_limit_check(f"login:{client_ip}", max_req, window):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later.",
            headers={"Retry-After": str(window)},
        )
    # Captcha (Cloudflare Turnstile) — no-op unless TURNSTILE_SECRET is set.
    # Security fix (2026-06-11): this helper existed but was never called,
    # leaving login brute-force protection to the IP rate limit alone.
    await verify_turnstile(raw_request)
    try:
        # Service-key read: the `users` table is tenant-scoped under RLS
        # (migration 002). An anonymous login request has no JWT, so an anon
        # read returns zero rows and every login fails with "Invalid
        # credentials" — even for valid accounts. Auth must look up the user
        # with the service role. (users stays private; never exposed via anon.)
        users = await _service_get(
            f"users?email=eq.{urllib.parse.quote(request.email, safe='')}&select=id,email,password_hash,role,operator_id,is_active"
        )

        if not users:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )

        user = users[0]

        if not verify_password(request.password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )

        # Security fix (2026-06-11): deactivated accounts could previously
        # still log in — is_active was never checked at login time.
        if user.get("is_active") is False:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated. Contact your administrator.",
            )

        operator_id = user.get("operator_id")

        vehicle_id = None
        vehicle_route_id = None
        if user["role"] == "driver":
            driver_vehicles = await _service_get(
                f"vehicles?assigned_driver_id=eq.{user['id']}&select=id,assigned_route_id"
            )
            if driver_vehicles:
                vehicle_id = driver_vehicles[0]["id"]
                vehicle_route_id = driver_vehicles[0].get("assigned_route_id")

        token = create_access_token(
            user_id=user["id"],
            email=user["email"],
            role=user["role"],
            operator_id=operator_id,
            vehicle_id=vehicle_id,
            vehicle_route_id=vehicle_route_id,
        )

        # Set the httpOnly auth cookie for browser clients. `remember` makes it
        # persistent (capped at the token's own 24h lifetime); otherwise it's a
        # session cookie cleared when the browser closes.
        response.set_cookie(
            key=AUTH_COOKIE_NAME,
            value=token,
            max_age=(JWT_EXPIRATION_HOURS * 3600) if request.remember else None,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
        )

        return TokenResponse(access_token=token, user_id=user["id"], role=user["role"])

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/api/auth/logout", response_model=MessageResponse, tags=["auth"])
async def logout(response: Response):
    """Clear the browser auth cookie.

    Bearer/native clients simply discard their token client-side; this endpoint
    exists so the browser console can revoke its httpOnly cookie (which JS can't
    delete itself).
    """
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return {"message": "Logged out."}


@router.post("/api/auth/register", response_model=UserResponse, tags=["auth"])
async def register(request: RegisterRequest, raw_request: Request):
    """Self-service user registration. Creates a viewer-role account."""
    client_ip = raw_request.client.host if raw_request.client else "unknown"
    if not await _rate_limit_check(f"register:{client_ip}", 5, 60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Try again later.",
            headers={"Retry-After": "60"},
        )
    try:
        if len(request.password) < 8:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Password must be at least 8 characters.",
            )

        existing = await _supabase_get(
            f"users?email=eq.{urllib.parse.quote(request.email, safe='')}&select=id"
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Email already registered."
            )

        hashed = hash_password(request.password)
        new_user = {
            "email": request.email,
            "password_hash": hashed,
            "full_name": request.full_name,
            "full_name_ar": request.full_name_ar,
            "role": "viewer",
            "phone": request.phone,
            "is_active": True,
        }
        result = await _supabase_post("users", new_user)
        created = result if isinstance(result, dict) else (result[0] if result else {})

        try:
            import sys
            import os

            sys.path.insert(
                0, os.path.join(os.path.dirname(__file__), "..", "..", "..")
            )
            from lib.email import send_welcome_email

            asyncio.create_task(
                send_welcome_email(
                    full_name=created.get("full_name", request.full_name),
                    email=created.get("email", request.email),
                    role="viewer",
                )
            )
        except ImportError:
            pass

        return UserResponse(
            id=created.get("id"),
            email=created.get("email"),
            full_name=created.get("full_name"),
            full_name_ar=created.get("full_name_ar"),
            role=created.get("role", "viewer"),
            phone=created.get("phone"),
            is_active=created.get("is_active", True),
            created_at=created.get("created_at"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/api/auth/forgot-password", response_model=MessageResponse, tags=["auth"])
async def forgot_password(request: ForgotPasswordRequest, raw_request: Request):
    """Initiate a password reset. Always returns 200 to avoid user enumeration."""
    client_ip = raw_request.client.host if raw_request.client else "unknown"
    if not await _rate_limit_check(f"forgot:{client_ip}", 3, 60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many password reset attempts. Try again later.",
            headers={"Retry-After": "60"},
        )
    try:
        users = await _supabase_get(
            f"users?email=eq.{urllib.parse.quote(request.email, safe='')}&select=id,email,full_name,is_active"
        )
        if not users or not users[0].get("is_active"):
            return {
                "message": "If that email is registered, a reset email has been sent."
            }

        user = users[0]

        # Generate a cryptographically secure token; store only its hash.
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()

        await _supabase_post(
            "password_reset_tokens",
            {
                "user_id": user["id"],
                "token_hash": token_hash,
                "expires_at": expires_at,
            },
        )

        base_url = os.getenv("APP_BASE_URL", "https://damascustransit.sy")
        # /admin/reset.html is the real page that consumes the token
        # (the old /reset-password path never existed — dead link in emails).
        reset_url = f"{base_url}/admin/reset.html?token={raw_token}"

        try:
            import sys

            sys.path.insert(
                0, os.path.join(os.path.dirname(__file__), "..", "..", "..")
            )
            from lib.email import send_password_reset_email

            asyncio.create_task(
                send_password_reset_email(
                    full_name=user.get("full_name", ""),
                    email=user["email"],
                    reset_url=reset_url,
                )
            )
        except ImportError:
            pass

        return {"message": "If that email is registered, a reset email has been sent."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/api/auth/reset-password", response_model=MessageResponse, tags=["auth"])
async def reset_password(request: ResetPasswordRequest, raw_request: Request):
    """Consume a time-limited reset token and set a new password."""
    client_ip = raw_request.client.host if raw_request.client else "unknown"
    if not await _rate_limit_check(f"reset:{client_ip}", 5, 60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many reset attempts. Try again later.",
            headers={"Retry-After": "60"},
        )
    try:
        token_hash = hashlib.sha256(request.token.encode()).hexdigest()
        now = datetime.now(timezone.utc).isoformat()

        rows = await _supabase_get(
            f"password_reset_tokens?token_hash=eq.{token_hash}"
            f"&expires_at=gt.{urllib.parse.quote(now, safe='')}"
            f"&used_at=is.null"
            f"&select=id,user_id"
        )
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token.",
            )

        token_row = rows[0]

        # Mark token as used before changing the password (prevents replay).
        await _supabase_patch(
            f"password_reset_tokens?id=eq.{token_row['id']}",
            {"used_at": now},
        )

        hashed = hash_password(request.new_password)
        # Set password_changed_at explicitly so JWT revocation works even on
        # databases where the migration-007 trigger is missing (fail-open gap).
        await _supabase_patch(
            f"users?id=eq.{token_row['user_id']}",
            {
                "password_hash": hashed,
                "must_change_password": False,
                "password_changed_at": now,
            },
        )

        return {"message": "Password has been reset successfully. You can now log in."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/api/auth/me", response_model=UserResponse, tags=["auth"])
async def get_my_profile(current_user: CurrentUser = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    try:
        # Service-role read of the caller's OWN row (id comes from the verified
        # token). The `users` table is RLS-scoped, so an anon/token-scoped read
        # returns zero rows → spurious "User not found"; the service key avoids
        # that. Same pattern login() uses to look the user up.
        users = await _service_get(
            f"users?id=eq.{current_user.user_id}&select=id,email,full_name,full_name_ar,role,phone,is_active,created_at"
        )
        if not users:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
            )
        u = users[0]
        return UserResponse(
            id=u["id"],
            email=u["email"],
            full_name=u["full_name"],
            full_name_ar=u.get("full_name_ar"),
            role=u["role"],
            phone=u.get("phone"),
            is_active=u["is_active"],
            created_at=u.get("created_at"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put("/api/auth/me", response_model=UserResponse, tags=["auth"])
async def update_my_profile(
    request: ProfileUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update the authenticated user's profile (name and phone only)."""
    try:
        update_dict: dict = {}
        if request.full_name is not None:
            update_dict["full_name"] = request.full_name
        if request.full_name_ar is not None:
            update_dict["full_name_ar"] = request.full_name_ar
        if request.phone is not None:
            update_dict["phone"] = request.phone

        if not update_dict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update."
            )

        result = await _supabase_patch(
            f"users?id=eq.{current_user.user_id}", update_dict
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
            )
        u = result[0]
        return UserResponse(
            id=u["id"],
            email=u["email"],
            full_name=u["full_name"],
            full_name_ar=u.get("full_name_ar"),
            role=u["role"],
            phone=u.get("phone"),
            is_active=u["is_active"],
            created_at=u.get("created_at"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/api/auth/change-password", response_model=MessageResponse, tags=["auth"])
async def change_password(
    request: ChangePasswordRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Change the authenticated user's password."""
    try:
        if len(request.new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="New password must be at least 8 characters.",
            )

        users = await _supabase_get(
            f"users?id=eq.{current_user.user_id}&select=id,password_hash"
        )
        if not users:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
            )

        if not verify_password(request.current_password, users[0]["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect.",
            )

        hashed = hash_password(request.new_password)
        # Explicit password_changed_at write — see reset_password note.
        await _supabase_patch(
            f"users?id=eq.{current_user.user_id}",
            {
                "password_hash": hashed,
                "must_change_password": False,
                "password_changed_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        return {"message": "Password changed successfully."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
