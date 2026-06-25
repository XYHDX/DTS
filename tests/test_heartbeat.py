"""Fleet-wide telemetry heartbeat watchdog — api/routers/cron.py.

Verifies the system-level GPS-silence detector: fresh -> ok, stale -> silent,
never-reported -> silent. Patches the DB readers so it's hermetic.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from api.routers import cron


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _patch(monkeypatch, last, count):
    async def _last():
        return last

    async def _count():
        return count

    monkeypatch.setattr(cron, "_last_position_update", _last)
    monkeypatch.setattr(cron, "_active_vehicle_count", _count)


def test_heartbeat_ok_when_recent(monkeypatch):
    recent = datetime.now(timezone.utc) - timedelta(seconds=10)
    _patch(monkeypatch, _iso(recent), 4)
    res = asyncio.run(cron._check_telemetry_heartbeat())
    assert res["status"] == "ok"
    assert res["age_seconds"] is not None and res["age_seconds"] < 120


def test_heartbeat_silent_when_stale(monkeypatch):
    stale = datetime.now(timezone.utc) - timedelta(
        seconds=cron.TELEMETRY_SILENCE_THRESHOLD_S + 600
    )
    _patch(monkeypatch, _iso(stale), 4)
    res = asyncio.run(cron._check_telemetry_heartbeat())
    assert res["status"] == "silent"
    assert res["age_seconds"] > cron.TELEMETRY_SILENCE_THRESHOLD_S


def test_heartbeat_silent_when_never_reported(monkeypatch):
    _patch(monkeypatch, None, 0)
    res = asyncio.run(cron._check_telemetry_heartbeat())
    assert res["status"] == "silent"
    assert res["age_seconds"] is None
