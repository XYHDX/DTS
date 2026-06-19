import hmac
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request

from api.core.database import _service_get, _service_patch, _service_post
from api.core.logging import logger
from api.routers.admin import _run_simulation

router = APIRouter()

CRON_SECRET = os.getenv("CRON_SECRET", "")

# The daily simulator writes synthetic GPS for EVERY active vehicle — a demo
# aid, not something that should ever run against a production fleet (it would
# overwrite real tracking). It is therefore OFF by default and only runs when
# SIMULATION_ENABLED is explicitly truthy. The manual, admin-gated
# POST /api/admin/simulate is unaffected and still works for demos.
SIMULATION_ENABLED = os.getenv("SIMULATION_ENABLED", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

# A real-GPS vehicle with no fix for longer than this is "silent" and raises a
# (deduped) connection_lost alert; the alert auto-resolves when it reports
# again. Override with the SILENT_BUS_THRESHOLD_S env var.
SILENT_BUS_THRESHOLD_S = int(os.getenv("SILENT_BUS_THRESHOLD_S", "300"))  # 5 min


@router.get("/api/cron/simulate", tags=["cron"])
async def cron_simulate_positions(request: Request):
    """Vercel Cron endpoint — generates simulated GPS positions on schedule.

    Secured by CRON_SECRET env var. Add to vercel.json crons config.
    The comparison is constant-time (hmac.compare_digest) to prevent a
    byte-by-byte timing oracle on the secret.
    """
    auth = request.headers.get("authorization", "")
    if not CRON_SECRET or not hmac.compare_digest(auth, f"Bearer {CRON_SECRET}"):
        raise HTTPException(status_code=401, detail="Invalid cron secret")
    # Disabled in production unless explicitly opted in — never overwrite a real
    # fleet's live positions on a schedule. Returns 200 so the scheduler does not
    # treat the skip as a failure and retry.
    if not SIMULATION_ENABLED:
        logger.info("cron_simulate skipped — SIMULATION_ENABLED is not set")
        return {"status": "disabled", "updated": 0}
    try:
        return await _run_simulation()
    except Exception as e:
        logger.error("Simulation failed", extra={"error": str(e)})
        logger.error("Unexpected error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Silent-bus detection (Phase 2 — hands-off reliability)
#
# A real-GPS vehicle that stops reporting (dead tracker, no signal, power loss)
# would silently vanish from the map with no warning. This scan raises a
# `connection_lost` alert through the existing alerts pipeline so it appears on
# the dispatcher dashboard, and auto-resolves it the moment the bus reports
# again. Reuses the existing alert_type enum — no schema change required.
# ---------------------------------------------------------------------------
def _parse_ts(raw):
    """Best-effort parse of an ISO timestamp to a UTC-aware datetime."""
    try:
        dt = (
            raw
            if isinstance(raw, datetime)
            else datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        )
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


async def _raise_silent_alert(vehicle: dict, last_dt: datetime) -> None:
    mins = SILENT_BUS_THRESHOLD_S // 60
    name = vehicle.get("name") or vehicle.get("vehicle_id") or "vehicle"
    name_ar = vehicle.get("name_ar") or name
    fleet = vehicle.get("vehicle_id") or ""
    try:
        await _service_post(
            "alerts",
            {
                "vehicle_id": vehicle["id"],
                "alert_type": "connection_lost",
                "severity": "warning",
                "title": f"GPS offline: {name} ({fleet})",
                "title_ar": f"انقطاع إشارة التتبع: {name_ar}",
                "description": (
                    f"No GPS fix for over {mins} min (last seen {last_dt.isoformat()})."
                ),
                "is_resolved": False,
                "operator_id": vehicle.get("operator_id"),
            },
        )
    except Exception:
        logger.error("silent-bus alert insert failed", exc_info=True)


async def _resolve_silent_alert(alert_id: str) -> None:
    try:
        await _service_patch(
            f"alerts?id=eq.{alert_id}",
            {
                "is_resolved": True,
                "resolved_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception:
        logger.error("silent-bus alert resolve failed", exc_info=True)


async def _scan_silent_buses() -> dict:
    """Raise/clear connection_lost alerts for stale real-GPS vehicles.

    Monitors approved, active, real-GPS vehicles. A vehicle with a last fix
    older than the threshold gets one alert (deduped against any still-open
    one); a vehicle reporting again has its open alert(s) resolved. Vehicles
    that have never reported are skipped (a freshly registered bus is not an
    outage).
    """
    vehicles = (
        await _service_get(
            "vehicles?is_real_gps=eq.true&is_active=eq.true"
            "&select=id,vehicle_id,name,name_ar,operator_id,approval_status"
        )
        or []
    )
    # Filter approval in Python so a missing approval_status column (older
    # schema) can't break the scan.
    monitored = [v for v in vehicles if v.get("approval_status") in (None, "approved")]
    if not monitored:
        return {"monitored": 0, "silent": 0, "raised": 0, "resolved": 0}

    ids = ",".join(v["id"] for v in monitored)
    latest = (
        await _service_get(
            f"vehicle_positions_latest?vehicle_id=in.({ids})"
            "&select=vehicle_id,recorded_at"
        )
        or []
    )
    last_by_id = {r["vehicle_id"]: r.get("recorded_at") for r in latest}

    open_alerts = (
        await _service_get(
            "alerts?is_resolved=eq.false&alert_type=eq.connection_lost"
            "&select=id,vehicle_id"
        )
        or []
    )
    open_by_vehicle: dict[str, list[str]] = {}
    for a in open_alerts:
        open_by_vehicle.setdefault(a["vehicle_id"], []).append(a["id"])

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=SILENT_BUS_THRESHOLD_S)
    silent = raised = resolved = 0

    for v in monitored:
        vid = v["id"]
        last_dt = _parse_ts(last_by_id.get(vid))
        if last_dt is None:
            continue  # never reported — not an outage
        has_alert = vid in open_by_vehicle
        if last_dt < cutoff:
            silent += 1
            if not has_alert:
                await _raise_silent_alert(v, last_dt)
                raised += 1
        elif has_alert:
            for aid in open_by_vehicle[vid]:
                await _resolve_silent_alert(aid)
                resolved += 1

    return {
        "monitored": len(monitored),
        "silent": silent,
        "raised": raised,
        "resolved": resolved,
    }


@router.get("/api/cron/silent_buses", tags=["cron"])
async def cron_silent_buses(request: Request):
    """Cron endpoint — flag real-GPS vehicles whose fix has gone stale.

    Secured by CRON_SECRET (same scheme as /api/cron/simulate). Trigger every
    few minutes from any scheduler (VPS crontab, Vercel Cron on Pro, or an
    external cron service). Idempotent: re-running never double-alerts.
    """
    auth = request.headers.get("authorization", "")
    if not CRON_SECRET or not hmac.compare_digest(auth, f"Bearer {CRON_SECRET}"):
        raise HTTPException(status_code=401, detail="Invalid cron secret")
    try:
        return await _scan_silent_buses()
    except Exception as e:
        logger.error("Silent-bus scan failed", extra={"error": str(e)})
        logger.error("Unexpected error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
