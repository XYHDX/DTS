"""Cloudflare Turnstile verification — step 85.

Used by /api/auth/login to gate brute-force attempts behind an invisible
challenge when TURNSTILE_SECRET is set in the environment. Failure to set
the secret is a no-op (the gate is off), so existing deployments keep
working without flipping a code switch.
"""

import os
from typing import Optional

import httpx
from fastapi import HTTPException, Request, status

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def turnstile_configured() -> bool:
    return bool(os.getenv("TURNSTILE_SECRET", "").strip())


async def verify_turnstile(
    request: Request,
    *,
    token: Optional[str] = None,
    raise_on_failure: bool = True,
) -> bool:
    """Verify a Turnstile token against Cloudflare.

    Resolution order for the token:
      1. The explicit `token` argument.
      2. `X-Turnstile-Token` header.
      3. `turnstile_token` field in the JSON body (only when already parsed).

    Returns True when the secret is unset (gate is off) or when CF responds
    with success. Raises HTTPException(403) otherwise when raise_on_failure.
    """
    secret = os.getenv("TURNSTILE_SECRET", "").strip()
    if not secret:
        return True

    token = (token
             or request.headers.get("x-turnstile-token", "").strip()
             or None)
    if not token:
        if raise_on_failure:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Captcha verification missing",
            )
        return False

    payload = {
        "secret": secret,
        "response": token,
        "remoteip": request.client.host if request.client else "",
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(VERIFY_URL, data=payload)
        data = resp.json() if resp.status_code == 200 else {}
    except (httpx.HTTPError, ValueError):
        # Soft-fail: if Cloudflare is unreachable we cannot block legitimate
        # users. The FastAPI rate limiter remains as the second line.
        return True

    if data.get("success") is True:
        return True
    if raise_on_failure:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Captcha verification failed",
        )
    return False
