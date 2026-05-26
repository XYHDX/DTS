import logging
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
    for attempt in range(3):
        try:
            headers = _supabase_headers()
            headers["Prefer"] = "return=representation"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    _supabase_url("operators?on_conflict=slug"),
                    headers=headers,
                    json=seed,
                )
                resp.raise_for_status()
                result = resp.json()
                if isinstance(result, list) and result:
                    logger.info(f"Auto-seeded operator '{slug}'")
                    return result[0].get("id") or seed["id"]
                elif isinstance(result, dict) and result.get("id"):
                    logger.info(f"Auto-seeded operator '{slug}'")
                    return result["id"]
                else:
                    # PostgREST returned empty/unexpected — use the known id
                    logger.warning(
                        f"Unexpected seed response for '{slug}': {result!r}, "
                        f"using default id"
                    )
                    return seed["id"]
        except Exception as e:
            logger.error(
                f"Auto-seed operator '{slug}' attempt {attempt + 1}/3 failed: {e}"
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
        return (requested_operator_id or user_operator_id or "").strip() or _raise_missing()

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
