"""
Security tests: rate limiting and input validation.

These tests use a stub Redis (None client path) so rate limiting always
passes in unit mode — they validate schema rejection and header presence
rather than actual throttle behavior.  Integration tests that need real
Redis are marked with @pytest.mark.integration.
"""

import pytest
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient

    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False

pytestmark = pytest.mark.skipif(not _HAS_FASTAPI, reason="fastapi not installed")


# ── helpers ──────────────────────────────────────────────────────────────────


def _client():
    from api.index import app

    return TestClient(app, raise_server_exceptions=False)


# ── Input validation — LoginRequest ──────────────────────────────────────────


class TestLoginValidation:
    def test_invalid_email_rejected(self):
        c = _client()
        resp = c.post(
            "/api/auth/login", json={"email": "not-an-email", "password": "pw"}
        )
        assert resp.status_code == 422

    def test_empty_email_rejected(self):
        c = _client()
        resp = c.post("/api/auth/login", json={"email": "", "password": "pw"})
        assert resp.status_code == 422

    def test_email_too_long_rejected(self):
        c = _client()
        long_email = "a" * 250 + "@x.com"
        resp = c.post("/api/auth/login", json={"email": long_email, "password": "pw"})
        assert resp.status_code == 422

    def test_password_too_long_rejected(self):
        c = _client()
        resp = c.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "x" * 129},
        )
        assert resp.status_code == 422


# ── Input validation — RegisterRequest ───────────────────────────────────────


class TestRegisterValidation:
    def test_short_password_rejected(self):
        c = _client()
        resp = c.post(
            "/api/auth/register",
            json={
                "email": "new@example.com",
                "password": "short",
                "full_name": "Test User",
            },
        )
        assert resp.status_code == 422

    def test_invalid_email_rejected(self):
        c = _client()
        resp = c.post(
            "/api/auth/register",
            json={
                "email": "bademail",
                "password": "validpassword123",
                "full_name": "Test User",
            },
        )
        assert resp.status_code == 422

    def test_name_too_long_rejected(self):
        c = _client()
        resp = c.post(
            "/api/auth/register",
            json={
                "email": "new@example.com",
                "password": "validpassword123",
                "full_name": "A" * 101,
            },
        )
        assert resp.status_code == 422


# ── Input validation — ForgotPasswordRequest ─────────────────────────────────


class TestForgotPasswordValidation:
    def test_invalid_email_rejected(self):
        c = _client()
        resp = c.post("/api/auth/forgot-password", json={"email": "notanemail"})
        assert resp.status_code == 422

    def test_email_too_long_rejected(self):
        c = _client()
        resp = c.post(
            "/api/auth/forgot-password",
            json={"email": "a" * 250 + "@b.com"},
        )
        assert resp.status_code == 422


# ── Input validation — FeedbackCreate ────────────────────────────────────────


class TestFeedbackValidation:
    def test_rating_below_range_rejected(self):
        from api.models.schemas import FeedbackCreate

        with pytest.raises(Exception):
            FeedbackCreate(trip_id="abc", rating=0)

    def test_rating_above_range_rejected(self):
        from api.models.schemas import FeedbackCreate

        with pytest.raises(Exception):
            FeedbackCreate(trip_id="abc", rating=6)

    def test_comment_too_long_rejected(self):
        from api.models.schemas import FeedbackCreate

        with pytest.raises(Exception):
            FeedbackCreate(trip_id="abc", rating=3, comment="x" * 2001)

    def test_html_stripped_from_comment(self):
        from api.models.schemas import FeedbackCreate

        fb = FeedbackCreate(
            trip_id="abc",
            rating=4,
            comment="<script>alert('xss')</script>nice ride",
        )
        assert "<script>" not in fb.comment
        assert "nice ride" in fb.comment

    def test_valid_feedback_accepted(self):
        from api.models.schemas import FeedbackCreate

        fb = FeedbackCreate(trip_id="abc-123", rating=5, comment="Great!")
        assert fb.rating == 5


# ── Input validation — PositionUpdate coordinate ranges ──────────────────────


class TestPositionValidation:
    def test_latitude_out_of_range_rejected(self):
        from api.models.schemas import PositionUpdate

        with pytest.raises(Exception):
            PositionUpdate(latitude=91.0, longitude=0.0)

    def test_latitude_below_range_rejected(self):
        from api.models.schemas import PositionUpdate

        with pytest.raises(Exception):
            PositionUpdate(latitude=-91.0, longitude=0.0)

    def test_longitude_out_of_range_rejected(self):
        from api.models.schemas import PositionUpdate

        with pytest.raises(Exception):
            PositionUpdate(latitude=0.0, longitude=181.0)

    def test_valid_coordinates_accepted(self):
        from api.models.schemas import PositionUpdate

        pos = PositionUpdate(latitude=33.5138, longitude=36.2765)
        assert pos.latitude == 33.5138


# ── Input validation — NearestStop query params ───────────────────────────────


class TestNearestStopValidation:
    def test_lat_too_high_rejected(self):
        c = _client()
        resp = c.get("/api/stops/nearest?lat=91&lon=36")
        assert resp.status_code == 422

    def test_lon_too_low_rejected(self):
        c = _client()
        resp = c.get("/api/stops/nearest?lat=33&lon=-181")
        assert resp.status_code == 422

    def test_radius_too_large_rejected(self):
        c = _client()
        resp = c.get("/api/stops/nearest?lat=33&lon=36&radius=9999")
        assert resp.status_code == 422

    def test_missing_lat_rejected(self):
        c = _client()
        resp = c.get("/api/stops/nearest?lon=36.2765")
        assert resp.status_code == 422


# ── Input validation — PushBroadcastRequest ──────────────────────────────────


class TestPushBroadcastValidation:
    def test_html_stripped_from_title(self):
        from api.models.schemas import PushBroadcastRequest

        req = PushBroadcastRequest(
            title="<b>Alert</b>",
            body="Normal body",
        )
        assert "<b>" not in req.title
        assert "Alert" in req.title

    def test_title_too_long_rejected(self):
        from api.models.schemas import PushBroadcastRequest

        with pytest.raises(Exception):
            PushBroadcastRequest(title="x" * 201, body="body")

    def test_body_too_long_rejected(self):
        from api.models.schemas import PushBroadcastRequest

        with pytest.raises(Exception):
            PushBroadcastRequest(title="title", body="x" * 1001)


# ── Rate limit — 429 + Retry-After header (mock Redis over limit) ─────────────


class TestRateLimitHeaders:
    def test_login_429_includes_retry_after(self):
        """When rate limit is exceeded, response must include Retry-After header."""

        async def _over_limit(identifier, max_req, window):
            return False

        with patch("api.routers.auth._rate_limit_check", side_effect=_over_limit):
            c = _client()
            resp = c.post(
                "/api/auth/login",
                json={"email": "a@b.com", "password": "password123"},
            )
        assert resp.status_code == 429
        assert "retry-after" in {k.lower() for k in resp.headers}

    def test_routes_429_includes_retry_after(self):
        async def _over_limit(identifier, max_req, window):
            return False

        with patch("api.routers.routes._rate_limit_check", side_effect=_over_limit):
            c = _client()
            resp = c.get("/api/routes")
        assert resp.status_code == 429
        assert "retry-after" in {k.lower() for k in resp.headers}

    def test_vehicles_429_includes_retry_after(self):
        async def _over_limit(identifier, max_req, window):
            return False

        with patch("api.routers.vehicles._rate_limit_check", side_effect=_over_limit):
            c = _client()
            resp = c.get("/api/vehicles")
        assert resp.status_code == 429
        assert "retry-after" in {k.lower() for k in resp.headers}

    def test_gtfs_static_429_includes_retry_after(self):
        async def _over_limit(identifier, max_req, window):
            return False

        with patch("api.routers.gtfs._rate_limit_check", side_effect=_over_limit):
            c = _client()
            resp = c.get("/api/gtfs/static/agency.txt")
        assert resp.status_code == 429
        assert "retry-after" in {k.lower() for k in resp.headers}


# ── SSRF guard on the PostgREST URL builder (CWE-918 / py/partial-ssrf) ───────


class TestSupabaseUrlSsrfGuard:
    """_supabase_url must pin requests to the configured Supabase host."""

    def test_valid_path_builds_url(self):
        from api.core.database import _supabase_url

        url = _supabase_url("trips?id=eq.abc&select=id,notes")
        assert (
            url == "http://mock-supabase.local/rest/v1/trips?id=eq.abc&select=id,notes"
        )

    @pytest.mark.parametrize(
        "ok",
        [
            "users?email=eq.a%40b.com&select=id",  # url-encoded value (@ -> %40)
            "vehicles?id=in.(11111111-2222-3333-4444-555555555555)",  # uuid + in.()
            "trips?driver_id=eq.x&status=in.(scheduled,dispatched,acked)",
            "alerts?select=*&order=created_at.desc&operator_id=eq.op-1",
            "stops?is_active=eq.true&select=id,name_ar",
        ],
    )
    def test_real_postgrest_paths_accepted(self, ok):
        from api.core.database import _supabase_url

        assert _supabase_url(ok).endswith(ok)

    @pytest.mark.parametrize(
        "bad",
        [
            "http://evil.com/x",  # absolute URL / scheme
            "trips://evil",  # scheme marker
            "/etc/passwd",  # leading slash (authority/abs path)
            "@evil.com/x",  # userinfo marker
            "trips?id=eq.1 OR x",  # raw whitespace
            "trips\r\nHost: evil",  # CRLF request splitting
            "trips\\..\\x",  # backslash
        ],
    )
    def test_unsafe_path_rejected(self, bad):
        from fastapi import HTTPException
        from api.core.database import _supabase_url

        with pytest.raises(HTTPException) as ei:
            _supabase_url(bad)
        assert ei.value.status_code == 400
