"""Tests for the M1 JWT-revocation helper.

Validates the cross-tz comparison in api.core.auth.is_token_revoked_by_password_change
and the iat claim emitted by create_access_token.
"""

from datetime import datetime, timedelta, timezone

import jwt

from api.core.auth import (
    JWT_ALGORITHM,
    _get_jwt_secret,
    create_access_token,
    is_token_revoked_by_password_change,
    verify_token,
)


def _aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def test_no_password_change_means_not_revoked():
    iat = datetime.utcnow()
    assert is_token_revoked_by_password_change(iat, None) is False


def test_no_iat_means_not_revoked():
    pwd = datetime.utcnow()
    assert is_token_revoked_by_password_change(None, pwd) is False


def test_token_issued_before_password_change_is_revoked():
    pwd = datetime.now(timezone.utc)
    iat = pwd - timedelta(hours=1)
    assert is_token_revoked_by_password_change(iat, pwd) is True


def test_token_issued_after_password_change_is_not_revoked():
    pwd = datetime.now(timezone.utc) - timedelta(hours=1)
    iat = datetime.now(timezone.utc)
    assert is_token_revoked_by_password_change(iat, pwd) is False


def test_naive_and_aware_datetimes_compare_safely():
    # Pydantic-decoded iat (from JWT) is typically naive UTC.
    # password_changed_at from PostgreSQL is tz-aware.
    # The helper must coerce rather than raise.
    pwd = datetime.now(timezone.utc)
    iat_naive = (pwd - timedelta(minutes=5)).replace(tzinfo=None)
    # Should not raise and should return True (token older than password change).
    assert is_token_revoked_by_password_change(iat_naive, pwd) is True


def test_create_access_token_embeds_iat(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "x" * 64)
    token = create_access_token(
        user_id="u1", email="a@b.test", role="driver", operator_id="op1"
    )
    decoded = jwt.decode(token, _get_jwt_secret(), algorithms=[JWT_ALGORITHM])
    assert "iat" in decoded
    assert "exp" in decoded
    # iat must precede exp
    assert decoded["iat"] < decoded["exp"]


def test_verify_token_round_trip_exposes_iat(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "x" * 64)
    token = create_access_token(
        user_id="u1", email="a@b.test", role="admin", operator_id="op1"
    )
    payload = verify_token(token)
    assert payload.iat is not None
    assert payload.user_id == "u1"
