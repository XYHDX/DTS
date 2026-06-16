"""Tests for the MQTT consumer worker (api/workers/mqtt_consumer.py).

Dependency-light: drives the async handler with ``asyncio.run`` (same style as
tests/test_live_bus.py) and stubs the shared ``_ingest`` pipeline + geo cache so
nothing touches a broker, Redis, or the database.
"""

from __future__ import annotations

import asyncio
import json

import pytest

import api.workers.mqtt_consumer as mc


def _run(coro):
    return asyncio.run(coro)


def _frame(vehicle_id="BUS-101", **over):
    f = {
        "vehicle_id": vehicle_id,
        "operator_id": "00000000-0000-0000-0000-000000000001",
        "timestamp": 1718540000000,
        "latitude": 33.5138,
        "longitude": 36.2765,
        "speed_kph": 12.3,
        "heading": 90.0,
        "engine_state": True,
    }
    f.update(over)
    return f


@pytest.fixture
def captured(monkeypatch):
    """Stub _ingest + geo_cache.remove_position; record what they receive."""
    ingested = []
    removed = []

    async def fake_ingest(decoded):
        ingested.append(decoded)

    async def fake_remove(*, operator_id, vehicle_id):
        removed.append((operator_id, vehicle_id))

    monkeypatch.setattr(mc, "_ingest", fake_ingest)
    monkeypatch.setattr(mc.geo_cache, "remove_position", fake_remove)
    return ingested, removed


# ── _frames() decoder ──────────────────────────────────────────────────────
class TestFrames:
    def test_single_object(self):
        out = mc._frames(json.dumps(_frame()).encode())
        assert len(out) == 1 and out[0]["vehicle_id"] == "BUS-101"

    def test_json_array_batch(self):
        out = mc._frames(json.dumps([_frame("A"), _frame("B")]).encode())
        assert [f["vehicle_id"] for f in out] == ["A", "B"]

    def test_wrapped_frames_key(self):
        out = mc._frames(json.dumps({"frames": [_frame("X")]}).encode())
        assert len(out) == 1 and out[0]["vehicle_id"] == "X"

    def test_non_dict_items_filtered(self):
        out = mc._frames(json.dumps([_frame("A"), 7, "nope"]).encode())
        assert len(out) == 1 and out[0]["vehicle_id"] == "A"

    def test_scalar_payload_is_empty(self):
        assert mc._frames(b"42") == []


# ── _handle() ──────────────────────────────────────────────────────────────
class TestHandle:
    def test_valid_status_frame_ingested(self, captured):
        ingested, _ = captured
        _run(mc._handle("vehicles/BUS-101/status", json.dumps(_frame()).encode()))
        assert len(ingested) == 1
        d = ingested[0]
        assert d.vehicle_id == "BUS-101"
        assert d.latitude == 33.5138 and d.longitude == 36.2765

    def test_batch_ingests_each(self, captured):
        ingested, _ = captured
        payload = json.dumps([_frame("A"), _frame("B")]).encode()
        _run(mc._handle("vehicles/+/status", payload))
        assert [d.vehicle_id for d in ingested] == ["A", "B"]

    def test_malformed_json_does_not_crash(self, captured):
        ingested, _ = captured
        _run(mc._handle("vehicles/BUS-1/status", b"{ not json"))
        assert ingested == []

    def test_invalid_frame_is_skipped(self, captured):
        ingested, _ = captured
        bad = _frame()
        del bad["latitude"]  # required field missing
        _run(mc._handle("vehicles/BUS-1/status", json.dumps(bad).encode()))
        assert ingested == []

    def test_event_engine_off_removes_from_geo(self, captured):
        ingested, removed = captured
        payload = json.dumps(_frame(engine_state=False)).encode()
        _run(mc._handle("vehicles/BUS-101/event", payload))
        assert len(ingested) == 1  # still ingested
        assert removed == [("00000000-0000-0000-0000-000000000001", "BUS-101")]

    def test_status_topic_never_removes(self, captured):
        _, removed = captured
        payload = json.dumps(_frame(engine_state=False)).encode()
        _run(mc._handle("vehicles/BUS-101/status", payload))
        assert removed == []  # /status is not an event — no geo removal
