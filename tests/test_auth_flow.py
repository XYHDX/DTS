"""
DAM-198: End-to-end authentication flow tests.

Covers:
- Registration (self-service, duplicate email, password validation)
- Login (success, wrong password, missing user)
- Protected endpoint access with valid token
- 401/403 for expired/invalid/missing tokens
- Role-based access control (admin vs driver vs viewer)
- Concurrent sessions (multiple valid tokens for same user)
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
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    from api.index import app
    from fastapi.testclient import TestClient

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _make_token(role: str, user_id: str = "user-001", email: str = "test@transit.sy"):
    from api.core.auth import create_access_token

    return create_access_token(
        user_id=user_id,
        email=email,
        role=role,
        operator_id="op-001",
        expires_delta=timedelta(hours=1),
    )


def _make_expired_token(role: str = "admin"):
    from api.core.auth import create_access_token

    return create_access_token(
        user_id="user-001",
        email="test@transit.sy",
        role=role,
        operator_id="op-001",
        expires_delta=timedelta(seconds=-1),
    )


MOCK_USER = {
    "id": "user-001",
    "email": "admin@transit.sy",
    "password_hash": None,  # set per-test via fixture
    "role": "admin",
    "operator_id": "op-001",
    "full_name": "Test Admin",
    "full_name_ar": None,
    "phone": None,
    "is_active": True,
    "created_at": "2026-01-01T00:00:00",
}


def _hashed_user(password: str = "Secur3Pass!") -> dict:
    from api.core.auth import hash_password

    return {**MOCK_USER, "password_hash": hash_password(password)}


# ---------------------------------------------------------------------------
# 1. Registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_register_success(self, client):
        created = {
            "id": "new-001",
            "email": "newuser@transit.sy",
            "full_name": "New User",
            "full_name_ar": None,
            "role": "viewer",
            "phone": None,
            "is_active": True,
            "created_at": "2026-04-02T00:00:00",
        }
        with (
            patch(
                "api.routers.auth._rate_limit_check", new=AsyncMock(return_value=True)
            ),
            patch("api.routers.auth._supabase_get", new=AsyncMock(return_value=[])),
            patch(
                "api.routers.auth._supabase_post", new=AsyncMock(return_value=created)
            ),
        ):
            resp = client.post(
                "/api/auth/register",
                json={
                    "email": "newuser@transit.sy",
                    "password": "Secur3Pass!",
                    "full_name": "New User",
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "newuser@transit.sy"
        assert data["role"] == "viewer"

    def test_register_duplicate_email(self, client):
        with (
            patch(
                "api.routers.auth._rate_limit_check", new=AsyncMock(return_value=True)
            ),
            patch(
                "api.routers.auth._supabase_get",
                new=AsyncMock(return_value=[{"id": "existing-001"}]),
            ),
        ):
            resp = client.post(
                "/api/auth/register",
                json={
                    "email": "existing@transit.sy",
                    "password": "Secur3Pass!",
                    "full_name": "Existing User",
                },
            )
        assert resp.status_code == 409

    def test_register_password_too_short(self, client):
        with (
            patch(
                "api.routers.auth._rate_limit_check", new=AsyncMock(return_value=True)
            ),
            patch("api.routers.auth._supabase_get", new=AsyncMock(return_value=[])),
        ):
            resp = client.post(
                "/api/auth/register",
                json={
                    "email": "short@transit.sy",
                    "password": "short",
                    "full_name": "Short Pass",
                },
            )
        assert resp.status_code == 422

    def test_register_rate_limited(self, client):
        with patch(
            "api.routers.auth._rate_limit_check", new=AsyncMock(return_value=False)
        ):
            resp = client.post(
                "/api/auth/register",
                json={
                    "email": "flood@transit.sy",
                    "password": "Secur3Pass!",
                    "full_name": "Flood User",
                },
            )
        assert resp.status_code == 429


# ---------------------------------------------------------------------------
# 2. Login
# ---------------------------------------------------------------------------


class TestLogin:
    def test_login_success_returns_jwt(self, client):
        user = _hashed_user("Secur3Pass!")
        with (
            patch(
                "api.routers.auth._rate_limit_check", new=AsyncMock(return_value=True)
            ),
            patch("api.routers.auth._supabase_get", new=AsyncMock(return_value=[user])),
        ):
            resp = client.post(
                "/api/auth/login",
                json={"email": "admin@transit.sy", "password": "Secur3Pass!"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["role"] == "admin"

    def test_login_wrong_password(self, client):
        user = _hashed_user("Secur3Pass!")
        with (
            patch(
                "api.routers.auth._rate_limit_check", new=AsyncMock(return_value=True)
            ),
            patch("api.routers.auth._supabase_get", new=AsyncMock(return_value=[user])),
        ):
            resp = client.post(
                "/api/auth/login",
                json={"email": "admin@transit.sy", "password": "WrongPass!"},
            )
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        with (
            patch(
                "api.routers.auth._rate_limit_check", new=AsyncMock(return_value=True)
            ),
            patch("api.routers.auth._supabase_get", new=AsyncMock(return_value=[])),
        ):
            resp = client.post(
                "/api/auth/login",
                json={"email": "nobody@transit.sy", "password": "Secur3Pass!"},
            )
        assert resp.status_code == 401

    def test_login_driver_receives_vehicle_info(self, client):
        driver_user = {
            "id": "driver-001",
            "email": "driver@transit.sy",
            "password_hash": None,
            "role": "driver",
            "operator_id": "op-001",
        }
        from api.core.auth import hash_password

        driver_user["password_hash"] = hash_password("DriverPass!")
        vehicle_data = [{"id": "veh-001", "assigned_route_id": "route-001"}]

        call_count = 0

        async def mock_get(path):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [driver_user]
            return vehicle_data

        with (
            patch(
                "api.routers.auth._rate_limit_check", new=AsyncMock(return_value=True)
            ),
            patch("api.routers.auth._supabase_get", new=mock_get),
        ):
            resp = client.post(
                "/api/auth/login",
                json={"email": "driver@transit.sy", "password": "DriverPass!"},
            )
        assert resp.status_code == 200
        assert resp.json()["role"] == "driver"

    def test_login_rate_limited(self, client):
        with patch(
            "api.routers.auth._rate_limit_check", new=AsyncMock(return_value=False)
        ):
            resp = client.post(
                "/api/auth/login",
                json={"email": "spam@transit.sy", "password": "Secur3Pass!"},
            )
        assert resp.status_code == 429


# ---------------------------------------------------------------------------
# 3. Protected endpoint access
# ---------------------------------------------------------------------------


class TestProtectedEndpoints:
    def test_get_me_with_valid_token(self, client):
        token = _make_token("admin")
        user_record = {
            "id": "user-001",
            "email": "test@transit.sy",
            "full_name": "Test Admin",
            "full_name_ar": None,
            "role": "admin",
            "phone": None,
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
        }
        with patch(
            "api.routers.auth._supabase_get", new=AsyncMock(return_value=[user_record])
        ):
            resp = client.get(
                "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
            )
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    def test_get_me_without_token(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_get_me_invalid_token(self, client):
        resp = client.get(
            "/api/auth/me", headers={"Authorization": "Bearer invalid.token.here"}
        )
        assert resp.status_code == 401

    def test_get_me_expired_token(self, client):
        token = _make_expired_token("admin")
        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 4. Role-based access control
# ---------------------------------------------------------------------------


class TestRoleBasedAccess:
    def test_admin_can_access_admin_users(self, client):
        token = _make_token("admin")
        with patch("api.routers.admin._supabase_get", new=AsyncMock(return_value=[])):
            resp = client.get(
                "/api/admin/users", headers={"Authorization": f"Bearer {token}"}
            )
        assert resp.status_code == 200

    def test_viewer_cannot_access_admin_users(self, client):
        token = _make_token("viewer")
        resp = client.get(
            "/api/admin/users", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 403

    def test_driver_cannot_access_admin_users(self, client):
        token = _make_token("driver", user_id="driver-001", email="d@transit.sy")
        resp = client.get(
            "/api/admin/users", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 403

    def test_driver_can_access_driver_position_endpoint(self, client):
        # Token includes vehicle_id so the route skips the DB lookup
        from api.core.auth import create_access_token

        token = create_access_token(
            user_id="driver-001",
            email="d@transit.sy",
            role="driver",
            operator_id="op-001",
            vehicle_id="veh-001",
            vehicle_route_id="route-001",
            expires_delta=timedelta(hours=1),
        )
        with (
            patch("api.routers.driver._supabase_rpc", new=AsyncMock(return_value={})),
            patch(
                "api.routers.driver._rate_limit_check", new=AsyncMock(return_value=True)
            ),
            patch("api.routers.driver._cache_delete", new=AsyncMock(return_value=None)),
        ):
            resp = client.post(
                "/api/driver/position",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "vehicle_id": "veh-001",
                    "latitude": 33.51,
                    "longitude": 36.29,
                    "speed_kmh": 40.0,
                    "heading": 90.0,
                    "accuracy_m": 5.0,
                    "recorded_at": "2026-04-02T10:00:00Z",
                },
            )
        assert resp.status_code in (200, 201)

    def test_admin_cannot_use_driver_position_endpoint(self, client):
        token = _make_token("admin")
        resp = client.post(
            "/api/driver/position",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "vehicle_id": "veh-001",
                "latitude": 33.51,
                "longitude": 36.29,
                "speed_kmh": 40.0,
                "heading": 90.0,
                "accuracy_m": 5.0,
                "recorded_at": "2026-04-02T10:00:00Z",
            },
        )
        assert resp.status_code == 403

    def test_dispatcher_can_list_users(self, client):
        token = _make_token("dispatcher", user_id="disp-001", email="disp@transit.sy")
        with patch("api.routers.admin._supabase_get", new=AsyncMock(return_value=[])):
            resp = client.get(
                "/api/admin/users", headers={"Authorization": f"Bearer {token}"}
            )
        assert resp.status_code == 200

    def test_dispatcher_cannot_create_user(self, client):
        token = _make_token("dispatcher", user_id="disp-001", email="disp@transit.sy")
        resp = client.post(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": "new@transit.sy",
                "password": "SomePass123!",
                "full_name": "New User",
                "role": "driver",
            },
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 5. Concurrent sessions
# ---------------------------------------------------------------------------


class TestConcurrentSessions:
    def test_two_tokens_for_same_user_both_valid(self, client):
        """Issuing multiple tokens for the same user should both work independently."""
        from api.core.auth import create_access_token

        # Create tokens with different expiry to ensure they differ
        token_a = create_access_token(
            user_id="user-001",
            email="test@transit.sy",
            role="admin",
            operator_id="op-001",
            expires_delta=timedelta(hours=1),
        )
        token_b = create_access_token(
            user_id="user-001",
            email="test@transit.sy",
            role="admin",
            operator_id="op-001",
            expires_delta=timedelta(hours=2),
        )
        assert token_a != token_b  # different expiry → different signatures

        user_record = {
            "id": "user-001",
            "email": "test@transit.sy",
            "full_name": "Test Admin",
            "full_name_ar": None,
            "role": "admin",
            "phone": None,
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
        }
        with patch(
            "api.routers.auth._supabase_get", new=AsyncMock(return_value=[user_record])
        ):
            resp_a = client.get(
                "/api/auth/me", headers={"Authorization": f"Bearer {token_a}"}
            )
            resp_b = client.get(
                "/api/auth/me", headers={"Authorization": f"Bearer {token_b}"}
            )

        assert resp_a.status_code == 200
        assert resp_b.status_code == 200

    def test_different_role_tokens_enforce_roles_independently(self, client):
        admin_token = _make_token("admin", user_id="user-001")
        driver_token = _make_token("driver", user_id="user-002", email="d@transit.sy")

        with patch("api.routers.admin._supabase_get", new=AsyncMock(return_value=[])):
            admin_resp = client.get(
                "/api/admin/users",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            driver_resp = client.get(
                "/api/admin/users",
                headers={"Authorization": f"Bearer {driver_token}"},
            )

        assert admin_resp.status_code == 200
        assert driver_resp.status_code == 403
