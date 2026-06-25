"""Fail-closed vehicle-approval policy — api/core/approval.py.

Hermetic: imports only the policy module (no DB, no app). Verifies the gate
denies on NULL / unknown / non-approved when the approval column is enforced,
and tolerates only a genuinely pre-migration (absent-column) database.
"""

from __future__ import annotations

import asyncio

from api.core import approval


class _Resp:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text


class _HTTPish(Exception):
    def __init__(self, resp):
        self.response = resp


def setup_function(_):
    approval.reset_cache()


def test_missing_column_error_detection():
    assert (
        approval.is_missing_column_error(
            _HTTPish(_Resp(400, "column vehicles.approval_status does not exist"))
        )
        is True
    )
    assert (
        approval.is_missing_column_error(_HTTPish(_Resp(400, '{"code":"42703"}'))) is True
    )
    # A transient 500 is NOT a missing-column error -> must not relax the gate.
    assert approval.is_missing_column_error(_HTTPish(_Resp(500, "boom"))) is False
    # An exception with no response object at all.
    assert approval.is_missing_column_error(RuntimeError("nope")) is False


def test_present_column_denies_null_and_nonapproved():
    # A row that carries approval_status is approved only if exactly 'approved'.
    run = asyncio.run
    assert (
        run(approval.is_vehicle_approved({"approval_status": "approved", "is_active": True}))
        is True
    )
    assert run(approval.is_vehicle_approved({"approval_status": None})) is False
    assert run(approval.is_vehicle_approved({"approval_status": "pending"})) is False
    assert run(approval.is_vehicle_approved({"approval_status": "suspended"})) is False
    assert (
        run(approval.is_vehicle_approved({"approval_status": "approved", "is_active": False}))
        is False
    )
    assert run(approval.is_vehicle_approved(None)) is False


def test_legacy_row_without_column_allowed():
    # Pre-migration row shape: the column is absent from the result -> tolerated.
    run = asyncio.run
    assert run(approval.is_vehicle_approved({"id": "v1", "is_active": True})) is True
    # ...but an inactive vehicle is still denied even on a legacy row.
    assert run(approval.is_vehicle_approved({"id": "v1", "is_active": False})) is False


def test_enforced_caches_first_definitive_answer():
    approval.note_column_present()
    assert asyncio.run(approval.approval_enforced()) is True
