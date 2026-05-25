import logging
import os
from typing import Optional

import httpx
from fastapi import HTTPException

try:
    from api.core.auth import current_user_token
except ImportError:
    current_user_token = None


logger = logging.getLogger(__name__)


def _supabase_headers(use_service_key: bool = False) -> dict:
    token = current_user_token.get() if current_user_token else None

    if use_service_key and not token:
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
    base = os.getenv("SUPABASE_URL", "")
    return f"{base}/rest/v1/{path}"


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
