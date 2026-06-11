"""Tests for the live position bus — Phase S3.4 of Scale_100k_Roadmap.md.

These run with **no real Redis**: they exercise the in-memory backend and the
disabled-default behaviour. The pub/sub round-trip semantics are backend-agnostic
(the Redis backend implements the same publish/subscribe contract), so the memory
backend is a faithful stand-in for unit coverage.

Deliberately dependency-light: uses ``asyncio.run`` instead of pytest-asyncio so
it runs anywhere pytest is installed.

Run with: pytest tests/test_live_bus.py -v
"""

import asyncio

import pytest

from api.core import live_bus


def run(coro):
    return asyncio.run(coro)


# ─── helpers ──────────────────────────────────────────────────────────────────


async def _primed_subscriber(operator_id):
    """Start a subscriber and return (async_gen, task-awaiting-first-item).

    The task is scheduled and given a tick to register on its channel and block
    on the queue, so a subsequent publish is guaranteed to reach it.
    """
    agen = live_bus.subscribe(operator_id=operator_id)
    iterator = agen.__aiter__()
    task = asyncio.ensure_future(iterator.__anext__())
    await asyncio.sleep(0.05)  # let the generator register + block on get()
    return agen, task


# ─── 1. Disabled by default ─────────────────────────────────────────────────


class TestDisabledDefault:
    def test_not_configured_without_env(self, monkeypatch):
        monkeypatch.delenv("REDIS_PUBSUB_URL", raising=False)
        monkeypatch.delenv("LIVE_BUS_BACKEND", raising=False)
        live_bus._reset_for_test()
        assert live_bus.configured() is False
        assert live_bus.backend_name() == "disabled"

    def test_publish_is_noop_when_disabled(self, monkeypatch):
        monkeypatch.delenv("REDIS_PUBSUB_URL", raising=False)
        monkeypatch.delenv("LIVE_BUS_BACKEND", raising=False)
        live_bus._reset_for_test()
        ok = run(live_bus.publish(operator_id="op-A", payload={"vehicle_id": "V1"}))
        assert ok is False

    def test_subscribe_ends_immediately_when_disabled(self, monkeypatch):
        monkeypatch.delenv("REDIS_PUBSUB_URL", raising=False)
        monkeypatch.delenv("LIVE_BUS_BACKEND", raising=False)
        live_bus._reset_for_test()

        async def scenario():
            received = []
            async for item in live_bus.subscribe(operator_id="op-A"):
                received.append(item)
            return received

        assert run(scenario()) == []


# ─── 2. Memory backend selection ─────────────────────────────────────────────


class TestBackendSelection:
    def test_redis_url_selects_redis_backend(self, monkeypatch):
        monkeypatch.setenv("REDIS_PUBSUB_URL", "redis://localhost:6379/0")
        live_bus._reset_for_test()
        try:
            assert live_bus.configured() is True
            assert live_bus.backend_name() == "redis"
        finally:
            live_bus._reset_for_test()

    def test_memory_env_selects_memory_backend(self, monkeypatch):
        monkeypatch.delenv("REDIS_PUBSUB_URL", raising=False)
        monkeypatch.setenv("LIVE_BUS_BACKEND", "memory")
        live_bus._reset_for_test()
        try:
            assert live_bus.configured() is True
            assert live_bus.backend_name() == "memory"
        finally:
            live_bus._reset_for_test()

    def test_redis_url_wins_over_memory(self, monkeypatch):
        monkeypatch.setenv("REDIS_PUBSUB_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("LIVE_BUS_BACKEND", "memory")
        live_bus._reset_for_test()
        try:
            assert live_bus.backend_name() == "redis"
        finally:
            live_bus._reset_for_test()


# ─── 3. Publish → subscribe round-trip (memory backend) ──────────────────────


class TestRoundTrip:
    def setup_method(self):
        live_bus._use_memory_backend()

    def teardown_method(self):
        live_bus._reset_for_test()

    def test_subscriber_receives_published_payload(self):
        async def scenario():
            agen, task = await _primed_subscriber("op-A")
            payload = {"vehicle_id": "V1", "latitude": 33.51, "longitude": 36.29}
            await live_bus.publish(operator_id="op-A", payload=payload)
            item = await asyncio.wait_for(task, timeout=1.0)
            await agen.aclose()
            return item

        assert run(scenario()) == {
            "vehicle_id": "V1",
            "latitude": 33.51,
            "longitude": 36.29,
        }

    def test_multiple_subscribers_all_receive(self):
        async def scenario():
            a_gen, a_task = await _primed_subscriber("op-A")
            b_gen, b_task = await _primed_subscriber("op-A")
            await live_bus.publish(operator_id="op-A", payload={"vehicle_id": "V2"})
            a = await asyncio.wait_for(a_task, timeout=1.0)
            b = await asyncio.wait_for(b_task, timeout=1.0)
            await a_gen.aclose()
            await b_gen.aclose()
            return a, b

        a, b = run(scenario())
        assert a == {"vehicle_id": "V2"}
        assert b == {"vehicle_id": "V2"}


# ─── 4. Operator isolation + firehose ────────────────────────────────────────


class TestOperatorIsolation:
    def setup_method(self):
        live_bus._use_memory_backend()

    def teardown_method(self):
        live_bus._reset_for_test()

    def test_subscriber_does_not_receive_other_operators(self):
        async def scenario():
            agen, task = await _primed_subscriber("op-A")
            # Publish for a DIFFERENT operator — op-A must not see it.
            await live_bus.publish(operator_id="op-B", payload={"vehicle_id": "VB"})
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=0.2)
                leaked = True
            except asyncio.TimeoutError:
                leaked = False
            # Cancel the in-flight __anext__ and let it unwind (runs the
            # generator's finally) before we stop referencing it.
            task.cancel()
            try:
                await task
            except BaseException:
                pass
            return leaked

        assert run(scenario()) is False

    def test_firehose_receives_every_operator(self):
        async def scenario():
            # operator_id=None subscribes to the firehose.
            agen, task = await _primed_subscriber(None)
            await live_bus.publish(operator_id="op-B", payload={"vehicle_id": "VB"})
            item = await asyncio.wait_for(task, timeout=1.0)
            await agen.aclose()
            return item

        assert run(scenario()) == {"vehicle_id": "VB"}


# ─── 5. /api/stream uses the bus when configured ─────────────────────────────


class TestStreamEndpointUsesBus:
    """End-to-end-ish: drive the route generator with the memory bus, no DB."""

    def setup_method(self):
        live_bus._use_memory_backend()

    def teardown_method(self):
        live_bus._reset_for_test()

    def test_stream_emits_snapshot_then_bus_updates(self):
        try:
            import api.routers.stream as stream_mod
        except Exception:  # pragma: no cover - only when FastAPI stack absent
            pytest.skip("API stack not importable in this environment")

        async def fake_snapshot(op_id):
            return ['data: {"snapshot": true}\n\n']

        # Avoid any database call — the snapshot is stubbed.
        stream_mod._snapshot_frames = fake_snapshot

        # 2026-06-11: public streams are always operator-scoped now; stub the
        # scope resolution so no DB is touched and publish to that channel.
        async def fake_scope(operator, current_user):
            return "op-test"

        stream_mod.resolve_read_scope = fake_scope

        async def scenario():
            resp = await stream_mod.stream_positions(operator=None, current_user=None)
            body = resp.body_iterator

            first = await asyncio.wait_for(body.__anext__(), timeout=1.0)

            # Drive the generator to the subscribe/await point, then publish.
            nxt = asyncio.ensure_future(body.__anext__())
            await asyncio.sleep(0.05)
            await live_bus.publish(operator_id="op-test", payload={"vehicle_id": "V7"})
            second = await asyncio.wait_for(nxt, timeout=2.0)

            await body.aclose()
            return first, second

        first, second = run(scenario())
        assert first == 'data: {"snapshot": true}\n\n'
        assert second.startswith("data: ")
        assert '"vehicle_id": "V7"' in second


if __name__ == "__main__":
    import os
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=os.path.join(os.path.dirname(__file__), ".."),
    )
    sys.exit(result.returncode)
