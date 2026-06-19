"""Sham Cash fare payments — scaffold (migration 020).

Damascus Transit fare flow:

  ┌─────────┐  scan QR   ┌──────────────┐  initiate   ┌─────────────┐
  │Passenger│ ─────────▶ │ Vehicle QR   │ ──────────▶ │ /api/pay/*  │
  │  app    │            │ (HMAC-signed)│             │  (pending)  │
  └─────────┘            └──────────────┘             └──────┬──────┘
       ▲                                                     │ deeplink
       │            confirmed via webhook                    ▼
       └──────────────────────────────────────────  Sham Cash wallet

Design decisions (see docs/ARCHITECTURE_DECISIONS.md §Payments):

* The QR payload is SIGNED by this server. A sticker swapped by a fraudster
  fails signature verification — passengers cannot be tricked into paying a
  different vehicle/operator.
* `payments.provider_ref` is UNIQUE — webhook retries and replayed
  callbacks are idempotent; a captured callback cannot double-credit.
* The webhook signature is HMAC-SHA256 over the raw body with
  SHAM_CASH_WEBHOOK_SECRET, compared in constant time.
* SANDBOX MODE (default): no Sham Cash credentials needed. Payments are
  created normally and confirmed through an admin-gated simulator endpoint.
  Set SHAM_CASH_MODE=live + the three SHAM_CASH_* secrets to go live —
  no code changes required.
* Payments only work on APPROVED vehicles (migration 019) — an unapproved
  or suspended vehicle cannot collect fares through the platform.

Env vars:
  SHAM_CASH_MODE            "sandbox" (default) | "live"
  SHAM_CASH_MERCHANT_ID     merchant account id   (live)
  SHAM_CASH_API_SECRET      API credential        (live)
  SHAM_CASH_WEBHOOK_SECRET  webhook HMAC secret   (live)
  QR_SIGNING_SECRET         optional dedicated QR HMAC key; sandbox derives
                            one from JWT_SECRET when unset. REQUIRED in live.
"""

import hashlib
import hmac
import os
import secrets
import urllib.parse
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from api.core.auth import CurrentUser, require_role
from api.core.cache import RATE_LIMIT_READ, _get_client_ip, _rate_limit_check
from api.core.database import _service_get, _service_patch, _service_post, _supabase_get
from api.core.tenancy import _op_filter
from api.models.schemas import (
    PaymentInitiateRequest,
    PaymentInitiateResponse,
    PaymentStatusResponse,
    ShamCashWebhookPayload,
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

QR_VERSION = "v1"
MAX_FARE_SYP = 1_000_000


def _mode() -> str:
    return os.getenv("SHAM_CASH_MODE", "sandbox").strip().lower()


def _is_sandbox() -> bool:
    return _mode() != "live"


async def _operator_sham(operator_id: str) -> dict:
    """Per-operator Sham Cash config (mode + merchant). The value set from the
    admin dashboard (operators.settings.sham_cash) overrides the env defaults;
    the actual secrets always come from env (never stored here)."""
    cfg = {"mode": _mode(), "merchant_id": os.getenv("SHAM_CASH_MERCHANT_ID", "")}
    if operator_id:
        try:
            rows = await _service_get(
                f"operators?id=eq.{urllib.parse.quote(operator_id, safe='')}&select=*"
            )
            sc = ((rows or [{}])[0].get("settings") or {}).get("sham_cash") or {}
            if sc.get("mode"):
                cfg["mode"] = sc["mode"]
            if sc.get("merchant_id"):
                cfg["merchant_id"] = sc["merchant_id"]
        except Exception:
            # Operator settings are optional UX config; on any read error we
            # deliberately fall back to the env defaults set above.
            logger.warning(
                "Could not read operator Sham Cash settings; using env defaults"
            )
    return cfg


def _qr_secret() -> str:
    """HMAC key for QR payloads. Live mode requires an explicit secret."""
    explicit = os.getenv("QR_SIGNING_SECRET", "").strip()
    if explicit:
        return explicit
    if not _is_sandbox():
        raise HTTPException(
            status_code=503,
            detail="QR_SIGNING_SECRET must be configured in live payment mode.",
        )
    # Sandbox: derive a stable key from JWT_SECRET (already enforced >=32 chars).
    base = os.getenv("JWT_SECRET", "")
    if not base:
        raise HTTPException(status_code=503, detail="JWT_SECRET is not configured.")
    return hashlib.sha256(f"qr-signing:{base}".encode()).hexdigest()


def _sign_qr(vehicle_uuid: str, operator_id: str, nonce: str) -> str:
    msg = f"{QR_VERSION}|{vehicle_uuid}|{operator_id}|{nonce}"
    return hmac.new(_qr_secret().encode(), msg.encode(), hashlib.sha256).hexdigest()[
        :32
    ]


def _build_qr_payload(vehicle_uuid: str, operator_id: str) -> str:
    nonce = secrets.token_urlsafe(8)
    sig = _sign_qr(vehicle_uuid, operator_id, nonce)
    return f"DTSPAY|{QR_VERSION}|{vehicle_uuid}|{operator_id}|{nonce}|{sig}"


def _parse_qr_payload(qr: str) -> tuple:
    """Validate + verify a scanned payload. Returns (vehicle_uuid, operator_id, nonce)."""
    parts = qr.strip().split("|")
    if len(parts) != 6 or parts[0] != "DTSPAY" or parts[1] != QR_VERSION:
        raise HTTPException(status_code=422, detail="Unrecognised QR code.")
    _, _, vehicle_uuid, operator_id, nonce, sig = parts
    expected = _sign_qr(vehicle_uuid, operator_id, nonce)
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="QR signature invalid — possible counterfeit sticker.",
        )
    return vehicle_uuid, operator_id, nonce


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/api/pay/qr/{vehicle_id}", tags=["payments"])
async def get_vehicle_qr(
    vehicle_id: str,
    current_user: CurrentUser = Depends(require_role("driver", "dispatcher", "admin")),
):
    """Return the signed QR payload for a vehicle (driver/operator/admin).

    The driver app renders this as a QR code; operators may also print it
    as the permanent in-vehicle sticker. Only approved vehicles get a code.
    """
    quoted = urllib.parse.quote(vehicle_id, safe="")
    rows = await _supabase_get(
        f"vehicles?id=eq.{quoted}&select=id,vehicle_id,operator_id,approval_status,is_active,assigned_route_id"
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    v = rows[0]

    # Tenant + driver checks: drivers may only request their own vehicle's QR.
    if current_user.role == "driver" and current_user.vehicle_id != v["id"]:
        raise HTTPException(status_code=403, detail="Not your vehicle.")
    if (
        current_user.role in ("dispatcher", "admin")
        and current_user.operator_id
        and v.get("operator_id") != current_user.operator_id
    ):
        raise HTTPException(status_code=404, detail="Vehicle not found")

    if v.get("is_active") is False or (
        v.get("approval_status") is not None and v["approval_status"] != "approved"
    ):
        raise HTTPException(
            status_code=403,
            detail="Vehicle is not approved to operate — no payment QR issued.",
        )

    # Look up the route fare so the driver/operator can see it and the
    # passenger app can show "Pay N SYP" before confirming.
    fare_syp = None
    rid = v.get("assigned_route_id")
    if rid:
        routes = await _supabase_get(
            f"routes?id=eq.{urllib.parse.quote(rid, safe='')}&select=fare_syp"
        )
        raw_fare = (routes or [{}])[0].get("fare_syp")
        if raw_fare:
            fare_syp = int(raw_fare)

    op_cfg = await _operator_sham(v.get("operator_id") or "")
    return {
        "vehicle_code": v.get("vehicle_id"),
        "payload": _build_qr_payload(v["id"], v.get("operator_id") or ""),
        "fare_syp": fare_syp,
        "sandbox": op_cfg["mode"] != "live",
    }


@router.post(
    "/api/pay/initiate", response_model=PaymentInitiateResponse, tags=["payments"]
)
async def initiate_payment(body: PaymentInitiateRequest, raw_request: Request):
    """Passenger scanned a vehicle QR — create a pending fare payment.

    Anti-tamper rules:
    * QR signature must verify (counterfeit stickers rejected).
    * When the vehicle's assigned route has a fixed fare (bus/microbus),
      the paid amount MUST equal the route fare — the client cannot
      manipulate the price. Taxis (no fixed fare) pass the metered amount.
    """
    client_ip = _get_client_ip(raw_request)
    max_req, window = RATE_LIMIT_READ
    if not await _rate_limit_check(f"payinit:{client_ip}", max_req, window):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many payment attempts. Try again later.",
            headers={"Retry-After": str(window)},
        )

    vehicle_uuid, operator_id, nonce = _parse_qr_payload(body.qr)

    rows = await _service_get(
        f"vehicles?id=eq.{urllib.parse.quote(vehicle_uuid, safe='')}"
        f"&select=id,vehicle_id,operator_id,assigned_route_id,approval_status,is_active,vehicle_type"
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    v = rows[0]

    if v.get("operator_id") != operator_id:
        raise HTTPException(
            status_code=403, detail="QR does not match vehicle operator."
        )
    if v.get("is_active") is False or (
        v.get("approval_status") is not None and v["approval_status"] != "approved"
    ):
        raise HTTPException(
            status_code=403,
            detail="This vehicle is not approved to collect fares.",
        )

    # Fixed-fare enforcement. On a fixed-fare route the price is server-set;
    # an amount supplied by the client may only confirm it, never change it.
    # If the client omits the amount, we fill in the route fare. Vehicles with
    # no fixed fare (e.g. taxis) must supply the amount.
    route_id = v.get("assigned_route_id")
    fare = None
    if route_id:
        routes = await _service_get(
            f"routes?id=eq.{urllib.parse.quote(route_id, safe='')}&select=id,fare_syp"
        )
        raw_fare = (routes or [{}])[0].get("fare_syp")
        fare = int(raw_fare) if raw_fare else None

    if fare and fare > 0:
        if body.amount_syp is not None and body.amount_syp != fare:
            raise HTTPException(
                status_code=422,
                detail=f"Fare for this route is {fare} SYP.",
            )
        amount = fare
    else:
        if not body.amount_syp or body.amount_syp <= 0:
            raise HTTPException(
                status_code=422,
                detail="Amount is required for this vehicle.",
            )
        amount = body.amount_syp

    # Mode comes from the operator's dashboard setting (env is the fallback).
    op_cfg = await _operator_sham(operator_id)
    sandbox = op_cfg["mode"] != "live"

    payment = {
        "operator_id": operator_id,
        "vehicle_id": v["id"],
        "route_id": route_id,
        "amount_syp": amount,
        "status": "pending",
        "qr_nonce": nonce,
        "sandbox": sandbox,
    }
    created = await _service_post("payments", payment)
    created = created if isinstance(created, dict) else (created[0] if created else {})
    if not created.get("id"):
        raise HTTPException(status_code=500, detail="Failed to create payment")

    # Deep link the passenger app opens. In live mode this is the official
    # Sham Cash payment URI with the merchant account; in sandbox it is a
    # clearly-marked test link.
    if sandbox:
        deeplink = f"shamcash://sandbox/pay?ref={created['id']}&amount={amount}"
    else:
        merchant = op_cfg.get("merchant_id") or ""
        deeplink = (
            f"shamcash://pay?merchant={urllib.parse.quote(merchant)}"
            f"&ref={created['id']}&amount={amount}&currency=SYP"
        )

    return PaymentInitiateResponse(
        payment_id=created["id"],
        status="pending",
        amount_syp=amount,
        vehicle_code=v.get("vehicle_id"),
        deeplink=deeplink,
        sandbox=sandbox,
        expires_at=created.get("expires_at"),
    )


@router.get(
    "/api/pay/status/{payment_id}",
    response_model=PaymentStatusResponse,
    tags=["payments"],
)
async def payment_status(payment_id: str):
    """Poll a payment's state (the UUID itself is the access capability)."""
    rows = await _service_get(
        f"payments?id=eq.{urllib.parse.quote(payment_id, safe='')}"
        f"&select=id,status,amount_syp,confirmed_at,sandbox"
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Payment not found")
    p = rows[0]
    return PaymentStatusResponse(
        payment_id=p["id"],
        status=p["status"],
        amount_syp=p["amount_syp"],
        confirmed_at=p.get("confirmed_at"),
        sandbox=p.get("sandbox", True),
    )


async def _confirm_payment(payload: ShamCashWebhookPayload) -> dict:
    """Shared by the real webhook and the sandbox simulator. Idempotent."""
    quoted = urllib.parse.quote(payload.payment_id, safe="")
    rows = await _service_get(
        f"payments?id=eq.{quoted}&select=id,status,amount_syp,expires_at"
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Payment not found")
    p = rows[0]

    # Idempotency / replay safety
    if p["status"] in ("confirmed", "refunded"):
        return {"status": p["status"], "idempotent": True}
    if payload.amount_syp != p["amount_syp"]:
        raise HTTPException(status_code=422, detail="Amount mismatch.")

    # A failed callback must NOT be terminal. Previously it set status='failed'
    # and wrote provider_ref, so a later GENUINE success for the same payment
    # could never confirm: the row was no longer 'pending', and the reused
    # provider_ref tripped its UNIQUE constraint. We now leave a failed attempt
    # 'pending' (it lapses via expires_at) and only ever write provider_ref /
    # confirmed_at on success.
    if payload.result != "success":
        return {"status": "failed", "terminal": False, "idempotent": False}

    update = {
        "status": "confirmed",
        "provider_ref": payload.provider_ref,
        "payer_hint": payload.payer_hint,
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
    }
    # &status=eq.pending + UNIQUE(provider_ref) keep this idempotent: a second
    # success or a replayed callback finds no pending row / a duplicate ref and
    # is ignored instead of double-crediting.
    result = await _service_patch(f"payments?id=eq.{p['id']}&status=eq.pending", update)
    if not result:
        return {"status": "ignored", "reason": "not_pending_or_duplicate_ref"}
    return {"status": "confirmed", "idempotent": False}


@router.post("/api/pay/webhook/shamcash", tags=["payments"])
async def shamcash_webhook(
    payload: ShamCashWebhookPayload,
    request: Request,
    x_shamcash_signature: Optional[str] = Header(default=None),
):
    """Sham Cash server-to-server confirmation callback (live mode).

    HMAC-SHA256 over the raw body with SHAM_CASH_WEBHOOK_SECRET,
    constant-time compared. Fails closed when the secret is unset.
    """
    secret = os.getenv("SHAM_CASH_WEBHOOK_SECRET", "").strip()
    if not secret:
        raise HTTPException(
            status_code=503,
            detail="Webhook not configured (SHAM_CASH_WEBHOOK_SECRET unset).",
        )
    raw = await request.body()
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    provided = (x_shamcash_signature or "").strip().lower()
    if not provided or not hmac.compare_digest(expected, provided):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    return await _confirm_payment(payload)


@router.post("/api/pay/sandbox/confirm", tags=["payments"])
async def sandbox_confirm(
    payload: ShamCashWebhookPayload,
    current_user: CurrentUser = Depends(
        require_role("admin", "dispatcher", "super_admin")
    ),
):
    """SANDBOX ONLY — simulate the Sham Cash confirmation callback.

    Disabled entirely in live mode. Lets the team demo the full passenger
    payment loop before merchant credentials exist.
    """
    if not _is_sandbox():
        raise HTTPException(status_code=404, detail="Not available in live mode.")
    return await _confirm_payment(payload)


@router.post("/api/pay/sandbox/selfpay/{payment_id}", tags=["payments"])
async def sandbox_selfpay(payment_id: str, raw_request: Request):
    """SANDBOX ONLY — let a passenger complete a demo payment themselves.

    Real payments are confirmed by Sham Cash's signed webhook. This endpoint
    exists so the passenger app can demonstrate the full pay loop end-to-end
    before merchant credentials exist. It moves no real money, 404s in live
    mode, and is rate-limited. The payment_id (an unguessable UUID returned by
    /api/pay/initiate) is the access capability.
    """
    if not _is_sandbox():
        raise HTTPException(status_code=404, detail="Not available in live mode.")

    client_ip = _get_client_ip(raw_request)
    max_req, window = RATE_LIMIT_READ
    if not await _rate_limit_check(f"payselfpay:{client_ip}", max_req, window):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Try again later.",
            headers={"Retry-After": str(window)},
        )

    rows = await _service_get(
        f"payments?id=eq.{urllib.parse.quote(payment_id, safe='')}"
        f"&select=id,amount_syp,status"
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Payment not found")
    p = rows[0]

    sim = ShamCashWebhookPayload(
        payment_id=p["id"],
        provider_ref=f"SANDBOX-{secrets.token_hex(6)}",
        result="success",
        amount_syp=p["amount_syp"],
        payer_hint="sandbox",
    )
    return await _confirm_payment(sim)


@router.get("/api/admin/payments", tags=["payments"])
async def list_payments(
    limit: int = 100,
    current_user: CurrentUser = Depends(
        require_role("admin", "dispatcher", "super_admin")
    ),
):
    """Operator-scoped payment ledger for the admin dashboard."""
    limit = max(1, min(limit, 500))
    op_suffix = ""
    if current_user.role != "super_admin" and current_user.operator_id:
        op_suffix = f"&{_op_filter(current_user.operator_id)}"
    rows = await _service_get(
        f"payments?select=id,vehicle_id,route_id,amount_syp,status,sandbox,"
        f"provider_ref,created_at,confirmed_at&order=created_at.desc&limit={limit}"
        f"{op_suffix}"
    )
    return rows or []
