"""Geo-set garbage collector — hot-path hygiene for the Redis live map.

Members linger in the Redis GEO sets forever unless explicitly removed (see the
TTL-hygiene note in ``api/core/geo_cache.py``). This worker periodically drops
vehicles whose last persisted position is older than ``GEO_PRUNE_AFTER_SECONDS``
so the live map doesn't accumulate stale "ghost" buses and Redis memory stays
bounded at scale.

Run it as its own process (it is intentionally NOT started in-band with the API
so the request hot-path stays import-cheap)::

    python -m api.workers.geo_gc

Soft-fail by design: every iteration swallows its errors and retries, so a
Postgres/Redis blip never crashes the worker. No-ops cleanly when Redis is not
configured.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from api.core import geo_cache

logger = logging.getLogger("api.workers.geo_gc")

# Drop a vehicle from the live set once its latest position is older than this.
_PRUNE_AFTER_SECONDS = int(os.getenv("GEO_PRUNE_AFTER_SECONDS", "3600"))
# How often to sweep.
_INTERVAL_SECONDS = int(os.getenv("GEO_PRUNE_INTERVAL_SECONDS", "1800"))


async def _prune_once() -> int:
    """Remove vehicles whose latest position is older than the cutoff.

    Returns the number of members removed. Returns 0 (no-op) when Redis is not
    configured.
    """
    if not geo_cache.configured():
        return 0

    from api.core.database import _service_get  # lazy import — keep startup cheap

    cutoff = (
        datetime.now(timezone.utc) - timedelta(seconds=_PRUNE_AFTER_SECONDS)
    ).isoformat()
    # vehicle_positions_latest holds exactly one row per vehicle with
    # recorded_at; quote the timestamp (it contains ':') for the PostgREST path.
    rows = await _service_get(
        "vehicle_positions_latest"
        f"?recorded_at=lt.{quote(cutoff, safe='')}"
        "&select=vehicle_id,operator_id"
    )
    removed = 0
    for r in rows or []:
        vid = r.get("vehicle_id")
        if not vid:
            continue
        op = r.get("operator_id") or "default"
        if await geo_cache.remove_position(operator_id=op, vehicle_id=vid):
            removed += 1
    return removed


async def run() -> None:
    logger.info(
        "geo_gc start: prune vehicles idle > %ss, sweep every %ss",
        _PRUNE_AFTER_SECONDS,
        _INTERVAL_SECONDS,
    )
    while True:
        try:
            n = await _prune_once()
            if n:
                logger.info("geo_gc pruned %d stale vehicle(s) from the live set", n)
        except Exception as e:  # never crash the loop
            logger.warning("geo_gc iteration failed: %s", e)
        await asyncio.sleep(_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(run())
