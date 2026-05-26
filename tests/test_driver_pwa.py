"""
Driver PWA API tests — login, route display, location sharing, trip management.
Covers: DAM-197

Run with: pytest tests/test_driver_pwa.py -v
"""

import os
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("SUPABASE_URL", "http://mock-supabase.local")
os.environ.setdefault("SUPABASE_KEY", "mock-key")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "mock-service-key")
os.environ.setdefault("SUPABASE_ANON_KEY", "mock-anon-key")
os.environ.setdefault("JWT_SECRET", "test-secret-for-ci-only-xxxxxxxxxxxxxxxxx")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from api.index import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope="module")
def driver_token():
    from api.core.auth import create_access_token

    return create_access_token(
        user_id="driver-001",
        email="driver01@damascustransit.sy",
        role="driver",
        operator_id="op-001",
        expires_delta=timedelta(hours=1),
    )


@pytest.fixture(scope="module")
def driver_token_with_vehicle():
    """JWT pre-loaded with vehicle and route — simulates successful login response."""
    from api.core.auth import create_access_token

    return create_access_token(
        user_id="driver-001",
        email="driver01@damascustransit.sy",
        role="driver",
        operator_id="op-001",
        vehicle_id="v-bus-001",
        vehicle_route_id="route-line-a",
        expires_delta=timedelta(hours=1),
    )


@pytest.fixture(scope="module")
def admin_token():
    from api.core.auth import create_access_token

    return create_access_token(
        user_id="admin-001",
        email="admin@damascustransit.sy",
        role="admin",
        operator_id="op-001",
        expires_delta=timedelta(hours=1),
    )


# ---------------------------------------------------------------------------
# 1. Driver Login
# ---------------------------------------------------------------------------


class TestDriverLogin:
    """Verify driver can authenticate and receives a JWT with vehicle info."""

    def test_login_driver_success(self, client):
        """Driver login returns token and user object."""
        import bcrypt

        hashed = bcrypt.hashpw(b"damascus2025", bcrypt.gensalt()).decode()
        mock_users = [
            {
                "id": "driver-001",
                "email": "driver01@damascustransit.sy",
                "password_hash": hashed,
                "role": "driver",
                "operator_id": "op-001",
            }
        ]
        mock_vehicle = [{"id": "v-bus-001", "assigned_route_id": "route-line-a"}]
        with (
            patch("api.routers.auth._supabase_get", new_callable=AsyncMock) as mock_get,
            patch(
                "api.routers.auth._rate_limit_check", new_callable=AsyncMock
            ) as mock_rl,
        ):
            mock_rl.return_value = True
            mock_get.side_effect = [mock_users, mock_vehicle]
            r = client.post(
                "/api/auth/login",
                json={
                    "email": "driver01@damascustransit.sy",
                    "password": "damascus2025",
                },
            )
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["role"] == "driver"

    def test_login_wrong_password_rejected(self, client):
        """Driver login with wrong password returns 401."""
        import bcrypt

        hashed = bcrypt.hashpw(b"correctpass", bcrypt.gensalt()).decode()
        mock_users = [
            {
                "id": "driver-001",
                "email": "driver01@damascustransit.sy",
                "password_hash": hashed,
                "role": "driver",
                "operator_id": "op-001",
            }
        ]
        with (
            patch("api.routers.auth._supabase_get", new_callable=AsyncMock) as mock_get,
            patch(
                "api.routers.auth._rate_limit_check", new_callable=AsyncMock
            ) as mock_rl,
        ):
            mock_rl.return_value = True
            mock_get.return_value = mock_users
            r = client.post(
                "/api/auth/login",
                json={
                    "email": "driver01@damascustransit.sy",
                    "password": "wrongpass",
                },
            )
        assert r.status_code == 401

    def test_login_unknown_email_rejected(self, client):
        """Unknown email returns 401."""
        with (
            patch("api.routers.auth._supabase_get", new_callable=AsyncMock) as mock_get,
            patch(
                "api.routers.auth._rate_limit_check", new_callable=AsyncMock
            ) as mock_rl,
        ):
            mock_rl.return_value = True
            mock_get.return_value = []
            r = client.post(
                "/api/auth/login",
                json={
                    "email": "ghost@damascustransit.sy",
                    "password": "damascus2025",
                },
            )
        assert r.status_code == 401

    def test_login_unauthenticated_me_returns_401(self, client):
        """Calling /api/auth/me without a token returns 401."""
        r = client.get("/api/auth/me")
        assert r.status_code in (401, 403)

    def test_driver_cannot_access_admin_routes(self, client, driver_token):
        """Driver JWT is rejected on admin-only endpoints."""
        r = client.get(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {driver_token}"},
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# 2. Route Display — Vehicle Assignment
# ---------------------------------------------------------------------------


class TestRouteDisplay:
    """Verify driver gets assigned-route info when starting a trip."""

    def test_start_trip_returns_trip_id(self, client, driver_token):
        """Starting a trip with a valid route returns trip_id."""
        mock_vehicles = [{"id": "v-bus-001"}]
        mock_trip = {"id": "trip-abc-001"}
        with (
            patch(
                "api.routers.driver._supabase_get", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "api.routers.driver._supabase_post", new_callable=AsyncMock
            ) as mock_post,
        ):
            mock_get.return_value = mock_vehicles
            mock_post.return_value = mock_trip
            r = client.post(
                "/api/driver/trip/start",
                json={"route_id": "line-a"},
                headers={"Authorization": f"Bearer {driver_token}"},
            )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "success"
        assert data["trip_id"] == "trip-abc-001"

    def test_start_trip_with_scheduled_departure(self, client, driver_token):
        """Scheduled departure is accepted in trip start payload."""
        mock_vehicles = [{"id": "v-bus-001"}]
        mock_trip = {"id": "trip-sched-001"}
        with (
            patch(
                "api.routers.driver._supabase_get", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "api.routers.driver._supabase_post", new_callable=AsyncMock
            ) as mock_post,
        ):
            mock_get.return_value = mock_vehicles
            mock_post.return_value = mock_trip
            r = client.post(
                "/api/driver/trip/start",
                json={
                    "route_id": "line-b",
                    "scheduled_departure": "2026-04-02T08:00:00Z",
                },
                headers={"Authorization": f"Bearer {driver_token}"},
            )
        assert r.status_code == 200
        assert r.json()["trip_id"] == "trip-sched-001"

    def test_start_trip_no_vehicle_assigned(self, client, driver_token):
        """Driver without a vehicle gets 404 when trying to start a trip."""
        with patch(
            "api.routers.driver._supabase_get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = []
            r = client.post(
                "/api/driver/trip/start",
                json={"route_id": "line-a"},
                headers={"Authorization": f"Bearer {driver_token}"},
            )
        assert r.status_code == 404
        assert "vehicle" in r.json()["detail"].lower()

    def test_start_trip_db_failure_returns_500(self, client, driver_token):
        """DB failure when persisting trip returns 500."""
        mock_vehicles = [{"id": "v-bus-001"}]
        with (
            patch(
                "api.routers.driver._supabase_get", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "api.routers.driver._supabase_post", new_callable=AsyncMock
            ) as mock_post,
        ):
            mock_get.return_value = mock_vehicles
            mock_post.return_value = None  # DB returned nothing
            r = client.post(
                "/api/driver/trip/start",
                json={"route_id": "line-a"},
                headers={"Authorization": f"Bearer {driver_token}"},
            )
        assert r.status_code == 500

    def test_start_trip_requires_auth(self, client):
        """Unauthenticated trip start is rejected."""
        r = client.post("/api/driver/trip/start", json={"route_id": "line-a"})
        assert r.status_code in (401, 403)

    def test_start_trip_requires_driver_role(self, client, admin_token):
        """Admin JWT cannot start a driver trip."""
        r = client.post(
            "/api/driver/trip/start",
            json={"route_id": "line-a"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# 3. Location Sharing — Position Reporting
# ---------------------------------------------------------------------------


class TestLocationSharing:
    """Verify driver position updates (location sharing toggle behavior)."""

    def test_position_update_basic(self, client, driver_token):
        """Basic lat/lon position update succeeds."""
        mock_vehicles = [{"id": "v-bus-001", "assigned_route_id": "route-line-a"}]
        with (
            patch(
                "api.routers.driver._supabase_get", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "api.routers.driver._supabase_rpc", new_callable=AsyncMock
            ) as mock_rpc,
        ):
            mock_get.return_value = mock_vehicles
            mock_rpc.return_value = {}
            r = client.post(
                "/api/driver/position",
                json={"latitude": 33.5117, "longitude": 36.2963},
                headers={"Authorization": f"Bearer {driver_token}"},
            )
        assert r.status_code == 200
        assert r.json()["status"] == "success"

    def test_position_update_with_speed_and_heading(self, client, driver_token):
        """Full position payload including speed and heading is accepted."""
        mock_vehicles = [{"id": "v-bus-001", "assigned_route_id": "route-line-a"}]
        with (
            patch(
                "api.routers.driver._supabase_get", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "api.routers.driver._supabase_rpc", new_callable=AsyncMock
            ) as mock_rpc,
        ):
            mock_get.return_value = mock_vehicles
            mock_rpc.return_value = {}
            r = client.post(
                "/api/driver/position",
                json={
                    "latitude": 33.5133,
                    "longitude": 36.2936,
                    "speed_kmh": 42.5,
                    "heading": 270,
                },
                headers={"Authorization": f"Bearer {driver_token}"},
            )
        assert r.status_code == 200

    def test_position_update_fast_path_uses_jwt_vehicle(
        self, client, driver_token_with_vehicle
    ):
        """JWT with embedded vehicle_id skips DB lookup."""
        with (
            patch(
                "api.routers.driver._supabase_get", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "api.routers.driver._supabase_rpc", new_callable=AsyncMock
            ) as mock_rpc,
        ):
            mock_rpc.return_value = {}
            r = client.post(
                "/api/driver/position",
                json={"latitude": 33.51, "longitude": 36.29},
                headers={"Authorization": f"Bearer {driver_token_with_vehicle}"},
            )
        assert r.status_code == 200
        mock_get.assert_not_called()
        rpc_args = mock_rpc.call_args[0][1]
        assert rpc_args["p_vehicle_id"] == "v-bus-001"
        assert rpc_args["p_route_id"] == "route-line-a"

    def test_position_rpc_passes_speed_and_heading(
        self, client, driver_token_with_vehicle
    ):
        """Speed and heading values are forwarded to the RPC correctly."""
        with (
            patch(
                "api.routers.driver._supabase_rpc", new_callable=AsyncMock
            ) as mock_rpc,
        ):
            mock_rpc.return_value = {}
            r = client.post(
                "/api/driver/position",
                json={
                    "latitude": 33.51,
                    "longitude": 36.28,
                    "speed_kmh": 55.0,
                    "heading": 90,
                },
                headers={"Authorization": f"Bearer {driver_token_with_vehicle}"},
            )
        assert r.status_code == 200
        rpc_args = mock_rpc.call_args[0][1]
        assert rpc_args["p_speed"] == 55.0
        assert rpc_args["p_heading"] == 90

    def test_position_update_no_vehicle(self, client, driver_token):
        """Driver with no vehicle assigned gets 404."""
        with patch(
            "api.routers.driver._supabase_get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = []
            r = client.post(
                "/api/driver/position",
                json={"latitude": 33.51, "longitude": 36.29},
                headers={"Authorization": f"Bearer {driver_token}"},
            )
        assert r.status_code == 404

    def test_position_stale_jwt_vehicle_triggers_relogin(
        self, client, driver_token_with_vehicle
    ):
        """FK violation on stale JWT vehicle forces re-login (401)."""
        from fastapi import HTTPException as FastAPIHTTPException

        fk_error = FastAPIHTTPException(
            status_code=500,
            detail="RPC call failed: 23503 foreign key constraint violation",
        )
        with patch(
            "api.routers.driver._supabase_rpc", new_callable=AsyncMock
        ) as mock_rpc:
            mock_rpc.side_effect = fk_error
            r = client.post(
                "/api/driver/position",
                json={"latitude": 33.51, "longitude": 36.29},
                headers={"Authorization": f"Bearer {driver_token_with_vehicle}"},
            )
        assert r.status_code == 401
        assert "log in again" in r.json()["detail"].lower()

    def test_position_invalid_coordinates_rejected(self, client, driver_token):
        """Coordinates outside valid range are rejected with 422."""
        r = client.post(
            "/api/driver/position",
            json={"latitude": 999.0, "longitude": 36.29},
            headers={"Authorization": f"Bearer {driver_token}"},
        )
        assert r.status_code == 422

    def test_position_requires_auth(self, client):
        """Unauthenticated position update is rejected."""
        r = client.post(
            "/api/driver/position",
            json={"latitude": 33.51, "longitude": 36.29},
        )
        assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 4. Status Updates — Trip End
# ---------------------------------------------------------------------------


class TestStatusUpdates:
    """Test driver trip lifecycle: active → completed."""

    def test_end_trip_success(self, client, driver_token):
        """Driver can end an active trip and record passenger count."""
        mock_trips = [{"id": "trip-abc-001", "status": "in_progress"}]
        with (
            patch(
                "api.routers.driver._supabase_get", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "api.routers.driver._supabase_patch", new_callable=AsyncMock
            ) as mock_patch,
        ):
            mock_get.return_value = mock_trips
            mock_patch.return_value = mock_trips
            r = client.post(
                "/api/driver/trip/end",
                json={"passenger_count": 28},
                headers={"Authorization": f"Bearer {driver_token}"},
            )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "success"
        assert data["trip_id"] == "trip-abc-001"

    def test_end_trip_no_passenger_count(self, client, driver_token):
        """Omitting passenger_count is allowed (optional field)."""
        mock_trips = [{"id": "trip-abc-002", "status": "in_progress"}]
        with (
            patch(
                "api.routers.driver._supabase_get", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "api.routers.driver._supabase_patch", new_callable=AsyncMock
            ) as mock_patch,
        ):
            mock_get.return_value = mock_trips
            mock_patch.return_value = mock_trips
            r = client.post(
                "/api/driver/trip/end",
                json={},
                headers={"Authorization": f"Bearer {driver_token}"},
            )
        assert r.status_code == 200

    def test_end_trip_no_active_trip(self, client, driver_token):
        """Ending a trip when no trip is in-progress returns 404."""
        with patch(
            "api.routers.driver._supabase_get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = []
            r = client.post(
                "/api/driver/trip/end",
                json={"passenger_count": 10},
                headers={"Authorization": f"Bearer {driver_token}"},
            )
        assert r.status_code == 404
        assert "trip" in r.json()["detail"].lower()

    def test_end_trip_requires_auth(self, client):
        """Unauthenticated trip end is rejected."""
        r = client.post("/api/driver/trip/end", json={})
        assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 5. Occupancy / Passenger Count Updates
# ---------------------------------------------------------------------------


class TestPassengerCount:
    """Verify speed and occupancy reporting via passenger count endpoint."""

    def test_update_passenger_count_success(self, client, driver_token):
        """Passenger count update for active trip succeeds."""
        mock_trips = [{"id": "trip-abc-001"}]
        with (
            patch(
                "api.routers.driver._supabase_get", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "api.routers.driver._supabase_patch", new_callable=AsyncMock
            ) as mock_patch,
        ):
            mock_get.return_value = mock_trips
            mock_patch.return_value = mock_trips
            r = client.post(
                "/api/driver/trip/passenger-count",
                json={"passenger_count": 35},
                headers={"Authorization": f"Bearer {driver_token}"},
            )
        assert r.status_code == 200
        assert r.json()["status"] == "success"

    def test_update_passenger_count_zero(self, client, driver_token):
        """Zero passengers is a valid count."""
        mock_trips = [{"id": "trip-abc-001"}]
        with (
            patch(
                "api.routers.driver._supabase_get", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "api.routers.driver._supabase_patch", new_callable=AsyncMock
            ) as mock_patch,
        ):
            mock_get.return_value = mock_trips
            mock_patch.return_value = mock_trips
            r = client.post(
                "/api/driver/trip/passenger-count",
                json={"passenger_count": 0},
                headers={"Authorization": f"Bearer {driver_token}"},
            )
        assert r.status_code == 200

    def test_update_passenger_count_negative_rejected(self, client, driver_token):
        """Negative passenger count is rejected with 422."""
        r = client.post(
            "/api/driver/trip/passenger-count",
            json={"passenger_count": -1},
            headers={"Authorization": f"Bearer {driver_token}"},
        )
        assert r.status_code == 422

    def test_update_passenger_count_no_active_trip(self, client, driver_token):
        """Updating count without an active trip returns 404."""
        with patch(
            "api.routers.driver._supabase_get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = []
            r = client.post(
                "/api/driver/trip/passenger-count",
                json={"passenger_count": 15},
                headers={"Authorization": f"Bearer {driver_token}"},
            )
        assert r.status_code == 404

    def test_update_passenger_count_requires_auth(self, client):
        """Unauthenticated passenger count update is rejected."""
        r = client.post(
            "/api/driver/trip/passenger-count",
            json={"passenger_count": 10},
        )
        assert r.status_code in (401, 403)
