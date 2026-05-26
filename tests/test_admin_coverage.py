"""
Targeted coverage tests for admin and driver endpoints.
Covers create/update/assign operations not exercised by other test files.
"""

import os
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SUPABASE_URL", "http://mock-supabase.local")
os.environ.setdefault("SUPABASE_KEY", "mock-key")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "mock-service-key")
os.environ.setdefault("SUPABASE_ANON_KEY", "mock-anon-key")
os.environ.setdefault("JWT_SECRET", "test-secret-for-ci-only-xxxxxxxxxxxxxxxxx")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")


@pytest.fixture(scope="module")
def client():
    from api.index import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope="module")
def admin_token():
    from api.core.auth import create_access_token

    return create_access_token(
        user_id="admin-001",
        email="admin@transit.sy",
        role="admin",
        operator_id="op-001",
        expires_delta=timedelta(hours=1),
    )


@pytest.fixture(scope="module")
def dispatcher_token():
    from api.core.auth import create_access_token

    return create_access_token(
        user_id="dispatcher-001",
        email="dispatcher@transit.sy",
        role="dispatcher",
        operator_id="op-001",
        expires_delta=timedelta(hours=1),
    )


# ---------------------------------------------------------------------------
# Admin: create user
# ---------------------------------------------------------------------------


class TestAdminCreateUser:
    def test_create_user_success(self, client, admin_token):
        mock_result = {
            "id": "u-new-001",
            "email": "new@transit.sy",
            "full_name": "New User",
            "full_name_ar": None,
            "role": "driver",
            "phone": None,
            "is_active": True,
        }
        with (
            patch(
                "api.routers.admin._supabase_get", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "api.routers.admin._supabase_post", new_callable=AsyncMock
            ) as mock_post,
        ):
            mock_get.return_value = []  # no existing email
            mock_post.return_value = mock_result
            r = client.post(
                "/api/admin/users",
                json={
                    "email": "new@transit.sy",
                    "password": "securepass123",
                    "full_name": "New User",
                    "role": "driver",
                },
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert r.status_code == 200
        assert r.json()["email"] == "new@transit.sy"

    def test_create_user_duplicate_email(self, client, admin_token):
        with patch(
            "api.routers.admin._supabase_get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = [{"id": "existing-001"}]
            r = client.post(
                "/api/admin/users",
                json={
                    "email": "existing@transit.sy",
                    "password": "securepass123",
                    "full_name": "Existing User",
                    "role": "driver",
                },
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert r.status_code == 409

    def test_create_user_requires_admin(self, client, dispatcher_token):
        r = client.post(
            "/api/admin/users",
            json={
                "email": "test@transit.sy",
                "password": "pass123",
                "full_name": "Test",
                "role": "driver",
            },
            headers={"Authorization": f"Bearer {dispatcher_token}"},
        )
        assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Admin: update user
# ---------------------------------------------------------------------------


class TestAdminUpdateUser:
    def test_update_user_success(self, client, admin_token):
        mock_result = [
            {
                "id": "u-001",
                "email": "admin@transit.sy",
                "full_name": "Updated Name",
                "full_name_ar": None,
                "role": "admin",
                "phone": "0991234567",
                "is_active": True,
            }
        ]
        with patch(
            "api.routers.admin._supabase_patch", new_callable=AsyncMock
        ) as mock_patch:
            mock_patch.return_value = mock_result
            r = client.put(
                "/api/admin/users/u-001",
                json={"full_name": "Updated Name", "phone": "0991234567"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert r.status_code == 200
        assert r.json()["full_name"] == "Updated Name"

    def test_update_user_not_found(self, client, admin_token):
        with patch(
            "api.routers.admin._supabase_patch", new_callable=AsyncMock
        ) as mock_patch:
            mock_patch.return_value = []
            r = client.put(
                "/api/admin/users/nonexistent",
                json={"full_name": "Updated Name"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert r.status_code == 404

    def test_update_user_no_fields(self, client, admin_token):
        r = client.put(
            "/api/admin/users/u-001",
            json={},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Admin: create vehicle
# ---------------------------------------------------------------------------


class TestAdminCreateVehicle:
    def test_create_vehicle_success(self, client, admin_token):
        mock_result = {
            "id": "v-new-001",
            "vehicle_id": "BUS-101",
            "name": "Bus 101",
            "name_ar": "حافلة 101",
            "vehicle_type": "bus",
            "capacity": 40,
            "status": "idle",
            "is_active": True,
        }
        with patch(
            "api.routers.admin._supabase_post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_result
            r = client.post(
                "/api/admin/vehicles",
                json={
                    "vehicle_id": "BUS-101",
                    "name": "Bus 101",
                    "name_ar": "حافلة 101",
                    "vehicle_type": "bus",
                    "capacity": 40,
                },
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert r.status_code == 200
        assert r.json()["vehicle_id"] == "BUS-101"

    def test_create_vehicle_db_failure(self, client, admin_token):
        with patch(
            "api.routers.admin._supabase_post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = None
            r = client.post(
                "/api/admin/vehicles",
                json={
                    "vehicle_id": "BUS-102",
                    "name": "Bus 102",
                    "name_ar": "حافلة 102",
                    "vehicle_type": "bus",
                    "capacity": 40,
                },
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert r.status_code == 500


# ---------------------------------------------------------------------------
# Admin: update vehicle
# ---------------------------------------------------------------------------


class TestAdminUpdateVehicle:
    def test_update_vehicle_success(self, client, admin_token):
        mock_result = [
            {
                "id": "v-001",
                "vehicle_id": "VH-001",
                "name": "Updated Bus",
                "name_ar": "حافلة محدثة",
                "vehicle_type": "bus",
                "capacity": 55,
                "status": "active",
                "is_active": True,
            }
        ]
        with patch(
            "api.routers.admin._supabase_patch", new_callable=AsyncMock
        ) as mock_patch:
            mock_patch.return_value = mock_result
            r = client.put(
                "/api/admin/vehicles/v-001",
                json={"name": "Updated Bus", "capacity": 55},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert r.status_code == 200

    def test_update_vehicle_not_found(self, client, admin_token):
        with patch(
            "api.routers.admin._supabase_patch", new_callable=AsyncMock
        ) as mock_patch:
            mock_patch.return_value = []
            r = client.put(
                "/api/admin/vehicles/nonexistent",
                json={"name": "Ghost Bus"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Admin: assign vehicle
# ---------------------------------------------------------------------------


class TestAdminAssignVehicle:
    def test_assign_vehicle_success(self, client, admin_token):
        mock_vehicle = [{"id": "v-001", "vehicle_id": "VH-001"}]
        with (
            patch(
                "api.routers.admin._supabase_patch", new_callable=AsyncMock
            ) as mock_patch,
            patch(
                "api.routers.admin._supabase_post", new_callable=AsyncMock
            ) as mock_post,
        ):
            mock_patch.return_value = mock_vehicle
            mock_post.return_value = {"id": "audit-001"}
            r = client.post(
                "/api/admin/vehicles/v-001/assign",
                json={"route_id": "route-001", "driver_id": "driver-001"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert r.status_code == 200
        assert r.json()["status"] == "success"

    def test_assign_vehicle_not_found(self, client, admin_token):
        with patch(
            "api.routers.admin._supabase_patch", new_callable=AsyncMock
        ) as mock_patch:
            mock_patch.return_value = []
            r = client.post(
                "/api/admin/vehicles/nonexistent/assign",
                json={"route_id": "route-001", "driver_id": "driver-001"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Admin: resolve alert
# ---------------------------------------------------------------------------


class TestAdminResolveAlert:
    def test_resolve_alert_success(self, client, admin_token):
        mock_result = [{"id": "alert-001", "is_resolved": True}]
        with patch(
            "api.routers.admin._supabase_patch", new_callable=AsyncMock
        ) as mock_patch:
            mock_patch.return_value = mock_result
            r = client.put(
                "/api/admin/alerts/alert-001/resolve",
                json={"resolved": True},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert r.status_code == 200

    def test_unresolve_alert(self, client, admin_token):
        mock_result = [{"id": "alert-001", "is_resolved": False}]
        with patch(
            "api.routers.admin._supabase_patch", new_callable=AsyncMock
        ) as mock_patch:
            mock_patch.return_value = mock_result
            r = client.put(
                "/api/admin/alerts/alert-001/resolve",
                json={"resolved": False},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert r.status_code == 200

    def test_resolve_alert_not_found(self, client, admin_token):
        with patch(
            "api.routers.admin._supabase_patch", new_callable=AsyncMock
        ) as mock_patch:
            mock_patch.return_value = []
            r = client.put(
                "/api/admin/alerts/nonexistent/resolve",
                json={"resolved": True},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Driver: trip start/end
# ---------------------------------------------------------------------------


class TestDriverTripManagement:
    @pytest.fixture(scope="class")
    def driver_token(self):
        from api.core.auth import create_access_token

        return create_access_token(
            user_id="driver-001",
            email="driver@transit.sy",
            role="driver",
            operator_id="op-001",
            expires_delta=timedelta(hours=1),
        )

    def test_start_trip_success(self, client, driver_token):
        mock_vehicles = [{"id": "v-001"}]
        mock_trip = {"id": "trip-001"}
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
                json={"route_id": "route-001"},
                headers={"Authorization": f"Bearer {driver_token}"},
            )
        assert r.status_code == 200
        assert r.json()["trip_id"] == "trip-001"

    def test_start_trip_no_vehicle(self, client, driver_token):
        with patch(
            "api.routers.driver._supabase_get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = []
            r = client.post(
                "/api/driver/trip/start",
                json={"route_id": "route-001"},
                headers={"Authorization": f"Bearer {driver_token}"},
            )
        assert r.status_code == 404

    def test_end_trip_success(self, client, driver_token):
        mock_trips = [{"id": "trip-001", "status": "in_progress"}]
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
                json={"trip_id": "trip-001"},
                headers={"Authorization": f"Bearer {driver_token}"},
            )
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# WS stats endpoint
# ---------------------------------------------------------------------------


class TestWebSocketStats:
    def test_ws_stats_returns_count(self, client):
        r = client.get("/api/ws/stats")
        assert r.status_code == 200
        data = r.json()
        assert "active_connections" in data


# ---------------------------------------------------------------------------
# Auth: register endpoint
# ---------------------------------------------------------------------------


class TestAuthRegister:
    def test_register_success(self, client):
        mock_result = {
            "id": "u-reg-001",
            "email": "newuser@transit.sy",
            "full_name": "New User",
            "full_name_ar": None,
            "role": "viewer",
            "phone": None,
            "is_active": True,
        }
        with (
            patch("api.routers.auth._supabase_get", new_callable=AsyncMock) as mock_get,
            patch(
                "api.routers.auth._supabase_post", new_callable=AsyncMock
            ) as mock_post,
            patch(
                "api.routers.auth._rate_limit_check", new_callable=AsyncMock
            ) as mock_rl,
        ):
            mock_rl.return_value = True
            mock_get.return_value = []
            mock_post.return_value = mock_result
            r = client.post(
                "/api/auth/register",
                json={
                    "email": "newuser@transit.sy",
                    "password": "securepass123",
                    "full_name": "New User",
                },
            )
        assert r.status_code in (200, 201)
        assert r.json()["email"] == "newuser@transit.sy"

    def test_register_duplicate_email(self, client):
        with (
            patch("api.routers.auth._supabase_get", new_callable=AsyncMock) as mock_get,
            patch(
                "api.routers.auth._rate_limit_check", new_callable=AsyncMock
            ) as mock_rl,
        ):
            mock_rl.return_value = True
            mock_get.return_value = [{"id": "existing"}]
            r = client.post(
                "/api/auth/register",
                json={
                    "email": "existing@transit.sy",
                    "password": "securepass123",
                    "full_name": "Test",
                },
            )
        assert r.status_code == 409

    def test_register_short_password(self, client):
        with patch(
            "api.routers.auth._rate_limit_check", new_callable=AsyncMock
        ) as mock_rl:
            mock_rl.return_value = True
            r = client.post(
                "/api/auth/register",
                json={
                    "email": "test@transit.sy",
                    "password": "short",
                    "full_name": "Test",
                },
            )
        assert r.status_code in (422, 400)

    def test_register_me_requires_auth(self, client):
        r = client.get("/api/auth/me")
        assert r.status_code in (401, 403)

    def test_change_password_requires_auth(self, client):
        r = client.post(
            "/api/auth/change-password",
            json={"current_password": "old", "new_password": "newpassword123"},
        )
        assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Admin: list users endpoint (unauthenticated)
# ---------------------------------------------------------------------------


class TestAdminUnauthenticated:
    def test_admin_users_requires_auth(self, client):
        r = client.get("/api/admin/users")
        assert r.status_code in (401, 403)

    def test_admin_vehicles_requires_auth(self, client):
        r = client.get("/api/admin/vehicles")
        assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Admin: list users / vehicles (authenticated)
# ---------------------------------------------------------------------------


class TestAdminListAuthenticated:
    def test_list_users_success(self, client, admin_token):
        mock_users = [
            {
                "id": "u-001",
                "email": "admin@transit.sy",
                "full_name": "Admin",
                "full_name_ar": None,
                "role": "admin",
                "phone": None,
                "is_active": True,
                "created_at": None,
            }
        ]
        with patch(
            "api.routers.admin._supabase_get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_users
            r = client.get(
                "/api/admin/users",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_vehicles_success(self, client, admin_token):
        mock_vehicles = [
            {
                "id": "v-001",
                "vehicle_id": "VH-001",
                "name": "Bus 1",
                "name_ar": "حافلة 1",
                "vehicle_type": "bus",
                "capacity": 40,
                "status": "idle",
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
        assert isinstance(r.json(), list)

    def test_list_trips_success(self, client, admin_token):
        with patch(
            "api.routers.admin._supabase_get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = []
            r = client.get(
                "/api/admin/trips",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert r.status_code == 200

    def test_list_alerts_success(self, client, admin_token):
        with patch(
            "api.routers.admin._supabase_get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = []
            r = client.get(
                "/api/admin/alerts",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Routes: list and get (read-only endpoints)
# ---------------------------------------------------------------------------


class TestRoutesList:
    def test_list_routes_returns_list(self, client):
        mock_routes = [
            {
                "id": "r-001",
                "route_id": "RT-01",
                "name": "Route 1",
                "name_ar": "خط 1",
                "route_type": "bus",
                "color": "#FF0000",
                "distance_km": 12.5,
                "avg_duration_min": 45,
                "fare_syp": 500,
                "is_active": True,
            }
        ]
        with (
            patch(
                "api.routers.routes._supabase_get", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "api.routers.routes._cache_get", new_callable=AsyncMock
            ) as mock_cache_get,
            patch("api.routers.routes._cache_set", new_callable=AsyncMock),
        ):
            mock_cache_get.return_value = None
            mock_get.side_effect = [mock_routes, []]  # routes then stops
            r = client.get("/api/routes")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_get_route_not_found(self, client):
        with (
            patch(
                "api.routers.routes._supabase_get", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "api.routers.routes._cache_get", new_callable=AsyncMock
            ) as mock_cache_get,
        ):
            mock_cache_get.return_value = None
            mock_get.return_value = []
            r = client.get("/api/routes/nonexistent-id")
        assert r.status_code == 404

    def test_get_route_success(self, client):
        mock_route = {
            "id": "r-001",
            "route_id": "RT-01",
            "name": "Route 1",
            "name_ar": "خط 1",
            "route_type": "bus",
            "color": "#FF0000",
            "distance_km": 12.5,
            "avg_duration_min": 45,
            "fare_syp": 500,
            "is_active": True,
        }
        with (
            patch(
                "api.routers.routes._supabase_get", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "api.routers.routes._cache_get", new_callable=AsyncMock
            ) as mock_cache_get,
            patch("api.routers.routes._cache_set", new_callable=AsyncMock),
        ):
            mock_cache_get.return_value = None
            mock_get.side_effect = [[mock_route], []]  # route then stops
            r = client.get("/api/routes/r-001")
        assert r.status_code == 200
        assert r.json()["route_id"] == "RT-01"


# ---------------------------------------------------------------------------
# Driver: position and passenger count
# ---------------------------------------------------------------------------


class TestDriverOperations:
    @pytest.fixture(scope="class")
    def driver_token(self):
        from api.core.auth import create_access_token

        return create_access_token(
            user_id="driver-002",
            email="driver2@transit.sy",
            role="driver",
            operator_id="op-001",
            expires_delta=timedelta(hours=1),
        )

    def test_report_position_success(self, client, driver_token):
        with (
            patch(
                "api.routers.driver._supabase_get", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "api.routers.driver._supabase_rpc", new_callable=AsyncMock
            ) as mock_rpc,
            patch(
                "api.routers.driver._rate_limit_check", new_callable=AsyncMock
            ) as mock_rl,
            patch("api.routers.driver._cache_delete", new_callable=AsyncMock),
        ):
            mock_rl.return_value = True
            mock_get.return_value = [{"id": "v-001", "assigned_route_id": "r-001"}]
            mock_rpc.return_value = None
            r = client.post(
                "/api/driver/position",
                json={"latitude": 33.51, "longitude": 36.29, "speed_kmh": 30.0},
                headers={"Authorization": f"Bearer {driver_token}"},
            )
        assert r.status_code == 200

    def test_report_position_no_vehicle(self, client, driver_token):
        with (
            patch(
                "api.routers.driver._supabase_get", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "api.routers.driver._rate_limit_check", new_callable=AsyncMock
            ) as mock_rl,
        ):
            mock_rl.return_value = True
            mock_get.return_value = []
            r = client.post(
                "/api/driver/position",
                json={"latitude": 33.51, "longitude": 36.29},
                headers={"Authorization": f"Bearer {driver_token}"},
            )
        assert r.status_code == 404

    def test_report_position_requires_auth(self, client):
        r = client.post(
            "/api/driver/position",
            json={"latitude": 33.51, "longitude": 36.29},
        )
        assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Form validation: required fields and format checks
# ---------------------------------------------------------------------------


class TestFormValidation:
    def test_create_user_missing_email(self, client, admin_token):
        r = client.post(
            "/api/admin/users",
            json={"password": "securepass123", "full_name": "Test", "role": "driver"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 422

    def test_create_user_missing_password(self, client, admin_token):
        r = client.post(
            "/api/admin/users",
            json={"email": "test@transit.sy", "full_name": "Test", "role": "driver"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 422

    def test_create_vehicle_missing_vehicle_id(self, client, admin_token):
        r = client.post(
            "/api/admin/vehicles",
            json={
                "name": "Bus",
                "name_ar": "حافلة",
                "vehicle_type": "bus",
                "capacity": 40,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 422

    def test_create_vehicle_missing_name(self, client, admin_token):
        r = client.post(
            "/api/admin/vehicles",
            json={
                "vehicle_id": "BUS-X",
                "name_ar": "حافلة",
                "vehicle_type": "bus",
                "capacity": 40,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 422

    def test_assign_vehicle_missing_route(self, client, admin_token):
        r = client.post(
            "/api/admin/vehicles/v-001/assign",
            json={"driver_id": "driver-001"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 422

    def test_driver_trip_start_missing_route(self, client):
        from api.core.auth import create_access_token

        driver_token = create_access_token(
            user_id="driver-003",
            email="driver3@transit.sy",
            role="driver",
            operator_id="op-001",
            expires_delta=timedelta(hours=1),
        )
        r = client.post(
            "/api/driver/trip/start",
            json={},
            headers={"Authorization": f"Bearer {driver_token}"},
        )
        assert r.status_code == 422
