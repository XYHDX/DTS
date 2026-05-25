"""
Unit tests for GET /api/stops/{stop_id}/eta endpoint.

All Supabase calls are mocked so these tests run without a live database.
"""

import os
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("SUPABASE_URL", "http://mock-supabase.local")
os.environ.setdefault("SUPABASE_KEY", "mock-key")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "mock-service-key")
os.environ.setdefault("SUPABASE_ANON_KEY", "mock-anon-key")
os.environ.setdefault("JWT_SECRET", "test-secret-for-ci-only-xxxxxxxxxxxxxx")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")

# ---------------------------------------------------------------------------
# Fixtures / shared data
# ---------------------------------------------------------------------------

STOP_UUID = "aaaaaaaa-0000-0000-0000-000000000001"
STOP_ID_STR = "STOP-001"

# PostGIS GeoJSON format as returned by Supabase
STOP_LOCATION = {"type": "Point", "coordinates": [36.2963, 33.5117]}  # lon, lat

MOCK_STOP = {
    "id": STOP_UUID,
    "stop_id": STOP_ID_STR,
    "name": "Al-Marjeh Square",
    "name_ar": "ساحة المرجة",
    "location": STOP_LOCATION,
    "has_shelter": True,
    "is_active": True,
    "operator_id": "op-001",
}

ROUTE_UUID = "bbbbbbbb-0000-0000-0000-000000000001"

MOCK_ROUTE_STOP = {"route_id": ROUTE_UUID}
MOCK_ROUTE = {"id": ROUTE_UUID, "name": "Central Route", "name_ar": "الخط المركزي"}

# Vehicle located ~1 km north of the stop, moving at 40 km/h → ~1.5 min ETA
VEHICLE_LOCATION_NEAR = {"type": "Point", "coordinates": [36.2963, 33.5207]}

# Vehicle located ~10 km away → higher ETA
VEHICLE_LOCATION_FAR = {"type": "Point", "coordinates": [36.3900, 33.5700]}

MOCK_POSITION_ON_ROUTE = {
    "vehicle_id": "veh-uuid-001",
    "location": VEHICLE_LOCATION_NEAR,
    "speed_kmh": 40.0,
    "source": "simulator",
    "recorded_at": "2026-04-05T10:00:00Z",
    "vehicles": {
        "id": "veh-uuid-001",
        "vehicle_id": "BUS-001",
        "name": "Bus 001",
        "name_ar": "حافلة 001",
        "assigned_route_id": ROUTE_UUID,
        "status": "active",
    },
}

MOCK_POSITION_FAR = {
    "vehicle_id": "veh-uuid-002",
    "location": VEHICLE_LOCATION_FAR,
    "speed_kmh": 30.0,
    "source": "simulator",
    "recorded_at": "2026-04-05T10:00:00Z",
    "vehicles": {
        "id": "veh-uuid-002",
        "vehicle_id": "BUS-002",
        "name": "Bus 002",
        "name_ar": "حافلة 002",
        "assigned_route_id": None,
        "status": "active",
    },
}

MOCK_POSITION_NO_GPS = {
    "vehicle_id": "veh-uuid-003",
    "location": None,
    "speed_kmh": None,
    "source": "simulator",
    "recorded_at": "2026-04-05T10:00:00Z",
    "vehicles": {
        "id": "veh-uuid-003",
        "vehicle_id": "BUS-003",
        "name": "Bus 003",
        "name_ar": "حافلة 003",
        "assigned_route_id": ROUTE_UUID,
        "status": "active",
    },
}

MOCK_POSITION_DECOMMISSIONED = {
    "vehicle_id": "veh-uuid-004",
    "location": VEHICLE_LOCATION_NEAR,
    "speed_kmh": 50.0,
    "source": "simulator",
    "recorded_at": "2026-04-05T10:00:00Z",
    "vehicles": {
        "id": "veh-uuid-004",
        "vehicle_id": "BUS-004",
        "name": "Bus 004",
        "name_ar": "حافلة 004",
        "assigned_route_id": ROUTE_UUID,
        "status": "decommissioned",
    },
}

MOCK_POSITION_STATIONARY = {
    "vehicle_id": "veh-uuid-005",
    "location": VEHICLE_LOCATION_NEAR,
    "speed_kmh": 0.0,  # stationary → should use city-average speed
    "source": "traccar",
    "recorded_at": "2026-04-05T10:00:00Z",
    "vehicles": {
        "id": "veh-uuid-005",
        "vehicle_id": "BUS-005",
        "name": "Bus 005",
        "name_ar": "حافلة 005",
        "assigned_route_id": ROUTE_UUID,
        "status": "active",
    },
}


# ---------------------------------------------------------------------------
# Helper: build mock _supabase_get that returns different data per query
# ---------------------------------------------------------------------------


def _make_supabase_get(
    stop_rows=None,
    route_stop_rows=None,
    position_rows=None,
    route_rows=None,
):
    """Return an AsyncMock that dispatches based on the query prefix."""
    stop_rows = stop_rows if stop_rows is not None else [MOCK_STOP]
    route_stop_rows = (
        route_stop_rows if route_stop_rows is not None else [MOCK_ROUTE_STOP]
    )
    position_rows = (
        position_rows if position_rows is not None else [MOCK_POSITION_ON_ROUTE]
    )
    route_rows = route_rows if route_rows is not None else [MOCK_ROUTE]

    async def _get(query: str):
        if query.startswith("stops?"):
            return stop_rows
        if query.startswith("route_stops?"):
            return route_stop_rows
        if query.startswith("vehicle_positions_latest"):
            return position_rows
        if query.startswith("routes?"):
            return route_rows
        return []

    return AsyncMock(side_effect=_get)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from api.index import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


class TestGetStopETA:
    """Tests for GET /api/stops/{stop_id}/eta."""

    def test_happy_path_returns_arrivals(self, client):
        """Stop with one nearby vehicle should return one arrival with ETA."""
        mock_get = _make_supabase_get()
        with patch("api.routers.stops._supabase_get", mock_get):
            resp = client.get(f"/api/stops/{STOP_UUID}/eta")
        assert resp.status_code == 200
        data = resp.json()
        assert data["stop_id"] == STOP_ID_STR
        assert data["stop_name"] == "Al-Marjeh Square"
        assert isinstance(data["arrivals"], list)
        assert len(data["arrivals"]) >= 1
        arrival = data["arrivals"][0]
        assert arrival["vehicle_id"] == "BUS-001"
        assert arrival["eta_minutes"] >= 1
        assert arrival["distance_km"] > 0
        assert arrival["source"] == "estimated"
        assert "updated_at" in data

    def test_route_serving_vehicles_sorted_first(self, client):
        """Vehicle on a route serving this stop should appear before unrelated vehicle."""
        mock_get = _make_supabase_get(
            position_rows=[MOCK_POSITION_FAR, MOCK_POSITION_ON_ROUTE]
        )
        with patch("api.routers.stops._supabase_get", mock_get):
            resp = client.get(f"/api/stops/{STOP_UUID}/eta")
        assert resp.status_code == 200
        arrivals = resp.json()["arrivals"]
        assert len(arrivals) >= 2
        # On-route vehicle (BUS-001) should be first since it has route_name set
        assert arrivals[0]["vehicle_id"] == "BUS-001"

    def test_no_vehicles_returns_empty_arrivals(self, client):
        """When no vehicles are in the system, arrivals should be an empty list."""
        mock_get = _make_supabase_get(position_rows=[])
        with patch("api.routers.stops._supabase_get", mock_get):
            resp = client.get(f"/api/stops/{STOP_UUID}/eta")
        assert resp.status_code == 200
        assert resp.json()["arrivals"] == []

    def test_stop_not_found_returns_404(self, client):
        """Unknown stop_id should return 404."""
        mock_get = _make_supabase_get(stop_rows=[])
        with patch("api.routers.stops._supabase_get", mock_get):
            resp = client.get("/api/stops/nonexistent-stop/eta")
        assert resp.status_code == 404

    def test_vehicle_with_no_gps_is_skipped(self, client):
        """Vehicles with null location must not appear in arrivals."""
        mock_get = _make_supabase_get(
            position_rows=[MOCK_POSITION_NO_GPS, MOCK_POSITION_ON_ROUTE]
        )
        with patch("api.routers.stops._supabase_get", mock_get):
            resp = client.get(f"/api/stops/{STOP_UUID}/eta")
        assert resp.status_code == 200
        arrivals = resp.json()["arrivals"]
        vehicle_ids = [a["vehicle_id"] for a in arrivals]
        assert "BUS-003" not in vehicle_ids  # no GPS
        assert "BUS-001" in vehicle_ids

    def test_decommissioned_vehicle_is_excluded(self, client):
        """Decommissioned vehicles must not appear in arrivals."""
        mock_get = _make_supabase_get(
            position_rows=[MOCK_POSITION_DECOMMISSIONED, MOCK_POSITION_ON_ROUTE]
        )
        with patch("api.routers.stops._supabase_get", mock_get):
            resp = client.get(f"/api/stops/{STOP_UUID}/eta")
        assert resp.status_code == 200
        arrivals = resp.json()["arrivals"]
        vehicle_ids = [a["vehicle_id"] for a in arrivals]
        assert "BUS-004" not in vehicle_ids

    def test_stationary_vehicle_uses_fallback_speed(self, client):
        """Stationary vehicle (speed=0) should use 25 km/h city-average for ETA."""
        mock_get = _make_supabase_get(position_rows=[MOCK_POSITION_STATIONARY])
        with patch("api.routers.stops._supabase_get", mock_get):
            resp = client.get(f"/api/stops/{STOP_UUID}/eta")
        assert resp.status_code == 200
        arrivals = resp.json()["arrivals"]
        assert len(arrivals) == 1
        # At 25 km/h and ~1 km distance, ETA should be ~2-3 min (max(1, round))
        assert arrivals[0]["eta_minutes"] >= 1
        assert arrivals[0]["eta_minutes"] <= 10

    def test_real_traccar_vehicle_marked_as_real(self, client):
        """Vehicle with source='traccar' should have source='real' in response."""
        mock_get = _make_supabase_get(position_rows=[MOCK_POSITION_STATIONARY])
        with patch("api.routers.stops._supabase_get", mock_get):
            resp = client.get(f"/api/stops/{STOP_UUID}/eta")
        assert resp.status_code == 200
        assert resp.json()["arrivals"][0]["source"] == "real"

    def test_limit_parameter_respected(self, client):
        """?limit=1 should return at most 1 arrival."""
        mock_get = _make_supabase_get(
            position_rows=[MOCK_POSITION_ON_ROUTE, MOCK_POSITION_FAR]
        )
        with patch("api.routers.stops._supabase_get", mock_get):
            resp = client.get(f"/api/stops/{STOP_UUID}/eta?limit=1")
        assert resp.status_code == 200
        assert len(resp.json()["arrivals"]) <= 1

    def test_arrivals_sorted_by_eta_ascending(self, client):
        """Arrivals on the same route should be sorted by eta_minutes ascending."""
        near = {**MOCK_POSITION_ON_ROUTE, "vehicle_id": "veh-near"}
        near["vehicles"] = {
            **MOCK_POSITION_ON_ROUTE["vehicles"],
            "vehicle_id": "BUS-NEAR",
        }
        far = {
            **MOCK_POSITION_ON_ROUTE,
            "location": VEHICLE_LOCATION_FAR,
            "vehicle_id": "veh-far",
        }
        far["vehicles"] = {
            **MOCK_POSITION_ON_ROUTE["vehicles"],
            "vehicle_id": "BUS-FAR",
        }
        mock_get = _make_supabase_get(position_rows=[far, near])
        with patch("api.routers.stops._supabase_get", mock_get):
            resp = client.get(f"/api/stops/{STOP_UUID}/eta?limit=2")
        assert resp.status_code == 200
        arrivals = resp.json()["arrivals"]
        if len(arrivals) >= 2:
            assert arrivals[0]["eta_minutes"] <= arrivals[1]["eta_minutes"]

    def test_stop_id_string_lookup_fallback(self, client):
        """When UUID lookup returns nothing, should fall back to stop_id string lookup."""

        async def _get_with_fallback(query: str):
            if query.startswith("stops?id=eq."):
                return []  # UUID lookup fails
            if query.startswith("stops?stop_id=eq."):
                return [MOCK_STOP]  # stop_id string lookup succeeds
            if query.startswith("route_stops?"):
                return [MOCK_ROUTE_STOP]
            if query.startswith("vehicle_positions_latest"):
                return [MOCK_POSITION_ON_ROUTE]
            if query.startswith("routes?"):
                return [MOCK_ROUTE]
            return []

        with patch(
            "api.routers.stops._supabase_get", AsyncMock(side_effect=_get_with_fallback)
        ):
            resp = client.get(f"/api/stops/{STOP_ID_STR}/eta")
        assert resp.status_code == 200
        assert resp.json()["stop_id"] == STOP_ID_STR


class TestHaversineHelper:
    """Unit tests for the _haversine_km helper function."""

    def test_same_point_is_zero(self):
        from api.routers.stops import _haversine_km

        assert _haversine_km(33.5, 36.3, 33.5, 36.3) == pytest.approx(0.0, abs=1e-6)

    def test_known_distance(self):
        """Damascus center to ~1 degree north is roughly 111 km."""
        from api.routers.stops import _haversine_km

        dist = _haversine_km(33.5, 36.3, 34.5, 36.3)
        assert 100 < dist < 120

    def test_symmetry(self):
        from api.routers.stops import _haversine_km

        d1 = _haversine_km(33.5, 36.3, 33.6, 36.4)
        d2 = _haversine_km(33.6, 36.4, 33.5, 36.3)
        assert d1 == pytest.approx(d2, rel=1e-6)
