"""
Client-side error logging endpoint.
Accepts uncaught JS errors reported by the browser and records them via the
structured logger (and Sentry when configured).

Hardening (2026-06-19): this endpoint is unauthenticated, so every field is
length-bounded at the schema, CR/LF-stripped before it reaches a log sink
(defuses log forging), the real client IP is resolved through the trusted-proxy
helper (X-Forwarded-For is spoofable), and a per-IP rate limit caps Sentry /
log-quota abuse. Over-limit reports are dropped silently (still 204).
"""

import logging
from typing import Optional

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from api.core.cache import RATE_LIMIT_READ, _get_client_ip, _rate_limit_check

router = APIRouter()
logger = logging.getLogger(__name__)

_MAX = 2000


class ClientErrorPayload(BaseModel):
    message: str = Field(max_length=_MAX)
    source: Optional[str] = Field(default="", max_length=1000)
    lineno: Optional[int] = 0
    colno: Optional[int] = 0
    type: Optional[str] = Field(default="Error", max_length=100)
    url: Optional[str] = Field(default="", max_length=1000)
    userAgent: Optional[str] = Field(default="", max_length=500)
    timestamp: Optional[str] = Field(default="", max_length=64)


def _clean(value: Optional[str], limit: int = 500) -> str:
    """Strip CR/LF (log-injection guard) and hard-truncate."""
    if not value:
        return ""
    return str(value).replace("\r", " ").replace("\n", " ")[:limit]


@router.post("/api/log-client-error", status_code=204, tags=["health"])
async def log_client_error(payload: ClientErrorPayload, request: Request):
    """Receive and record an uncaught JS error from a browser client."""
    client_ip = _get_client_ip(request)

    # Per-IP rate limit: drop (do not log / forward) once a client floods us,
    # so a hostile page can't run up the Sentry quota or the log bill.
    max_req, window = RATE_LIMIT_READ
    if not await _rate_limit_check(f"clientlog:{client_ip}", max_req, window):
        return Response(status_code=204)

    logger.error(
        "client_js_error",
        extra={
            "error_type": _clean(payload.type, 100),
            "message": _clean(payload.message, _MAX),
            "source": _clean(payload.source, 1000),
            "lineno": payload.lineno,
            "colno": payload.colno,
            "page_url": _clean(payload.url, 1000),
            "client_ip": client_ip,
            "client_timestamp": _clean(payload.timestamp, 64),
        },
    )

    try:
        import sentry_sdk

        sentry_sdk.capture_message(
            f"[Client JS] {_clean(payload.type, 100)}: {_clean(payload.message, _MAX)}",
            level="error",
            extras={
                "page_url": _clean(payload.url, 1000),
                "error_source_file": _clean(payload.source, 1000),
                "lineno": payload.lineno,
                "colno": payload.colno,
                "userAgent": _clean(payload.userAgent, 500),
            },
        )
    except Exception:
        pass  # Sentry not configured — already logged above
    return Response(status_code=204)
