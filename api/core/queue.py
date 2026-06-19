"""Upstash QStash — delayed and scheduled job dispatch (step 81).

QStash is a serverless queue + HTTP cron service. We use it for two purposes:

  1. Delayed retries of alert emails when Resend rate-limits us.
  2. Scheduled jobs that complement Vercel cron (which is limited on the free tier).

The implementation degrades gracefully: when QSTASH_TOKEN is not set, calls
become no-ops and the caller proceeds without queueing. This keeps local dev
and the Docker ministry topology unaffected.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx

QSTASH_URL = "https://qstash.upstash.io/v2"


def _qstash_token() -> Optional[str]:
    t = os.getenv("QSTASH_TOKEN", "").strip()
    return t or None


def qstash_configured() -> bool:
    return _qstash_token() is not None


async def enqueue(
    *,
    target_url: str,
    payload: dict[str, Any],
    delay_seconds: int = 0,
    retries: int = 3,
    deduplication_id: Optional[str] = None,
) -> Optional[str]:
    """Publish a single delayed HTTP request via QStash.

    Returns the QStash message id on success, None when QStash is unconfigured
    or the publish fails. The caller decides whether a None return is fatal.

    Example — retry an alert email after 90 seconds:

        await enqueue(
            target_url="https://api.example.com/api/cron/retry-email",
            payload={"alert_id": "...", "to": "ops@..."},
            delay_seconds=90,
            deduplication_id=f"email:{alert_id}",
        )
    """
    token = _qstash_token()
    if token is None:
        return None

    headers: dict[str, str] = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Upstash-Retries": str(max(0, min(retries, 5))),
    }
    if delay_seconds > 0:
        headers["Upstash-Delay"] = f"{delay_seconds}s"
    if deduplication_id:
        headers["Upstash-Deduplication-Id"] = deduplication_id

    url = f"{QSTASH_URL}/publish/{target_url}"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code in (200, 202):
            data = resp.json() if resp.content else {}
            return data.get("messageId")
    except httpx.HTTPError:
        return None
    return None


async def schedule_cron(
    *,
    target_url: str,
    cron_expression: str,
    payload: Optional[dict[str, Any]] = None,
    schedule_id: Optional[str] = None,
) -> Optional[str]:
    """Create or update a repeating job. Idempotent when schedule_id is set."""
    token = _qstash_token()
    if token is None:
        return None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Upstash-Cron": cron_expression,
    }
    if schedule_id:
        headers["Upstash-Schedule-Id"] = schedule_id
    url = f"{QSTASH_URL}/schedules/{target_url}"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(url, headers=headers, json=payload or {})
        if resp.status_code in (200, 201, 202):
            return (resp.json() or {}).get("scheduleId")
    except httpx.HTTPError:
        return None
    return None


def verify_signature(request_headers: dict[str, str]) -> bool:
    """Stub: QStash signs callbacks with an HMAC the receiving endpoint should
    verify. We accept any header in dev (no token set) and require the
    `Upstash-Signature` header otherwise.

    A full HMAC verification implementation belongs in the receiving route
    once we actually wire a QStash → /api/cron/* callback. Until then this
    helper is a placeholder that documents the contract.
    """
    if not qstash_configured():
        return True
    raise NotImplementedError(
        "QStash signature verification is not implemented — verify the Upstash "
        "HMAC over the raw request body before trusting QStash callbacks."
    )
