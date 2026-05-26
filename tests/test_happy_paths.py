"""
Happy-path tests with mocked Supabase helpers.

These tests patch the internal _supabase_* helpers so that endpoints
return real 200 responses, exercising the data-mapping / business-logic
code that contract tests cannot reach (Supabase is unavailable in CI).
"""

import os
from datetime import timedelta
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

MOCK_ROUTE = {
    "id": "route-001",
    "route_id": "R-1",
    "name": "Central",
    "name_ar": "المركز",
    "route_type": "bus",
    "color": "#FF0000",
    "distance_km": 12.5,
    "avg_duration_min": 45,
    "fare_syp": 500.0,
    "is_active": True,
}

MOCK_STOP = {
    "id": "stop-001",
    "stop_id": "S-1",
    "name": "Main Square",
    "name_ar": "الميدان",
    "latitude": 33.51,
    "longitude": 36.29,
    "has_shelter": True,
    "is_active": True,
}

MOCK_VEHICLE_POS = {
    "vehicle_id": "v-001",
    "latitude": 33.5,
    "longitude": 36.3,
    "speed_kmh": 40.0,
    "occupancy_pct": 60,
    "recorded_at": "2026-03-30T07:00:00",
    "vehicles": {
        "id": "v-001",
        "vehicle_id": "VH-001",
        "name": "Bus 1",
        "name_ar": "حافلة 1",
        "vehicle_type": "bus",
        "capacity": 50,
        "status": "active",
        "assigned_route_id": "route-001",
    },
}

MOCK_SCHEDULE = {
    "id": "sched-001",
    "route_id": "route-001",
    "day_of_week": 1,
    "first_departure": "06:00",
    "last_departure": "22:00",
    "frequency_min": 15,
}

MOCK_ALERT = {
    "id": "alert-001",
    "vehicle_id": "v-001",
    "alert_type": "speed",
    "severity": "high",
    "title": "Speeding",
    "title_ar": "تجاوز السرعة",
    "description": "Vehicle exceeded speed limit",
    "is_resolved": False,
    "created_at": "2026-03-30T07:00:00",
}

MOCK_VEHICLE_STATUS = [
    {"id": "v-001", "status": "active"},
    {"id": "v-002", "status": "idle"},
    {"id": "v-003", "status": "maintenance"},
]


@pytest.fixture(scope="module")
def client():
    from api.index import app
    from fastapi.testclient import TestClient

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope="module")
def admin_token():
    """Generate a real admin JWT for authenticated endpoints."""
    from api.core.auth import create_access_token

    return create_access_token(
        user_id="admin-001",
        email="admin@transit.sy",
        role="admin",
        expires_delta=timedelta(hours=1),
    )


@pytest.fixture(scope="module")
def driver_token():
    from api.core.auth import create_access_token

    return create_access_token(
        user_id="driver-001",
        email="driver@transit.sy",
        role="driver",
        expires_delta=timedelta(hours=1),
    )


@pytest.fixture(scope="module")
def driver_token_with_vehicle():
    """Driver JWT with vehicle_id pre-cached (post-optimisation token shape)."""
    from api.core.auth import create_access_token

    return create_access_token(
        user_id="driver-001",
        email="driver@transit.sy",
        role="driver",
        expires_delta=timedelta(hours=1),
        vehicle_id="v-cached-001",
        vehicle_route_id="route-001",
    )


# ---------------------------------------------------------------------------
# Auth unit tests (no HTTP, no mocking needed)
# ---------------------------------------------------------------------------


class TestAuthHelpers:
    def test_hash_and_verify_password(self):
        from api.core.auth import hash_password, verify_password

        hashed = hash_password("s3cr3t")
        assert verify_password("s3cr3t", hashed) is True
        assert verify_password("wrong", hashed) is False

    def test_verify_password_bad_hash(self):
        from api.core.auth import verify_password

        assert verify_password("pass", "not-a-hash") is False

    def test_create_and_verify_token(self):
        from api.core.auth import create_access_token, verify_token

        token = create_access_token("u-1", "x@x.com", "driver")
        payload = verify_token(token)
        assert payload.user_id == "u-1"
        assert payload.email == "x@x.com"
        assert payload.role == "driver"

    def test_verify_token_invalid(self):
        from fastapi import HTTPException

        from api.core.auth import verify_token

        with pytest.raises(HTTPException) as exc:
            verify_token("bad.token.here")
        assert exc.value.status_code == 401

    def test_supabase_headers_includes_keys(self):
        from api.core.database import _supabase_headers

        headers = _supabase_headers()
        assert "apikey" in headers
        assert "Authorization" in headers

    def test_supabase_url_builds_correctly(self):
        from api.core.database import _supabase_url

        url = _supabase_url("routes?select=*")
        assert "mock-supabase.local" in url
        assert "routes" in url


# ---------------------------------------------------------------------------
# Routes happy path
# ---------------------------------------------------------------------------


class TestRoutesHappyPath:
    def test_list_routes_returns_200(self, client):
        with (
            patch(
                "api.routers.routes._supabase_get", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "api.routers.routes._resolve_operator_id",
                new_callable=AsyncMock,
                return_value="op-001",
            ),
        ):
            mock_get.side_effect = [
                [MOCK_ROUTE],  # routes query
                [],  # route_stops for route-001
            ]
            r = client.get("/api/routes?operator=damascus")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert data[0]["route_id"] == "R-1"
        assert data[0]["stop_count"] == 0

    def test_get_single_route_returns_200(self, client):
        with (
            patch(
                "api.routers.routes._supabase_get", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "api.routers.routes._resolve_operator_id",
                new_callable=AsyncMock,
                return_value="op-001",
            ),
        ):
            mock_get.side_effect = [
                [MOCK_ROUTE],  # route lookup
                [MOCK_STOP],  # stops for route
            ]
            r = client.get("/api/routes/route-001?operator=damascus")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == "route-001"

    def test_get_route_not_found_returns_404(self, client):
        with (
            patch(
                "api.routers.routes._supabase_get", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "api.routers.routes._resolve_operator_id",
                new_callable=AsyncMock,
                return_value="op-001",
            ),
        ):
            mock_get.return_value = []
            r = client.get("/api/routes/nonexistent?operator=damascus")
        assert r.status_code == 404
        assert r.headers["content-type"].startswith("application/json")


# ---------------------------------------------------------------------------
# Stops happy path
# ---------------------------------------------------------------------------


class TestStopsHappyPath:
    def test_list_stops_returns_200(self, client):
        with (
            patch(
                "api.routers.stops._supabase_get", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "api.routers.stops._resolve_operator_id",
                new_callable=AsyncMock,
                return_value="op-001",
            ),
        ):
            mock_get.return_value = [MOCK_STOP]
            r = client.get("/api/stops?operator=damascus")
        assert r.status_code == 200
        data = r.json()
        assert data[0]["stop_id"] == "S-1"

    def test_nearest_stops_returns_200(self, client):
        mock_stop = {**MOCK_STOP, "lat": 33.51, "lon": 36.29, "distance_m": 250}
        with (
            patch(
                "api.routers.stops._supabase_rpc", new_callable=AsyncMock
            ) as mock_rpc,
            patch(
                "api.routers.stops._resolve_operator_id",
                new_callable=AsyncMock,
                return_value="op-001",
            ),
        ):
            mock_rpc.return_value = [mock_stop]
            r = client.get("/api/stops/nearest?lat=33.5&lon=36.3&operator=damascus")
        assert r.status_code == 200
        data = r.json()
        assert data[0]["distance_m"] == 250


# ---------------------------------------------------------------------------
# Vehicles happy path
# ---------------------------------------------------------------------------


class TestVehiclesHappyPath:
    def test_list_vehicles_returns_200(self, client):
        mock_vehicle = {
            "id": "v-001",
            "vehicle_id": "VH-001",
            "name": "Bus 1",
            "name_ar": "حافلة 1",
            "vehicle_type": "bus",
            "capacity": 50,
            "status": "active",
            "assigned_route_id": "route-001",
        }
        mock_position = {
            "vehicle_id": "v-001",
            "location": {"type": "Point", "coordinates": [36.3, 33.5]},
            "speed_kmh": 40.0,
            "occupancy_pct": 60,
            "recorded_at": "2026-03-30T07:00:00",
        }
        with (
            patch(
                "api.routers.vehicles._supabase_get", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "api.routers.vehicles._resolve_operator_id",
                new_callable=AsyncMock,
                return_value="op-001",
            ),
        ):
            mock_get.side_effect = [[mock_vehicle], [mock_position]]
            r = client.get("/api/vehicles?operator=damascus")
        assert r.status_code == 200
        data = r.json()
        assert data[0]["vehicle_id"] == "VH-001"

    def test_list_vehicles_empty_positions(self, client):
        with (
            patch(
                "api.routers.vehicles._supabase_get", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "api.routers.vehicles._resolve_operator_id",
                new_callable=AsyncMock,
                return_value="op-001",
            ),
        ):
            mock_get.return_value = []
            r = client.get("/api/vehicles?operator=damascus")
        assert r.status_code == 200
        assert r.json() == []

    def test_vehicle_positions_returns_200(self, client):
        mock_pos = {
            "vehicle_id": "v-001",
            "location": {"type": "Point", "coordinates": [36.3, 33.5]},
            "speed_kmh": 40,
            "heading": 90,
            "source": "gps",
            "occupancy_pct": 50,
            "recorded_at": "2026-03-30T07:00:00",
        }
        mock_vehicle = {
            "id": "v-001",
            "vehicle_id": "VH-001",
            "vehicle_type": "bus",
            "name": "Bus 1",
            "name_ar": "حافلة 1",
            "assigned_route_id": "route-001",
        }
        with (
            patch(
                "api.routers.vehicles._supabase_get", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "api.routers.vehicles._resolve_operator_id",
                new_callable=AsyncMock,
                return_value="op-001",
            ),
        ):
            mock_get.side_effect = [[mock_vehicle], [mock_pos]]
            r = client.get("/api/vehicles/positions?operator=damascus")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# Stats happy path
# ---------------------------------------------------------------------------


class TestStatsHappyPath:
    def test_get_stats_returns_200(self, client):
        with (
            patch(
                "api.routers.stats._supabase_get", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "api.routers.stats._resolve_operator_id",
                new_callable=AsyncMock,
                return_value="op-001",
            ),
        ):
            mock_get.side_effect = [
                MOCK_VEHICLE_STATUS,  # vehicles
                [MOCK_ROUTE],  # routes
                [MOCK_STOP],  # stops
                [{"id": "d-001", "is_active": True}],  # active drivers
                [{"occupancy_pct": 60}],  # occupancy
            ]
            r = client.get("/api/stats?operator=damascus")
        assert r.status_code == 200
        data = r.json()
        assert "total_vehicles" in data
        assert data["total_vehicles"] == 3
        assert data["active_vehicles"] == 1


# ---------------------------------------------------------------------------
# Schedules happy path
# ---------------------------------------------------------------------------


class TestSchedulesHappyPath:
    def test_get_schedules_returns_200(self, client):
        with (
            patch(
                "api.routers.schedules._supabase_get", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "api.routers.schedules._resolve_operator_id",
                new_callable=AsyncMock,
                return_value="op-001",
            ),
        ):
            mock_get.return_value = [MOCK_SCHEDULE]
            r = client.get("/api/schedules/route-001?operator=damascus")
        assert r.status_code == 200
        data = r.json()
        assert data[0]["route_id"] == "route-001"
        assert data[0]["frequency_min"] == 15


# ---------------------------------------------------------------------------
# Alerts happy path
# ---------------------------------------------------------------------------


class TestAlertsHappyPath:
    def test_list_active_alerts_returns_200(self, client):
        with (
            patch(
                "api.routers.alerts._supabase_get", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "api.routers.alerts._resolve_operator_id",
                new_callable=AsyncMock,
                return_value="op-001",
            ),
        ):
            mock_get.return_value = [MOCK_ALERT]
            r = client.get("/api/alerts/active?operator=damascus")
        assert r.status_code == 200
        data = r.json()
        assert data[0]["alert_type"] == "speed"
        assert data[0]["is_resolved"] is False


# ---------------------------------------------------------------------------
# Auth login happy path
# ---------------------------------------------------------------------------


class TestLoginHappyPath:
    def test_login_success(self, client):
        from api.core.auth import hash_password

        hashed = hash_password("correct-password")
        mock_user = {
            "id": "user-001",
            "email": "driver@transit.sy",
            "password_hash": hashed,
            "role": "driver",
        }
        with patch(
            "api.routers.auth._supabase_get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = [mock_user]
            r = client.post(
                "/api/auth/login",
                json={"email": "driver@transit.sy", "password": "correct-password"},
            )
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client):
        from api.core.auth import hash_password

        hashed = hash_password("real-password")
        mock_user = {
            "id": "user-001",
            "email": "x@x.com",
            "password_hash": hashed,
            "role": "driver",
        }
        with patch(
            "api.routers.auth._supabase_get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = [mock_user]
            r = client.post(
                "/api/auth/login",
                json={"email": "x@x.com", "password": "wrong-password"},
            )
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Admin endpoints with valid JWT
# ---------------------------------------------------------------------------


class TestAdminWithAuth:
    def test_list_users_with_admin_token(self, client, admin_token):
        mock_users = [
            {
                "id": "u-001",
                "email": "admin@transit.sy",
                "full_name": "Admin",
                "role": "admin",
                "is_active": True,
                "created_at": "2026-01-01T00:00:00",
            }
        ]
        with patch(
            "api.routers.admin._supabase_get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_users
            r = client.get(
                "/api/admin/users", headers={"Authorization": f"Bearer {admin_token}"}
            )
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_vehicles_admin(self, client, admin_token):
        mock_vehicles = [
            {
                "id": "v-001",
                "vehicle_id": "VH-001",
                "name": "Bus 1",
                "name_ar": "حافلة 1",
                "vehicle_type": "bus",
                "capacity": 50,
                "status": "active",
                "is_active": True,
            }
        ]
        with patch(
            "api.routers.admin._supabase_get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_vehicles
            r = client.get(
                "/api/admin/vehicles",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert r.status_code == 200

    def test_list_admin_alerts(self, client, admin_token):
        with patch(
            "api.routers.admin._supabase_get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = [MOCK_ALERT]
            r = client.get(
                "/api/admin/alerts",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert r.status_code == 200

    def test_list_admin_trips(self, client, admin_token):
        with patch(
            "api.routers.admin._supabase_get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = []
            r = client.get(
                "/api/admin/trips",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert r.status_code == 200

    def test_analytics_overview(self, client, admin_token):
        with patch(
            "api.routers.admin._supabase_get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.side_effect = [
                MOCK_VEHICLE_STATUS,  # vehicles
                [{"id": "r-001"}],  # active routes
                [{"id": "r-001"}],  # routes total
                [MOCK_STOP],  # stops
                [{"id": "d-001", "is_active": True}],  # active drivers
                [{"id": "d-001"}],  # total drivers
                [{"occupancy_pct": 55}],  # occupancy
            ]
            r = client.get(
                "/api/admin/analytics/overview",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert r.status_code == 200
        data = r.json()
        assert "total_vehicles" in data


# ---------------------------------------------------------------------------
# Driver endpoints with valid JWT
# ---------------------------------------------------------------------------


class TestDriverWithAuth:
    def test_driver_position_update(self, client, driver_token):
        mock_vehicles = [{"id": "v-001", "vehicle_id": "VH-001"}]
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
                json={"latitude": 33.5, "longitude": 36.3},
                headers={"Authorization": f"Bearer {driver_token}"},
            )
        assert r.status_code == 200
        assert r.json()["status"] == "success"

    def test_driver_position_fast_path_uses_jwt_vehicle(
        self, client, driver_token_with_vehicle
    ):
        """JWT with vehicle_id: no DB lookup, only the RPC call is made."""
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
                json={"latitude": 33.5, "longitude": 36.3},
                headers={"Authorization": f"Bearer {driver_token_with_vehicle}"},
            )
        assert r.status_code == 200
        assert r.json()["status"] == "success"
        mock_get.assert_not_called()
        assert mock_rpc.call_args[0][1]["p_vehicle_id"] == "v-cached-001"
        assert mock_rpc.call_args[0][1]["p_route_id"] == "route-001"

    def test_driver_position_stale_jwt_vehicle_returns_401(
        self, client, driver_token_with_vehicle
    ):
        """FK violation on stale JWT vehicle_id triggers 401 forcing re-login."""
        from fastapi import HTTPException as FastAPIHTTPException

        fk_error = FastAPIHTTPException(
            status_code=500,
            detail="RPC call failed: 23503 foreign key constraint violation",
        )
        with (
            patch(
                "api.routers.driver._supabase_rpc", new_callable=AsyncMock
            ) as mock_rpc,
        ):
            mock_rpc.side_effect = fk_error
            r = client.post(
                "/api/driver/position",
                json={"latitude": 33.5, "longitude": 36.3},
                headers={"Authorization": f"Bearer {driver_token_with_vehicle}"},
            )
        assert r.status_code == 401
        assert "log in again" in r.json()["detail"].lower()

    def test_driver_position_no_vehicle(self, client, driver_token):
        with (
            patch(
                "api.routers.driver._supabase_get", new_callable=AsyncMock
            ) as mock_get,
        ):
            mock_get.return_value = []
            r = client.post(
                "/api/driver/position",
                json={"latitude": 33.5, "longitude": 36.3},
                headers={"Authorization": f"Bearer {driver_token}"},
            )
        assert r.status_code == 404

    def test_wrong_role_forbidden(self, client, driver_token):
        """Driver cannot access admin-only endpoints."""
        with patch("api.routers.admin._supabase_get", new_callable=AsyncMock):
            r = client.get(
                "/api/admin/users",
                headers={"Authorization": f"Bearer {driver_token}"},
            )
        assert r.status_code == 403
