"""Redis Geo cache — sub-millisecond nearest-vehicle and live-map queries.

Implements §4.A of transit_architecture_guide.md and step S3.1 of
Scale_100k_Roadmap.md.

Why this exists
---------------
At 100,000 vehicles the live-map query ("which vehicles are within X metres
of this point?") cannot afford a PostGIS round-trip on every request. Redis'
GEO commands run in memory at O(log N) — well under a millisecond even with
millions of members per set.

Soft-fail design
----------------
When Upstash Redis is not configured (`UPSTASH_REDIS_REST_URL` empty), every
function in this module returns a sensible neutral value: `update_position`
becomes a no-op, `nearest_vehicles` returns an empty list. The caller can
remain in the legacy PostGIS path without branching.
"""

from __future__ import annotations

import os
from typing import Iterable, Optional

from api.core.cache import _get_redis_client


def _key(operator_id: str) -> str:
    """Per-operator key so multi-tenant queries don't bleed across operators."""
    safe = (operator_id or "default").replace(":", "_")
    return f"geo:vehicles:{safe}"


def configured() -> bool:
    return _get_redis_client() is not None


async def update_position(
    *,
    operator_id: str,
    vehicle_id: str,
    lat: float,
    lon: float,
) -> bool:
    """Upsert a vehicle's last-known position into the operator's GEO set.

    Returns True when the write succeeded, False otherwise. Soft-fails on
    any exception — telemetry ingestion never fails because of a Redis blip.
    """
    client = _get_redis_client()
    if client is None:
        return False
    try:
        # Upstash REST exposes the same surface as redis-py for these calls.
        await client.geoadd(
            _key(operator_id),
            (lon, lat, vehicle_id),
        )
        return True
    except Exception:
        return False


async def remove_position(*, operator_id: str, vehicle_id: str) -> bool:
    """Pull a vehicle out of the live set (called on trip end / device off)."""
    client = _get_redis_client()
    if client is None:
        return False
    try:
        await client.zrem(_key(operator_id), vehicle_id)
        return True
    except Exception:
        return False


async def nearest_vehicles(
    *,
    operator_id: str,
    lat: float,
    lon: float,
    radius_m: int = 1500,
    limit: int = 25,
) -> list[dict[str, float | str]]:
    """Return at most `limit` vehicles within `radius_m` of (lat, lon).

    Output shape (sorted ascending by distance):
        [
          { "vehicle_id": "DAM-024", "lat": 33.51, "lon": 36.29, "distance_m": 142.3 },
          ...
        ]
    """
    client = _get_redis_client()
    if client is None:
        return []
    try:
        # GEOSEARCH replaces the deprecated GEORADIUS. Returns
        # [(member, distance_m_str, (lon, lat))] when requested with
        # WITHDIST + WITHCOORD.
        raw = await client.geosearch(
            _key(operator_id),
            longitude=lon,
            latitude=lat,
            radius=radius_m,
            unit="m",
            sort="ASC",
            count=limit,
            withdist=True,
            withcoord=True,
        )
    except Exception:
        return []

    results: list[dict[str, float | str]] = []
    for entry in raw or []:
        try:
            # Upstash returns dicts; redis-py returns tuples. Handle both.
            if isinstance(entry, dict):
                member = entry.get("member")
                dist   = float(entry.get("dist", 0))
                coords = entry.get("coords") or (0.0, 0.0)
                lon_, lat_ = float(coords[0]), float(coords[1])
            else:
                member, dist_raw, coord = entry
                dist = float(dist_raw)
                lon_, lat_ = float(coord[0]), float(coord[1])
            results.append({
                "vehicle_id": str(member),
                "lat":        lat_,
                "lon":        lon_,
                "distance_m": dist,
            })
        except (TypeError, ValueError, IndexError):
            continue
    return results


async def bulk_positions(
    *,
    operator_id: str,
    vehicle_ids: Iterable[str],
) -> dict[str, tuple[float, float]]:
    """Look up known positions for a set of vehicles in a single GEOPOS call.

    Returns { vehicle_id: (lat, lon) } omitting unknowns.
    """
    client = _get_redis_client()
    if client is None:
        return {}
    members = list(vehicle_ids)
    if not members:
        return {}
    try:
        raw = await client.geopos(_key(operator_id), *members)
    except Exception:
        return {}
    out: dict[str, tuple[float, float]] = {}
    for vid, pos in zip(members, raw or []):
        if not pos:
            continue
        try:
            lon_, lat_ = float(pos[0]), float(pos[1])
            out[vid] = (lat_, lon_)
        except (TypeError, ValueError, IndexError):
            continue
    return out


# ─── TTL hygiene ──────────────────────────────────────────────────────────
#
# Members linger in a Redis GEO set forever unless explicitly removed.
# At 100k vehicles with churn this matters. The recommended pattern is:
#
#   1. Every 30 minutes a small worker iterates `vehicles` table for rows
#      where last_seen_at is older than 1 hour and calls remove_position()
#      for each.
#   2. The MQTT broker's `LWT` (last will and testament) tells the backend
#      to call remove_position() when a device drops cleanly.
#
# The implementation of that worker lives in api/workers/geo_gc.py — not
# in this module so the hot-path stays import-cheap.

_PRUNE_AFTER_SECONDS = int(os.getenv("GEO_PRUNE_AFTER_SECONDS", "3600"))
