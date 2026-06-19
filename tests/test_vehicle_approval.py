"""Vehicle operating-approval workflow tests (migration 019).

Covers the restructure decisions of 2026-06-11:
  * dispatcher-created vehicles start `pending`; admin-created are approved
  * dispatchers can create ONLY driver accounts
  * only admins decide approvals (approve/reject/suspend/resubmit)
  * state-machine transition rules
  * drivers of unapproved vehicles cannot start trips or post positions
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


VEHICLE_BODY = {
    "vehicle_id": "B-900",
    "name": "Bus 900",
    "name_ar": "حافلة ٩٠٠",
    "vehicle_type": "bus",
    "capacity": 40,
}


# ---------------------------------------------------------------------------
# Creation → approval state
# ---------------------------------------------------------------------------


class TestVehicleCreationApprovalState:
    def test_dispatcher_created_vehicle_is_pending(self, client):
        created = {}

        async def fake_post(table, data):
            created.update(data)
            return {**data, "id": "veh-1", "created_at": "2026-06-11T00:00:00Z"}

        with (
            patch("api.routers.admin._service_get", new_callable=AsyncMock) as g,
            patch("api.routers.admin._service_post", side_effect=fake_post),
        ):
            g.return_value = []  # no duplicate
            r = client.post(
                "/api/admin/vehicles",
                json=VEHICLE_BODY,
                headers=_h(_token("dispatcher")),
            )
        assert r.status_code == 200, r.text
        assert created["approval_status"] == "pending"
        assert r.json()["approval_status"] == "pending"

    def test_admin_created_vehicle_is_approved(self, client):
        created = {}

        async def fake_post(table, data):
            created.update(data)
            return {**data, "id": "veh-2", "created_at": "2026-06-11T00:00:00Z"}

        with (
            patch("api.routers.admin._service_get", new_callable=AsyncMock) as g,
            patch("api.routers.admin._service_post", side_effect=fake_post),
        ):
            g.return_value = []
            r = client.post(
                "/api/admin/vehicles",
                json={**VEHICLE_BODY, "vehicle_id": "B-901"},
                headers=_h(_token("admin")),
            )
        assert r.status_code == 200, r.text
        assert created["approval_status"] == "approved"
        assert created["approved_by"] is not None

    def test_duplicate_fleet_code_rejected(self, client):
        with patch(
            "api.routers.admin._service_get", new_callable=AsyncMock
        ) as g:
            g.return_value = [{"id": "existing"}]
            r = client.post(
                "/api/admin/vehicles",
                json=VEHICLE_BODY,
                headers=_h(_token("admin")),
            )
        assert r.status_code == 409


# ---------------------------------------------------------------------------
# Dispatcher provisioning limits
# ---------------------------------------------------------------------------


class TestDispatcherUserCreation:
    def test_dispatcher_can_create_driver(self, client):
        async def fake_post(table, data):
            return {**data, "id": "drv-1"}

        with (
            patch("api.routers.admin._service_get", new_callable=AsyncMock) as g,
            patch("api.routers.admin._service_post", side_effect=fake_post),
        ):
            g.return_value = []
            r = client.post(
                "/api/admin/users",
                json={
                    "email": "driver1@op.sy",
                    "password": "longenough8",
                    "full_name": "Driver One",
                    "role": "driver",
                },
                headers=_h(_token("dispatcher")),
            )
        assert r.status_code == 200, r.text

    def test_dispatcher_cannot_create_admin(self, client):
        r = client.post(
            "/api/admin/users",
            json={
                "email": "evil@op.sy",
                "password": "longenough8",
                "full_name": "Evil Admin",
                "role": "admin",
            },
            headers=_h(_token("dispatcher")),
        )
        assert r.status_code == 403

    def test_viewer_cannot_create_users(self, client):
        r = client.post(
            "/api/admin/users",
            json={
                "email": "x@op.sy",
                "password": "longenough8",
                "full_name": "X",
                "role": "driver",
            },
            headers=_h(_token("viewer")),
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Approval decisions
# ---------------------------------------------------------------------------


class TestApprovalDecisions:
    def _decide(self, client, role, action, current_state, note=None):
        async def fake_get(query):
            return [
                {
                    "id": "veh-1",
                    "vehicle_id": "B-900",
                    "approval_status": current_state,
                }
            ]

        async def fake_patch(query, data):
            return [{"id": "veh-1", **data}]

        async def fake_post(table, data):
            return {**data, "id": "audit-1"}

        with (
            patch("api.routers.admin._service_get", side_effect=fake_get),
            patch("api.routers.admin._service_patch", side_effect=fake_patch),
            patch("api.routers.admin._service_post", side_effect=fake_post),
        ):
            return client.post(
                "/api/admin/vehicles/veh-1/approval",
                json={"action": action, "note": note},
                headers=_h(_token(role)),
            )

    def test_admin_approves_pending(self, client):
        r = self._decide(client, "admin", "approve", "pending")
        assert r.status_code == 200
        assert r.json()["status"] == "approved"

    def test_admin_rejects_pending_with_note(self, client):
        r = self._decide(client, "admin", "reject", "pending", note="missing GPS unit")
        assert r.status_code == 200
        assert r.json()["status"] == "rejected"

    def test_admin_suspends_approved(self, client):
        r = self._decide(client, "admin", "suspend", "approved")
        assert r.status_code == 200
        assert r.json()["status"] == "suspended"

    def test_resubmit_rejected_back_to_pending(self, client):
        r = self._decide(client, "admin", "resubmit", "rejected")
        assert r.status_code == 200
        assert r.json()["status"] == "pending"

    def test_cannot_approve_rejected_directly(self, client):
        r = self._decide(client, "admin", "approve", "rejected")
        assert r.status_code == 409

    def test_cannot_suspend_pending(self, client):
        r = self._decide(client, "admin", "suspend", "pending")
        assert r.status_code == 409

    def test_dispatcher_cannot_decide(self, client):
        r = self._decide(client, "dispatcher", "approve", "pending")
        assert r.status_code == 403

    def test_driver_cannot_decide(self, client):
        r = self._decide(client, "driver", "approve", "pending")
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Enforcement: unapproved vehicles cannot operate
# ---------------------------------------------------------------------------


class TestApprovalEnforcement:
    def test_trip_start_blocked_for_pending_vehicle(self, client):
        async def fake_get(query):
            return [
                {
                    "id": "veh-1",
                    "assigned_route_id": "route-1",
                    "approval_status": "pending",
                    "is_active": True,
                }
            ]

        with patch("api.routers.driver._service_get", side_effect=fake_get):
            r = client.post(
                "/api/driver/trip/start",
                json={"route_id": "route-1"},
                headers=_h(_token("driver", user_id="drv-9")),
            )
        assert r.status_code == 403

    def test_position_blocked_for_suspended_vehicle(self, client):
        async def fake_get(query):
            return [
                {
                    "id": "veh-1",
                    "assigned_route_id": "route-1",
                    "approval_status": "suspended",
                    "is_active": True,
                }
            ]

        with patch("api.routers.driver._service_get", side_effect=fake_get):
            r = client.post(
                "/api/driver/position",
                json={"latitude": 33.5, "longitude": 36.3, "speed_kmh": 30},
                headers=_h(_token("driver", user_id="drv-9")),
            )
        assert r.status_code == 403

    def test_trip_start_allowed_for_approved_vehicle(self, client):
        async def fake_get(query):
            # The concurrent-trip guard asks for an existing in_progress trip;
            # there is none here.
            if "trips?" in query and "in_progress" in query:
                return []
            return [
                {
                    "id": "veh-1",
                    "assigned_route_id": "route-1",
                    "approval_status": "approved",
                    "is_active": True,
                }
            ]

        async def fake_post(table, data):
            return {**data, "id": "trip-1"}

        with (
            patch("api.routers.driver._service_get", side_effect=fake_get),
            patch("api.routers.driver._service_post", side_effect=fake_post),
        ):
            r = client.post(
                "/api/driver/trip/start",
                json={"route_id": "route-1"},
                headers=_h(_token("driver", user_id="drv-9")),
            )
        assert r.status_code == 200, r.text

    def test_legacy_db_without_column_still_works(self, client):
        """Before migration 019 the approval_status key is absent — treated
        as approved so the live fleet never halts on deploy order."""

        async def fake_get(query):
            if "trips?" in query and "in_progress" in query:
                return []
            return [{"id": "veh-1", "assigned_route_id": "route-1", "is_active": True}]

        async def fake_post(table, data):
            return {**data, "id": "trip-1"}

        with (
            patch("api.routers.driver._service_get", side_effect=fake_get),
            patch("api.routers.driver._service_post", side_effect=fake_post),
        ):
            r = client.post(
                "/api/driver/trip/start",
                json={"route_id": "route-1"},
                headers=_h(_token("driver", user_id="drv-9")),
            )
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Pending count endpoint (sidebar badge)
# ---------------------------------------------------------------------------


class TestPendingCount:
    def test_pending_count(self, client):
        with patch(
            "api.routers.admin._service_get", new_callable=AsyncMock
        ) as g:
            g.return_value = [{"id": "1"}, {"id": "2"}]
            r = client.get(
                "/api/admin/vehicles/pending-count", headers=_h(_token("admin"))
            )
        assert r.status_code == 200
        assert r.json()["pending"] == 2

    def test_pending_count_requires_staff(self, client):
        r = client.get(
            "/api/admin/vehicles/pending-count", headers=_h(_token("viewer"))
        )
        assert r.status_code == 403
