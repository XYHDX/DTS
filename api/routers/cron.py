import os

from fastapi import APIRouter, HTTPException, Request

from api.core.logging import logger
from api.routers.admin import _run_simulation

router = APIRouter()

CRON_SECRET = os.getenv("CRON_SECRET", "")


@router.get("/api/cron/simulate", tags=["cron"])
async def cron_simulate_positions(request: Request):
    """Vercel Cron endpoint — generates simulated GPS positions on schedule.

    Secured by CRON_SECRET env var. Add to vercel.json crons config.
    """
    auth = request.headers.get("authorization", "")
    if not CRON_SECRET or auth != f"Bearer {CRON_SECRET}":
        raise HTTPException(status_code=401, detail="Invalid cron secret")
    try:
        return await _run_simulation()
    except Exception as e:
        logger.error("Simulation failed", extra={"error": str(e)})
        logger.error("Unexpected error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
