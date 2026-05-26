import hashlib
import hmac
import os
import sys
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException, Request, status
import urllib.parse

from api.core.database import _supabase_get, _supabase_post, _supabase_rpc
from api.core.logging import logger
from api.models.schemas import TraccarEvent, TraccarPosition, WebhookResponse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
try:
    from lib.email import send_alert_email as _send_alert_email  # noqa: E402

    _email_available = True
except ImportError:
    _email_available = False

router = APIRouter()

TRACCAR_WEBHOOK_SECRET = os.getenv("TRACCAR_WEBHOOK_SECRET")
if not TRACCAR_WEBHOOK_SECRET:
    logger.warning(
        "TRACCAR_WEBHOOK_SECRET is not set. "
        "Traccar webhook endpoints will reject all requests until configured."
    )


def _require_secret() -> str:
    """Return the webhook secret or raise 503 if not configured."""
    if not TRACCAR_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Traccar webhook integration is not configured.",
        )
    return TRACCAR_WEBHOOK_SECRET


def verify_traccar_signature(request_body: bytes, signature: str) -> bool:
    """Verify Traccar webhook signature using HMAC."""
    secret = _require_secret()
    computed = hmac.new(secret.encode(), request_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)


@router.post("/api/traccar/position", response_model=WebhookResponse, tags=["traccar"])
async def traccar_position_webhook(
    position: TraccarPosition,
    request: Request,
    x_traccar_signature: str = Header(..., description="HMAC-SHA256 signature"),
):
    """Webhook for Traccar GPS position updates. Secured by HMAC signature."""
    raw_body = await request.body()
    if not verify_traccar_signature(raw_body, x_traccar_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )

    try:
        quoted_id = urllib.parse.quote(position.deviceId, safe="")
        devices = await _supabase_get(
            f"vehicles?gps_device_id=eq.{quoted_id}&select=id,vehicle_id"
        )
        if not devices:
            return {"status": "ignored", "reason": "device_not_found"}

        vehicle = devices[0]

        await _supabase_rpc(
            "upsert_vehicle_position",
            {
                "p_vehicle_id": vehicle["id"],
                "p_lat": position.latitude,
                "p_lon": position.longitude,
                "p_speed": position.speed or 0,
                "p_heading": position.heading or 0,
                "p_source": "traccar",
                "p_route_id": None,
                "p_occupancy": None,
            },
        )

        return {"status": "success", "timestamp": datetime.utcnow().isoformat()}

    except Exception as e:
        logger.error("Traccar position webhook error", extra={"error": str(e)})
        return {"status": "error", "detail": str(e)}


@router.post("/api/traccar/event", response_model=WebhookResponse, tags=["traccar"])
async def traccar_event_webhook(
    event: TraccarEvent,
    request: Request,
    x_traccar_signature: str = Header(..., description="HMAC-SHA256 signature"),
):
    """Webhook for Traccar events (engine on/off, speeding, etc). Secured by HMAC."""
    raw_body = await request.body()
    if not verify_traccar_signature(raw_body, x_traccar_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )

    try:
        quoted_id = urllib.parse.quote(event.deviceId, safe="")
        devices = await _supabase_get(
            f"vehicles?gps_device_id=eq.{quoted_id}&select=id"
        )
        if not devices:
            return {"status": "ignored", "reason": "device_not_found"}

        vehicle_id = devices[0]["id"]

        event_type_map = {
            "motion": "speeding",
            "overspeed": "speeding",
            "geofenceEnter": "geofence_enter",
            "geofenceExit": "geofence_exit",
            "deviceOffline": "offline",
            "deviceOnline": "online",
        }

        alert_type = event_type_map.get(event.type, event.type)
        critical_events = ["overspeed", "geofenceExit", "deviceOffline"]

        if event.type in critical_events:
            severity = "high" if event.type == "overspeed" else "medium"
            alert_data = {
                "vehicle_id": vehicle_id,
                "alert_type": alert_type,
                "severity": severity,
                "title": f"Alert: {event.type}",
                "title_ar": f"تنبيه: {event.type}",
                "description": f"Event from Traccar: {event.data}",
                "is_resolved": False,
            }
            await _supabase_post("alerts", alert_data)

            if _email_available:
                import asyncio

                asyncio.create_task(
                    _send_alert_email(
                        alert_type=alert_type,
                        severity=severity,
                        title=f"Alert: {event.type}",
                        vehicle_id=event.deviceName,
                        description=f"Event from Traccar: {event.data}",
                        created_at=datetime.utcnow().isoformat(),
                    )
                )

        return {"status": "success", "timestamp": datetime.utcnow().isoformat()}

    except Exception as e:
        logger.error("Traccar event webhook error", extra={"error": str(e)})
        return {"status": "error", "detail": str(e)}
