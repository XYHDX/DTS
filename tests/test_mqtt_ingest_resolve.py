"""Friendly fleet-code → UUID resolution in api/routers/mqtt_ingest.py.

Lets firmware publish a human code like "DTS002" instead of the vehicle UUID;
the ingest pipeline rewrites it to the canonical UUID so the live map, Redis
geo, and vehicle_positions all key on the same id.
"""

from __future__ import annotations

import asyncio
import os

os.environ.setdefault("SUPABASE_URL", "http://mock-supabase.local")
os.environ.setdefault("SUPABASE_KEY", "mock-key")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "mock-service-key")
os.environ.setdefault("JWT_SECRET", "test-secret-for-ci-only-xxxxxxxxxxxxxxxxx")

import pytest  # noqa: E402

import api.routers.mqtt_ingest as mi  # noqa: E402

VID = "11111111-2222-3333-4444-555555555555"


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _clear_caches():
    mi._resolve_cache.clear()
    mi._approval_cache.clear()
    yield
    mi._resolve_cache.clear()
    mi._approval_cache.clear()


def test_resolve_by_fleet_code_queries_text_column(monkeypatch):
    seen = {}

    async def fake_get(path):
        seen["path"] = path
        return [{"id": VID, "operator_id": "op-1"}]

    monkeypatch.setattr("api.core.database._service_get", fake_get)
    out = _run(mi._resolve_vehicle("DTS002"))
    assert out == (VID, "op-1")
    assert "vehicle_id=eq.DTS002" in seen["path"]  # matched the human code column


def test_resolve_by_uuid_queries_id_column(monkeypatch):
    seen = {}

    async def fake_get(path):
        seen["path"] = path
        return [{"id": VID, "operator_id": "op-1"}]

    monkeypatch.setattr("api.core.database._service_get", fake_get)
    out = _run(mi._resolve_vehicle(VID))
    assert out == (VID, "op-1")
    assert f"id=eq.{VID}" in seen["path"]


def test_ingest_rewrites_code_to_uuid(monkeypatch):
    async def fake_get(path):
        if "vehicle_id=eq.DTS002" in path:
            return [{"id": VID, "operator_id": "op-1"}]
        # approval-gate lookup by the resolved UUID
        return [{"id": VID, "approval_status": "approved", "is_active": True}]

    monkeypatch.setattr("api.core.database._service_get", fake_get)

    geo = {}
    persisted = {}

    async def fake_geo(*, operator_id, vehicle_id, lat, lon):
        geo["vehicle_id"] = vehicle_id
        geo["operator_id"] = operator_id

    async def fake_persist(decoded, *, fuel_smoothed):
        persisted["vehicle_id"] = decoded.vehicle_id

    async def fake_pub(**kwargs):
        pass

    monkeypatch.setattr(mi, "geo_update", fake_geo)
    monkeypatch.setattr(mi, "_persist", fake_persist)
    monkeypatch.setattr(mi.live_bus, "publish", fake_pub)

    decoded = mi._PartialDecode(
        vehicle_id="DTS002",
        timestamp=1718540000000,
        latitude=33.5,
        longitude=36.3,
        operator_id="op-1",
    )
    _run(mi._ingest(decoded))

    assert decoded.vehicle_id == VID  # rewritten code → UUID
    assert geo["vehicle_id"] == VID  # live map keyed by the UUID
    assert persisted["vehicle_id"] == VID  # history persisted under the UUID


def test_ingest_unknown_id_is_dropped_not_rewritten(monkeypatch):
    # DB reachable but nothing matches → resolve returns None and the approval
    # gate drops the frame (fail-open only happens on a DB *error*).
    async def fake_get(path):
        return []

    monkeypatch.setattr("api.core.database._service_get", fake_get)

    called = {"geo": False}

    async def fake_geo(*, operator_id, vehicle_id, lat, lon):
        called["geo"] = True

    async def fake_persist(decoded, *, fuel_smoothed):
        pass

    async def fake_pub(**kwargs):
        pass

    monkeypatch.setattr(mi, "geo_update", fake_geo)
    monkeypatch.setattr(mi, "_persist", fake_persist)
    monkeypatch.setattr(mi.live_bus, "publish", fake_pub)

    decoded = mi._PartialDecode(
        vehicle_id="UNKNOWN-XYZ",
        timestamp=1718540000000,
        latitude=33.5,
        longitude=36.3,
        operator_id="op-1",
    )
    _run(mi._ingest(decoded))
    assert decoded.vehicle_id == "UNKNOWN-XYZ"  # not rewritten / not blanked
    assert called["geo"] is False  # unknown vehicle dropped at the approval gate


def test_persist_uses_upsert_rpc_not_raw_insert(monkeypatch):
    """Regression for the silent telemetry-drop bug (C1).

    _persist must go through the upsert_vehicle_position RPC (correct columns +
    PostGIS point, updates vehicle_positions_latest) — NOT a raw insert of the
    non-existent ts/lat/lon/speed columns, which failed and was swallowed.
    """
    calls = {}

    async def fake_rpc(func_name, params):
        calls["func"] = func_name
        calls["params"] = params
        return None

    async def fake_post(path, data):  # must NOT be used by _persist anymore
        calls["post_path"] = path
        return {}

    monkeypatch.setattr("api.core.database._service_rpc", fake_rpc)
    monkeypatch.setattr("api.core.database._service_post", fake_post)

    decoded = mi._PartialDecode(
        vehicle_id=VID,
        timestamp=1718540000000,
        latitude=33.5,
        longitude=36.3,
        operator_id="op-1",
    )
    _run(mi._persist(decoded, fuel_smoothed=None))

    assert calls.get("func") == "upsert_vehicle_position"
    assert "post_path" not in calls  # no raw vehicle_positions insert
    p = calls["params"]
    assert p["p_vehicle_id"] == VID
    assert p["p_lat"] == 33.5 and p["p_lon"] == 36.3
    assert p["p_source"] == "mqtt"
