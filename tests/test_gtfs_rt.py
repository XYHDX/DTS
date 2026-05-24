"""
Tests for the GTFS-Realtime feed endpoint: GET /api/gtfs/realtime
Also covers the /api/public/gtfs-rt alias.

Validates:
- Correct Content-Type header (application/x-protobuf)
- Valid GTFS-RT FeedMessage structure (parseable protobuf)
- VehiclePosition entities with speed, bearing, occupancy
- TripUpdate entities for in-progress trips
- Graceful empty-data response
- Null coordinates are skipped
- Occupancy percentage boundary mapping
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

try:
    from google.transit import gtfs_realtime_pb2

    GTFS_RT_AVAILABLE = True
except ImportError:
    GTFS_RT_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not GTFS_RT_AVAILABLE, reason="gtfs-realtime-bindings not installed"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_feed(content: bytes) -> "gtfs_realtime_pb2.FeedMessage":
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(content)
    return feed


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VEHICLE_UUID = "vehicle-uuid-001"
ROUTE_UUID = "route-uuid-001"
TRIP_UUID = "trip-uuid-001"

SAMPLE_POSITIONS = [
    {
        "vehicle_id": VEHICLE_UUID,
        "location": {"type": "Point", "coordinates": [36.2920, 33.5138]},
        "speed_kmh": 36.0,
        "heading": 90.0,
        "occupancy_pct": 60.0,
        "recorded_at": "2026-03-30T09:00:00Z",
    }
]

SAMPLE_VEHICLES = [
    {
        "id": VEHICLE_UUID,
        "vehicle_id": "V001",
        "name": "Bus 001",
        "assigned_route_id": ROUTE_UUID,
    }
]

SAMPLE_ROUTES = [
    {
        "id": ROUTE_UUID,
        "route_id": "R001",
    }
]

SAMPLE_TRIPS = [
    {
        "id": TRIP_UUID,
        "vehicle_id": VEHICLE_UUID,
        "route_id": ROUTE_UUID,
        "actual_start": "2026-03-30T08:00:00Z",
        "status": "in_progress",
    }
]


def _mock_supabase_get(positions, vehicles, routes, trips):
    """Return an AsyncMock side_effect that serves the right data per query path."""

    async def _get(path, params=None):
        if "vehicle_positions_latest" in path:
            return positions
        if "vehicles" in path:
            return vehicles
        if "routes" in path:
            return routes
        if "trips" in path:
            return trips
        return []

    return _get


@pytest.fixture(scope="module")
def client():
    from api.index import app
    from fastapi.testclient import TestClient

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(autouse=True)
def _clear_gtfs_rt_cache():
    """Reset the in-memory GTFS-RT cache before each test."""
    from api.routers.gtfs import _gtfs_rt_cache

    _gtfs_rt_cache["data"] = None
    _gtfs_rt_cache["timestamp"] = 0.0
    _gtfs_rt_cache["content_type"] = None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGTFSRealtime:
    """GTFS-RT endpoint tests."""

    def test_returns_protobuf(self, client):
        """Endpoint returns binary protobuf with correct Content-Type."""
        with patch(
            "api.routers.gtfs._supabase_get",
            new_callable=AsyncMock,
            side_effect=_mock_supabase_get(
                SAMPLE_POSITIONS, SAMPLE_VEHICLES, SAMPLE_ROUTES, SAMPLE_TRIPS
            ),
        ):
            resp = client.get("/api/gtfs/realtime")

        assert resp.status_code == 200
        assert "application/x-protobuf" in resp.headers["content-type"]
        assert resp.headers.get("x-gtfs-rt-version") == "2.0"

    def test_public_alias(self, client):
        """The /api/public/gtfs-rt alias returns the same feed."""
        with patch(
            "api.routers.gtfs._supabase_get",
            new_callable=AsyncMock,
            side_effect=_mock_supabase_get(
                SAMPLE_POSITIONS, SAMPLE_VEHICLES, SAMPLE_ROUTES, SAMPLE_TRIPS
            ),
        ):
            resp = client.get("/api/public/gtfs-rt")

        assert resp.status_code == 200
        assert "application/x-protobuf" in resp.headers["content-type"]

    def test_valid_feed_message(self, client):
        """Response body is a parseable GTFS-RT FeedMessage."""
        with patch(
            "api.routers.gtfs._supabase_get",
            new_callable=AsyncMock,
            side_effect=_mock_supabase_get(
                SAMPLE_POSITIONS, SAMPLE_VEHICLES, SAMPLE_ROUTES, SAMPLE_TRIPS
            ),
        ):
            resp = client.get("/api/gtfs/realtime")

        feed = _parse_feed(resp.content)
        assert feed.header.gtfs_realtime_version == "2.0"
        assert feed.header.timestamp > 0

    def test_vehicle_position_entity(self, client):
        """VehiclePosition entity contains position, speed, bearing, occupancy."""
        with patch(
            "api.routers.gtfs._supabase_get",
            new_callable=AsyncMock,
            side_effect=_mock_supabase_get(
                SAMPLE_POSITIONS, SAMPLE_VEHICLES, SAMPLE_ROUTES, SAMPLE_TRIPS
            ),
        ):
            feed = _parse_feed(client.get("/api/gtfs/realtime").content)

        vp_entities = [e for e in feed.entity if e.HasField("vehicle")]
        assert len(vp_entities) == 1

        vp = vp_entities[0].vehicle
        assert vp.vehicle.id == "V001"
        assert vp.vehicle.label == "Bus 001"
        assert vp.trip.route_id == "R001"
        assert vp.trip.trip_id == TRIP_UUID
        assert abs(vp.position.latitude - 33.5138) < 0.0001
        assert abs(vp.position.longitude - 36.2920) < 0.0001
        # 36 km/h -> 10 m/s
        assert abs(vp.position.speed - 10.0) < 0.01
        assert vp.position.bearing == 90.0
        # 60% -> STANDING_ROOM_ONLY
        assert (
            vp.occupancy_status == gtfs_realtime_pb2.VehiclePosition.STANDING_ROOM_ONLY
        )

    def test_trip_update_entity(self, client):
        """TripUpdate entity is present for in-progress trips."""
        with patch(
            "api.routers.gtfs._supabase_get",
            new_callable=AsyncMock,
            side_effect=_mock_supabase_get(
                SAMPLE_POSITIONS, SAMPLE_VEHICLES, SAMPLE_ROUTES, SAMPLE_TRIPS
            ),
        ):
            feed = _parse_feed(client.get("/api/gtfs/realtime").content)

        tu_entities = [e for e in feed.entity if e.HasField("trip_update")]
        assert len(tu_entities) == 1

        tu = tu_entities[0].trip_update
        assert tu.trip.trip_id == TRIP_UUID
        assert tu.trip.route_id == "R001"
        assert tu.vehicle.id == "V001"
        assert tu.timestamp > 0

    def test_empty_data_returns_valid_feed(self, client):
        """With no data the feed is still valid protobuf."""
        with patch(
            "api.routers.gtfs._supabase_get",
            new_callable=AsyncMock,
            side_effect=_mock_supabase_get([], [], [], []),
        ):
            resp = client.get("/api/gtfs/realtime")

        assert resp.status_code == 200
        feed = _parse_feed(resp.content)
        assert feed.header.gtfs_realtime_version == "2.0"
        assert len(feed.entity) == 0

    def test_skips_positions_with_null_coords(self, client):
        """Positions missing lat/lon are excluded."""
        bad_pos = [
            {
                "vehicle_id": VEHICLE_UUID,
                "location": None,
                "speed_kmh": None,
                "heading": None,
                "occupancy_pct": None,
                "recorded_at": None,
            }
        ]
        with patch(
            "api.routers.gtfs._supabase_get",
            new_callable=AsyncMock,
            side_effect=_mock_supabase_get(bad_pos, SAMPLE_VEHICLES, SAMPLE_ROUTES, []),
        ):
            feed = _parse_feed(client.get("/api/gtfs/realtime").content)

        vp_entities = [e for e in feed.entity if e.HasField("vehicle")]
        assert len(vp_entities) == 0

    def test_no_trip_when_vehicle_not_on_trip(self, client):
        """Vehicle with position but no active trip still emits VehiclePosition."""
        with patch(
            "api.routers.gtfs._supabase_get",
            new_callable=AsyncMock,
            side_effect=_mock_supabase_get(
                SAMPLE_POSITIONS, SAMPLE_VEHICLES, SAMPLE_ROUTES, []
            ),
        ):
            feed = _parse_feed(client.get("/api/gtfs/realtime").content)

        vp_entities = [e for e in feed.entity if e.HasField("vehicle")]
        assert len(vp_entities) == 1
        assert vp_entities[0].vehicle.trip.trip_id == ""

    def test_occupancy_boundaries(self, client):
        """Occupancy percentage maps to correct OccupancyStatus enum."""
        from api.routers.gtfs import _gtfs_rt_cache

        pb = gtfs_realtime_pb2.VehiclePosition

        cases = [
            (0.0, pb.EMPTY),
            (15.0, pb.MANY_SEATS_AVAILABLE),
            (40.0, pb.FEW_SEATS_AVAILABLE),
            (65.0, pb.STANDING_ROOM_ONLY),
            (90.0, pb.FULL),
        ]

        for pct, expected_status in cases:
            # Clear cache between iterations to avoid stale responses
            _gtfs_rt_cache["data"] = None
            _gtfs_rt_cache["timestamp"] = 0.0
            _gtfs_rt_cache["content_type"] = None

            pos = [{**SAMPLE_POSITIONS[0], "occupancy_pct": pct}]
            with patch(
                "api.routers.gtfs._supabase_get",
                new_callable=AsyncMock,
                side_effect=_mock_supabase_get(pos, SAMPLE_VEHICLES, SAMPLE_ROUTES, []),
            ):
                feed = _parse_feed(client.get("/api/gtfs/realtime").content)

            vp_entities = [e for e in feed.entity if e.HasField("vehicle")]
            assert len(vp_entities) == 1, f"No VehiclePosition for occupancy={pct}"
            assert vp_entities[0].vehicle.occupancy_status == expected_status, (
                f"occupancy={pct} expected {expected_status}, "
                f"got {vp_entities[0].vehicle.occupancy_status}"
            )
