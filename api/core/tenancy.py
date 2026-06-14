import logging
import os
import urllib.parse
from typing import Optional

import httpx
from fastapi import HTTPException, status

from api.core.database import _supabase_get, _supabase_headers, _supabase_url

logger = logging.getLogger("damascus_transit")

# Default operator seed data
_DEFAULT_OPERATORS = {
    "damascus": {
        "id": "00000000-0000-0000-0000-000000000001",
        "slug": "damascus",
        "name": "Damascus Transit Authority",
        "name_ar": "\u0647\u064a\u0626\u0629 \u0646\u0642\u0644 \u062f\u0645\u0634\u0642",
        "is_active": True,
    },
}


async def _ensure_operator(slug: str) -> Optional[str]:
    """Seed a default operator if it is missing, return its id or None."""
    seed = _DEFAULT_OPERATORS.get(slug)
    if not seed:
        return None
    # Strip CR/LF before the slug reaches any log sink (defuses log injection;
    # slug is already constrained to a known seed key above).
    safe_slug = str(slug).replace("\r", " ").replace("\n", " ")
    for attempt in range(3):
        try:
            # Use the service-role key so the insert bypasses RLS. The anon
            # key cannot write to `operators`, which silently broke auto-seed
            # in production (every operator-scoped read then 404'd with
            # "Operator 'damascus' not found"). Fall back to anon headers only
            # when no service key is configured.
            try:
                headers = _supabase_headers(use_service_key=True)
            except Exception:
                headers = _supabase_headers()
            headers["Prefer"] = "return=representation,resolution=merge-duplicates"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    _supabase_url("operators?on_conflict=slug"),
                    headers=headers,
                    json=seed,
                )
                resp.raise_for_status()
                result = resp.json()
                if isinstance(result, list) and result:
                    logger.info("Auto-seeded operator '%s'", safe_slug)
                    return result[0].get("id") or seed["id"]
                elif isinstance(result, dict) and result.get("id"):
                    logger.info("Auto-seeded operator '%s'", safe_slug)
                    return result["id"]
                else:
                    # PostgREST returned empty/unexpected — use the known id
                    logger.warning(
                        "Unexpected seed response for '%s': %r, using default id",
                        safe_slug,
                        result,
                    )
                    return seed["id"]
        except Exception as e:
            logger.error(
                "Auto-seed operator '%s' attempt %d/3 failed: %s",
                safe_slug,
                attempt + 1,
                e,
            )
            if attempt < 2:
                import asyncio

                await asyncio.sleep(0.5 * (attempt + 1))
    return None


async def _resolve_operator_id(operator_slug: Optional[str]) -> str:
    if not operator_slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="operator query parameter is required",
        )
    operators = await _supabase_get(
        f"operators?slug=eq.{urllib.parse.quote(operator_slug, safe='')}&is_active=eq.true&select=id"
    )
    if operators:
        return operators[0]["id"]
    # Attempt auto-seed for known default operators
    op_id = await _ensure_operator(operator_slug)
    if op_id:
        return op_id
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Operator '{operator_slug}' not found",
    )


def _op_filter(operator_id: str) -> str:
    return f"operator_id=eq.{operator_id}"


# ---------------------------------------------------------------------------
# Read-scope resolution for public endpoints.
#
# Security fix (2026-06-11): previously, anonymous requests without an
# `?operator=` parameter resolved to op_id=None and the operator filter was
# silently skipped — returning EVERY tenant's rows (cross-tenant data leak).
# Public reads now always resolve to exactly one operator: the caller's
# tenant, the requested slug, or the configured default operator.
# ---------------------------------------------------------------------------
DEFAULT_OPERATOR_SLUG = os.getenv("DEFAULT_OPERATOR_SLUG", "damascus")

# Cache slug -> operator_id so anonymous public reads don't pay an extra
# DB roundtrip per request. Entries refresh every 5 minutes.
_SLUG_CACHE_TTL = 300.0
_slug_cache: dict = {}


async def _resolve_operator_id_cached(operator_slug: str) -> str:
    import time as _time

    cached = _slug_cache.get(operator_slug)
    now = _time.monotonic()
    if cached is not None and (now - cached[0]) < _SLUG_CACHE_TTL:
        return cached[1]
    try:
        op_id = await _resolve_operator_id(operator_slug)
    except Exception as exc:
        # Unknown slug (404) propagates. On transport/DB errors (500), the
        # default operator's FIXED id (migration 002 + seed.sql +
        # _DEFAULT_OPERATORS all agree on it) keeps reads scoped rather
        # than failing or leaking across tenants.
        if (
            isinstance(exc, HTTPException)
            and exc.status_code == status.HTTP_404_NOT_FOUND
        ):
            raise
        seed = _DEFAULT_OPERATORS.get(operator_slug)
        if seed:
            return seed["id"]
        raise
    _slug_cache[operator_slug] = (now, op_id)
    return op_id


async def resolve_read_scope(operator_slug, current_user) -> str:
    """Resolve the single operator_id a read request is allowed to see.

    Rules:
      - super_admin: may request any operator via ?operator=; defaults to
        their own tenant, then to the default operator.
      - any other authenticated user: always their own tenant.
      - anonymous: the requested slug, else DEFAULT_OPERATOR_SLUG.

    Never returns None — public data is always scoped to one tenant.
    """
    if current_user is not None and current_user.role == "super_admin":
        if operator_slug:
            return await _resolve_operator_id_cached(operator_slug)
        if current_user.operator_id:
            return current_user.operator_id
        return await _resolve_operator_id_cached(DEFAULT_OPERATOR_SLUG)
    if current_user is not None and current_user.operator_id:
        return current_user.operator_id
    return await _resolve_operator_id_cached(operator_slug or DEFAULT_OPERATOR_SLUG)


# ---------------------------------------------------------------------------
# M3 — operator-scope guard
# ---------------------------------------------------------------------------
def ensure_operator_scope(
    requested_operator_id: Optional[str],
    user_operator_id: Optional[str],
    user_role: Optional[str] = None,
) -> str:
    """Validate that a request's target operator matches the user's tenant.

    Call this from any admin/dispatcher endpoint that accepts an operator_id
    in the URL or body. Pass the user's role to allow super_admin to bypass.

    Raises:
        HTTPException(400) — neither side resolved to an operator_id.
        HTTPException(403) — user is requesting another operator's data.

    Returns:
        The resolved operator_id (string) to use for the rest of the request.
    """
    SUPER = "super_admin"
    if user_role == SUPER:
        # Super admin may operate across operators. Honour the request value
        # if provided, otherwise fall back to their token's operator_id.
        return (
            requested_operator_id or user_operator_id or ""
        ).strip() or _raise_missing()

    if user_operator_id is None or not str(user_operator_id).strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not bound to an operator; cannot perform tenant-scoped action",
        )

    if requested_operator_id is None or not str(requested_operator_id).strip():
        # No operator on the request — default to the user's own.
        return str(user_operator_id)

    if str(requested_operator_id).strip() != str(user_operator_id).strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator scope mismatch — requested operator does not match user's tenant",
        )

    return str(user_operator_id)


def _raise_missing() -> str:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="operator_id is required for this action",
    )
