"""
Tests for WebSocket real-time vehicle tracking (ConnectionManager upgrade).
"""

import json
import pytest

from api.routers.websocket import ConnectionManager


class TestConnectionManager:
    def test_connect_increments_count(self):
        mgr = ConnectionManager()
        assert mgr.count == 0

        class FakeWS:
            pass

        ws = FakeWS()
        mgr.connect(ws)
        assert mgr.count == 1

    def test_disconnect_removes_connection(self):
        mgr = ConnectionManager()

        class FakeWS:
            pass

        ws = FakeWS()
        mgr.connect(ws)
        mgr.disconnect(ws)
        assert mgr.count == 0

    def test_disconnect_unknown_is_safe(self):
        mgr = ConnectionManager()

        class FakeWS:
            pass

        mgr.disconnect(FakeWS())

    def test_subscribe_updates_route_filter(self):
        mgr = ConnectionManager()

        class FakeWS:
            pass

        ws = FakeWS()
        mgr.connect(ws)
        mgr.subscribe(ws, "route-123")
        assert mgr._connections[ws] == "route-123"

    def test_subscribe_unknown_ws_is_safe(self):
        mgr = ConnectionManager()

        class FakeWS:
            pass

        mgr.subscribe(FakeWS(), "route-123")

    @pytest.mark.anyio
    async def test_broadcast_positions_filters_by_route(self):
        mgr = ConnectionManager()
        received_a = []
        received_b = []

        class FakeWS:
            def __init__(self, store):
                self._store = store

            async def send_text(self, text):
                self._store.append(json.loads(text))

        ws_a = FakeWS(received_a)
        ws_b = FakeWS(received_b)
        mgr.connect(ws_a, route_id="route-001")
        mgr.connect(ws_b, route_id=None)

        positions = [
            {"vehicle_id": "v1", "route_id": "route-001", "latitude": 33.5},
            {"vehicle_id": "v2", "route_id": "route-002", "latitude": 33.6},
        ]
        await mgr.broadcast_positions(positions)

        assert len(received_a) == 1
        assert len(received_a[0]["data"]) == 1
        assert received_a[0]["data"][0]["vehicle_id"] == "v1"

        assert len(received_b) == 1
        assert len(received_b[0]["data"]) == 2

    @pytest.mark.anyio
    async def test_broadcast_removes_dead_connections(self):
        mgr = ConnectionManager()

        class DeadWS:
            async def send_text(self, text):
                raise RuntimeError("connection closed")

        ws = DeadWS()
        mgr.connect(ws)
        assert mgr.count == 1

        await mgr.broadcast_positions([])
        assert mgr.count == 0

    @pytest.mark.anyio
    async def test_broadcast_alert_sends_to_all(self):
        mgr = ConnectionManager()
        received_a = []
        received_b = []

        class FakeWS:
            def __init__(self, store):
                self._store = store

            async def send_text(self, text):
                self._store.append(json.loads(text))

        mgr.connect(FakeWS(received_a), route_id="route-001")
        mgr.connect(FakeWS(received_b), route_id="route-002")

        await mgr.broadcast_alert({"alert_id": "a1", "message": "Geofence exit"})

        assert received_a[0]["type"] == "geofence_alert"
        assert received_b[0]["type"] == "geofence_alert"


class TestWebSocketStatsEndpoint:
    def test_stats_returns_connection_count(self, client):
        response = client.get("/api/ws/stats")
        assert response.status_code == 200
        data = response.json()
        assert "active_connections" in data
        assert isinstance(data["active_connections"], int)
