"""Shared vehicle-approval policy (migration 019) — fail-closed, no migration required.

The approval gate is a core safety control: no vehicle may stream GPS, run a
trip, or collect fares until an admin approves it. Historically each gate
treated a NULL/absent ``approval_status`` — and, in the telemetry path, a DB
error — as *approved* (fail-open), so a dropped column or a transient blip
silently turned the control off (audit finding H2).

This module centralizes the decision and makes it fail **closed** without
requiring any migration to be applied. It probes once whether
``vehicles.approval_status`` exists:

* **Column present** (the normal, migrated state): NULL / unknown vehicle / a
  transient lookup error all resolve to **not approved**.
* **Column genuinely absent** (a pre-migration DB): logs one loud warning and
  stays tolerant, so a partially-migrated deployment is not bricked.

Enforcement state is cached after the first definitive answer, so the hot path
costs nothing after warm-up.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from api.core.logging import logger

# None = undetermined · True = column present (enforce) · False = absent (tolerate)
_enforced: Optional[bool] = None
_probe_lock = asyncio.Lock()
_warned_absent = False


def _warn_absent_once() -> None:
    global _warned_absent
    if not _warned_absent:
        _warned_absent = True
        logger.warning(
            "approval_gate_tolerant: vehicles.approval_status is absent — the "
            "approval gate cannot fail closed. Apply migration 019 to enforce it."
        )


def is_missing_column_error(exc: BaseException) -> bool:
    """True when ``exc`` is a PostgREST 'undefined column' style error.

    Distinguishes a genuinely pre-migration schema (column does not exist) from
    a transient DB error, so only the former relaxes the gate.
    """
    resp = getattr(exc, "response", None)
    if resp is None:
        return False
    try:
        if resp.status_code not in (400, 404):
            return False
        body = (resp.text or "").lower()
    except Exception:
        return False
    return (
        "approval_status" in body
        or "42703" in body  # postgres undefined_column
        or "pgrst204" in body  # column not found in schema cache
        or "does not exist" in body
    )


async def _probe_enforced() -> bool:
    """Return True if the column exists, False if definitively absent.

    Raises on a transient/indeterminate error so the caller can default safely.
    """
    from api.core.database import _service_get  # lazy import avoids a cycle

    try:
        await _service_get("vehicles?select=approval_status&limit=1")
        return True
    except Exception as e:
        if is_missing_column_error(e):
            return False
        raise


async def approval_enforced() -> bool:
    """Whether the approval gate should fail closed.

    Cached after the first definitive answer. On a transient error we default to
    **True** (enforce — the safe direction) and do not cache, so a later call
    re-probes.
    """
    global _enforced
    if _enforced is not None:
        return _enforced
    async with _probe_lock:
        if _enforced is not None:
            return _enforced
        try:
            result = await _probe_enforced()
        except Exception:
            return True  # indeterminate -> enforce, don't cache
        _enforced = result
        if result is False:
            _warn_absent_once()
        return result


async def is_vehicle_approved(vehicle: Optional[dict]) -> bool:
    """Decide approval for a fetched vehicle row — fail-closed.

    * No row (unknown vehicle)                 -> not approved
    * ``is_active`` is False                   -> not approved
    * ``approval_status`` key absent from row  -> approved (legacy/pre-migration
      shape: the column isn't in the result, so it can't be enforced — tolerated
      for backward compatibility, exactly as before)
    * ``approval_status`` key present          -> approved ONLY if it is exactly
      ``'approved'``. NULL / pending / rejected / suspended all DENY. (This is
      the fail-closed fix — NULL used to be treated as approved, audit H2.)

    Async by contract so call sites can ``await`` it; intentionally pure (no
    global state) so it never leaks enforcement state across requests/tests.
    """
    if not vehicle:
        return False
    if vehicle.get("is_active") is False:
        return False
    if "approval_status" not in vehicle:
        return True
    return vehicle["approval_status"] == "approved"


def note_column_present() -> None:
    """Opportunistic hint: a successful ``approval_status`` read proves the
    column exists, so callers can set enforcement without a separate probe."""
    global _enforced
    if _enforced is None:
        _enforced = True


def note_missing_column() -> None:
    """Opportunistic hint from a caught missing-column error."""
    global _enforced
    if _enforced is None:
        _enforced = False
        _warn_absent_once()


def reset_cache() -> None:
    """Test hook — clear cached enforcement state."""
    global _enforced, _warned_absent
    _enforced = None
    _warned_absent = False
