import logging
import os
import re
from typing import Optional
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

try:
    from api.core.auth import current_user_token
except ImportError:
    current_user_token = None


logger = logging.getLogger(__name__)

# SSRF guard (CWE-918 / CodeQL py/partial-ssrf): PostgREST paths are assembled
# server-side from table names, operators, and URL-encoded values, so a
# legitimate path never contains a control char, whitespace, or backslash.
# Rejecting those — plus any scheme/authority marker — means request data can
# never redirect a call off the trusted Supabase host.
_UNSAFE_PATH_CHARS = re.compile(r"[\x00-\x20\\]")


def _supabase_headers(use_service_key: bool = False) -> dict:
    token = current_user_token.get() if current_user_token else None

    # Service-key requests must ALWAYS use the service role, even when a user
    # token is present. Previously the `and not token` condition meant an
    # authenticated request (which sets current_user_token) silently forwarded
    # the user JWT instead — so server-trusted reads (admin/dispatcher/driver
    # dashboards via the _service_* helpers) were still gated by RLS and came
    # back empty even though the data exists.
    if use_service_key:
        key = os.getenv("SUPABASE_SERVICE_KEY", "")
        if not key:
            raise HTTPException(
                status_code=500, detail="SUPABASE_SERVICE_KEY not configured"
            )
        auth_header = f"Bearer {key}"
        apikey = key
    else:
        apikey = os.getenv("SUPABASE_ANON_KEY", os.getenv("SUPABASE_KEY", ""))
        if not apikey:
            raise HTTPException(
                status_code=500, detail="SUPABASE_ANON_KEY not configured"
            )
        auth_header = f"Bearer {token}" if token else f"Bearer {apikey}"

    return {
        "apikey": apikey,
        "Authorization": auth_header,
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _supabase_url(path: str) -> str:
    """Build a PostgREST URL, pinned to the configured Supabase host.

    SSRF barrier (CWE-918): ``path`` is built from request-derived values
    (ids, filters), so it is validated before it can reach an outbound request.
    We reject a scheme (``://``), an authority/userinfo (leading ``/`` or
    ``@``), a backslash, or any whitespace/control char (which could enable
    CRLF request-splitting). As defence in depth, the final URL's host must
    still match the configured base, so the request can only ever target
    Supabase.
    """
    base = os.getenv("SUPABASE_URL", "")
    if (
        not isinstance(path, str)
        or "://" in path
        or path.startswith(("/", "@"))
        or _UNSAFE_PATH_CHARS.search(path) is not None
    ):
        raise HTTPException(status_code=400, detail="Invalid query path")
    url = f"{base}/rest/v1/{path}"
    if urlparse(url).netloc != urlparse(base).netloc:
        raise HTTPException(status_code=400, detail="Invalid query path")
    return url


async def _supabase_get(path: str, params: Optional[dict] = None) -> list:
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=3.0)
        ) as client:
            resp = await client.get(
                _supabase_url(path), headers=_supabase_headers(), params=params
            )
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else [data] if data else []
    except Exception as e:
        logger.error("Database query failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


async def _supabase_post(path: str, data: dict) -> dict:
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=3.0)
        ) as client:
            resp = await client.post(
                _supabase_url(path), headers=_supabase_headers(), json=data
            )
            resp.raise_for_status()
            return resp.json() if resp.content else {}
    except Exception as e:
        logger.error("Database operation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


async def _supabase_patch(path: str, data: dict) -> list:
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=3.0)
        ) as client:
            resp = await client.patch(
                _supabase_url(path), headers=_supabase_headers(), json=data
            )
            resp.raise_for_status()
            result = resp.json()
            return result if isinstance(result, list) else [result] if result else []
    except Exception as e:
        logger.error("Database update failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


async def _supabase_delete(path: str) -> None:
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=3.0)
        ) as client:
            resp = await client.delete(_supabase_url(path), headers=_supabase_headers())
            resp.raise_for_status()
    except Exception as e:
        logger.error("Database delete failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


async def _supabase_rpc(func_name: str, params: dict):
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=3.0)
        ) as client:
            resp = await client.post(
                f"{os.getenv('SUPABASE_URL')}/rest/v1/rpc/{func_name}",
                headers=_supabase_headers(),
                json=params,
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error("RPC call failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


async def _service_get(path: str) -> list:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            _supabase_url(path), headers=_supabase_headers(use_service_key=True)
        )
        resp.raise_for_status()
        if not resp.content:
            return []
        data = resp.json()
        return data if isinstance(data, list) else [data] if data else []


async def _service_post(path: str, data: dict) -> dict:
    """INSERT with the service-role key (bypasses RLS — server-trusted paths).

    Bug fix (2026-06-11): api/routers/mqtt_ingest.py lazily imported this
    helper but it was never defined, so every telemetry persist raised
    ImportError and the frame was dropped. Defined now; also used by the
    Sham Cash payments scaffold.
    """
    headers = _supabase_headers(use_service_key=True)
    headers["Prefer"] = "return=representation"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(_supabase_url(path), headers=headers, json=data)
        resp.raise_for_status()
        if not resp.content:
            return {}
        result = resp.json()
        return result[0] if isinstance(result, list) and result else result


async def _service_patch(path: str, data: dict) -> list:
    """UPDATE with the service-role key (bypasses RLS — server-trusted paths)."""
    headers = _supabase_headers(use_service_key=True)
    headers["Prefer"] = "return=representation"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.patch(_supabase_url(path), headers=headers, json=data)
        resp.raise_for_status()
        if not resp.content:
            return []
        result = resp.json()
        return result if isinstance(result, list) else [result]


async def _service_rpc(func_name: str, params: dict):
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{os.getenv('SUPABASE_URL')}/rest/v1/rpc/{func_name}",
            headers=_supabase_headers(use_service_key=True),
            json=params,
        )
        resp.raise_for_status()
        return resp.json() if resp.content else None


async def _health_check() -> bool:
    try:
        await _supabase_get("users?select=id&limit=1")
        return True
    except Exception:
        return False


async def _last_position_update() -> Optional[str]:
    try:
        rows = await _supabase_get(
            "vehicle_positions_latest?select=recorded_at&order=recorded_at.desc&limit=1"
        )
        if rows:
            return rows[0].get("recorded_at")
        return None
    except Exception:
        return None


async def _active_vehicle_count() -> Optional[int]:
    try:
        rows = await _supabase_get(
            "vehicles?is_active=eq.true&status=eq.active&select=id"
        )
        return len(rows) if rows is not None else None
    except Exception:
        return None
