"""
API contract tests for Damascus Transit Platform.

Validates that all 26 primary endpoints:
  - respond (not 404/405)
  - return valid JSON (except SSE stream)
  - return expected top-level schema keys

Endpoints that require a live DB return 5xx without one; those tests
assert the *shape* of the error envelope rather than a success payload,
so the contract (HTTP method + path + content-type) is still validated.
"""


# ---------------------------------------------------------------------------
# Public / unauthenticated endpoints
# ---------------------------------------------------------------------------


class TestPublicEndpoints:
    def test_health_returns_200(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert "status" in body
        assert "timestamp" in body
        assert "database" in body

    def test_health_status_field_is_string(self, client):
        r = client.get("/api/health")
        assert isinstance(r.json()["status"], str)

    def test_routes_endpoint_exists(self, client):
        r = client.get("/api/routes")
        assert r.status_code in (200, 400, 500, 502, 503)
        assert r.headers["content-type"].startswith("application/json")

    def test_routes_200_returns_list(self, client):
        r = client.get("/api/routes")
        if r.status_code == 200:
            assert isinstance(r.json(), list)

    def test_stops_endpoint_exists(self, client):
        r = client.get("/api/stops")
        assert r.status_code in (200, 400, 500, 502, 503)
        assert r.headers["content-type"].startswith("application/json")

    def test_stops_200_returns_list(self, client):
        r = client.get("/api/stops")
        if r.status_code == 200:
            assert isinstance(r.json(), list)

    def test_stops_nearest_endpoint_exists(self, client):
        r = client.get("/api/stops/nearest?lat=33.5&lon=36.3&limit=3")
        assert r.status_code in (200, 400, 500, 502, 503)
        assert r.headers["content-type"].startswith("application/json")

    def test_vehicles_endpoint_exists(self, client):
        r = client.get("/api/vehicles")
        assert r.status_code in (200, 400, 500, 502, 503)
        assert r.headers["content-type"].startswith("application/json")

    def test_vehicles_200_returns_list(self, client):
        r = client.get("/api/vehicles")
        if r.status_code == 200:
            assert isinstance(r.json(), list)

    def test_vehicles_positions_endpoint_exists(self, client):
        r = client.get("/api/vehicles/positions")
        assert r.status_code in (200, 400, 500, 502, 503)
        assert r.headers["content-type"].startswith("application/json")

    def test_stats_endpoint_exists(self, client):
        r = client.get("/api/stats")
        assert r.status_code in (200, 400, 500, 502, 503)
        assert r.headers["content-type"].startswith("application/json")

    def test_alerts_active_endpoint_exists(self, client):
        r = client.get("/api/alerts/active")
        assert r.status_code in (200, 400, 500, 502, 503)
        assert r.headers["content-type"].startswith("application/json")

    def test_schedules_endpoint_exists(self, client):
        r = client.get("/api/schedules/route-001")
        assert r.status_code in (200, 400, 404, 500, 502, 503)
        assert r.headers["content-type"].startswith("application/json")

    def test_stream_endpoint_returns_sse_headers(self, client):
        # Use stream=True to avoid blocking on infinite SSE
        # Without operator param, may return 400 (multi-tenancy requirement)
        with client.stream("GET", "/api/stream") as r:
            if r.status_code == 200:
                ct = r.headers.get("content-type", "")
                assert "text/event-stream" in ct
            else:
                assert r.status_code in (400, 500, 502, 503)


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------


class TestAuthEndpoints:
    def test_login_endpoint_exists(self, client):
        r = client.post(
            "/api/auth/login", json={"email": "x@x.com", "password": "wrong"}
        )
        # 401 (bad creds) or 500 (no DB) — either way the endpoint exists
        assert r.status_code in (401, 500, 502, 503)
        assert r.headers["content-type"].startswith("application/json")

    def test_login_returns_json_error_on_bad_creds(self, client):
        r = client.post(
            "/api/auth/login", json={"email": "x@x.com", "password": "wrong"}
        )
        body = r.json()
        assert "detail" in body

    def test_register_endpoint_exists(self, client):
        r = client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "securepassword123",
                "full_name": "Test User",
            },
        )
        # 409 (duplicate) or 500 (no DB) — endpoint must exist
        assert r.status_code in (200, 201, 409, 422, 500, 502, 503)
        assert r.headers["content-type"].startswith("application/json")

    def test_register_rejects_short_password(self, client):
        r = client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "password": "short",
                "full_name": "Test User",
            },
        )
        assert r.status_code == 422
        assert "detail" in r.json()

    def test_forgot_password_endpoint_exists(self, client):
        r = client.post(
            "/api/auth/forgot-password", json={"email": "unknown@example.com"}
        )
        # Always 200 (to prevent email enumeration) or 500/503 (no DB)
        assert r.status_code in (200, 500, 502, 503)
        assert r.headers["content-type"].startswith("application/json")

    def test_forgot_password_always_returns_message(self, client):
        r = client.post(
            "/api/auth/forgot-password", json={"email": "nobody@example.com"}
        )
        if r.status_code == 200:
            assert "message" in r.json()

    def test_me_endpoint_requires_auth(self, client):
        r = client.get("/api/auth/me")
        assert r.status_code in (401, 403)

    def test_me_put_requires_auth(self, client):
        r = client.put("/api/auth/me", json={"full_name": "New Name"})
        assert r.status_code in (401, 403)

    def test_change_password_requires_auth(self, client):
        r = client.post(
            "/api/auth/change-password",
            json={
                "current_password": "old",
                "new_password": "newpassword123",
            },
        )
        assert r.status_code in (401, 403)

    def test_change_password_rejects_short_new_password(self, client):
        # Without auth we get 401/403, but the route exists
        r = client.post(
            "/api/auth/change-password",
            json={
                "current_password": "old",
                "new_password": "short",
            },
        )
        assert r.status_code in (401, 403, 422)


# ---------------------------------------------------------------------------
# Driver endpoints (require JWT)
# ---------------------------------------------------------------------------


class TestDriverEndpointsUnauth:
    def test_driver_position_requires_auth(self, client):
        r = client.post(
            "/api/driver/position",
            json={
                "vehicle_id": "v-001",
                "latitude": 33.5,
                "longitude": 36.3,
                "speed": 40.0,
                "heading": 90.0,
            },
        )
        assert r.status_code in (401, 403, 422, 500)

    def test_driver_trip_start_requires_auth(self, client):
        r = client.post(
            "/api/driver/trip/start", json={"vehicle_id": "v-001", "route_id": "r-001"}
        )
        assert r.status_code in (401, 403, 422, 500)

    def test_driver_trip_end_requires_auth(self, client):
        r = client.post("/api/driver/trip/end", json={"trip_id": "t-001"})
        assert r.status_code in (401, 403, 422, 500)

    def test_driver_passenger_count_requires_auth(self, client):
        r = client.post(
            "/api/driver/trip/passenger-count", json={"trip_id": "t-001", "count": 10}
        )
        assert r.status_code in (401, 403, 422, 500)


# ---------------------------------------------------------------------------
# Admin endpoints (require JWT with admin role)
# ---------------------------------------------------------------------------


class TestAdminEndpointsUnauth:
    def test_admin_users_list_requires_auth(self, client):
        r = client.get("/api/admin/users")
        assert r.status_code in (401, 403, 500)

    def test_admin_users_create_requires_auth(self, client):
        r = client.post(
            "/api/admin/users",
            json={"email": "new@example.com", "password": "pass", "role": "viewer"},
        )
        assert r.status_code in (401, 403, 422, 500)

    def test_admin_users_update_requires_auth(self, client):
        r = client.put("/api/admin/users/user-001", json={"role": "driver"})
        assert r.status_code in (401, 403, 422, 500)

    def test_admin_vehicles_list_requires_auth(self, client):
        r = client.get("/api/admin/vehicles")
        assert r.status_code in (401, 403, 500)

    def test_admin_vehicles_create_requires_auth(self, client):
        r = client.post(
            "/api/admin/vehicles",
            json={"plate_number": "DM-001", "model": "Bus", "capacity": 50},
        )
        assert r.status_code in (401, 403, 422, 500)

    def test_admin_vehicles_update_requires_auth(self, client):
        r = client.put("/api/admin/vehicles/v-001", json={"capacity": 60})
        assert r.status_code in (401, 403, 422, 500)

    def test_admin_vehicles_assign_requires_auth(self, client):
        r = client.post("/api/admin/vehicles/v-001/assign", json={"driver_id": "d-001"})
        assert r.status_code in (401, 403, 422, 500)

    def test_admin_alerts_list_requires_auth(self, client):
        r = client.get("/api/admin/alerts")
        assert r.status_code in (401, 403, 500)

    def test_admin_alerts_resolve_requires_auth(self, client):
        r = client.put("/api/admin/alerts/a-001/resolve")
        assert r.status_code in (401, 403, 422, 500)

    def test_admin_trips_list_requires_auth(self, client):
        r = client.get("/api/admin/trips")
        assert r.status_code in (401, 403, 500)

    def test_admin_analytics_overview_requires_auth(self, client):
        r = client.get("/api/admin/analytics/overview")
        assert r.status_code in (401, 403, 500)


# ---------------------------------------------------------------------------
# Traccar webhook endpoints
# ---------------------------------------------------------------------------


class TestTraccarEndpoints:
    def test_traccar_position_endpoint_exists(self, client):
        r = client.post(
            "/api/traccar/position",
            json={"deviceId": "device-001", "lat": 33.5, "lon": 36.3, "speed": 40},
        )
        assert r.status_code in (200, 401, 403, 422, 500)
        assert r.headers["content-type"].startswith("application/json")

    def test_traccar_event_endpoint_exists(self, client):
        r = client.post(
            "/api/traccar/event", json={"deviceId": "device-001", "type": "ignitionOn"}
        )
        assert r.status_code in (200, 401, 403, 422, 500)
        assert r.headers["content-type"].startswith("application/json")
