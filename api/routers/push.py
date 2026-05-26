import json
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

from api.core.auth import CurrentUser, optional_auth, require_role
from api.core.cache import (
    RATE_LIMIT_PUSH_SUB,
    _cache_delete,
    _cache_set,
    _get_client_ip,
    _get_redis_client,
    _rate_limit_check,
)
from api.core.logging import logger
from api.models.schemas import (
    PushBroadcastRequest,
    PushBroadcastResponse,
    PushSubscribeRequest,
    PushSubscribeResponse,
    PushTestResponse,
    PushUnsubscribeResponse,
    VapidKeyResponse,
)

try:
    from pywebpush import webpush, WebPushException

    _webpush_available = True
except ImportError:
    _webpush_available = False

router = APIRouter()

# In-memory push subscription store (keyed by endpoint URL).
# Each value: {"subscription": {...}, "stopIds": [...], "role": "passenger"|"driver", "createdAt": "..."}
# For production, migrate to Supabase push_subscriptions table.
_push_subscriptions: dict = {}


def _get_vapid_claims() -> dict:
    """Build VAPID claims dict from environment variables."""
    return {
        "sub": os.environ.get("VAPID_SUBJECT", "mailto:admin@damascustransit.sy"),
    }


async def send_push_notification(
    subscription_info: dict,
    title: str,
    body: str,
    icon: str = "/passenger/manifest.json",
    data: Optional[dict] = None,
    endpoint: Optional[str] = None,
) -> bool:
    """Send a Web Push notification using VAPID.

    Returns True on success, False on failure. Expired subscriptions
    are pruned automatically (410 Gone).
    """
    if not _webpush_available:
        logger.warning("pywebpush not installed — push notification skipped")
        return False

    vapid_private = os.environ.get("VAPID_PRIVATE_KEY", "")
    vapid_public = os.environ.get("VAPID_PUBLIC_KEY", "")
    if not vapid_private or not vapid_public:
        logger.warning("VAPID keys not configured — push notification skipped")
        return False

    payload = json.dumps(
        {
            "title": title,
            "body": body,
            "icon": icon,
            "data": data or {},
        }
    )

    try:
        webpush(
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=vapid_private,
            vapid_claims=_get_vapid_claims(),
        )
        return True
    except WebPushException as e:
        status_code = getattr(e.response, "status_code", None) if e.response else None
        if status_code == 410:
            # Subscription expired — remove it
            ep = endpoint or subscription_info.get("endpoint", "")
            if ep:
                _push_subscriptions.pop(ep, None)
                redis = _get_redis_client()
                if redis:
                    try:
                        await _cache_delete(f"push_sub:{ep}")
                    except Exception:
                        pass
            logger.info("Removed expired push subscription", extra={"endpoint": ep})
        else:
            logger.warning(
                "WebPush send failed", extra={"error": str(e), "status": status_code}
            )
        return False
    except Exception as e:
        logger.warning("Push notification error", extra={"error": str(e)})
        return False


@router.get(
    "/api/push/vapid-public-key", response_model=VapidKeyResponse, tags=["push"]
)
async def get_vapid_public_key():
    """Return the VAPID public key for Web Push subscription setup."""
    key = os.environ.get("VAPID_PUBLIC_KEY", "")
    return {"publicKey": key, "enabled": bool(key)}


@router.post("/api/push/subscribe", response_model=PushSubscribeResponse, tags=["push"])
async def subscribe_push(
    req: PushSubscribeRequest,
    raw_request: Request,
    current_user: Optional[CurrentUser] = Depends(optional_auth),
):
    """Store a Web Push subscription.

    Passengers associate subscriptions with stop IDs to receive arrival alerts.
    Drivers receive dispatch and route-change notifications.
    """
    client_ip = _get_client_ip(raw_request)
    max_req, window = RATE_LIMIT_PUSH_SUB
    if not await _rate_limit_check(f"pushsub:{client_ip}", max_req, window):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many subscription requests. Try again later.",
        )

    # Determine role — authenticated driver/admin roles win; fallback to request body
    role = req.role or "passenger"
    if current_user and current_user.role in ("driver", "admin", "dispatcher"):
        role = current_user.role

    endpoint = req.subscription.endpoint
    _push_subscriptions[endpoint] = {
        "subscription": req.subscription.model_dump(),
        "stopIds": req.stopIds or [],
        "role": role,
        "userId": current_user.user_id if current_user else None,
        "createdAt": datetime.utcnow().isoformat(),
    }

    redis = _get_redis_client()
    if redis:
        try:
            await _cache_set(
                f"push_sub:{endpoint}",
                _push_subscriptions[endpoint],
                ttl=60 * 60 * 24 * 30,
            )
        except Exception:
            pass

    return {"status": "subscribed", "endpoint": endpoint, "role": role}


@router.delete(
    "/api/push/subscribe", response_model=PushUnsubscribeResponse, tags=["push"]
)
async def unsubscribe_push(req: dict):
    """Remove a Web Push subscription by endpoint URL."""
    endpoint = req.get("endpoint", "")
    _push_subscriptions.pop(endpoint, None)
    redis = _get_redis_client()
    if redis:
        try:
            await _cache_delete(f"push_sub:{endpoint}")
        except Exception:
            pass
    return {"status": "unsubscribed"}


@router.post("/api/push/broadcast", response_model=PushBroadcastResponse, tags=["push"])
async def broadcast_push(
    req: PushBroadcastRequest,
    current_user: CurrentUser = Depends(require_role("admin")),
):
    """Broadcast a push notification to all matching subscribers (admin only).

    Filter by role ('passenger', 'driver', or None for all).
    Returns counts of sent/failed/skipped notifications.
    """
    if not _webpush_available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="pywebpush is not installed on this server.",
        )

    sent = 0
    failed = 0
    skipped = 0

    for ep, record in list(_push_subscriptions.items()):
        # Role filter
        if req.role and record.get("role") != req.role:
            skipped += 1
            continue

        ok = await send_push_notification(
            subscription_info=record["subscription"],
            title=req.title,
            body=req.body,
            icon=req.icon or "/passenger/manifest.json",
            data=req.data,
            endpoint=ep,
        )
        if ok:
            sent += 1
        else:
            failed += 1

    return {"sent": sent, "failed": failed, "skipped": skipped}


@router.post("/api/push/test", response_model=PushTestResponse, tags=["push"])
async def test_push_self(
    current_user: CurrentUser = Depends(require_role("admin")),
):
    """Send a test push notification to all current admin subscriptions."""
    if not _webpush_available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="pywebpush is not installed on this server.",
        )

    admin_subs = [
        (ep, rec)
        for ep, rec in _push_subscriptions.items()
        if rec.get("userId") == current_user.user_id
    ]
    if not admin_subs:
        return {
            "status": "no_subscriptions",
            "message": "No push subscriptions found for your account.",
        }

    sent = 0
    for ep, record in admin_subs:
        ok = await send_push_notification(
            subscription_info=record["subscription"],
            title="Damascus Transit — Test Notification",
            body="Push notifications are working correctly.",
            endpoint=ep,
        )
        if ok:
            sent += 1

    return {"status": "sent" if sent else "failed", "count": sent}
