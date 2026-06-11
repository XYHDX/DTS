"""Sham Cash payments scaffold tests (migration 020).

Security properties under test:
  * QR payloads are HMAC-signed — forged/altered stickers are rejected
  * fixed-fare routes reject tampered amounts
  * unapproved vehicles cannot collect fares
  * webhook requires a valid constant-time HMAC signature; fails closed
  * confirmation is idempotent (no double-credit on replay)
  * sandbox confirm is staff-gated and disabled in live mode
"""

import hashlib
import hmac as hmac_lib
import json
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


def _token(role, user_id="u-1", operator_id="op-001", vehicle_id=None):
    from api.core.auth import create_access_token

    return create_access_token(
        user_id=user_id,
        email=f"{role}@transit.sy",
        role=role,
        operator_id=operator_id,
        vehicle_id=vehicle_id,
        expires_delta=timedelta(hours=1),
    )


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def _make_qr(vehicle_uuid="veh-1", operator_id="op-001", nonce="abc12345"):
    from api.routers.payments import _sign_qr, QR_VERSION

    sig = _sign_qr(vehicle_uuid, operator_id, nonce)
    return f"DTSPAY|{QR_VERSION}|{vehicle_uuid}|{operator_id}|{nonce}|{sig}"


APPROVED_VEHICLE = {
    "id": "veh-1",
    "vehicle_id": "B-104",
    "operator_id": "op-001",
    "assigned_route_id": None,
    "approval_status": "approved",
    "is_active": True,
    "vehicle_type": "taxi",
}


# ---------------------------------------------------------------------------
# QR integrity
# ---------------------------------------------------------------------------


class TestQrIntegrity:
    def test_forged_signature_rejected(self, client):
        qr = _make_qr()[:-4] + "beef"  # tamper with the signature
        r = client.post("/api/pay/initiate", json={"qr": qr, "amount_syp": 5000})
        assert r.status_code == 403

    def test_tampered_vehicle_rejected(self, client):
        qr = _make_qr(vehicle_uuid="veh-1").replace("veh-1", "veh-2")
        r = client.post("/api/pay/initiate", json={"qr": qr, "amount_syp": 5000})
        assert r.status_code == 403

    def test_garbage_qr_rejected(self, client):
        r = client.post(
            "/api/pay/initiate", json={"qr": "not-a-valid-payload-at-all", "amount_syp": 5000}
        )
        assert r.status_code == 422

    def test_unapproved_vehicle_cannot_collect(self, client):
        async def fake_get(query):
            return [{**APPROVED_VEHICLE, "approval_status": "pending"}]

        with patch("api.routers.payments._service_get", side_effect=fake_get):
            r = client.post(
                "/api/pay/initiate", json={"qr": _make_qr(), "amount_syp": 5000}
            )
        assert r.status_code == 403

    def test_valid_qr_creates_pending_payment(self, client):
        async def fake_get(query):
            if query.startswith("vehicles?"):
                return [APPROVED_VEHICLE]
            return []

        async def fake_post(table, data):
            return {**data, "id": "pay-00000001", "expires_at": "2026-06-11T01:00:00Z"}

        with (
            patch("api.routers.payments._service_get", side_effect=fake_get),
            patch("api.routers.payments._service_post", side_effect=fake_post),
        ):
            r = client.post(
                "/api/pay/initiate", json={"qr": _make_qr(), "amount_syp": 5000}
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "pending"
        assert body["sandbox"] is True
        assert body["deeplink"].startswith("shamcash://")

    def test_fixed_fare_amount_tampering_rejected(self, client):
        vehicle = {**APPROVED_VEHICLE, "assigned_route_id": "route-1"}

        async def fake_get(query):
            if query.startswith("vehicles?"):
                return [vehicle]
            if query.startswith("routes?"):
                return [{"id": "route-1", "fare_syp": 5000}]
            return []

        with patch("api.routers.payments._service_get", side_effect=fake_get):
            r = client.post(
                "/api/pay/initiate", json={"qr": _make_qr(), "amount_syp": 100}
            )
        assert r.status_code == 422
        assert "5000" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Webhook security + idempotency
# ---------------------------------------------------------------------------


WEBHOOK_BODY = {
    "payment_id": "pay-00000001",
    "provider_ref": "SC-12345",
    "result": "success",
    "amount_syp": 5000,
}


class TestWebhook:
    def test_webhook_fails_closed_without_secret(self, client):
        os.environ.pop("SHAM_CASH_WEBHOOK_SECRET", None)
        r = client.post("/api/pay/webhook/shamcash", json=WEBHOOK_BODY)
        assert r.status_code == 503

    def test_webhook_rejects_bad_signature(self, client):
        os.environ["SHAM_CASH_WEBHOOK_SECRET"] = "whsec-test"
        try:
            r = client.post(
                "/api/pay/webhook/shamcash",
                json=WEBHOOK_BODY,
                headers={"X-ShamCash-Signature": "deadbeef"},
            )
            assert r.status_code == 401
        finally:
            os.environ.pop("SHAM_CASH_WEBHOOK_SECRET", None)

    def test_webhook_accepts_valid_signature_and_is_idempotent(self, client):
        os.environ["SHAM_CASH_WEBHOOK_SECRET"] = "whsec-test"
        try:
            raw = json.dumps(WEBHOOK_BODY).encode()
            sig = hmac_lib.new(b"whsec-test", raw, hashlib.sha256).hexdigest()

            state = {"status": "pending"}

            async def fake_get(query):
                return [
                    {
                        "id": "pay-00000001",
                        "status": state["status"],
                        "amount_syp": 5000,
                        "expires_at": "2099-01-01T00:00:00Z",
                    }
                ]

            async def fake_patch(query, data):
                state["status"] = data["status"]
                return [{"id": "pay-00000001", **data}]

            with (
                patch("api.routers.payments._service_get", side_effect=fake_get),
                patch("api.routers.payments._service_patch", side_effect=fake_patch),
            ):
                r1 = client.post(
                    "/api/pay/webhook/shamcash",
                    content=raw,
                    headers={
                        "X-ShamCash-Signature": sig,
                        "Content-Type": "application/json",
                    },
                )
                assert r1.status_code == 200, r1.text
                assert r1.json()["status"] == "confirmed"

                # Replay the same callback — must NOT double-process.
                r2 = client.post(
                    "/api/pay/webhook/shamcash",
                    content=raw,
                    headers={
                        "X-ShamCash-Signature": sig,
                        "Content-Type": "application/json",
                    },
                )
                assert r2.status_code == 200
                assert r2.json().get("idempotent") is True
        finally:
            os.environ.pop("SHAM_CASH_WEBHOOK_SECRET", None)

    def test_amount_mismatch_rejected(self, client):
        os.environ["SHAM_CASH_WEBHOOK_SECRET"] = "whsec-test"
        try:
            body = {**WEBHOOK_BODY, "amount_syp": 99999}
            raw = json.dumps(body).encode()
            sig = hmac_lib.new(b"whsec-test", raw, hashlib.sha256).hexdigest()

            async def fake_get(query):
                return [
                    {
                        "id": "pay-00000001",
                        "status": "pending",
                        "amount_syp": 5000,
                        "expires_at": "2099-01-01T00:00:00Z",
                    }
                ]

            with patch("api.routers.payments._service_get", side_effect=fake_get):
                r = client.post(
                    "/api/pay/webhook/shamcash",
                    content=raw,
                    headers={
                        "X-ShamCash-Signature": sig,
                        "Content-Type": "application/json",
                    },
                )
            assert r.status_code == 422
        finally:
            os.environ.pop("SHAM_CASH_WEBHOOK_SECRET", None)


# ---------------------------------------------------------------------------
# Sandbox gating + roles
# ---------------------------------------------------------------------------


class TestSandboxAndRoles:
    def test_sandbox_confirm_requires_staff(self, client):
        r = client.post(
            "/api/pay/sandbox/confirm",
            json=WEBHOOK_BODY,
            headers=_h(_token("viewer")),
        )
        assert r.status_code == 403

    def test_sandbox_confirm_disabled_in_live_mode(self, client):
        os.environ["SHAM_CASH_MODE"] = "live"
        try:
            r = client.post(
                "/api/pay/sandbox/confirm",
                json=WEBHOOK_BODY,
                headers=_h(_token("admin")),
            )
            assert r.status_code == 404
        finally:
            os.environ["SHAM_CASH_MODE"] = "sandbox"

    def test_driver_qr_only_own_vehicle(self, client):
        async def fake_get(query):
            return [APPROVED_VEHICLE]

        with patch("api.routers.payments._supabase_get", side_effect=fake_get):
            r = client.get(
                "/api/pay/qr/veh-1",
                headers=_h(_token("driver", vehicle_id="OTHER-vehicle")),
            )
        assert r.status_code == 403

    def test_admin_payments_list_requires_staff(self, client):
        r = client.get("/api/admin/payments", headers=_h(_token("viewer")))
        assert r.status_code == 403
