"""
Tests for driver performance analytics endpoints.

GET /api/stats/drivers        — list all drivers with metrics
GET /api/stats/drivers/{id}   — individual driver detail with sparklines
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
# Fixtures
# ---------------------------------------------------------------------------

MOCK_DRIVERS = [
    {
        "id": "drv-001",
        "full_name": "Ahmad Khalil",
        "full_name_ar": "أحمد خليل",
        "is_active": True,
    },
    {
        "id": "drv-002",
        "full_name": "Sara Nasser",
        "full_name_ar": "سارة ناصر",
        "is_active": False,
    },
]

MOCK_TRIPS = [
    {
        "driver_id": "drv-001",
        "on_time_pct": 90.0,
        "distance_km": 15.5,
        "speed_kmh": 42.0,
        "actual_start": "2026-03-30T07:00:00+00:00",
        "actual_end": "2026-03-30T08:00:00+00:00",
    },
    {
        "driver_id": "drv-001",
        "on_time_pct": 70.0,
        "distance_km": 12.0,
        "speed_kmh": 38.0,
        "actual_start": "2026-03-30T09:00:00+00:00",
        "actual_end": "2026-03-30T09:45:00+00:00",
    },
    {
        "driver_id": "drv-002",
        "on_time_pct": None,
        "distance_km": 8.0,
        "speed_kmh": None,
        "actual_start": "2026-03-29T06:30:00+00:00",
        "actual_end": "2026-03-29T07:00:00+00:00",
    },
]

MOCK_POSITIONS = [
    {"vehicle_id": "veh-001", "speed_kmh": 45.0},
    {"vehicle_id": "veh-002", "speed_kmh": 0.0},
]

MOCK_VEHICLES = [
    {"id": "veh-001", "assigned_driver_id": "drv-001"},
    {"id": "veh-002", "assigned_driver_id": "drv-002"},
]


@pytest.fixture(scope="module")
def client():
    from api.index import app
    from fastapi.testclient import TestClient

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _mock_supabase_get(url: str):
    """Route mock Supabase GET calls to the appropriate fixture data."""
    if "users?role=eq.driver" in url and "id=eq." not in url:
        return MOCK_DRIVERS
    if "users?id=eq.drv-001" in url:
        return [MOCK_DRIVERS[0]]
    if "users?id=eq.drv-002" in url:
        return [MOCK_DRIVERS[1]]
    if "users?id=eq.drv-999" in url:
        return []
    if "trips?" in url and "driver_id=eq." not in url:
        return MOCK_TRIPS
    if "trips?driver_id=eq.drv-001" in url:
        return [t for t in MOCK_TRIPS if t["driver_id"] == "drv-001"]
    if "trips?driver_id=eq.drv-002" in url:
        return [t for t in MOCK_TRIPS if t["driver_id"] == "drv-002"]
    if "vehicle_positions_latest" in url:
        return MOCK_POSITIONS
    if "vehicles?" in url and "assigned_driver_id=eq." not in url:
        return MOCK_VEHICLES
    if "vehicles?assigned_driver_id=eq.drv-001" in url:
        return [{"id": "veh-001"}]
    if "vehicles?assigned_driver_id=eq.drv-002" in url:
        return [{"id": "veh-002"}]
    return []


# ---------------------------------------------------------------------------
# GET /api/stats/drivers
# ---------------------------------------------------------------------------


class TestGetDriverStats:
    def test_returns_list(self, client):
        with patch(
            "api.routers.stats._supabase_get",
            new=AsyncMock(side_effect=_mock_supabase_get),
        ):
            resp = client.get("/api/stats/drivers")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_sorted_by_trips_descending(self, client):
        with patch(
            "api.routers.stats._supabase_get",
            new=AsyncMock(side_effect=_mock_supabase_get),
        ):
            resp = client.get("/api/stats/drivers")
        data = resp.json()
        # drv-001 has 2 trips, drv-002 has 1 — drv-001 should be first
        assert data[0]["driver_id"] == "drv-001"
        assert data[0]["total_trips"] == 2

    def test_metrics_computed_correctly(self, client):
        with patch(
            "api.routers.stats._supabase_get",
            new=AsyncMock(side_effect=_mock_supabase_get),
        ):
            resp = client.get("/api/stats/drivers")
        d = next(x for x in resp.json() if x["driver_id"] == "drv-001")
        assert d["total_trips"] == 2
        assert d["on_time_pct"] == 80.0  # (90 + 70) / 2
        assert d["avg_speed_kmh"] == 40.0  # (42 + 38) / 2
        assert d["total_distance_km"] == 27.5  # 15.5 + 12.0
        assert (
            d["active_hours"] == 1.8
        )  # 60min + 45min = 6300s = 1.75h → round(1.75,1) = 1.8

    def test_null_on_time_for_driver_with_no_pct(self, client):
        with patch(
            "api.routers.stats._supabase_get",
            new=AsyncMock(side_effect=_mock_supabase_get),
        ):
            resp = client.get("/api/stats/drivers")
        d = next(x for x in resp.json() if x["driver_id"] == "drv-002")
        assert d["on_time_pct"] is None
        assert d["avg_speed_kmh"] is None

    def test_is_active_field_present(self, client):
        with patch(
            "api.routers.stats._supabase_get",
            new=AsyncMock(side_effect=_mock_supabase_get),
        ):
            resp = client.get("/api/stats/drivers")
        by_id = {d["driver_id"]: d for d in resp.json()}
        assert by_id["drv-001"]["is_active"] is True
        assert by_id["drv-002"]["is_active"] is False

    def test_days_query_param_accepted(self, client):
        with patch(
            "api.routers.stats._supabase_get",
            new=AsyncMock(side_effect=_mock_supabase_get),
        ):
            resp = client.get("/api/stats/drivers?days=7")
        assert resp.status_code == 200

    def test_invalid_days_rejected(self, client):
        resp = client.get("/api/stats/drivers?days=0")
        assert resp.status_code == 422

    def test_empty_fleet_returns_empty_list(self, client):
        with patch(
            "api.routers.stats._supabase_get",
            new=AsyncMock(return_value=[]),
        ):
            resp = client.get("/api/stats/drivers")
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/stats/drivers/{driver_id}
# ---------------------------------------------------------------------------


class TestGetDriverDetail:
    def test_returns_single_driver(self, client):
        with patch(
            "api.routers.stats._supabase_get",
            new=AsyncMock(side_effect=_mock_supabase_get),
        ):
            resp = client.get("/api/stats/drivers/drv-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["driver_id"] == "drv-001"

    def test_sparklines_present(self, client):
        with patch(
            "api.routers.stats._supabase_get",
            new=AsyncMock(side_effect=_mock_supabase_get),
        ):
            resp = client.get("/api/stats/drivers/drv-001")
        data = resp.json()
        assert "sparkline_7d" in data
        assert "sparkline_30d" in data
        assert len(data["sparkline_30d"]) == 30
        assert len(data["sparkline_7d"]) == 7

    def test_sparkline_has_date_and_trips_keys(self, client):
        with patch(
            "api.routers.stats._supabase_get",
            new=AsyncMock(side_effect=_mock_supabase_get),
        ):
            resp = client.get("/api/stats/drivers/drv-001")
        entry = resp.json()["sparkline_30d"][0]
        assert "date" in entry
        assert "trips" in entry

    def test_sparkline_dates_ascending(self, client):
        with patch(
            "api.routers.stats._supabase_get",
            new=AsyncMock(side_effect=_mock_supabase_get),
        ):
            resp = client.get("/api/stats/drivers/drv-001")
        dates = [e["date"] for e in resp.json()["sparkline_30d"]]
        assert dates == sorted(dates)

    def test_metrics_in_detail(self, client):
        with patch(
            "api.routers.stats._supabase_get",
            new=AsyncMock(side_effect=_mock_supabase_get),
        ):
            resp = client.get("/api/stats/drivers/drv-001")
        d = resp.json()
        assert d["total_trips"] == 2
        assert d["on_time_pct"] == 80.0
        assert d["total_distance_km"] == 27.5

    def test_driver_not_found_returns_404(self, client):
        with patch(
            "api.routers.stats._supabase_get",
            new=AsyncMock(side_effect=_mock_supabase_get),
        ):
            resp = client.get("/api/stats/drivers/drv-999")
        assert resp.status_code == 404

    def test_driver_with_no_trips(self, client):
        """Driver exists but has no trips — metrics should be zero/null."""
        no_trip_mock = AsyncMock(
            side_effect=lambda url: (
                [MOCK_DRIVERS[1]]
                if "id=eq.drv-002" in url and "users?" in url
                else []
                if "trips?" in url
                else []
                if "vehicles?" in url
                else []
            )
        )
        with patch("api.routers.stats._supabase_get", new=no_trip_mock):
            resp = client.get("/api/stats/drivers/drv-002")
        assert resp.status_code == 200
        d = resp.json()
        assert d["total_trips"] == 0
        assert d["on_time_pct"] is None
        assert d["active_hours"] == 0.0
        assert len(d["sparkline_30d"]) == 30
