"""
Production smoke test suite — Damascus Transit System.

Run against the live deployment:
    pytest tests/smoke_test_production.py -v

Environment variables:
    SMOKE_BASE_URL   base URL of the production deployment
                     (default: https://syrian-transit-system.vercel.app)
    SMOKE_ADMIN_EMAIL    admin user email (default: admin@damascustransit.sy)
    SMOKE_ADMIN_PASSWORD admin user password (default: read from TRANSIT_ADMIN_PASSWORD)

All tests are integration tests that hit real production endpoints.
No mocking — failures here mean the production stack is broken.
"""

import asyncio
import json
import os
import time

import httpx
import pytest

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = os.getenv(
    "SMOKE_BASE_URL", "https://syrian-transit-system.vercel.app"
).rstrip("/")
ADMIN_EMAIL = os.getenv("SMOKE_ADMIN_EMAIL", "admin@damascustransit.sy")
ADMIN_PASSWORD = os.getenv(
    "SMOKE_ADMIN_PASSWORD", os.getenv("TRANSIT_ADMIN_PASSWORD", "")
)

# Operator slug required by the multi-tenant API for public endpoints
OPERATOR = os.getenv("SMOKE_OPERATOR", "damascus")

# Timeout applied to every HTTP request (seconds)
HTTP_TIMEOUT = 15.0
# Maximum acceptable page load time for the homepage (seconds)
HOMEPAGE_MAX_LOAD_SECONDS = 3.0

# WebSocket URL — wss:// for production (https -> wss)
WS_URL = (
    BASE_URL.replace("https://", "wss://").replace("http://", "ws://") + "/api/ws/track"
)


# ---------------------------------------------------------------------------
# Shared sync client fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    """Synchronous httpx client pointing at production."""
    with httpx.Client(
        base_url=BASE_URL, timeout=HTTP_TIMEOUT, follow_redirects=True
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# 1. Health endpoint
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_returns_200(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    def test_health_status_is_healthy(self, client):
        r = client.get("/api/health")
        body = r.json()
        assert body.get("status") == "healthy", (
            f"status is '{body.get('status')}', expected 'healthy'. Full body: {body}"
        )

    def test_health_database_true(self, client):
        r = client.get("/api/health")
        body = r.json()
        assert body.get("database") is True, (
            f"database={body.get('database')}, expected True. Full body: {body}"
        )

    def test_health_redis_true(self, client):
        r = client.get("/api/health")
        body = r.json()
        assert body.get("redis") is True, (
            f"redis={body.get('redis')}, expected True. Full body: {body}"
        )


# ---------------------------------------------------------------------------
# 2. Vehicles — returns list with positions
# ---------------------------------------------------------------------------


class TestVehicles:
    def test_vehicles_returns_200(self, client):
        r = client.get("/api/vehicles", params={"operator": OPERATOR})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    def test_vehicles_returns_list(self, client):
        r = client.get("/api/vehicles", params={"operator": OPERATOR})
        body = r.json()
        assert isinstance(body, list), (
            f"Expected list, got {type(body).__name__}: {body}"
        )

    def test_vehicles_have_positions(self, client):
        r = client.get("/api/vehicles", params={"operator": OPERATOR})
        vehicles = r.json()
        if not vehicles:
            pytest.skip("No vehicles in production data — skipping position check")
        for v in vehicles:
            assert "latitude" in v or "lat" in v, f"Vehicle missing latitude field: {v}"
            assert "longitude" in v or "lng" in v or "lon" in v, (
                f"Vehicle missing longitude field: {v}"
            )


# ---------------------------------------------------------------------------
# 3. Routes — returns list with stops
# ---------------------------------------------------------------------------


class TestRoutes:
    def test_routes_returns_200(self, client):
        r = client.get("/api/routes", params={"operator": OPERATOR})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    def test_routes_returns_list(self, client):
        r = client.get("/api/routes", params={"operator": OPERATOR})
        body = r.json()
        assert isinstance(body, list), (
            f"Expected list, got {type(body).__name__}: {body}"
        )

    def test_routes_have_stop_count(self, client):
        r = client.get("/api/routes", params={"operator": OPERATOR})
        routes = r.json()
        if not routes:
            pytest.skip("No routes in production data — skipping stop_count check")
        for route in routes:
            assert "stop_count" in route, f"Route missing stop_count field: {route}"
            assert isinstance(route["stop_count"], int), (
                f"stop_count is not an int: {route['stop_count']}"
            )

    def test_routes_have_distinct_stop_counts(self, client):
        r = client.get("/api/routes", params={"operator": OPERATOR})
        routes = r.json()
        if len(routes) < 2:
            pytest.skip("Fewer than 2 routes — cannot check for distinct stop counts")
        counts = [route["stop_count"] for route in routes]
        assert len(set(counts)) > 1, (
            f"All routes have identical stop_count={counts[0]} — "
            "per-route filter is likely broken (regression: httpx params={} drops URL query params)"
        )


# ---------------------------------------------------------------------------
# 4. Homepage — loads in <3s, map tiles accessible, vehicles endpoint reachable
# ---------------------------------------------------------------------------


class TestHomepage:
    def test_homepage_returns_200(self, client):
        r = client.get("/")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"

    def test_homepage_loads_under_3s(self, client):
        start = time.perf_counter()
        r = client.get("/")
        elapsed = time.perf_counter() - start
        assert r.status_code == 200
        assert elapsed < HOMEPAGE_MAX_LOAD_SECONDS, (
            f"Homepage took {elapsed:.2f}s, expected < {HOMEPAGE_MAX_LOAD_SECONDS}s"
        )

    def test_homepage_contains_map_reference(self, client):
        r = client.get("/")
        # The homepage HTML should reference a map library (Leaflet, MapboxGL, etc.)
        text = r.text.lower()
        has_map = any(
            kw in text for kw in ("leaflet", "mapbox", "maplibre", "map", "tile")
        )
        assert has_map, "Homepage HTML contains no reference to a map library"

    def test_vehicles_endpoint_reachable_from_homepage_context(self, client):
        """Vehicles data endpoint must be reachable (what the map JS loads)."""
        r = client.get("/api/vehicles", params={"operator": OPERATOR})
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# 5. WebSocket — connects and receives position update message
# ---------------------------------------------------------------------------


class TestWebSocket:
    def test_websocket_connects_and_receives_positions(self):
        """Connect to /api/ws/track and expect a 'positions' message.

        Note: Vercel serverless functions do not support WebSocket upgrades, so
        a 404 rejection is treated as a known platform limitation and skipped.
        """
        try:
            import websockets  # type: ignore
            from websockets.exceptions import InvalidStatus  # type: ignore
        except ImportError:
            pytest.skip("websockets package not installed — skipping WS smoke test")

        async def _run():
            try:
                async with websockets.connect(WS_URL, open_timeout=10) as ws:
                    raw = await asyncio.wait_for(ws.recv(), timeout=10)
                    msg = json.loads(raw)
                    assert msg.get("type") == "positions", (
                        f"First WS message type was '{msg.get('type')}', expected 'positions'"
                    )
                    assert "data" in msg, f"WS message missing 'data' key: {msg}"
                    return msg
            except InvalidStatus as exc:
                if exc.response.status_code == 404:
                    pytest.skip(
                        "WebSocket endpoint returned 404 — likely not supported on this deployment platform (Vercel serverless)"
                    )
                raise

        asyncio.run(_run())

    def test_websocket_responds_to_ping(self):
        """Send a ping and expect a pong.

        Note: Vercel serverless functions do not support WebSocket upgrades, so
        a 404 rejection is treated as a known platform limitation and skipped.
        """
        try:
            import websockets  # type: ignore
            from websockets.exceptions import InvalidStatus  # type: ignore
        except ImportError:
            pytest.skip("websockets package not installed — skipping WS ping test")

        async def _run():
            try:
                async with websockets.connect(WS_URL, open_timeout=10) as ws:
                    # Drain the initial positions message
                    await asyncio.wait_for(ws.recv(), timeout=10)
                    # Send ping
                    await ws.send(json.dumps({"type": "ping"}))
                    raw = await asyncio.wait_for(ws.recv(), timeout=10)
                    msg = json.loads(raw)
                    assert msg.get("type") == "pong", f"Expected pong, got: {msg}"
            except InvalidStatus as exc:
                if exc.response.status_code == 404:
                    pytest.skip(
                        "WebSocket endpoint returned 404 — likely not supported on this deployment platform (Vercel serverless)"
                    )
                raise

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# 6. Admin login page and credentials
# ---------------------------------------------------------------------------


class TestAdmin:
    def test_admin_login_page_returns_200(self, client):
        r = client.get("/admin/")
        assert r.status_code == 200, f"Admin login page returned {r.status_code}"

    def test_admin_login_page_has_form(self, client):
        r = client.get("/admin/")
        text = r.text.lower()
        has_login = any(kw in text for kw in ("login", "sign in", "email", "password"))
        assert has_login, "Admin page has no login form elements"

    @pytest.mark.skipif(
        not ADMIN_PASSWORD,
        reason="SMOKE_ADMIN_PASSWORD / TRANSIT_ADMIN_PASSWORD not set — skipping credential test",
    )
    def test_admin_login_accepts_valid_credentials(self, client):
        r = client.post(
            "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        assert r.status_code == 200, f"Admin login failed ({r.status_code}): {r.text}"
        body = r.json()
        assert "access_token" in body, f"Login response missing access_token: {body}"
        assert body.get("role") in ("admin", "superadmin"), (
            f"Expected admin role, got: {body.get('role')}"
        )


# ---------------------------------------------------------------------------
# 7. Driver and passenger apps — load without server errors
# ---------------------------------------------------------------------------


class TestApps:
    def test_driver_app_returns_200(self, client):
        r = client.get("/driver/")
        assert r.status_code == 200, f"Driver app returned {r.status_code}"

    def test_driver_app_no_server_error_in_html(self, client):
        r = client.get("/driver/")
        # 500-level errors sometimes leak into the HTML body
        assert "internal server error" not in r.text.lower()

    def test_driver_app_has_html_document(self, client):
        r = client.get("/driver/")
        assert "<!doctype html>" in r.text.lower() or "<html" in r.text.lower()

    def test_passenger_app_returns_200(self, client):
        r = client.get("/passenger/")
        assert r.status_code == 200, f"Passenger app returned {r.status_code}"

    def test_passenger_app_no_server_error_in_html(self, client):
        r = client.get("/passenger/")
        assert "internal server error" not in r.text.lower()

    def test_passenger_app_has_html_document(self, client):
        r = client.get("/passenger/")
        assert "<!doctype html>" in r.text.lower() or "<html" in r.text.lower()


# ---------------------------------------------------------------------------
# 8. All key pages return 200
# ---------------------------------------------------------------------------


class TestAllPagesReturn200:
    PAGES = [
        "/",
        "/admin/",
        "/driver/",
        "/passenger/",
    ]

    @pytest.mark.parametrize("path", PAGES)
    def test_page_returns_200(self, client, path):
        r = client.get(path)
        assert r.status_code == 200, (
            f"GET {path} returned {r.status_code} (expected 200)"
        )

    # Endpoints that require the operator query param for multi-tenant routing
    _OPERATOR_PARAMS = {"/api/vehicles", "/api/routes"}

    API_ENDPOINTS = [
        "/api/health",
        "/api/vehicles",
        "/api/routes",
    ]

    @pytest.mark.parametrize("path", API_ENDPOINTS)
    def test_api_endpoint_returns_200(self, client, path):
        params = {"operator": OPERATOR} if path in self._OPERATOR_PARAMS else {}
        r = client.get(path, params=params)
        assert r.status_code == 200, (
            f"GET {path} returned {r.status_code} (expected 200): {r.text[:200]}"
        )
