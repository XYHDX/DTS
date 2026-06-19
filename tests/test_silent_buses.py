"""Silent-bus detection (api/routers/cron.py).

A real-GPS vehicle that stops sending fixes raises a deduped `connection_lost`
alert on the dispatcher dashboard; the alert auto-resolves when the bus reports
again. Vehicles that have never reported are not treated as outages.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("SUPABASE_URL", "http://mock-supabase.local")
os.environ.setdefault("SUPABASE_KEY", "mock-key")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "mock-service-key")
os.environ.setdefault("JWT_SECRET", "test-secret-for-ci-only-xxxxxxxxxxxxxxxxx")

import api.routers.cron as cron  # noqa: E402

VID = "11111111-2222-3333-4444-555555555555"


def _run(coro):
    return asyncio.run(coro)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _vehicle(**kw):
    base = {
        "id": VID,
        "vehicle_id": "DTS002",
        "name": "Real Bus",
        "name_ar": "حافلة حقيقية",
        "operator_id": "op-1",
        "approval_status": "approved",
    }
    base.update(kw)
    return base


def _patch_services(monkeypatch, vehicles, latest, open_alerts):
    posts: list = []
    patches: list = []

    async def fake_get(query):
        if query.startswith("vehicles?"):
            return vehicles
        if query.startswith("vehicle_positions_latest?"):
            return latest
        if query.startswith("alerts?"):
            return open_alerts
        return []

    async def fake_post(table, payload):
        posts.append((table, payload))
        return {"id": "alert-new"}

    async def fake_patch(query, payload):
        patches.append((query, payload))
        return [{"id": "patched"}]

    monkeypatch.setattr(cron, "_service_get", fake_get)
    monkeypatch.setattr(cron, "_service_post", fake_post)
    monkeypatch.setattr(cron, "_service_patch", fake_patch)
    return posts, patches


def test_raises_alert_for_silent_vehicle(monkeypatch):
    stale = _iso(datetime.now(timezone.utc) - timedelta(minutes=20))
    posts, _ = _patch_services(
        monkeypatch,
        vehicles=[_vehicle()],
        latest=[{"vehicle_id": VID, "recorded_at": stale}],
        open_alerts=[],
    )
    result = _run(cron._scan_silent_buses())
    assert result == {"monitored": 1, "silent": 1, "raised": 1, "resolved": 0}
    assert posts and posts[0][0] == "alerts"
    assert posts[0][1]["alert_type"] == "connection_lost"
    assert posts[0][1]["severity"] == "warning"
    assert posts[0][1]["vehicle_id"] == VID


def test_dedupes_existing_open_alert(monkeypatch):
    stale = _iso(datetime.now(timezone.utc) - timedelta(minutes=20))
    posts, _ = _patch_services(
        monkeypatch,
        vehicles=[_vehicle()],
        latest=[{"vehicle_id": VID, "recorded_at": stale}],
        open_alerts=[{"id": "a1", "vehicle_id": VID}],
    )
    result = _run(cron._scan_silent_buses())
    assert result["silent"] == 1 and result["raised"] == 0
    assert posts == []  # no duplicate alert raised


def test_resolves_when_reporting_again(monkeypatch):
    fresh = _iso(datetime.now(timezone.utc) - timedelta(seconds=30))
    _, patches = _patch_services(
        monkeypatch,
        vehicles=[_vehicle()],
        latest=[{"vehicle_id": VID, "recorded_at": fresh}],
        open_alerts=[{"id": "a1", "vehicle_id": VID}],
    )
    result = _run(cron._scan_silent_buses())
    assert result["resolved"] == 1 and result["raised"] == 0
    assert patches and patches[0][1]["is_resolved"] is True


def test_skips_never_reported(monkeypatch):
    posts, _ = _patch_services(
        monkeypatch,
        vehicles=[_vehicle()],
        latest=[],  # no position row at all
        open_alerts=[],
    )
    result = _run(cron._scan_silent_buses())
    assert result == {"monitored": 1, "silent": 0, "raised": 0, "resolved": 0}
    assert posts == []


def test_endpoint_requires_secret(client, monkeypatch):
    monkeypatch.setattr(cron, "CRON_SECRET", "topsecret")
    r = client.get("/api/cron/silent_buses")  # no Authorization header
    assert r.status_code == 401


def test_endpoint_runs_with_secret(client, monkeypatch):
    monkeypatch.setattr(cron, "CRON_SECRET", "topsecret")

    async def fake_scan():
        return {"monitored": 2, "silent": 0, "raised": 0, "resolved": 0}

    monkeypatch.setattr(cron, "_scan_silent_buses", fake_scan)
    r = client.get(
        "/api/cron/silent_buses",
        headers={"Authorization": "Bearer topsecret"},
    )
    assert r.status_code == 200
    assert r.json()["monitored"] == 2
