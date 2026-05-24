"""Pytest fixtures for Damascus Transit API tests."""

import os
import pytest

try:
    from fastapi.testclient import TestClient

    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False

# Set env vars before importing the app
os.environ.setdefault("SUPABASE_URL", "http://mock-supabase.local")
os.environ.setdefault("SUPABASE_KEY", "mock-key")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "mock-service-key")
os.environ.setdefault("SUPABASE_ANON_KEY", "mock-anon-key")
os.environ.setdefault("JWT_SECRET", "test-secret-for-ci-only-xxxxxxxxxxxxxxxxx")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Clear in-memory rate limiter state before each test.

    In CI there is no Redis, so the in-memory sliding-window limiter is used.
    Without this reset the accumulated request timestamps from earlier tests
    carry over and cause HTTP 429 failures in later tests.
    """
    try:
        import api.core.cache as _cache

        _cache._rl_memory.clear()
    except Exception:
        pass
    yield


@pytest.fixture(scope="session")
def client():
    """TestClient for the FastAPI app."""
    if not _HAS_FASTAPI:
        pytest.skip("fastapi not installed — skipping unit-test client fixture")
    from api.index import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope="session")
def auth_token(client):
    """Obtain a JWT token via login (requires seeded DB — skipped in unit mode)."""
    return None
