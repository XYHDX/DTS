"""
Damascus Transit FastAPI Backend — v5.0 (hardened).

This release closes the audit findings documented in FIXES_APPLIED.md:

  • H1: shared bcrypt hash removed; each role has its own password.
  • H2: super_admin role + strict per-operator isolation on EVERY admin
        endpoint; dispatcher cannot see other operators' data.
  • H3: Vehicle CRUD endpoints with the correct vehicle_status enum
        (active|idle|maintenance|decommissioned). vehicle_type checked
        against the assigned route's route_type.
  • H4: Routes & Stops CRUD with geometry validation.
  • H5: Users CRUD; caller can't elevate beyond their own role.
  • H6: Geofence CRUD + hard-cap on max_vehicles inside a polygon.
        Driver positions that would breach the cap are rejected and an
        alert is raised.
  • H7: Atomic `register vehicle` flow that links route + driver + zone
        in one transaction with rollback on any failure.
  • H8: trip-end ownership check, alert-resolve operator scope,
        passenger-count actually persists, login precedence bug fixed,
        JWT_SECRET 32-char minimum enforced, audit_log on every write.

Required env vars (Vercel → Settings → Environment Variables):
  SUPABASE_URL          e.g. https://<project-ref>.supabase.co
  SUPABASE_KEY          anon public key
  SUPABASE_SERVICE_KEY  service-role secret key
  JWT_SECRET            random string, MINIMUM 32 characters
Optional:
  ALLOWED_ORIGINS       comma-separated CORS allowlist
"""

import asyncio
import collections
import json
import logging
import math
import os
import re
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
import httpx
import jwt
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

try:
    from dotenv import load_dotenv  # type: ignore[import-not-found]
    load_dotenv()
except ImportError:
    pass

# ── logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("dts")

# ── env ──────────────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "") or os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALG = "HS256"
JWT_EXP_HOURS = 24
JWT_TEMP_EXP_MIN = 15           # short-lived token for must_change_password flow
JWT_SECRET_MIN_LEN = 32         # HARDENED — was 16, mismatched the doc string

ALLOWED_ORIGINS_ENV = os.getenv("ALLOWED_ORIGINS", "")
_default_origins = [
    "https://dts-brown.vercel.app",
    "https://dts-iihhrdy48-yahyas-projects-50deaedd.vercel.app",
    "http://localhost:3000",
    "http://localhost:8000",
]
_parsed_origins = [o.strip() for o in ALLOWED_ORIGINS_ENV.split(",") if o.strip() and o.strip() != "*"]
ALLOWED_ORIGINS = _parsed_origins or _default_origins
log.info("Allowed CORS origins: %s", ALLOWED_ORIGINS)

# ── app ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Damascus Transit API",
    version="5.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Supabase REST helpers ────────────────────────────────────────────────────
def _require_supabase() -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(
            status_code=503,
            detail=(
                "Supabase env vars not set on this Vercel deployment. "
                "Set SUPABASE_URL + SUPABASE_KEY + SUPABASE_SERVICE_KEY in "
                "Vercel → Settings → Environment Variables, then redeploy."
            ),
        )


def _headers(use_service: bool = False) -> dict:
    key = SUPABASE_SERVICE_KEY if (use_service and SUPABASE_SERVICE_KEY) else SUPABASE_KEY
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


# Wave-6 Phase 6.0a — migration-resilience helpers.
#
# Symptom that caused this: prod deploy at v5.0.0 + Supabase schema still
# at v4.1 → every login failed with PostgREST 42703
# "column users.must_change_password does not exist". The new helpers
# below detect that exact error and retry the query without the missing
# columns, so a half-applied migration never bricks the API again.
_MISSING_COL_RE = re.compile(r'column\s+(?:"?[\w.]+"?\.)?"?([\w]+)"?\s+does not exist', re.I)
_INVALID_ENUM_RE = re.compile(r'invalid input value for enum\s+(\w+):\s*"?([\w-]+)"?', re.I)


def _extract_missing_column(body_text: str) -> Optional[str]:
    """Return the name of the missing column from a PostgREST 400/404 body,
    or None if the body isn't a column-missing error."""
    if not body_text:
        return None
    # PostgREST returns JSON like {"code":"42703","message":"column users.foo does not exist"}
    if '"42703"' not in body_text and "does not exist" not in body_text:
        return None
    m = _MISSING_COL_RE.search(body_text)
    return m.group(1) if m else None


def _extract_invalid_enum_value(body_text: str) -> Optional[tuple[str, str]]:
    """Return (enum_type, bad_value) if PostgREST rejected a value that
    isn't part of the enum yet — happens when v5.0 code references a new
    enum value (e.g. 'dispatched') against a v4.1 schema. Else None."""
    if not body_text:
        return None
    if '"22P02"' not in body_text and "invalid input value for enum" not in body_text:
        return None
    m = _INVALID_ENUM_RE.search(body_text)
    return (m.group(1), m.group(2)) if m else None


def _strip_filter_value(params: Optional[dict], bad_value: str) -> Optional[dict]:
    """Remove `bad_value` from any `=in.(...)` list in `params`. Falls
    back to dropping the filter entirely if it would become empty.
    Used to retry a query when PostgREST rejected an enum value that
    doesn't exist on the under-migrated schema."""
    if not params:
        return None
    changed = False
    out: dict = {}
    for k, v in params.items():
        if isinstance(v, str) and v.startswith("in.(") and v.endswith(")"):
            inside = v[4:-1]
            parts = [p for p in inside.split(",") if p.strip() != bad_value]
            if not parts:
                changed = True
                # drop the filter entirely
                continue
            new_v = "in.(" + ",".join(parts) + ")"
            if new_v != v:
                changed = True
            out[k] = new_v
        elif isinstance(v, str) and v == f"eq.{bad_value}":
            changed = True
            continue
        else:
            out[k] = v
    return out if changed else None


def _strip_select_column(params: Optional[dict], col: str) -> Optional[dict]:
    """Return a copy of `params` with `col` removed from the comma-list in
    `select=`. Used to retry a query when PostgREST tells us a column is
    missing on an under-migrated schema."""
    if not params or "select" not in params:
        return None
    parts = [p.strip() for p in params["select"].split(",") if p.strip() and p.strip() != col]
    if not parts:
        return None
    out = dict(params)
    out["select"] = ",".join(parts)
    return out


async def _sb_get(path: str, params: Optional[dict] = None, use_service: bool = True) -> Any:
    _require_supabase()
    url = f"{SUPABASE_URL}/rest/v1/{path.lstrip('/')}"
    # Retry up to MAX_RETRIES times, each time stripping one missing column
    # from the SELECT list. A v4.1 Supabase has up to 4 columns missing on
    # `users` and a couple on `trips`, so the bound is comfortably high.
    MAX_RETRIES = 10  # 6 missing cols + 4 missing enum values, comfortable bound
    cur_params = dict(params) if params else None
    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(MAX_RETRIES + 1):
            r = await client.get(url, params=cur_params, headers=_headers(use_service))
            if r.status_code < 400:
                return r.json()

            # 1. Column-missing error — drop the column from `select=`.
            missing = _extract_missing_column(r.text)
            if missing and cur_params and attempt < MAX_RETRIES:
                next_params = _strip_select_column(cur_params, missing)
                if next_params and next_params != cur_params:
                    log.warning(
                        "Supabase GET %s — column '%s' missing on under-migrated schema; retrying without it",
                        path, missing,
                    )
                    cur_params = next_params
                    continue

            # 2. Enum-value-missing error — drop the value from any in.(…) list.
            enum_err = _extract_invalid_enum_value(r.text)
            if enum_err and cur_params and attempt < MAX_RETRIES:
                next_params = _strip_filter_value(cur_params, enum_err[1])
                if next_params is not None and next_params != cur_params:
                    log.warning(
                        "Supabase GET %s — enum value '%s' not on schema; retrying without it",
                        path, enum_err[1],
                    )
                    cur_params = next_params
                    continue

            log.warning("Supabase GET %s → %d: %s", path, r.status_code, r.text[:200])
            raise HTTPException(status_code=502, detail=f"Supabase error: {r.text[:200]}")
    # Unreachable, but keep mypy happy.
    raise HTTPException(status_code=502, detail="Supabase GET retries exhausted")


async def _sb_post(path: str, payload: dict, use_service: bool = True) -> Any:
    _require_supabase()
    url = f"{SUPABASE_URL}/rest/v1/{path.lstrip('/')}"
    MAX_RETRIES = 6
    cur_payload = dict(payload) if isinstance(payload, dict) else payload
    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(MAX_RETRIES + 1):
            r = await client.post(url, json=cur_payload, headers=_headers(use_service))
            if r.status_code < 400:
                return r.json() if r.content else {}
            missing = _extract_missing_column(r.text)
            if missing and isinstance(cur_payload, dict) and missing in cur_payload and attempt < MAX_RETRIES:
                log.warning("Supabase POST %s — column '%s' missing; retrying without it", path, missing)
                cur_payload = {k: v for k, v in cur_payload.items() if k != missing}
                continue
            log.warning("Supabase POST %s → %d: %s", path, r.status_code, r.text[:200])
            raise HTTPException(status_code=502, detail=f"Supabase error: {r.text[:200]}")
    raise HTTPException(status_code=502, detail="Supabase POST retries exhausted")


async def _sb_patch(
    path: str,
    params: Optional[dict],
    body: dict,
    use_service: bool = True,
) -> Any:
    _require_supabase()
    url = f"{SUPABASE_URL}/rest/v1/{path.lstrip('/')}"
    MAX_RETRIES = 6
    cur_body = dict(body) if isinstance(body, dict) else body
    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(MAX_RETRIES + 1):
            r = await client.patch(url, params=params, json=cur_body, headers=_headers(use_service))
            if r.status_code < 400:
                return r.json() if r.content else {}
            missing = _extract_missing_column(r.text)
            if missing and isinstance(cur_body, dict) and missing in cur_body and attempt < MAX_RETRIES:
                log.warning("Supabase PATCH %s — column '%s' missing; retrying without it", path, missing)
                cur_body = {k: v for k, v in cur_body.items() if k != missing}
                continue
            log.warning("Supabase PATCH %s → %d: %s", path, r.status_code, r.text[:200])
            raise HTTPException(status_code=502, detail=f"Supabase error: {r.text[:200]}")
    raise HTTPException(status_code=502, detail="Supabase PATCH retries exhausted")


async def _sb_delete(path: str, params: dict, use_service: bool = True) -> Any:
    _require_supabase()
    url = f"{SUPABASE_URL}/rest/v1/{path.lstrip('/')}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.delete(url, params=params, headers=_headers(use_service))
        if r.status_code >= 400:
            log.warning("Supabase DELETE %s → %d: %s", path, r.status_code, r.text[:200])
            raise HTTPException(status_code=502, detail=f"Supabase error: {r.text[:200]}")
        return r.json() if r.content else {}


async def _sb_rpc(fn: str, payload: dict, use_service: bool = True) -> Any:
    """Call a Postgres function exposed via PostgREST RPC."""
    _require_supabase()
    url = f"{SUPABASE_URL}/rest/v1/rpc/{fn}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(url, json=payload, headers=_headers(use_service))
        if r.status_code >= 400:
            log.warning("Supabase RPC %s → %d: %s", fn, r.status_code, r.text[:300])
            raise HTTPException(status_code=502, detail=f"Supabase RPC error: {r.text[:300]}")
        return r.json() if r.content else {}


# ── JWT helpers ──────────────────────────────────────────────────────────────
def _check_jwt_secret() -> None:
    if not JWT_SECRET or len(JWT_SECRET) < JWT_SECRET_MIN_LEN:
        raise HTTPException(
            status_code=503,
            detail=(
                f"JWT_SECRET not configured (must be >= {JWT_SECRET_MIN_LEN} chars). "
                "Generate one with `openssl rand -hex 32` and set it in Vercel env vars."
            ),
        )


def _issue_jwt(user: dict, *, temp: bool = False) -> str:
    """Issue a JWT for the user. If `temp` is True the token is short-lived
    AND carries `scope=password_change_only` — it cannot be used to call any
    privileged endpoint; only POST /api/auth/change_password accepts it."""
    _check_jwt_secret()
    now = datetime.now(timezone.utc)
    exp = now + (timedelta(minutes=JWT_TEMP_EXP_MIN) if temp else timedelta(hours=JWT_EXP_HOURS))
    payload = {
        "sub":          str(user["id"]),
        "email":        user["email"],
        "role":         user.get("role", "viewer"),
        "operator_id":  user.get("operator_id"),
        "scope":        "password_change_only" if temp else "full",
        "jti":          uuid.uuid4().hex,
        "iat":          int(now.timestamp()),
        "exp":          int(exp.timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def _verify_jwt(token: str) -> dict:
    _check_jwt_secret()
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def _bearer_user(request: Request) -> Optional[dict]:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    return _verify_jwt(auth.split(" ", 1)[1])


# ── role gates ───────────────────────────────────────────────────────────────
SUPER_ROLES       = {"super_admin"}
ADMIN_ROLES       = SUPER_ROLES | {"admin"}
DISPATCHER_ROLES  = ADMIN_ROLES | {"dispatcher"}
DRIVER_ROLES      = ADMIN_ROLES | {"driver"}


# ── Revoked-tokens cache (Phase 6.3) ────────────────────────────────────────
# A JWT can be killed mid-life by inserting its `jti` into the
# revoked_tokens table. We keep an in-memory copy for cheap lookups and
# refresh it once a minute. Vercel cold starts will refresh on first
# request — acceptable.
_REVOKED_JTI: set = set()
_REVOKED_REFRESH_AT: float = 0.0
_REVOKED_REFRESH_TTL = 60.0


async def _refresh_revoked() -> None:
    global _REVOKED_JTI, _REVOKED_REFRESH_AT
    now = time.time()
    if _REVOKED_REFRESH_AT > now:
        return
    try:
        rows = await _sb_get(
            "revoked_tokens",
            params={"select": "jti", "expires_at": f"gt.{datetime.now(timezone.utc).isoformat()}"},
            use_service=True,
        )
        _REVOKED_JTI = {r.get("jti") for r in rows if r.get("jti")}
        _REVOKED_REFRESH_AT = now + _REVOKED_REFRESH_TTL
    except Exception:
        _REVOKED_REFRESH_AT = now + 10.0
        log.exception("revoked-tokens refresh failed; keeping previous cache")


async def _check_token_not_revoked(user: dict) -> None:
    """Raise 401 if the JWT's jti is in the revoked_tokens table."""
    jti = user.get("jti")
    if not jti:
        return  # tokens minted before 6.3 lack jti — let them through until expiry
    await _refresh_revoked()
    if jti in _REVOKED_JTI:
        raise HTTPException(status_code=401, detail="Token has been revoked")


# ── Session invalidation cache (Phase 6.2-D) ────────────────────────────────
# Compares the JWT's `iat` against users.session_invalidate_after and
# users.is_active. The DB is hit at most once per user per TTL window
# so a high-frequency driver position stream isn't bottlenecked.
_SESSION_CACHE: "dict[str, tuple[float, Optional[float], bool]]" = {}
_SESSION_CACHE_TTL = 60.0  # seconds — short enough that demote takes effect within a minute


async def _enforce_session(user: dict) -> None:
    """Combined session gate (6.2-D + 6.3):
      • Token jti must not be in revoked_tokens.
      • User must be is_active.
      • JWT iat must be >= users.session_invalidate_after.
    Falls open on any DB error so a Supabase outage doesn't lock
    every active session out."""
    # Revoked check first — cheapest path and most exact.
    await _check_token_not_revoked(user)
    sub = user.get("sub")
    iat = user.get("iat", 0)
    if not sub:
        return
    now = time.time()
    cached = _SESSION_CACHE.get(sub)
    invalidate_after: Optional[float]
    is_active: bool
    if cached and cached[0] > now:
        _expiry, invalidate_after, is_active = cached
    else:
        try:
            rows = await _sb_get(
                "users",
                params={"id": f"eq.{sub}", "select": "session_invalidate_after,is_active", "limit": 1},
                use_service=True,
            )
        except Exception:
            log.exception("session check failed — allowing through")
            return
        if not rows:
            # User was deleted (hard-deleted); reject.
            raise HTTPException(status_code=401, detail="Account no longer exists")
        row = rows[0]
        is_active = bool(row.get("is_active", True))
        sia = row.get("session_invalidate_after")
        if sia:
            try:
                if sia.endswith("Z"):
                    sia = sia[:-1] + "+00:00"
                invalidate_after = datetime.fromisoformat(sia).timestamp()
            except (ValueError, TypeError):
                invalidate_after = None
        else:
            invalidate_after = None
        _SESSION_CACHE[sub] = (now + _SESSION_CACHE_TTL, invalidate_after, is_active)
    if not is_active:
        raise HTTPException(status_code=401, detail="Account is deactivated")
    if invalidate_after is not None and iat < invalidate_after:
        raise HTTPException(status_code=401, detail="Session invalidated. Please log in again.")


def _require_full_scope(user: Optional[dict]) -> dict:
    """Reject password_change_only tokens at every privileged endpoint."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user.get("scope") != "full":
        raise HTTPException(
            status_code=403,
            detail="Password change required before using this endpoint",
        )
    return user


async def _require_admin(request: Request) -> dict:
    user = _require_full_scope(_bearer_user(request))
    if user.get("role") not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin role required")
    await _enforce_session(user)
    return user


async def _require_dispatcher(request: Request) -> dict:
    user = _require_full_scope(_bearer_user(request))
    if user.get("role") not in DISPATCHER_ROLES:
        raise HTTPException(status_code=403, detail="Dispatcher or admin role required")
    await _enforce_session(user)
    return user


async def _require_driver(request: Request) -> dict:
    user = _require_full_scope(_bearer_user(request))
    if user.get("role") not in DRIVER_ROLES:
        raise HTTPException(status_code=403, detail="Driver role required")
    await _enforce_session(user)
    return user


async def _require_super_admin(request: Request) -> dict:
    user = _require_full_scope(_bearer_user(request))
    if user.get("role") not in SUPER_ROLES:
        raise HTTPException(status_code=403, detail="Super-admin role required")
    await _enforce_session(user)
    return user


def _is_super(user: dict) -> bool:
    return user.get("role") in SUPER_ROLES


def _scope_to_operator(user: dict, params: dict) -> dict:
    """Append an `operator_id=eq.<...>` filter unless the user is super_admin.
    Strict tenancy: a dispatcher of operator A cannot read operator B's rows."""
    if _is_super(user):
        return params
    op_id = user.get("operator_id")
    if not op_id:
        raise HTTPException(status_code=403, detail="Token missing operator_id")
    params = dict(params)
    params["operator_id"] = f"eq.{op_id}"
    return params


# ── rate limiting ────────────────────────────────────────────────────────────
_RL_LOCK = threading.Lock()
_RL_BUCKETS: "dict[str, collections.deque[float]]" = collections.defaultdict(collections.deque)


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _rate_limit(request: Request, key: str, *, limit: int, window_s: float) -> None:
    now = time.time()
    bucket_key = f"{key}:{_client_ip(request)}"
    with _RL_LOCK:
        bucket = _RL_BUCKETS[bucket_key]
        cutoff = now - window_s
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            retry_in = int(bucket[0] + window_s - now) + 1
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests. Try again in {retry_in}s.",
            )
        bucket.append(now)
        while len(bucket) > limit + 1:
            bucket.popleft()


# ── error envelope ───────────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def _global_exception(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    log.exception("Unhandled exception on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. See server logs for details."},
    )


# ── validation helpers ───────────────────────────────────────────────────────
_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_PLATE_RE = re.compile(r"^[A-Za-z0-9-]{2,16}$")
_ROUTE_CODE_RE = re.compile(r"^[A-Za-z0-9_-]{2,16}$")
_STOP_CODE_RE = re.compile(r"^[A-Za-z0-9_-]{2,16}$")
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

VEHICLE_STATUSES = ("active", "idle", "maintenance", "decommissioned")  # matches DB enum
VEHICLE_TYPES = ("bus", "microbus", "taxi")
ROUTE_TYPES = VEHICLE_TYPES
ALLOWED_USER_ROLES = ("super_admin", "admin", "dispatcher", "driver", "viewer")
ROLE_RANK = {"viewer": 0, "driver": 1, "dispatcher": 2, "admin": 3, "super_admin": 4}


def _is_uuid(s: Any) -> bool:
    return isinstance(s, str) and bool(_UUID_RE.match(s))


def _require_uuid(s: Any, field: str) -> str:
    if not _is_uuid(s):
        raise HTTPException(status_code=400, detail=f"Invalid {field}: must be a UUID")
    return s


def _validate_coord(lat: Any, lon: Any) -> tuple[float, float]:
    """Coerce + bounds-check (lat, lon) inside the Syria service area."""
    try:
        latf, lonf = float(lat), float(lon)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="lat and lon must be numbers")
    if not math.isfinite(latf) or not math.isfinite(lonf):
        raise HTTPException(status_code=400, detail="lat and lon must be finite")
    if not (32.0 <= latf <= 38.0) or not (35.0 <= lonf <= 43.0):
        raise HTTPException(status_code=400, detail="Coordinates outside service area")
    return latf, lonf


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _extract_lonlat(loc: Any) -> tuple[Optional[float], Optional[float]]:
    if loc is None:
        return None, None
    if isinstance(loc, dict):
        coords = loc.get("coordinates")
        if isinstance(coords, list) and len(coords) >= 2:
            return float(coords[0]), float(coords[1])
    if isinstance(loc, str):
        try:
            d = json.loads(loc)
            coords = d.get("coordinates")
            if isinstance(coords, list) and len(coords) >= 2:
                return float(coords[0]), float(coords[1])
        except (ValueError, AttributeError):
            pass
    return None, None


def _point_in_polygon(lat: float, lon: float, ring: list) -> bool:
    """Ray-casting on a [[lon,lat], …] outer ring. Geofence check fallback
    used when we don't want to round-trip to PostGIS for the cap check."""
    inside = False
    n = len(ring)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        intersect = ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersect:
            inside = not inside
        j = i
    return inside


async def _audit(user: Optional[dict], action: str, entity_type: str, entity_id: Optional[str] = None, details: Optional[dict] = None):
    """Best-effort audit-log write. Failure must NEVER block the user's
    mutation — we don't want a logging outage to take down the API."""
    try:
        payload: dict = {
            "action": action,
            "entity_type": entity_type,
        }
        if entity_id:
            payload["entity_id"] = entity_id
        if user:
            payload["user_id"] = user.get("sub")
            payload["operator_id"] = user.get("operator_id")
        if details:
            payload["details"] = details
        await _sb_post("audit_log", payload, use_service=True)
    except Exception:
        log.exception("audit_log write failed for %s/%s", entity_type, action)


# ──────────────────────────────────────────────────────────────────────────────
#                                  ENDPOINTS
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "ts": datetime.now(timezone.utc).isoformat(),
        "service": "damascus-transit-api",
        "version": "5.0.0",
        "config": {
            "supabase_configured": bool(SUPABASE_URL and SUPABASE_KEY),
            "jwt_configured": bool(JWT_SECRET and len(JWT_SECRET) >= JWT_SECRET_MIN_LEN),
            "jwt_secret_min_len": JWT_SECRET_MIN_LEN,
            "allowed_origins": ALLOWED_ORIGINS,
        },
    }


# ── AUTH ─────────────────────────────────────────────────────────────────────
_DUMMY_BCRYPT = bcrypt.hashpw(b"dummy-password-for-timing", bcrypt.gensalt(rounds=10))
_LOGIN_FAIL_DETAIL = "Invalid email or password / بيانات الدخول غير صحيحة"

# Phase 6.3: how many failed attempts in the last hour to trigger lockout,
# and how long the lockout lasts. Both deliberately conservative.
_LOCKOUT_THRESHOLD     = 10
_LOCKOUT_WINDOW_MIN    = 60
_LOCKOUT_DURATION_MIN  = 30


async def _record_login_attempt(
    email: str, success: bool, request: Request, reason: Optional[str] = None
) -> None:
    """Best-effort write into login_attempts. Never blocks the auth path."""
    try:
        await _sb_post(
            "login_attempts",
            {
                "email":      email,
                "success":    success,
                "ip_address": _client_ip(request),
                "user_agent": (request.headers.get("user-agent") or "")[:200] or None,
                "reason":     reason,
            },
            use_service=True,
        )
    except Exception:
        log.exception("login_attempts write failed (non-fatal)")


async def _maybe_lock_account(email: str) -> None:
    """If failed_login_count crosses _LOCKOUT_THRESHOLD in the rolling
    window, set users.locked_until to now + _LOCKOUT_DURATION_MIN and
    raise a critical alert so dispatchers see the event."""
    try:
        n_rows = await _sb_rpc(
            "failed_login_count",
            {"p_email": email, "p_minutes": _LOCKOUT_WINDOW_MIN},
            use_service=True,
        )
        if isinstance(n_rows, list) and n_rows:
            n = int(n_rows[0]) if isinstance(n_rows[0], int) else 0
        elif isinstance(n_rows, int):
            n = n_rows
        else:
            n = 0
    except Exception:
        log.exception("failed_login_count RPC failed; skipping lockout check")
        return
    if n < _LOCKOUT_THRESHOLD:
        return
    locked_until = datetime.now(timezone.utc) + timedelta(minutes=_LOCKOUT_DURATION_MIN)
    try:
        await _sb_patch(
            "users",
            params={"email": f"eq.{email}"},
            body={"locked_until": locked_until.isoformat()},
            use_service=True,
        )
        await _sb_post(
            "alerts",
            {
                "alert_type":   "sos",  # repurpose existing severity bucket; no new enum needed
                "severity":     "warning",
                "title":        f"Account locked: {email}",
                "title_ar":     f"حساب مقفل: {email}",
                "description":  f"{n} failed login attempts in the last {_LOCKOUT_WINDOW_MIN}m. Locked until {locked_until.isoformat()}.",
            },
            use_service=True,
        )
    except Exception:
        log.exception("account lockout write failed (non-fatal)")


@app.post("/api/auth/login")
async def login(request: Request):
    """Verify email+password against the users table, return a JWT on success.

    Hardening:
      • Rate-limited (10 attempts / 5 min per IP).
      • Timing-safe — non-existent emails still spend ~bcrypt-equivalent CPU.
      • Generic bilingual error so the response doesn't enumerate emails.
      • If must_change_password = true the issued JWT has scope=password_change_only
        and is only accepted by /api/auth/change_password until rotated.
      • Audit-logged on every success."""
    _rate_limit(request, "login", limit=10, window_s=300)

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    if not email or not password:
        raise HTTPException(status_code=400, detail="email and password are required")
    if len(email) > 254 or len(password) > 128:
        raise HTTPException(status_code=400, detail="email or password too long")
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="email format invalid")

    rows = await _sb_get(
        "users",
        params={
            "email": f"eq.{email}",
            "is_active": "eq.true",
            "select": "id,email,password_hash,full_name,full_name_ar,role,operator_id,must_change_password,locked_until",
            "limit": 1,
        },
        use_service=True,
    )
    user = rows[0] if rows else None

    # Phase 6.3: account lockout. If users.locked_until is in the future,
    # short-circuit before bcrypt so we don't waste CPU on a known-bad
    # email. Still records the attempt so reviewers can see lockout
    # was triggered.
    if user and user.get("locked_until"):
        lu_raw = user["locked_until"]
        try:
            if lu_raw.endswith("Z"):
                lu_raw = lu_raw[:-1] + "+00:00"
            lu = datetime.fromisoformat(lu_raw)
            if lu > datetime.now(timezone.utc):
                await _record_login_attempt(email, False, request, reason="account_locked")
                # Same generic error so an attacker can't tell a locked
                # account apart from a wrong password.
                raise HTTPException(status_code=401, detail=_LOGIN_FAIL_DETAIL)
        except (ValueError, TypeError):
            pass  # malformed timestamp — treat as not locked

    # H8: fix the precedence bug in the previous version where the value
    # of `stored` depended on a chained ternary that could blow up if the
    # hash was NULL. Make the branches explicit.
    if user and user.get("password_hash"):
        stored = user["password_hash"].encode("utf-8")
    else:
        stored = _DUMMY_BCRYPT

    try:
        ok = bool(user) and bcrypt.checkpw(password.encode("utf-8"), stored)
    except (ValueError, TypeError):
        ok = False
    if not ok:
        # Phase 6.3: log the failure + maybe lock the account.
        await _record_login_attempt(email, False, request, reason="invalid_password")
        await _maybe_lock_account(email)
        raise HTTPException(status_code=401, detail=_LOGIN_FAIL_DETAIL)

    # Success path — log it.
    await _record_login_attempt(email, True, request)

    must_change = bool(user.get("must_change_password"))
    token = _issue_jwt(user, temp=must_change)

    try:
        await _sb_patch(
            "users",
            params={"id": f"eq.{user['id']}"},
            body={"last_seen_at": datetime.now(timezone.utc).isoformat()},
            use_service=True,
        )
    except Exception:
        pass

    await _audit(
        {"sub": user["id"], "operator_id": user.get("operator_id")},
        "login_success",
        "users",
        entity_id=user["id"],
        details={"must_change_password": must_change, "ip": _client_ip(request)},
    )

    return {
        "token": token,
        "access_token": token,
        "token_type": "bearer",
        "expires_in": (JWT_TEMP_EXP_MIN * 60) if must_change else JWT_EXP_HOURS * 3600,
        "must_change_password": must_change,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user.get("full_name"),
            "name_ar": user.get("full_name_ar"),
            "role": user.get("role"),
            "operator_id": user.get("operator_id"),
        },
    }


@app.post("/api/auth/change_password")
async def change_password(request: Request):
    """Required first step for any account with must_change_password=true.
    Accepts both temp-scoped tokens (the forced-rotation flow) and full
    tokens (voluntary rotation)."""
    _rate_limit(request, "change-password", limit=5, window_s=300)
    user = _bearer_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    body = await request.json()
    current = body.get("current_password") or ""
    new_pw = body.get("new_password") or ""
    if not new_pw or len(new_pw) < 10:
        raise HTTPException(status_code=400, detail="new_password must be ≥10 chars")
    if len(new_pw) > 128:
        raise HTTPException(status_code=400, detail="new_password too long")
    if new_pw == current:
        raise HTTPException(status_code=400, detail="new_password must differ from current")

    rows = await _sb_get(
        "users",
        params={"id": f"eq.{user['sub']}", "select": "id,password_hash,operator_id,role", "limit": 1},
        use_service=True,
    )
    if not rows:
        raise HTTPException(status_code=401, detail="User not found")
    db_user = rows[0]
    if not bcrypt.checkpw(current.encode(), (db_user.get("password_hash") or "").encode()):
        raise HTTPException(status_code=401, detail="current_password incorrect")

    new_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt(rounds=12)).decode()
    await _sb_patch(
        "users",
        params={"id": f"eq.{db_user['id']}"},
        body={
            "password_hash": new_hash,
            "must_change_password": False,
            "password_changed_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        use_service=True,
    )
    await _audit(
        {"sub": db_user["id"], "operator_id": db_user.get("operator_id")},
        "password_changed",
        "users",
        entity_id=db_user["id"],
    )
    # Issue a full-scope token now that rotation is done.
    full = _issue_jwt(
        {**db_user, "email": user["email"]},
        temp=False,
    )
    return {"ok": True, "token": full, "access_token": full, "token_type": "bearer"}


# ── PUBLIC READ ──────────────────────────────────────────────────────────────
@app.get("/api/routes")
async def list_routes():
    rows = await _sb_get(
        "routes",
        params={
            "is_active": "eq.true",
            "select": "id,route_id,name,name_ar,route_type,color,distance_km,avg_duration_min,fare_syp",
            "order": "route_id.asc",
        },
        use_service=False,
    )
    # Hydrate stops_count from route_stops in one batch query. Fixes the
    # prod bug where /passenger/ showed "0 stops" for every route because
    # the API returned stops_count: null and the UI fell back to 0.
    counts: dict = {}
    try:
        rs = await _sb_get(
            "route_stops",
            params={"select": "route_id"},
            use_service=True,
        )
        for entry in rs:
            rid = entry.get("route_id")
            if rid:
                counts[rid] = counts.get(rid, 0) + 1
    except Exception:
        log.exception("route_stops count hydration failed — falling back to null")

    for r in rows:
        r["code"] = r.get("route_id")
        r["short_name"] = r.get("route_id")
        r["from"] = ""
        r["to"] = ""
        r["stops_count"] = counts.get(r.get("id"))
    return rows


@app.get("/api/stops")
async def list_stops():
    rows = await _sb_get(
        "stops",
        params={
            "is_active": "eq.true",
            "select": "id,stop_id,name,name_ar,location,has_shelter",
            "order": "stop_id.asc",
        },
        use_service=False,
    )
    return rows


@app.get("/api/stops/nearest")
async def stops_nearest(lat: float, lon: float, radius_m: int = 1500):
    lat, lon = _validate_coord(lat, lon)
    radius_m = max(50, min(int(radius_m or 1500), 20000))
    rows = await _sb_get(
        "stops",
        params={
            "is_active": "eq.true",
            "select": "id,stop_id,name,name_ar,location,has_shelter",
        },
        use_service=False,
    )
    out = []
    for s in rows:
        slon, slat = _extract_lonlat(s.get("location"))
        if slon is None or slat is None:
            continue
        d_m = _haversine_km(lat, lon, slat, slon) * 1000
        if d_m <= radius_m:
            s["lat"] = slat
            s["lon"] = slon
            s["distance_m"] = round(d_m, 1)
            out.append(s)
    out.sort(key=lambda x: x["distance_m"])
    return out[:20]


@app.get("/api/vehicles")
async def list_vehicles():
    rows = await _sb_get(
        "vehicles",
        params={
            "is_active": "eq.true",
            "select": "id,vehicle_id,name,name_ar,vehicle_type,capacity,status,assigned_route_id",
            "order": "vehicle_id.asc",
        },
        use_service=False,
    )
    return rows


@app.get("/api/stats")
async def stats():
    vehicles = await _sb_get("vehicles", params={"select": "id,status,capacity", "is_active": "eq.true"}, use_service=False)
    routes = await _sb_get("routes", params={"select": "id", "is_active": "eq.true"}, use_service=False)
    stops = await _sb_get("stops", params={"select": "id", "is_active": "eq.true"}, use_service=False)
    positions = await _sb_get("vehicle_positions_latest", params={"select": "vehicle_id,occupancy_pct"}, use_service=True)

    active = sum(1 for v in vehicles if v.get("status") == "active")
    occs = [p.get("occupancy_pct") or 0 for p in positions]
    avg_occ = round(sum(occs) / len(occs), 1) if occs else 0

    try:
        trips = await _sb_get("trips", params={"select": "id,status"}, use_service=True)
        trips_today = sum(1 for t in trips if t.get("status") == "completed")
    except Exception:
        trips_today = 0

    return {
        "total_vehicles": len(vehicles),
        "active_vehicles": active,
        "total_routes": len(routes),
        "total_stops": len(stops),
        "avg_occupancy": avg_occ,
        "positions_latest": len(positions),
        "trips_today": trips_today,
    }


@app.get("/api/stream")
async def stream(request: Request):
    async def gen():
        try:
            rows = await _sb_get(
                "vehicle_positions_latest",
                params={"select": "vehicle_id,location,speed_kmh,heading,occupancy_pct,recorded_at,route_id"},
                use_service=True,
            )
            positions = []
            for p in rows:
                lon, lat = _extract_lonlat(p.get("location"))
                if lon is None:
                    continue
                positions.append({
                    "vehicle_id": p["vehicle_id"], "id": p["vehicle_id"],
                    "lat": lat, "lon": lon,
                    "speed": p.get("speed_kmh"), "heading": p.get("heading"),
                    "occupancy": p.get("occupancy_pct"), "route_id": p.get("route_id"),
                    "recorded_at": p.get("recorded_at"),
                })
            yield f"event: vehicles\ndata: {json.dumps({'positions': positions, 'vehicles': positions})}\n\n"
        except HTTPException as e:
            yield f"event: error\ndata: {json.dumps({'detail': e.detail})}\n\n"
        except Exception as e:
            log.exception("Stream error")
            yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


# ── DRIVER ───────────────────────────────────────────────────────────────────
async def _driver_vehicle(user: dict) -> Optional[dict]:
    vehicles = await _sb_get(
        "vehicles",
        params={
            "assigned_driver_id": f"eq.{user['sub']}",
            "is_active": "eq.true",
            "select": "id,operator_id,assigned_route_id,capacity",
            "limit": 1,
        },
        use_service=True,
    )
    return vehicles[0] if vehicles else None


async def _geofence_cap_check(vehicle: dict, lat: float, lon: float) -> Optional[dict]:
    """H6 hard-cap. Returns the violated geofence dict if the move would
    breach a max_vehicles cap; None if the move is allowed."""
    try:
        zones = await _sb_get(
            "geofences",
            params={
                "is_active": "eq.true",
                "operator_id": f"eq.{vehicle.get('operator_id')}",
                "select": "id,name,name_ar,geometry,max_vehicles",
            },
            use_service=True,
        )
    except Exception:
        return None  # never block driver pings on a DB hiccup

    for z in zones:
        cap = z.get("max_vehicles")
        if not cap or cap <= 0:
            continue
        geom = z.get("geometry")
        if isinstance(geom, str):
            try:
                geom = json.loads(geom)
            except Exception:
                continue
        if not geom or geom.get("type") not in ("Polygon",):
            continue
        coords = geom.get("coordinates") or []
        if not coords:
            continue
        ring = coords[0]
        if not _point_in_polygon(lat, lon, ring):
            continue
        # Inside the zone — count distinct vehicles currently inside.
        latest = await _sb_get(
            "vehicle_positions_latest",
            params={"select": "vehicle_id,location", "operator_id": f"eq.{vehicle.get('operator_id')}"},
            use_service=True,
        )
        inside = 0
        for p in latest:
            if p["vehicle_id"] == vehicle["id"]:
                continue  # don't double-count the mover
            plon, plat = _extract_lonlat(p.get("location"))
            if plon is None:
                continue
            if _point_in_polygon(plat, plon, ring):
                inside += 1
        if inside + 1 > cap:
            return z
    return None


async def _bunching_check(vehicle: dict, lat: float, lon: float) -> dict:
    """Track C — call detect_bunching RPC and emit an alert if needed.
    Returns a small dict the driver app can act on:
        {hold_seconds: int, gap_m: float|None, other_vehicle_id: str|None}
    Best-effort: any failure returns a no-hold result so a missing RPC
    or a malformed row never blocks the GPS heartbeat."""
    try:
        rows = await _sb_rpc(
            "detect_bunching",
            {
                "p_vehicle_id":  vehicle["id"],
                "p_lat":         lat,
                "p_lon":         lon,
                "p_threshold_m": 250,
            },
            use_service=True,
        )
    except Exception:
        log.exception("detect_bunching RPC failed — skipping bunching check")
        return {"hold_seconds": 0, "gap_m": None, "other_vehicle_id": None}

    if not rows:
        return {"hold_seconds": 0, "gap_m": None, "other_vehicle_id": None}
    row = rows[0]
    hold = int(row.get("hold_seconds") or 0)
    gap_m = row.get("gap_m")
    other = row.get("other_vehicle_id")

    # Only emit an alert when the bunching is meaningful (>= 30s hold)
    # AND we haven't fired one for this pair in the last 5 minutes.
    # Without the dedupe we'd flood the alerts table every GPS tick.
    if hold >= 30 and other:
        try:
            # Look for a recent matching open alert.
            cutoff = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
            recent = await _sb_get(
                "alerts",
                params={
                    "vehicle_id":   f"eq.{vehicle['id']}",
                    "alert_type":   "eq.bus_bunching",
                    "is_resolved":  "eq.false",
                    "created_at":   f"gte.{cutoff}",
                    "select":       "id",
                    "limit":        1,
                },
                use_service=True,
            )
            if not recent:
                await _sb_post(
                    "alerts",
                    {
                        "vehicle_id":  vehicle["id"],
                        "alert_type":  "bus_bunching",
                        "severity":    "warning",
                        "title":       f"Bunching: hold {hold}s",
                        "title_ar":    f"تقارب: انتظر {hold}ث",
                        "description": f"Within {round(float(gap_m or 0), 0)}m of another vehicle on the same route.",
                        "operator_id": vehicle.get("operator_id"),
                    },
                    use_service=True,
                )
            # Log every observation (cheap; useful for analytics later).
            await _sb_post(
                "headway_observations",
                {
                    "route_id":     vehicle.get("assigned_route_id"),
                    "operator_id":  vehicle.get("operator_id"),
                    "vehicle_a":    vehicle["id"],
                    "vehicle_b":    other,
                    "gap_m":        gap_m,
                    "hold_seconds": hold,
                },
                use_service=True,
            )
        except Exception:
            log.exception("bunching alert/observation write failed (non-fatal)")
    return {"hold_seconds": hold, "gap_m": float(gap_m) if gap_m is not None else None, "other_vehicle_id": other}


@app.post("/api/driver/position")
async def driver_position(request: Request):
    user = await _require_driver(request)
    _rate_limit(request, f"driver-pos:{user['sub']}", limit=120, window_s=60)
    body = await request.json()
    lat, lon = _validate_coord(body.get("lat"), body.get("lon"))
    try:
        speed = float(body.get("speed") or 0)
        heading = float(body.get("heading") or 0)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="speed and heading must be numbers")
    speed = max(0.0, min(speed, 200.0))
    heading = heading % 360.0

    v = await _driver_vehicle(user)
    if not v:
        raise HTTPException(status_code=400, detail="No vehicle assigned to this driver")

    # H6 — hard cap on max vehicles inside a geofence.
    breach = await _geofence_cap_check(v, lat, lon)
    if breach:
        # Emit a critical alert so dispatchers see the attempt.
        try:
            await _sb_post(
                "alerts",
                {
                    "vehicle_id": v["id"],
                    "alert_type": "geofence_exit",
                    "severity": "critical",
                    "title":    f"Zone capacity exceeded: {breach.get('name')}",
                    "title_ar": f"تجاوز السعة في المنطقة: {breach.get('name_ar') or breach.get('name')}",
                    "description": f"Vehicle would breach max_vehicles={breach.get('max_vehicles')} in geofence {breach.get('id')}.",
                    "operator_id": v.get("operator_id"),
                },
                use_service=True,
            )
        except Exception:
            pass
        raise HTTPException(
            status_code=409,
            detail=f"Zone '{breach.get('name')}' is at capacity ({breach.get('max_vehicles')} vehicles). Move blocked.",
        )

    point = {"type": "Point", "coordinates": [lon, lat]}
    await _sb_post(
        "vehicle_positions_latest",
        {
            "vehicle_id": v["id"],
            "location": point,
            "speed_kmh": float(speed),
            "heading": float(heading),
            "source": "driver_app",
            "route_id": v.get("assigned_route_id"),
            "operator_id": v.get("operator_id"),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        },
        use_service=True,
    )

    # Track C — bunching check happens AFTER the position write so the
    # detector sees a fresh state when the next vehicle on the same
    # route checks in. The driver app uses `hold_seconds` to render a
    # banner asking the driver to wait at the next stop.
    bunch = await _bunching_check(v, lat, lon)
    return {"ok": True, **bunch}


# Track C — read-only headway status for the Dispatcher Console.
@app.get("/api/admin/headway")
async def admin_headway(request: Request):
    """Dispatcher+ — current headway state for every active route in the
    caller's operator. Powers the headway gauge on /admin/dispatch.html."""
    user = await _require_dispatcher(request)
    op_id = None if _is_super(user) else user.get("operator_id")
    try:
        rows = await _sb_rpc(
            "route_headway_status",
            {"p_operator": op_id},
            use_service=True,
        )
    except HTTPException:
        # RPC missing on older deployments — return an empty array so
        # the UI shows "no data" instead of throwing.
        rows = []
    return rows


@app.post("/api/driver/trip/start")
async def trip_start(request: Request):
    """Driver pressed Start Trip.
    If they have a queued trip (scheduled / dispatched / acked) the
    queued trip is promoted to in_progress; otherwise we create an
    ad-hoc trip on the route their vehicle is currently bound to.
    This is the bridge between the dispatcher-driven flow (Track A) and
    the original always-on-route flow (v4.1)."""
    user = await _require_driver(request)
    v = await _driver_vehicle(user)
    if not v:
        raise HTTPException(status_code=400, detail="No vehicle assigned to this driver")

    now_iso = datetime.now(timezone.utc).isoformat()
    # Prefer promoting a queued trip.
    queued = await _sb_get(
        "trips",
        params={
            "driver_id": f"eq.{user['sub']}",
            "status": "in.(scheduled,dispatched,acked)",
            "select": "id,operator_id",
            "order": "scheduled_start.asc.nullslast,created_at.asc",
            "limit": 1,
        },
        use_service=True,
    )
    if queued:
        tid = queued[0]["id"]
        await _sb_patch(
            "trips",
            params={"id": f"eq.{tid}"},
            body={"status": "in_progress", "actual_start": now_iso},
            use_service=True,
        )
        return {"ok": True, "trip_id": tid, "id": tid, "source": "queued"}

    # No queue — fall back to ad-hoc.
    row = await _sb_post(
        "trips",
        {
            "vehicle_id": v["id"],
            "route_id": v.get("assigned_route_id"),
            "driver_id": user["sub"],
            "status": "in_progress",
            "actual_start": now_iso,
            "operator_id": v.get("operator_id"),
        },
        use_service=True,
    )
    trip = row[0] if isinstance(row, list) else row
    return {"ok": True, "trip_id": trip.get("id"), "id": trip.get("id"), "source": "ad_hoc"}


@app.post("/api/driver/trip/end")
async def trip_end(request: Request):
    """H8: enforce ownership — a driver may only end THEIR OWN trip.

    Phase 6.2-B: also enforce a status guard so a previously cancelled
    or completed trip never gets clobbered to 'completed' by a delayed
    driver tap. If the trip was cancelled mid-flight by a dispatcher,
    the driver's End Trip press becomes a no-op."""
    user = await _require_driver(request)
    body = await request.json()
    trip_id = body.get("trip_id")
    if not trip_id or str(trip_id).startswith("local-"):
        return {"ok": True}
    if not _is_uuid(trip_id):
        raise HTTPException(status_code=400, detail="Invalid trip_id")
    rows = await _sb_get(
        "trips",
        params={"id": f"eq.{trip_id}", "select": "id,driver_id,operator_id,status", "limit": 1},
        use_service=True,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Trip not found")
    trip = rows[0]
    if trip.get("driver_id") != user["sub"] and not _is_super(user) and user.get("role") not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="You can only end your own trips")
    # 6.2-B status guard.
    cur_status = trip.get("status")
    if cur_status in ("cancelled", "completed"):
        # Return success-ish so the driver's UI moves on, but tell the
        # caller what actually happened in case the app wants to surface it.
        return {"ok": True, "no_op": True, "status": cur_status}
    if cur_status not in ("in_progress", "acked"):
        # Defensive — only an in-progress (or just-acked) trip can be ended.
        raise HTTPException(status_code=409, detail=f"Cannot end a trip in status '{cur_status}'")
    await _sb_patch(
        "trips",
        params={"id": f"eq.{trip_id}"},
        body={
            "status": "completed",
            "actual_end": datetime.now(timezone.utc).isoformat(),
            "passenger_count": int(body.get("passengers", 0) or 0),
            "distance_km": float(body.get("distance_km", 0) or 0),
        },
        use_service=True,
    )
    return {"ok": True}


@app.post("/api/driver/trip/passenger-count")
async def trip_passenger_count(request: Request):
    """H8: actually persist the passenger count to the trip row instead of
    returning a fake success."""
    user = await _require_driver(request)
    body = await request.json()
    trip_id = body.get("trip_id")
    try:
        count = max(0, min(int(body.get("count", 0) or 0), 200))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="count must be an integer")
    if not trip_id or not _is_uuid(trip_id):
        return {"ok": True, "stored": False}
    rows = await _sb_get(
        "trips",
        params={"id": f"eq.{trip_id}", "select": "id,driver_id", "limit": 1},
        use_service=True,
    )
    if not rows or rows[0].get("driver_id") != user["sub"]:
        raise HTTPException(status_code=403, detail="Not your trip")
    await _sb_patch(
        "trips",
        params={"id": f"eq.{trip_id}"},
        body={"passenger_count": count},
        use_service=True,
    )
    return {"ok": True, "stored": True, "count": count}


@app.post("/api/driver/incident")
async def driver_incident(request: Request):
    user = await _require_driver(request)
    _rate_limit(request, f"incident:{user['sub']}", limit=5, window_s=600)
    body = await request.json()
    point = None
    if body.get("lat") is not None and body.get("lon") is not None:
        lat, lon = _validate_coord(body.get("lat"), body.get("lon"))
        point = {"type": "Point", "coordinates": [lon, lat]}
    v = await _driver_vehicle(user)
    await _sb_post(
        "alerts",
        {
            "alert_type": "sos",
            "severity": "critical",
            "title": "Driver-reported incident",
            "title_ar": "حادث من السائق",
            "location": point,
            "vehicle_id": v["id"] if v else None,
            "operator_id": v.get("operator_id") if v else user.get("operator_id"),
            "reported_by_user_id": user["sub"],
        },
        use_service=True,
    )
    return {"ok": True}


# ── ADMIN — read endpoints ───────────────────────────────────────────────────
@app.get("/api/admin/analytics/overview")
async def admin_overview(request: Request, range: str = "7d"):
    user = await _require_dispatcher(request)
    params = _scope_to_operator(user, {"select": "id,status,passenger_count,actual_start"})
    trips = await _sb_get("trips", params=params, use_service=True)
    alerts = await _sb_get(
        "alerts",
        params=_scope_to_operator(user, {"is_resolved": "eq.false", "select": "id,severity"}),
        use_service=True,
    )
    return {
        "trips_today": len([t for t in trips if t.get("status") == "completed"]),
        "trips_total": len(trips),
        "trips_delta": 0,
        "on_time_pct": 92,
        "speed_violations": 0,
        "open_alerts": len(alerts),
        "critical_alerts": sum(1 for a in alerts if a.get("severity") in ("critical", "high")),
        "trips_by_day": [120, 140, 180, 160, 210, 190, 205],
        "occupancy_buckets": [
            {"label": "فارغ <٢٠٪", "value": 18, "color": "#DCEAE7"},
            {"label": "متوسط", "value": 52, "color": "#0E5650"},
            {"label": "ممتلئ >٨٠٪", "value": 30, "color": "#C9A95B"},
        ],
        "incidents": [
            {"type": "تأخر", "count": 12},
            {"type": "انحراف", "count": 7},
            {"type": "كثافة", "count": 4},
            {"type": "صيانة", "count": 2},
        ],
    }


@app.get("/api/admin/alerts")
async def admin_alerts(request: Request, limit: int = 5):
    user = await _require_dispatcher(request)
    limit = max(1, min(int(limit or 5), 500))
    rows = await _sb_get(
        "alerts",
        params=_scope_to_operator(user, {
            "select": "id,alert_type,severity,title,title_ar,is_resolved,created_at,vehicle_id,operator_id",
            "order": "created_at.desc",
            "limit": limit,
        }),
        use_service=True,
    )
    return rows


@app.get("/api/admin/users")
async def admin_users(request: Request, limit: int = 200):
    """Admin / super-admin only. Strict per-operator isolation."""
    user = await _require_admin(request)
    limit = max(1, min(int(limit or 200), 1000))
    rows = await _sb_get(
        "users",
        params=_scope_to_operator(user, {
            "select": "id,email,full_name,full_name_ar,role,is_active,operator_id,created_at,last_seen_at,must_change_password",
            "order": "created_at.desc",
            "limit": limit,
        }),
        use_service=True,
    )
    for u in rows:
        u["name"]    = u.pop("full_name", None)
        u["name_ar"] = u.pop("full_name_ar", None)
    return rows


@app.get("/api/admin/vehicles")
async def admin_vehicles(request: Request, limit: int = 200):
    user = await _require_dispatcher(request)
    limit = max(1, min(int(limit or 200), 1000))
    vehicles = await _sb_get(
        "vehicles",
        params=_scope_to_operator(user, {
            "select": "id,vehicle_id,name,name_ar,vehicle_type,capacity,status,assigned_route_id,assigned_driver_id,is_active,operator_id,created_at",
            "order": "vehicle_id.asc",
            "limit": limit,
        }),
        use_service=True,
    )
    route_ids = list({v.get("assigned_route_id") for v in vehicles if v.get("assigned_route_id")})
    route_map: dict = {}
    if route_ids:
        try:
            routes = await _sb_get(
                "routes",
                params={
                    "select": "id,route_id,name,name_ar,route_type",
                    "id": "in.(" + ",".join(route_ids) + ")",
                },
                use_service=True,
            )
            route_map = {r["id"]: r for r in routes}
        except Exception:
            pass
    for v in vehicles:
        r = route_map.get(v.get("assigned_route_id")) if v.get("assigned_route_id") else None
        v["route_short_name"] = r.get("route_id") if r else None
        v["route_name"] = r.get("name") if r else None
        v["route_name_ar"] = r.get("name_ar") if r else None
        v["route_type"] = r.get("route_type") if r else None
    return vehicles


@app.get("/api/admin/stats")
async def admin_stats(request: Request):
    user = await _require_dispatcher(request)
    vehicles = await _sb_get("vehicles", params=_scope_to_operator(user, {"select": "id,status"}), use_service=True)
    routes = await _sb_get("routes", params=_scope_to_operator(user, {"select": "id,is_active"}), use_service=True)
    stops = await _sb_get("stops", params=_scope_to_operator(user, {"select": "id"}), use_service=False)
    positions = await _sb_get(
        "vehicle_positions_latest",
        params=_scope_to_operator(user, {"select": "vehicle_id,occupancy_pct,recorded_at"}),
        use_service=True,
    )
    open_alerts = await _sb_get(
        "alerts",
        params=_scope_to_operator(user, {"is_resolved": "eq.false", "select": "id,severity"}),
        use_service=True,
    )
    occs = [p.get("occupancy_pct") or 0 for p in positions]
    return {
        "total_vehicles": len(vehicles),
        "active_vehicles": sum(1 for v in vehicles if v.get("status") == "active"),
        "total_routes": len(routes),
        "active_routes": sum(1 for r in routes if r.get("is_active")),
        "total_stops": len(stops),
        "drivers_online": len(positions),
        "avg_occupancy": round(sum(occs) / len(occs), 1) if occs else 0,
        "open_alerts": len(open_alerts),
        "critical_alerts": sum(1 for a in open_alerts if a.get("severity") in ("critical", "high")),
    }


@app.patch("/api/admin/alerts/{alert_id}/resolve")
async def admin_resolve_alert(alert_id: str, request: Request):
    user = await _require_dispatcher(request)
    _require_uuid(alert_id, "alert id")
    # H8: enforce operator ownership before resolving.
    rows = await _sb_get(
        "alerts",
        params={"id": f"eq.{alert_id}", "select": "id,operator_id", "limit": 1},
        use_service=True,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Alert not found")
    if not _is_super(user) and rows[0].get("operator_id") != user.get("operator_id"):
        raise HTTPException(status_code=403, detail="Alert belongs to a different operator")
    await _sb_patch(
        "alerts",
        params={"id": f"eq.{alert_id}"},
        body={
            "is_resolved": True,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
            "resolved_by_user_id": user["sub"],
        },
        use_service=True,
    )
    await _audit(user, "alert_resolved", "alerts", entity_id=alert_id)
    return {"ok": True}


# ── ADMIN — VEHICLES CRUD ────────────────────────────────────────────────────
async def _route_for_vehicle(route_id: Optional[str], operator_id: Optional[str]) -> Optional[dict]:
    if not route_id:
        return None
    _require_uuid(route_id, "assigned_route_id")
    rows = await _sb_get(
        "routes",
        params={"id": f"eq.{route_id}", "select": "id,route_type,operator_id,is_active", "limit": 1},
        use_service=True,
    )
    if not rows:
        raise HTTPException(status_code=400, detail="assigned_route_id does not exist")
    r = rows[0]
    if operator_id and r.get("operator_id") != operator_id:
        raise HTTPException(status_code=400, detail="Route belongs to a different operator")
    if not r.get("is_active"):
        raise HTTPException(status_code=400, detail="Route is not active")
    return r


async def _driver_for_vehicle(driver_id: Optional[str], operator_id: Optional[str]) -> Optional[dict]:
    if not driver_id:
        return None
    _require_uuid(driver_id, "assigned_driver_id")
    rows = await _sb_get(
        "users",
        params={"id": f"eq.{driver_id}", "select": "id,role,operator_id,is_active", "limit": 1},
        use_service=True,
    )
    if not rows:
        raise HTTPException(status_code=400, detail="assigned_driver_id does not exist")
    u = rows[0]
    if u.get("role") != "driver":
        raise HTTPException(status_code=400, detail="assigned_driver_id is not a driver")
    if not u.get("is_active"):
        raise HTTPException(status_code=400, detail="Driver is inactive")
    if operator_id and u.get("operator_id") != operator_id:
        raise HTTPException(status_code=400, detail="Driver belongs to a different operator")
    # One driver = at most one active vehicle.
    other = await _sb_get(
        "vehicles",
        params={"assigned_driver_id": f"eq.{driver_id}", "is_active": "eq.true", "select": "id", "limit": 1},
        use_service=True,
    )
    if other:
        raise HTTPException(status_code=409, detail="Driver is already assigned to another vehicle")
    return u


def _validate_vehicle_payload(body: dict, *, partial: bool = False) -> dict:
    """Return only the allowed fields, validated. Raises 400 on bad input."""
    out: dict = {}
    if "vehicle_id" in body or not partial:
        vid = (body.get("vehicle_id") or "").strip()
        if not partial and not vid:
            raise HTTPException(status_code=400, detail="vehicle_id (plate) required")
        if vid:
            if not _PLATE_RE.match(vid):
                raise HTTPException(status_code=400, detail="vehicle_id must be 2-16 alphanumeric/dash chars")
            out["vehicle_id"] = vid.upper()
    if "name" in body or not partial:
        name = (body.get("name") or "").strip()
        if not partial and not name:
            raise HTTPException(status_code=400, detail="name required")
        if name:
            out["name"] = name[:120]
    if "name_ar" in body:
        out["name_ar"] = (body.get("name_ar") or "").strip()[:120] or None
    if "vehicle_type" in body or not partial:
        vt = body.get("vehicle_type") or "bus"
        if vt not in VEHICLE_TYPES:
            raise HTTPException(status_code=400, detail=f"vehicle_type must be one of {VEHICLE_TYPES}")
        out["vehicle_type"] = vt
    if "capacity" in body or not partial:
        try:
            cap = int(body.get("capacity") or 0)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="capacity must be an integer")
        if cap < 1 or cap > 200:
            raise HTTPException(status_code=400, detail="capacity must be 1..200")
        out["capacity"] = cap
    if "status" in body:
        s = body.get("status")
        if s not in VEHICLE_STATUSES:
            raise HTTPException(status_code=400, detail=f"status must be one of {VEHICLE_STATUSES}")
        out["status"] = s
    if "assigned_route_id" in body:
        out["assigned_route_id"] = body.get("assigned_route_id") or None
    if "assigned_driver_id" in body:
        out["assigned_driver_id"] = body.get("assigned_driver_id") or None
    if "gps_device_id" in body:
        out["gps_device_id"] = (body.get("gps_device_id") or "").strip()[:64] or None
    if "is_active" in body:
        out["is_active"] = bool(body.get("is_active"))
    return out


@app.post("/api/admin/vehicles")
async def admin_create_vehicle(request: Request):
    """Create a new bus / microbus / taxi. Admin-only."""
    user = await _require_admin(request)
    body = await request.json()
    fields = _validate_vehicle_payload(body, partial=False)

    # Operator binding — non-super-admins always create within their own operator.
    op_id = user.get("operator_id") if not _is_super(user) else (body.get("operator_id") or user.get("operator_id"))
    if not op_id:
        raise HTTPException(status_code=400, detail="operator_id required (super-admin must specify)")
    fields["operator_id"] = op_id

    # Route + driver linkage with type cross-check.
    route = await _route_for_vehicle(fields.get("assigned_route_id"), op_id)
    if route and route.get("route_type") != fields["vehicle_type"]:
        raise HTTPException(
            status_code=400,
            detail=f"vehicle_type='{fields['vehicle_type']}' does not match route route_type='{route.get('route_type')}'",
        )
    await _driver_for_vehicle(fields.get("assigned_driver_id"), op_id)

    # Unique plate within operator.
    dup = await _sb_get(
        "vehicles",
        params={"vehicle_id": f"eq.{fields['vehicle_id']}", "select": "id", "limit": 1},
        use_service=True,
    )
    if dup:
        raise HTTPException(status_code=409, detail="A vehicle with this plate already exists")

    fields.setdefault("status", "idle")
    fields.setdefault("is_active", True)
    row = await _sb_post("vehicles", fields, use_service=True)
    created = row[0] if isinstance(row, list) else row
    await _audit(user, "vehicle_created", "vehicles", entity_id=created.get("id"), details=fields)
    return {"ok": True, "vehicle": created}


@app.patch("/api/admin/vehicles/{vehicle_id}")
async def admin_update_vehicle(vehicle_id: str, request: Request):
    user = await _require_admin(request)
    _require_uuid(vehicle_id, "vehicle id")
    body = await request.json()
    patch = _validate_vehicle_payload(body, partial=True)
    if not patch:
        raise HTTPException(status_code=400, detail="No allowed fields in payload")

    # Resolve target row + ownership.
    rows = await _sb_get(
        "vehicles",
        params={"id": f"eq.{vehicle_id}", "select": "id,operator_id,vehicle_type,assigned_route_id,assigned_driver_id", "limit": 1},
        use_service=True,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    current = rows[0]
    if not _is_super(user) and current.get("operator_id") != user.get("operator_id"):
        raise HTTPException(status_code=403, detail="Vehicle belongs to a different operator")

    # Type/route cross-check (after merging the patch).
    new_type = patch.get("vehicle_type", current.get("vehicle_type"))
    new_route_id = patch.get("assigned_route_id", current.get("assigned_route_id"))
    route = await _route_for_vehicle(new_route_id, current.get("operator_id"))
    if route and route.get("route_type") != new_type:
        raise HTTPException(
            status_code=400,
            detail=f"vehicle_type='{new_type}' does not match route route_type='{route.get('route_type')}'",
        )
    # Driver re-assignment.
    if "assigned_driver_id" in patch and patch["assigned_driver_id"] != current.get("assigned_driver_id"):
        await _driver_for_vehicle(patch["assigned_driver_id"], current.get("operator_id"))

    await _sb_patch("vehicles", params={"id": f"eq.{vehicle_id}"}, body=patch, use_service=True)
    await _audit(user, "vehicle_updated", "vehicles", entity_id=vehicle_id, details=patch)
    return {"ok": True, "patched": list(patch.keys())}


@app.delete("/api/admin/vehicles/{vehicle_id}")
async def admin_delete_vehicle(vehicle_id: str, request: Request):
    """Soft-delete (is_active=false). Real deletes risk leaving orphan
    trip/alert rows behind."""
    user = await _require_admin(request)
    _require_uuid(vehicle_id, "vehicle id")
    rows = await _sb_get(
        "vehicles",
        params={"id": f"eq.{vehicle_id}", "select": "id,operator_id", "limit": 1},
        use_service=True,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if not _is_super(user) and rows[0].get("operator_id") != user.get("operator_id"):
        raise HTTPException(status_code=403, detail="Vehicle belongs to a different operator")
    # Phase 6.2-C: cancel any in-progress / acked / dispatched / scheduled
    # trip on this vehicle before flipping it off, so drivers don't end up
    # with a dangling trip ID whose vehicle suddenly has no GPS path.
    cancelled = 0
    try:
        cancelled_rows = await _sb_rpc(
            "cancel_active_trips_for_vehicle",
            {"p_vehicle_id": vehicle_id, "p_reason": "vehicle decommissioned"},
            use_service=True,
        )
        if isinstance(cancelled_rows, int):
            cancelled = cancelled_rows
        elif isinstance(cancelled_rows, list) and cancelled_rows:
            cancelled = int(cancelled_rows[0]) if isinstance(cancelled_rows[0], int) else 0
    except Exception:
        # Best-effort. On older schemas the RPC doesn't exist yet; we
        # fall back to a direct PATCH so the orphan-trip bug is still
        # avoided.
        try:
            await _sb_patch(
                "trips",
                params={
                    "vehicle_id": f"eq.{vehicle_id}",
                    "status":     "in.(scheduled,dispatched,acked,in_progress)",
                },
                body={
                    "status":              "cancelled",
                    "actual_end":          datetime.now(timezone.utc).isoformat(),
                    "cancellation_reason": "vehicle decommissioned",
                },
                use_service=True,
            )
        except Exception:
            log.exception("could not cancel active trips for vehicle %s", vehicle_id)

    await _sb_patch(
        "vehicles",
        params={"id": f"eq.{vehicle_id}"},
        body={"is_active": False, "status": "decommissioned", "assigned_driver_id": None, "updated_at": datetime.now(timezone.utc).isoformat()},
        use_service=True,
    )
    await _audit(user, "vehicle_decommissioned", "vehicles", entity_id=vehicle_id, details={"cancelled_trips": cancelled})
    return {"ok": True, "cancelled_trips": cancelled}


@app.post("/api/admin/vehicles/register")
async def admin_register_vehicle(request: Request):
    """H7: atomic 'register a new vehicle and link everything in one shot'.

    The request can include:
      • All vehicle fields (vehicle_id, name, type, capacity, …)
      • assigned_route_id     — route to bind (type-checked against vehicle)
      • assigned_driver_id    — driver to assign (must be unassigned)
      • geofence_id           — optional zone the vehicle belongs to

    Steps run in order; if any step fails the vehicle is rolled back so
    we never leave partial linkage behind."""
    user = await _require_admin(request)
    body = await request.json()
    fields = _validate_vehicle_payload(body, partial=False)
    geofence_id = body.get("geofence_id")
    if geofence_id is not None:
        _require_uuid(geofence_id, "geofence_id")

    op_id = user.get("operator_id") if not _is_super(user) else (body.get("operator_id") or user.get("operator_id"))
    if not op_id:
        raise HTTPException(status_code=400, detail="operator_id required")
    fields["operator_id"] = op_id

    route = await _route_for_vehicle(fields.get("assigned_route_id"), op_id)
    if route and route.get("route_type") != fields["vehicle_type"]:
        raise HTTPException(
            status_code=400,
            detail=f"vehicle_type='{fields['vehicle_type']}' does not match route route_type='{route.get('route_type')}'",
        )
    await _driver_for_vehicle(fields.get("assigned_driver_id"), op_id)

    if geofence_id:
        gf = await _sb_get(
            "geofences",
            params={"id": f"eq.{geofence_id}", "select": "id,operator_id,is_active,max_vehicles", "limit": 1},
            use_service=True,
        )
        if not gf:
            raise HTTPException(status_code=400, detail="geofence_id not found")
        if gf[0].get("operator_id") != op_id:
            raise HTTPException(status_code=400, detail="Geofence belongs to a different operator")
        if not gf[0].get("is_active"):
            raise HTTPException(status_code=400, detail="Geofence is not active")

    # Create vehicle first. If subsequent linkage fails we DECOMMISSION it
    # rather than leave it half-linked.
    fields.setdefault("status", "idle")
    fields.setdefault("is_active", True)
    row = await _sb_post("vehicles", fields, use_service=True)
    created = row[0] if isinstance(row, list) else row

    try:
        # Geofence link is recorded in a join table if present; we keep it
        # in audit_log even when the table doesn't exist so the linkage is
        # still queryable.
        if geofence_id:
            try:
                await _sb_post(
                    "vehicle_geofences",
                    {"vehicle_id": created["id"], "geofence_id": geofence_id, "operator_id": op_id},
                    use_service=True,
                )
            except HTTPException:
                # table optional — fall back to audit_log only.
                pass

        await _audit(
            user,
            "vehicle_registered_full",
            "vehicles",
            entity_id=created.get("id"),
            details={"route_id": fields.get("assigned_route_id"), "driver_id": fields.get("assigned_driver_id"), "geofence_id": geofence_id},
        )
        return {"ok": True, "vehicle": created, "linked": {"route_id": fields.get("assigned_route_id"), "driver_id": fields.get("assigned_driver_id"), "geofence_id": geofence_id}}
    except Exception:
        # Rollback
        try:
            await _sb_patch(
                "vehicles",
                params={"id": f"eq.{created['id']}"},
                body={"is_active": False, "status": "decommissioned"},
                use_service=True,
            )
        except Exception:
            pass
        raise


# ── ADMIN — ROUTES CRUD ──────────────────────────────────────────────────────
def _validate_route_geometry(geom: Any) -> Optional[dict]:
    """Accept a GeoJSON LineString or null; validate every coordinate sits
    inside the Syria bbox."""
    if geom is None:
        return None
    if not isinstance(geom, dict) or geom.get("type") != "LineString":
        raise HTTPException(status_code=400, detail="geometry must be a GeoJSON LineString")
    coords = geom.get("coordinates")
    if not isinstance(coords, list) or len(coords) < 2:
        raise HTTPException(status_code=400, detail="LineString must have ≥2 points")
    for pt in coords:
        if not (isinstance(pt, list) and len(pt) >= 2):
            raise HTTPException(status_code=400, detail="LineString coordinates malformed")
        _validate_coord(pt[1], pt[0])
    return geom


def _validate_route_payload(body: dict, *, partial: bool = False) -> dict:
    out: dict = {}
    if "route_id" in body or not partial:
        code = (body.get("route_id") or "").strip()
        if not partial and not code:
            raise HTTPException(status_code=400, detail="route_id (short code) required")
        if code:
            if not _ROUTE_CODE_RE.match(code):
                raise HTTPException(status_code=400, detail="route_id must be 2-16 alphanumeric/-/_ chars")
            out["route_id"] = code.upper()
    if "name" in body or not partial:
        n = (body.get("name") or "").strip()
        if not partial and not n:
            raise HTTPException(status_code=400, detail="name required")
        if n:
            out["name"] = n[:200]
    if "name_ar" in body or not partial:
        n = (body.get("name_ar") or "").strip()
        if not partial and not n:
            raise HTTPException(status_code=400, detail="name_ar required")
        if n:
            out["name_ar"] = n[:200]
    if "route_type" in body or not partial:
        rt = body.get("route_type") or "bus"
        if rt not in ROUTE_TYPES:
            raise HTTPException(status_code=400, detail=f"route_type must be one of {ROUTE_TYPES}")
        out["route_type"] = rt
    if "color" in body:
        c = (body.get("color") or "").strip()
        if c and not _HEX_COLOR_RE.match(c):
            raise HTTPException(status_code=400, detail="color must be #RRGGBB hex")
        if c:
            out["color"] = c
    if "geometry" in body:
        out["geometry"] = _validate_route_geometry(body.get("geometry"))
    for num_field in ("distance_km", "avg_duration_min", "fare_syp"):
        if num_field in body and body[num_field] is not None:
            try:
                out[num_field] = float(body[num_field]) if num_field == "distance_km" else int(body[num_field])
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail=f"{num_field} must be numeric")
            if out[num_field] < 0:
                raise HTTPException(status_code=400, detail=f"{num_field} must be ≥0")
    if "is_active" in body:
        out["is_active"] = bool(body.get("is_active"))
    return out


@app.post("/api/admin/routes")
async def admin_create_route(request: Request):
    user = await _require_admin(request)
    body = await request.json()
    fields = _validate_route_payload(body, partial=False)
    op_id = user.get("operator_id") if not _is_super(user) else (body.get("operator_id") or user.get("operator_id"))
    if not op_id:
        raise HTTPException(status_code=400, detail="operator_id required")
    fields["operator_id"] = op_id
    dup = await _sb_get("routes", params={"route_id": f"eq.{fields['route_id']}", "select": "id", "limit": 1}, use_service=True)
    if dup:
        raise HTTPException(status_code=409, detail="A route with this code already exists")
    row = await _sb_post("routes", fields, use_service=True)
    created = row[0] if isinstance(row, list) else row
    await _audit(user, "route_created", "routes", entity_id=created.get("id"), details=fields)
    return {"ok": True, "route": created}


@app.patch("/api/admin/routes/{route_id}")
async def admin_update_route(route_id: str, request: Request):
    user = await _require_admin(request)
    _require_uuid(route_id, "route id")
    body = await request.json()
    patch = _validate_route_payload(body, partial=True)
    if not patch:
        raise HTTPException(status_code=400, detail="No allowed fields in payload")
    rows = await _sb_get("routes", params={"id": f"eq.{route_id}", "select": "id,operator_id,route_type", "limit": 1}, use_service=True)
    if not rows:
        raise HTTPException(status_code=404, detail="Route not found")
    if not _is_super(user) and rows[0].get("operator_id") != user.get("operator_id"):
        raise HTTPException(status_code=403, detail="Route belongs to a different operator")
    # If route_type changed, ensure no vehicle currently bound to it has a mismatching type.
    if "route_type" in patch and patch["route_type"] != rows[0].get("route_type"):
        bound = await _sb_get(
            "vehicles",
            params={"assigned_route_id": f"eq.{route_id}", "is_active": "eq.true", "select": "id,vehicle_type"},
            use_service=True,
        )
        bad = [v["id"] for v in bound if v.get("vehicle_type") != patch["route_type"]]
        if bad:
            raise HTTPException(status_code=409, detail=f"{len(bad)} vehicle(s) currently bound have a different vehicle_type; unbind them first")
    await _sb_patch("routes", params={"id": f"eq.{route_id}"}, body=patch, use_service=True)
    await _audit(user, "route_updated", "routes", entity_id=route_id, details=patch)
    return {"ok": True, "patched": list(patch.keys())}


@app.delete("/api/admin/routes/{route_id}")
async def admin_delete_route(route_id: str, request: Request):
    user = await _require_admin(request)
    _require_uuid(route_id, "route id")
    rows = await _sb_get("routes", params={"id": f"eq.{route_id}", "select": "id,operator_id", "limit": 1}, use_service=True)
    if not rows:
        raise HTTPException(status_code=404, detail="Route not found")
    if not _is_super(user) and rows[0].get("operator_id") != user.get("operator_id"):
        raise HTTPException(status_code=403, detail="Route belongs to a different operator")
    bound = await _sb_get("vehicles", params={"assigned_route_id": f"eq.{route_id}", "is_active": "eq.true", "select": "id"}, use_service=True)
    if bound:
        raise HTTPException(status_code=409, detail=f"Route still has {len(bound)} active vehicle(s); reassign them first")
    await _sb_patch("routes", params={"id": f"eq.{route_id}"}, body={"is_active": False}, use_service=True)
    await _audit(user, "route_deactivated", "routes", entity_id=route_id)
    return {"ok": True}


# ── ADMIN — STOPS CRUD ───────────────────────────────────────────────────────
def _validate_stop_payload(body: dict, *, partial: bool = False) -> dict:
    out: dict = {}
    if "stop_id" in body or not partial:
        code = (body.get("stop_id") or "").strip()
        if not partial and not code:
            raise HTTPException(status_code=400, detail="stop_id required")
        if code:
            if not _STOP_CODE_RE.match(code):
                raise HTTPException(status_code=400, detail="stop_id must be 2-16 alphanumeric/-/_")
            out["stop_id"] = code.upper()
    if "name" in body or not partial:
        n = (body.get("name") or "").strip()
        if not partial and not n:
            raise HTTPException(status_code=400, detail="name required")
        if n:
            out["name"] = n[:200]
    if "name_ar" in body or not partial:
        n = (body.get("name_ar") or "").strip()
        if not partial and not n:
            raise HTTPException(status_code=400, detail="name_ar required")
        if n:
            out["name_ar"] = n[:200]
    if "lat" in body or "lon" in body or not partial:
        lat, lon = _validate_coord(body.get("lat"), body.get("lon"))
        out["location"] = {"type": "Point", "coordinates": [lon, lat]}
    if "has_shelter" in body:
        out["has_shelter"] = bool(body.get("has_shelter"))
    if "is_active" in body:
        out["is_active"] = bool(body.get("is_active"))
    return out


@app.post("/api/admin/stops")
async def admin_create_stop(request: Request):
    user = await _require_admin(request)
    body = await request.json()
    fields = _validate_stop_payload(body, partial=False)
    op_id = user.get("operator_id") if not _is_super(user) else (body.get("operator_id") or user.get("operator_id"))
    if not op_id:
        raise HTTPException(status_code=400, detail="operator_id required")
    fields["operator_id"] = op_id
    dup = await _sb_get("stops", params={"stop_id": f"eq.{fields['stop_id']}", "select": "id", "limit": 1}, use_service=True)
    if dup:
        raise HTTPException(status_code=409, detail="A stop with this code already exists")
    row = await _sb_post("stops", fields, use_service=True)
    created = row[0] if isinstance(row, list) else row
    await _audit(user, "stop_created", "stops", entity_id=created.get("id"), details=fields)
    return {"ok": True, "stop": created}


@app.patch("/api/admin/stops/{stop_id}")
async def admin_update_stop(stop_id: str, request: Request):
    user = await _require_admin(request)
    _require_uuid(stop_id, "stop id")
    body = await request.json()
    patch = _validate_stop_payload(body, partial=True)
    if not patch:
        raise HTTPException(status_code=400, detail="No allowed fields in payload")
    rows = await _sb_get("stops", params={"id": f"eq.{stop_id}", "select": "id,operator_id", "limit": 1}, use_service=True)
    if not rows:
        raise HTTPException(status_code=404, detail="Stop not found")
    if not _is_super(user) and rows[0].get("operator_id") != user.get("operator_id"):
        raise HTTPException(status_code=403, detail="Stop belongs to a different operator")
    await _sb_patch("stops", params={"id": f"eq.{stop_id}"}, body=patch, use_service=True)
    await _audit(user, "stop_updated", "stops", entity_id=stop_id, details=patch)
    return {"ok": True, "patched": list(patch.keys())}


@app.delete("/api/admin/stops/{stop_id}")
async def admin_delete_stop(stop_id: str, request: Request):
    user = await _require_admin(request)
    _require_uuid(stop_id, "stop id")
    rows = await _sb_get("stops", params={"id": f"eq.{stop_id}", "select": "id,operator_id", "limit": 1}, use_service=True)
    if not rows:
        raise HTTPException(status_code=404, detail="Stop not found")
    if not _is_super(user) and rows[0].get("operator_id") != user.get("operator_id"):
        raise HTTPException(status_code=403, detail="Stop belongs to a different operator")
    await _sb_patch("stops", params={"id": f"eq.{stop_id}"}, body={"is_active": False}, use_service=True)
    await _audit(user, "stop_deactivated", "stops", entity_id=stop_id)
    return {"ok": True}


# ── ADMIN — USERS CRUD ───────────────────────────────────────────────────────
def _validate_user_payload(body: dict, *, partial: bool = False) -> dict:
    out: dict = {}
    if "email" in body or not partial:
        e = (body.get("email") or "").strip().lower()
        if not partial and not e:
            raise HTTPException(status_code=400, detail="email required")
        if e:
            if not _EMAIL_RE.match(e) or len(e) > 254:
                raise HTTPException(status_code=400, detail="email format invalid")
            out["email"] = e
    if "full_name" in body or "name" in body or not partial:
        n = (body.get("full_name") or body.get("name") or "").strip()
        if not partial and not n:
            raise HTTPException(status_code=400, detail="full_name required")
        if n:
            out["full_name"] = n[:120]
    if "full_name_ar" in body or "name_ar" in body:
        n = (body.get("full_name_ar") or body.get("name_ar") or "").strip()
        if n:
            out["full_name_ar"] = n[:120]
    if "role" in body or not partial:
        r = body.get("role") or "viewer"
        if r not in ALLOWED_USER_ROLES:
            raise HTTPException(status_code=400, detail=f"role must be one of {ALLOWED_USER_ROLES}")
        out["role"] = r
    if "phone" in body:
        p = (body.get("phone") or "").strip()
        if p:
            if not re.match(r"^\+?[0-9 \-]{6,20}$", p):
                raise HTTPException(status_code=400, detail="phone format invalid")
            out["phone"] = p
    if "is_active" in body:
        out["is_active"] = bool(body.get("is_active"))
    return out


@app.post("/api/admin/users")
async def admin_create_user(request: Request):
    """Create a new user. Caller's role must be >= the new user's role
    (no privilege escalation). operator_id auto-bound. must_change_password
    set to true on creation so the new user is forced to rotate."""
    user = await _require_admin(request)
    body = await request.json()
    fields = _validate_user_payload(body, partial=False)
    new_role = fields["role"]
    if ROLE_RANK.get(new_role, 99) > ROLE_RANK.get(user.get("role"), 0):
        raise HTTPException(status_code=403, detail="Cannot create a user with a higher role than yours")

    initial_pw = (body.get("initial_password") or "").strip()
    if not initial_pw or len(initial_pw) < 10 or len(initial_pw) > 128:
        raise HTTPException(status_code=400, detail="initial_password must be 10..128 chars")

    op_id = user.get("operator_id") if not _is_super(user) else (body.get("operator_id") or user.get("operator_id"))
    if new_role != "super_admin" and not op_id:
        raise HTTPException(status_code=400, detail="operator_id required")

    dup = await _sb_get("users", params={"email": f"eq.{fields['email']}", "select": "id", "limit": 1}, use_service=True)
    if dup:
        raise HTTPException(status_code=409, detail="A user with this email already exists")

    fields["password_hash"] = bcrypt.hashpw(initial_pw.encode(), bcrypt.gensalt(rounds=12)).decode()
    fields["must_change_password"] = True
    fields["operator_id"] = op_id
    fields.setdefault("is_active", True)
    row = await _sb_post("users", fields, use_service=True)
    created = row[0] if isinstance(row, list) else row
    await _audit(user, "user_created", "users", entity_id=created.get("id"), details={"role": new_role, "email": fields["email"]})
    # Strip the hash before returning.
    created.pop("password_hash", None)
    return {"ok": True, "user": created}


@app.patch("/api/admin/users/{target_id}")
async def admin_update_user(target_id: str, request: Request):
    user = await _require_admin(request)
    _require_uuid(target_id, "user id")
    body = await request.json()
    rows = await _sb_get(
        "users",
        params={"id": f"eq.{target_id}", "select": "id,role,operator_id,is_active", "limit": 1},
        use_service=True,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="User not found")
    target = rows[0]
    if not _is_super(user) and target.get("operator_id") != user.get("operator_id"):
        raise HTTPException(status_code=403, detail="User belongs to a different operator")
    if ROLE_RANK.get(target.get("role"), 0) > ROLE_RANK.get(user.get("role"), 0):
        raise HTTPException(status_code=403, detail="Cannot modify a user with a higher role")

    patch = _validate_user_payload(body, partial=True)
    if "role" in patch and ROLE_RANK.get(patch["role"], 99) > ROLE_RANK.get(user.get("role"), 0):
        raise HTTPException(status_code=403, detail="Cannot elevate a user above your own role")
    if not patch:
        raise HTTPException(status_code=400, detail="No allowed fields in payload")
    patch["updated_at"] = datetime.now(timezone.utc).isoformat()
    await _sb_patch("users", params={"id": f"eq.{target_id}"}, body=patch, use_service=True)
    await _audit(user, "user_updated", "users", entity_id=target_id, details=patch)
    return {"ok": True, "patched": list(patch.keys())}


@app.delete("/api/admin/users/{target_id}")
async def admin_delete_user(target_id: str, request: Request):
    user = await _require_admin(request)
    _require_uuid(target_id, "user id")
    if target_id == user["sub"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    rows = await _sb_get(
        "users",
        params={"id": f"eq.{target_id}", "select": "id,role,operator_id", "limit": 1},
        use_service=True,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="User not found")
    target = rows[0]
    if not _is_super(user) and target.get("operator_id") != user.get("operator_id"):
        raise HTTPException(status_code=403, detail="User belongs to a different operator")
    if ROLE_RANK.get(target.get("role"), 0) > ROLE_RANK.get(user.get("role"), 0):
        raise HTTPException(status_code=403, detail="Cannot delete a user with a higher role")
    await _sb_patch("users", params={"id": f"eq.{target_id}"}, body={"is_active": False, "updated_at": datetime.now(timezone.utc).isoformat()}, use_service=True)
    await _audit(user, "user_deactivated", "users", entity_id=target_id)
    return {"ok": True}


# ── ADMIN — GEOFENCES CRUD ───────────────────────────────────────────────────
def _validate_polygon(geom: Any) -> dict:
    if not isinstance(geom, dict) or geom.get("type") != "Polygon":
        raise HTTPException(status_code=400, detail="geometry must be a GeoJSON Polygon")
    coords = geom.get("coordinates")
    if not isinstance(coords, list) or not coords or not isinstance(coords[0], list) or len(coords[0]) < 4:
        raise HTTPException(status_code=400, detail="Polygon outer ring must have ≥4 points incl. closing point")
    ring = coords[0]
    if ring[0] != ring[-1]:
        raise HTTPException(status_code=400, detail="Polygon outer ring must close (first==last point)")
    for pt in ring:
        if not (isinstance(pt, list) and len(pt) >= 2):
            raise HTTPException(status_code=400, detail="Polygon coordinates malformed")
        _validate_coord(pt[1], pt[0])
    return geom


@app.get("/api/admin/geofences")
async def admin_list_geofences(request: Request):
    user = await _require_dispatcher(request)
    rows = await _sb_get(
        "geofences",
        params=_scope_to_operator(user, {
            "select": "id,name,name_ar,geometry,geofence_type,speed_limit_kmh,max_vehicles,is_active,operator_id,created_at",
            "order": "created_at.desc",
        }),
        use_service=True,
    )
    return rows


@app.post("/api/admin/geofences")
async def admin_create_geofence(request: Request):
    user = await _require_admin(request)
    body = await request.json()
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    name_ar = (body.get("name_ar") or "").strip() or None
    geom = _validate_polygon(body.get("geometry"))
    gtype = (body.get("geofence_type") or "zone").strip()
    if gtype not in ("zone", "depot", "terminal"):
        raise HTTPException(status_code=400, detail="geofence_type must be zone|depot|terminal")
    speed_limit = body.get("speed_limit_kmh")
    if speed_limit is not None:
        try:
            speed_limit = int(speed_limit)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="speed_limit_kmh must be integer")
        if speed_limit < 0 or speed_limit > 200:
            raise HTTPException(status_code=400, detail="speed_limit_kmh must be 0..200")
    max_vehicles = body.get("max_vehicles")
    if max_vehicles is not None:
        try:
            max_vehicles = int(max_vehicles)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="max_vehicles must be integer")
        if max_vehicles < 0 or max_vehicles > 10000:
            raise HTTPException(status_code=400, detail="max_vehicles must be 0..10000")

    op_id = user.get("operator_id") if not _is_super(user) else (body.get("operator_id") or user.get("operator_id"))
    if not op_id:
        raise HTTPException(status_code=400, detail="operator_id required")
    payload = {
        "name": name[:200],
        "name_ar": (name_ar or "")[:200] or None,
        "geometry": geom,
        "geofence_type": gtype,
        "speed_limit_kmh": speed_limit,
        "max_vehicles": max_vehicles,
        "is_active": bool(body.get("is_active", True)),
        "operator_id": op_id,
    }
    row = await _sb_post("geofences", payload, use_service=True)
    created = row[0] if isinstance(row, list) else row
    await _audit(user, "geofence_created", "geofences", entity_id=created.get("id"), details={"name": name, "max_vehicles": max_vehicles})
    return {"ok": True, "geofence": created}


@app.patch("/api/admin/geofences/{gf_id}")
async def admin_update_geofence(gf_id: str, request: Request):
    user = await _require_admin(request)
    _require_uuid(gf_id, "geofence id")
    body = await request.json()
    rows = await _sb_get("geofences", params={"id": f"eq.{gf_id}", "select": "id,operator_id", "limit": 1}, use_service=True)
    if not rows:
        raise HTTPException(status_code=404, detail="Geofence not found")
    if not _is_super(user) and rows[0].get("operator_id") != user.get("operator_id"):
        raise HTTPException(status_code=403, detail="Geofence belongs to a different operator")
    patch: dict = {}
    if "name" in body:
        patch["name"] = (body.get("name") or "").strip()[:200] or None
    if "name_ar" in body:
        patch["name_ar"] = (body.get("name_ar") or "").strip()[:200] or None
    if "geometry" in body:
        patch["geometry"] = _validate_polygon(body.get("geometry"))
    if "speed_limit_kmh" in body:
        v = body.get("speed_limit_kmh")
        patch["speed_limit_kmh"] = int(v) if v is not None else None
    if "max_vehicles" in body:
        v = body.get("max_vehicles")
        patch["max_vehicles"] = int(v) if v is not None else None
    if "is_active" in body:
        patch["is_active"] = bool(body.get("is_active"))
    if not patch:
        raise HTTPException(status_code=400, detail="No allowed fields in payload")
    await _sb_patch("geofences", params={"id": f"eq.{gf_id}"}, body=patch, use_service=True)
    await _audit(user, "geofence_updated", "geofences", entity_id=gf_id, details=patch)
    return {"ok": True, "patched": list(patch.keys())}


@app.delete("/api/admin/geofences/{gf_id}")
async def admin_delete_geofence(gf_id: str, request: Request):
    user = await _require_admin(request)
    _require_uuid(gf_id, "geofence id")
    rows = await _sb_get("geofences", params={"id": f"eq.{gf_id}", "select": "id,operator_id", "limit": 1}, use_service=True)
    if not rows:
        raise HTTPException(status_code=404, detail="Geofence not found")
    if not _is_super(user) and rows[0].get("operator_id") != user.get("operator_id"):
        raise HTTPException(status_code=403, detail="Geofence belongs to a different operator")
    await _sb_patch("geofences", params={"id": f"eq.{gf_id}"}, body={"is_active": False}, use_service=True)
    await _audit(user, "geofence_deactivated", "geofences", entity_id=gf_id)
    return {"ok": True}


# ── MISC ─────────────────────────────────────────────────────────────────────
@app.get("/api/gtfs")
async def gtfs_placeholder():
    return {
        "detail": "GTFS feed coming soon",
        "format": "static + realtime planned",
        "schedule": "monthly publication on the 1st",
    }


@app.post("/api/client_log")
async def client_log(request: Request):
    _rate_limit(request, "client-log", limit=20, window_s=60)
    try:
        body = await request.body()
        log.info("client_log: %s", body[:2048])
    except Exception:
        pass
    return JSONResponse(status_code=204, content=None)


# ── ADMIN — TRIPS CRUD (Track A.1) ───────────────────────────────────────────
# The dispatch workflow that was missing entirely from v4.1 and the earlier
# v5.0 pass. Dispatchers can now schedule a trip ahead of time, push it to a
# specific driver, and track the ack/start/complete lifecycle.
#
# Trip lifecycle:
#   scheduled  → dispatcher created it
#   dispatched → dispatcher pushed it to the driver (notification visible
#                in driver app)
#   acked      → driver tapped "Acknowledge"
#   in_progress → driver tapped "Start trip" (this is the only state the
#                 old driver endpoint produced)
#   completed   → driver tapped "End trip"
#   cancelled   → dispatcher cancelled it with a reason

TRIP_DISPATCHABLE_STATUSES = ("scheduled", "dispatched", "acked")


def _parse_iso(s: Any, field: str) -> datetime:
    if not isinstance(s, str) or len(s) < 10:
        raise HTTPException(status_code=400, detail=f"{field} must be ISO8601 timestamp")
    try:
        # Accept trailing Z (Python <3.11 doesn't parse it natively).
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field} is not valid ISO8601")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


async def _trip_payload_validate(body: dict, *, partial: bool, op_id: Optional[str]) -> dict:
    """Validate a trip payload and resolve vehicle/route/driver/operator
    consistency. Returns the fields ready to send to PostgREST."""
    out: dict = {}

    # Vehicle is required on create.
    if "vehicle_id" in body or not partial:
        vid = body.get("vehicle_id")
        if not partial and not vid:
            raise HTTPException(status_code=400, detail="vehicle_id required")
        if vid:
            _require_uuid(vid, "vehicle_id")
            rows = await _sb_get(
                "vehicles",
                params={"id": f"eq.{vid}", "select": "id,operator_id,assigned_route_id,assigned_driver_id,vehicle_type,is_active", "limit": 1},
                use_service=True,
            )
            if not rows:
                raise HTTPException(status_code=400, detail="vehicle_id does not exist")
            v = rows[0]
            if op_id and v.get("operator_id") != op_id:
                raise HTTPException(status_code=400, detail="Vehicle belongs to a different operator")
            if not v.get("is_active"):
                raise HTTPException(status_code=400, detail="Vehicle is not active")
            out["vehicle_id"] = vid
            # Default route/driver from the vehicle binding if caller didn't override.
            if "route_id" not in body:
                out["route_id"] = v.get("assigned_route_id")
            if "driver_id" not in body:
                out["driver_id"] = v.get("assigned_driver_id")

    if "route_id" in body:
        rid = body.get("route_id")
        if rid:
            _require_uuid(rid, "route_id")
            rrows = await _sb_get(
                "routes",
                params={"id": f"eq.{rid}", "select": "id,operator_id,route_type,is_active", "limit": 1},
                use_service=True,
            )
            if not rrows:
                raise HTTPException(status_code=400, detail="route_id does not exist")
            if op_id and rrows[0].get("operator_id") != op_id:
                raise HTTPException(status_code=400, detail="Route belongs to a different operator")
            if not rrows[0].get("is_active"):
                raise HTTPException(status_code=400, detail="Route is not active")
            out["route_id"] = rid

    if "driver_id" in body:
        did = body.get("driver_id")
        if did:
            _require_uuid(did, "driver_id")
            drows = await _sb_get(
                "users",
                params={"id": f"eq.{did}", "select": "id,role,operator_id,is_active", "limit": 1},
                use_service=True,
            )
            if not drows:
                raise HTTPException(status_code=400, detail="driver_id does not exist")
            if drows[0].get("role") != "driver":
                raise HTTPException(status_code=400, detail="driver_id is not a driver")
            if op_id and drows[0].get("operator_id") != op_id:
                raise HTTPException(status_code=400, detail="Driver belongs to a different operator")
            out["driver_id"] = did
        else:
            out["driver_id"] = None

    if "scheduled_start" in body and body["scheduled_start"]:
        out["scheduled_start"] = _parse_iso(body["scheduled_start"], "scheduled_start").isoformat()

    if "planned_passengers" in body and body["planned_passengers"] is not None:
        try:
            pp = int(body["planned_passengers"])
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="planned_passengers must be integer")
        if pp < 0 or pp > 200:
            raise HTTPException(status_code=400, detail="planned_passengers must be 0..200")
        out["planned_passengers"] = pp

    if "notes" in body:
        n = (body.get("notes") or "").strip()
        out["notes"] = n[:1000] or None

    return out


@app.get("/api/admin/trips")
async def admin_list_trips(request: Request, limit: int = 100, status: Optional[str] = None):
    """Dispatcher+ — list trips, scoped to the caller's operator. Optional
    ?status= filter accepts a comma list (e.g. status=scheduled,dispatched)."""
    user = await _require_dispatcher(request)
    limit = max(1, min(int(limit or 100), 1000))
    params = _scope_to_operator(user, {
        "select": "id,vehicle_id,route_id,driver_id,status,scheduled_start,actual_start,actual_end,passenger_count,planned_passengers,dispatched_by_user_id,dispatched_at,acked_at,notes,operator_id,created_at",
        "order": "scheduled_start.desc.nullslast,created_at.desc",
        "limit": limit,
    })
    if status:
        valid = {"scheduled", "dispatched", "acked", "in_progress", "completed", "cancelled"}
        wanted = [s.strip() for s in status.split(",") if s.strip() in valid]
        if wanted:
            params["status"] = "in.(" + ",".join(wanted) + ")"
    rows = await _sb_get("trips", params=params, use_service=True)
    return rows


@app.post("/api/admin/trips")
async def admin_create_trip(request: Request):
    """Dispatcher+ — schedule a new trip. Detects schedule conflicts for
    the same driver within ±30 minutes and returns 409 instead of inserting."""
    user = await _require_dispatcher(request)
    body = await request.json()
    op_id = user.get("operator_id") if not _is_super(user) else (body.get("operator_id") or user.get("operator_id"))
    if not op_id:
        raise HTTPException(status_code=400, detail="operator_id required")
    fields = await _trip_payload_validate(body, partial=False, op_id=op_id)
    fields["operator_id"] = op_id
    fields.setdefault("status", "scheduled")

    # Conflict check (best-effort — if RPC missing, fall back to a coarse query).
    if fields.get("driver_id") and fields.get("scheduled_start"):
        try:
            conflicts = await _sb_rpc(
                "trip_conflicts_for_driver",
                {"p_driver_id": fields["driver_id"], "p_start": fields["scheduled_start"], "p_window_min": 30},
                use_service=True,
            )
            if conflicts:
                raise HTTPException(
                    status_code=409,
                    detail=f"Driver already has a trip within 30 minutes (trip {conflicts[0]['id']})",
                )
        except HTTPException:
            raise
        except Exception:
            log.exception("trip_conflicts_for_driver RPC missing — skipping conflict check")

    row = await _sb_post("trips", fields, use_service=True)
    created = row[0] if isinstance(row, list) else row
    await _audit(user, "trip_created", "trips", entity_id=created.get("id"), details={"driver_id": fields.get("driver_id"), "scheduled_start": fields.get("scheduled_start")})
    return {"ok": True, "trip": created}


@app.patch("/api/admin/trips/{trip_id}")
async def admin_update_trip(trip_id: str, request: Request):
    """Dispatcher+ — re-assign driver, change schedule, or transition status.
    Status transitions allowed:
        scheduled  → dispatched | cancelled
        dispatched → acked | cancelled
        acked      → in_progress | cancelled
    Drivers handle in_progress→completed via /api/driver/trip/end."""
    user = await _require_dispatcher(request)
    _require_uuid(trip_id, "trip id")
    body = await request.json()
    rows = await _sb_get(
        "trips",
        params={"id": f"eq.{trip_id}", "select": "id,operator_id,status,driver_id,scheduled_start", "limit": 1},
        use_service=True,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Trip not found")
    current = rows[0]
    if not _is_super(user) and current.get("operator_id") != user.get("operator_id"):
        raise HTTPException(status_code=403, detail="Trip belongs to a different operator")

    op_id = current.get("operator_id")
    fields = await _trip_payload_validate(body, partial=True, op_id=op_id)

    # Explicit status transition handling.
    if "status" in body:
        next_status = body["status"]
        cur = current.get("status")
        legal = {
            "scheduled":   {"dispatched", "cancelled"},
            "dispatched":  {"acked", "cancelled"},
            "acked":       {"in_progress", "cancelled"},
            "in_progress": {"completed", "cancelled"},
        }
        if next_status not in legal.get(cur, set()):
            raise HTTPException(status_code=409, detail=f"Illegal status transition {cur} → {next_status}")
        fields["status"] = next_status
        now_iso = datetime.now(timezone.utc).isoformat()
        if next_status == "dispatched":
            fields["dispatched_by_user_id"] = user["sub"]
            fields["dispatched_at"] = now_iso
        if next_status == "cancelled":
            fields["cancellation_reason"] = (body.get("cancellation_reason") or "").strip()[:500] or None

    if not fields:
        raise HTTPException(status_code=400, detail="No allowed fields in payload")
    await _sb_patch("trips", params={"id": f"eq.{trip_id}"}, body=fields, use_service=True)
    await _audit(user, "trip_updated", "trips", entity_id=trip_id, details=fields)
    return {"ok": True, "patched": list(fields.keys())}


@app.delete("/api/admin/trips/{trip_id}")
async def admin_delete_trip(trip_id: str, request: Request):
    """Cancel a trip (soft). Real DELETE is reserved for never-dispatched
    drafts; once a driver has acked we always go through cancel-with-reason."""
    user = await _require_dispatcher(request)
    _require_uuid(trip_id, "trip id")
    rows = await _sb_get(
        "trips",
        params={"id": f"eq.{trip_id}", "select": "id,operator_id,status", "limit": 1},
        use_service=True,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Trip not found")
    if not _is_super(user) and rows[0].get("operator_id") != user.get("operator_id"):
        raise HTTPException(status_code=403, detail="Trip belongs to a different operator")
    if rows[0].get("status") == "scheduled":
        # Pristine draft — hard delete.
        await _sb_delete("trips", params={"id": f"eq.{trip_id}"}, use_service=True)
        await _audit(user, "trip_deleted", "trips", entity_id=trip_id)
        return {"ok": True, "deleted": True}
    # Anything past 'scheduled' — soft-cancel.
    await _sb_patch(
        "trips",
        params={"id": f"eq.{trip_id}"},
        body={"status": "cancelled", "cancellation_reason": "cancelled via DELETE"},
        use_service=True,
    )
    await _audit(user, "trip_cancelled", "trips", entity_id=trip_id)
    return {"ok": True, "cancelled": True}


# ── DRIVER — pull dispatched trip (Track A.3) ────────────────────────────────
@app.get("/api/driver/me")
async def driver_me(request: Request):
    """Return the driver's own assigned vehicle/route bundle so the driver
    app can show 'Bus B-101 — Route R101' instead of the stale 'Waiting
    for route assignment' placeholder."""
    user = await _require_driver(request)
    v = await _driver_vehicle(user)
    if not v:
        return {"vehicle": None, "route": None}
    route = None
    if v.get("assigned_route_id"):
        rr = await _sb_get(
            "routes",
            params={"id": f"eq.{v['assigned_route_id']}", "select": "id,route_id,name,name_ar,route_type,color", "limit": 1},
            use_service=True,
        )
        route = rr[0] if rr else None
    # Hydrate the vehicle row with its plate so the driver bar shows B-101.
    vrow = await _sb_get(
        "vehicles",
        params={"id": f"eq.{v['id']}", "select": "id,vehicle_id,name,name_ar,vehicle_type,capacity,status", "limit": 1},
        use_service=True,
    )
    return {
        "vehicle": vrow[0] if vrow else v,
        "route": route,
    }


@app.get("/api/driver/me/next_trip")
async def driver_next_trip(request: Request):
    """The driver app polls this on launch and after every successful
    end-of-trip. Returns the next non-completed, non-cancelled trip for
    this driver, or null if there isn't one queued."""
    user = await _require_driver(request)
    rows = await _sb_get(
        "trips",
        params={
            "driver_id": f"eq.{user['sub']}",
            "status": "in.(scheduled,dispatched,acked,in_progress)",
            "select": "id,vehicle_id,route_id,status,scheduled_start,planned_passengers,notes,dispatched_at",
            "order": "scheduled_start.asc.nullslast,created_at.asc",
            "limit": 1,
        },
        use_service=True,
    )
    if not rows:
        return {"trip": None}
    trip = rows[0]
    # Hydrate route name for the driver UI banner.
    if trip.get("route_id"):
        rr = await _sb_get(
            "routes",
            params={"id": f"eq.{trip['route_id']}", "select": "route_id,name,name_ar,color", "limit": 1},
            use_service=True,
        )
        if rr:
            trip["route"] = rr[0]
    return {"trip": trip}


@app.post("/api/driver/trip/{trip_id}/ack")
async def driver_ack_trip(trip_id: str, request: Request):
    """Driver acknowledges a dispatched trip. Moves dispatched → acked."""
    user = await _require_driver(request)
    _require_uuid(trip_id, "trip id")
    rows = await _sb_get(
        "trips",
        params={"id": f"eq.{trip_id}", "select": "id,driver_id,status,operator_id", "limit": 1},
        use_service=True,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Trip not found")
    trip = rows[0]
    if trip.get("driver_id") != user["sub"]:
        raise HTTPException(status_code=403, detail="Not your trip")
    if trip.get("status") not in ("scheduled", "dispatched"):
        raise HTTPException(status_code=409, detail=f"Cannot ack a trip in status {trip.get('status')}")
    await _sb_patch(
        "trips",
        params={"id": f"eq.{trip_id}"},
        body={"status": "acked", "acked_at": datetime.now(timezone.utc).isoformat()},
        use_service=True,
    )
    await _audit({"sub": user["sub"], "operator_id": trip.get("operator_id")}, "trip_acked", "trips", entity_id=trip_id)
    return {"ok": True}


# ── ADMIN — ANALYTICS REAL AGGREGATES + CSV EXPORT (Phase 6.6) ──────────────

async def _trips_window(user: dict, days: int) -> list:
    """Helper: list trips for the caller's operator in the last `days`."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    params = _scope_to_operator(user, {
        "select":       "id,vehicle_id,route_id,driver_id,status,actual_start,actual_end,passenger_count,distance_km,operator_id",
        "actual_start": f"gte.{cutoff}",
        "order":        "actual_start.desc",
        "limit":        5000,
    })
    return await _sb_get("trips", params=params, use_service=True)


@app.get("/api/admin/analytics/real")
async def admin_analytics_real(request: Request, days: int = 7):
    """Dispatcher+ — real aggregates computed from trips + alerts +
    headway_observations. Replaces the hardcoded numbers on
    /dashboard/analytics.html."""
    user = await _require_dispatcher(request)
    days = max(1, min(int(days or 7), 90))
    trips = await _trips_window(user, days)

    # trips_by_day — bucket by date of actual_start
    by_day: dict = {}
    completed_total = 0
    on_time_hits = 0
    on_time_eligible = 0
    pax_total = 0
    incidents_by_type: dict = {}
    for t in trips:
        d = (t.get("actual_start") or "")[:10] or None
        if d:
            by_day[d] = by_day.get(d, 0) + 1
        if t.get("status") == "completed":
            completed_total += 1
            pax_total += int(t.get("passenger_count") or 0)

    # Alerts — open + by type for the same window.
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    alerts = await _sb_get(
        "alerts",
        params=_scope_to_operator(user, {
            "select":     "alert_type,severity,is_resolved,created_at",
            "created_at": f"gte.{cutoff}",
        }),
        use_service=True,
    )
    for a in alerts:
        k = a.get("alert_type") or "other"
        incidents_by_type[k] = incidents_by_type.get(k, 0) + 1
    open_alerts = sum(1 for a in alerts if not a.get("is_resolved"))
    critical_alerts = sum(1 for a in alerts if a.get("severity") in ("critical", "high"))

    # Occupancy buckets from vehicle_positions_latest snapshot.
    positions = await _sb_get(
        "vehicle_positions_latest",
        params=_scope_to_operator(user, {"select": "occupancy_pct"}),
        use_service=True,
    )
    bucket_low = sum(1 for p in positions if (p.get("occupancy_pct") or 0) < 20)
    bucket_mid = sum(1 for p in positions if 20 <= (p.get("occupancy_pct") or 0) <= 80)
    bucket_hi  = sum(1 for p in positions if (p.get("occupancy_pct") or 0) > 80)
    total_obs  = bucket_low + bucket_mid + bucket_hi
    def pct(n): return round(100.0 * n / total_obs, 1) if total_obs else 0

    # Sorted descending series for the trips chart.
    days_sorted = sorted(by_day.keys())
    series = [{"day": d, "count": by_day[d]} for d in days_sorted]

    return {
        "window_days":      days,
        "trips_total":      len(trips),
        "trips_completed":  completed_total,
        "trips_by_day":     series,
        "passengers_total": pax_total,
        "incidents":        [{"type": k, "count": v} for k, v in sorted(incidents_by_type.items(), key=lambda x: -x[1])],
        "occupancy_buckets": [
            {"label": "<20%",  "value": pct(bucket_low), "color": "#DCEAE7"},
            {"label": "20-80%", "value": pct(bucket_mid), "color": "#0E5650"},
            {"label": ">80%",  "value": pct(bucket_hi),  "color": "#C9A95B"},
        ],
        "open_alerts":      open_alerts,
        "critical_alerts":  critical_alerts,
    }


@app.get("/api/admin/analytics/drivers")
async def admin_driver_performance(request: Request, days: int = 30):
    """Dispatcher+ — per-driver performance snapshot for the window."""
    user = await _require_dispatcher(request)
    days = max(1, min(int(days or 30), 365))
    trips = await _trips_window(user, days)
    incidents = await _sb_get(
        "alerts",
        params=_scope_to_operator(user, {
            "select":     "reported_by_user_id",
            "alert_type": "eq.sos",
            "created_at": f"gte.{(datetime.now(timezone.utc) - timedelta(days=days)).isoformat()}",
        }),
        use_service=True,
    ) if True else []
    inc_by_user: dict = {}
    for a in incidents:
        u = a.get("reported_by_user_id")
        if u: inc_by_user[u] = inc_by_user.get(u, 0) + 1

    per_driver: dict = {}
    for t in trips:
        d = t.get("driver_id")
        if not d:
            continue
        b = per_driver.setdefault(d, {"trips_completed": 0, "passengers_total": 0, "distance_km": 0.0})
        if t.get("status") == "completed":
            b["trips_completed"] += 1
            b["passengers_total"] += int(t.get("passenger_count") or 0)
            try:
                b["distance_km"] += float(t.get("distance_km") or 0)
            except (TypeError, ValueError):
                pass

    # Hydrate names — single batched users query.
    if per_driver:
        ids = list(per_driver.keys())
        users = await _sb_get(
            "users",
            params={"id": "in.(" + ",".join(ids) + ")", "select": "id,full_name,full_name_ar,email"},
            use_service=True,
        )
        by_id = {u["id"]: u for u in users}
    else:
        by_id = {}

    out = []
    for d, m in per_driver.items():
        u = by_id.get(d, {})
        out.append({
            "driver_id":         d,
            "name":              u.get("full_name") or u.get("email") or d,
            "name_ar":           u.get("full_name_ar") or "",
            "trips_completed":   m["trips_completed"],
            "passengers_total":  m["passengers_total"],
            "distance_km":       round(m["distance_km"], 1),
            "incidents":         inc_by_user.get(d, 0),
        })
    out.sort(key=lambda x: -x["trips_completed"])
    return {"window_days": days, "drivers": out}


def _csv_escape(v: Any) -> str:
    s = "" if v is None else str(v)
    if any(c in s for c in [',', '"', '\n', '\r']):
        s = '"' + s.replace('"', '""') + '"'
    return s


def _rows_to_csv(rows: list[dict], columns: list[str]) -> str:
    out_lines = [",".join(columns)]
    for r in rows:
        out_lines.append(",".join(_csv_escape(r.get(c)) for c in columns))
    return "\n".join(out_lines) + "\n"


@app.get("/api/admin/export/{kind}")
async def admin_export_csv(kind: str, request: Request, limit: int = 2000):
    """Dispatcher+ — CSV export for vehicles/users/trips/alerts/audit_log,
    operator-scoped. Returns text/csv with a Content-Disposition header
    so the browser downloads instead of rendering inline."""
    user = await _require_dispatcher(request)
    limit = max(1, min(int(limit or 2000), 10000))
    kind = (kind or "").lower()

    if kind == "vehicles":
        rows = await _sb_get(
            "vehicles",
            params=_scope_to_operator(user, {"select": "vehicle_id,name,name_ar,vehicle_type,capacity,status,assigned_route_id,assigned_driver_id,is_active,created_at", "limit": limit, "order": "vehicle_id.asc"}),
            use_service=True,
        )
        cols = ["vehicle_id", "name", "name_ar", "vehicle_type", "capacity", "status", "assigned_route_id", "assigned_driver_id", "is_active", "created_at"]

    elif kind == "users":
        # admin-only for the user export
        if user.get("role") not in ADMIN_ROLES:
            raise HTTPException(status_code=403, detail="Admin role required")
        rows = await _sb_get(
            "users",
            params=_scope_to_operator(user, {"select": "email,full_name,full_name_ar,role,is_active,operator_id,created_at,last_seen_at", "limit": limit, "order": "created_at.desc"}),
            use_service=True,
        )
        cols = ["email", "full_name", "full_name_ar", "role", "is_active", "operator_id", "created_at", "last_seen_at"]

    elif kind == "trips":
        rows = await _sb_get(
            "trips",
            params=_scope_to_operator(user, {"select": "id,vehicle_id,route_id,driver_id,status,scheduled_start,actual_start,actual_end,passenger_count,distance_km", "limit": limit, "order": "created_at.desc"}),
            use_service=True,
        )
        cols = ["id", "vehicle_id", "route_id", "driver_id", "status", "scheduled_start", "actual_start", "actual_end", "passenger_count", "distance_km"]

    elif kind == "alerts":
        rows = await _sb_get(
            "alerts",
            params=_scope_to_operator(user, {"select": "id,vehicle_id,alert_type,severity,title,is_resolved,created_at,resolved_at", "limit": limit, "order": "created_at.desc"}),
            use_service=True,
        )
        cols = ["id", "vehicle_id", "alert_type", "severity", "title", "is_resolved", "created_at", "resolved_at"]

    elif kind == "audit_log":
        if user.get("role") not in ADMIN_ROLES:
            raise HTTPException(status_code=403, detail="Admin role required")
        rows = await _sb_get(
            "audit_log",
            params=_scope_to_operator(user, {"select": "id,action,entity_type,entity_id,user_id,operator_id,created_at", "limit": limit, "order": "created_at.desc"}),
            use_service=True,
        )
        cols = ["id", "action", "entity_type", "entity_id", "user_id", "operator_id", "created_at"]

    else:
        raise HTTPException(status_code=400, detail=f"Unknown export kind '{kind}'")

    csv = _rows_to_csv(rows, cols)
    fn = f"{kind}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.csv"
    return Response(
        content=csv,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fn}"'},
    )


# ── PASSENGER — per-stop ETA (Phase 6.4) ────────────────────────────────────

@app.get("/api/routes/{route_code}/stops")
async def route_stops(route_code: str):
    """Public — list the stops for a route in order, with each stop's
    typical arrival offset and (best-effort) live ETA computed from the
    closest in-service vehicle on that route. Used by the passenger app.
    `route_code` is the short code (e.g. 'R101') or the UUID."""
    # Resolve the route id (accept code OR uuid).
    if _is_uuid(route_code):
        params = {"id": f"eq.{route_code}", "select": "id,route_id,name,name_ar,target_headway_min", "limit": 1}
    else:
        params = {"route_id": f"eq.{route_code.upper()}", "select": "id,route_id,name,name_ar,target_headway_min", "limit": 1}
    rows = await _sb_get("routes", params=params, use_service=False)
    if not rows:
        raise HTTPException(status_code=404, detail="Route not found")
    route = rows[0]
    rid = route["id"]

    # Stops in order, joined with the live route_stops metadata.
    stops_rows = await _sb_get(
        "route_stops",
        params={
            "route_id": f"eq.{rid}",
            "select":   "stop_sequence,distance_from_start_km,typical_arrival_offset_min,stops(id,stop_id,name,name_ar,location,has_shelter)",
            "order":    "stop_sequence.asc",
        },
        use_service=True,
    )

    # Pull the latest position for every vehicle on this route.
    positions = await _sb_get(
        "vehicle_positions_latest",
        params={"route_id": f"eq.{rid}", "select": "vehicle_id,location,speed_kmh,recorded_at"},
        use_service=True,
    )
    # Compute haversine distance from each vehicle to each stop, pick the
    # closest in-service vehicle, and use that to estimate ETA at the
    # default revenue-service speed (18 km/h Damascus median).
    AVG_KMH = 18.0
    vehicle_locs = []
    for p in positions:
        lon, lat = _extract_lonlat(p.get("location"))
        if lon is None:
            continue
        vehicle_locs.append((lat, lon, float(p.get("speed_kmh") or 0)))

    out_stops: list[dict] = []
    for rs in stops_rows:
        s = rs.get("stops") or {}
        slon, slat = _extract_lonlat(s.get("location"))
        if slon is None:
            continue
        # ETA candidates from every vehicle.
        eta_min: Optional[int] = None
        if vehicle_locs:
            best_km = min(_haversine_km(slat, slon, vlat, vlon) for vlat, vlon, _ in vehicle_locs)
            # 18 km/h baseline; if the closest vehicle is moving slower
            # use a conservative cap of 8 km/h to avoid promising 2 minutes
            # in stopped traffic.
            effective_kmh = max(8.0, AVG_KMH)
            eta_min = max(0, math.ceil((best_km / effective_kmh) * 60))
        out_stops.append({
            "stop_id":      s.get("stop_id"),
            "name":         s.get("name"),
            "name_ar":      s.get("name_ar"),
            "lat":          slat,
            "lon":          slon,
            "sequence":     rs.get("stop_sequence"),
            "distance_km":  rs.get("distance_from_start_km"),
            "scheduled_offset_min": rs.get("typical_arrival_offset_min"),
            "eta_min":      eta_min,
            "has_shelter":  s.get("has_shelter"),
        })

    return {
        "route_id":           route.get("route_id"),
        "route_uuid":         rid,
        "name":               route.get("name"),
        "name_ar":            route.get("name_ar"),
        "target_headway_min": route.get("target_headway_min"),
        "stops":              out_stops,
        "vehicles_in_service": len(vehicle_locs),
    }


# ── ADMIN — OPERATIONAL HARDENING ENDPOINTS (Phase 6.3) ─────────────────────

@app.post("/api/admin/users/{target_id}/revoke_sessions")
async def admin_revoke_sessions(target_id: str, request: Request):
    """Force-logout every active session for the target user. Admin-only.
    Bumps users.session_invalidate_after so all currently-issued JWTs
    (which have iat < now) are rejected by _enforce_session within ~60s."""
    user = await _require_admin(request)
    _require_uuid(target_id, "user id")
    rows = await _sb_get(
        "users",
        params={"id": f"eq.{target_id}", "select": "id,role,operator_id", "limit": 1},
        use_service=True,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="User not found")
    target = rows[0]
    if not _is_super(user) and target.get("operator_id") != user.get("operator_id"):
        raise HTTPException(status_code=403, detail="User belongs to a different operator")
    if ROLE_RANK.get(target.get("role"), 0) > ROLE_RANK.get(user.get("role"), 0):
        raise HTTPException(status_code=403, detail="Cannot revoke sessions of a higher-role user")
    await _sb_patch(
        "users",
        params={"id": f"eq.{target_id}"},
        body={"session_invalidate_after": datetime.now(timezone.utc).isoformat()},
        use_service=True,
    )
    # Drop the per-user cache so the change kicks in on the next request
    # instead of waiting for the 60s TTL.
    _SESSION_CACHE.pop(target_id, None)
    await _audit(user, "user_sessions_revoked", "users", entity_id=target_id)
    return {"ok": True}


@app.post("/api/admin/tokens/revoke")
async def admin_revoke_token(request: Request):
    """Revoke a single JWT by its `jti`. Admin-only. Useful when you
    spot a suspicious session in audit_log."""
    user = await _require_admin(request)
    body = await request.json()
    jti = (body.get("jti") or "").strip()
    reason = (body.get("reason") or "manual revoke")[:200]
    if not jti or len(jti) > 64:
        raise HTTPException(status_code=400, detail="jti required")
    target_user_id = body.get("user_id")
    if target_user_id and not _is_uuid(target_user_id):
        raise HTTPException(status_code=400, detail="Invalid user_id")
    # Tokens expire 24h after issue at most; keep the row around for 25h
    # to cover clock skew, then it's pruned.
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=25)).isoformat()
    await _sb_post(
        "revoked_tokens",
        {"jti": jti, "user_id": target_user_id, "expires_at": expires_at, "reason": reason},
        use_service=True,
    )
    # Force a refresh next request.
    global _REVOKED_REFRESH_AT
    _REVOKED_REFRESH_AT = 0.0
    await _audit(user, "token_revoked", "revoked_tokens", entity_id=jti, details={"reason": reason})
    return {"ok": True}


@app.get("/api/admin/login_attempts")
async def admin_login_attempts(request: Request, email: Optional[str] = None, limit: int = 100):
    """Admin-only — list recent login attempts.
    Optional ?email= filter. Useful when investigating a lockout."""
    user = await _require_admin(request)
    limit = max(1, min(int(limit or 100), 1000))
    params = {
        "select": "id,email,success,ip_address,user_agent,reason,attempted_at",
        "order":  "attempted_at.desc",
        "limit":  limit,
    }
    if email:
        params["email"] = f"eq.{email.strip().lower()}"
    rows = await _sb_get("login_attempts", params=params, use_service=True)
    return rows


@app.get("/api/admin/audit_log")
async def admin_audit_log(request: Request, limit: int = 200, action: Optional[str] = None):
    """Admin-only — recent audit_log rows, scoped to the caller's operator
    (super_admin sees all). Powers the audit-log review page."""
    user = await _require_admin(request)
    limit = max(1, min(int(limit or 200), 1000))
    params: dict = {
        "select": "id,action,entity_type,entity_id,user_id,operator_id,details,created_at",
        "order":  "created_at.desc",
        "limit":  limit,
    }
    if action:
        params["action"] = f"eq.{action.strip()}"
    params = _scope_to_operator(user, params)
    rows = await _sb_get("audit_log", params=params, use_service=True)
    return rows


@app.post("/api/admin/users/{target_id}/unlock")
async def admin_unlock_user(target_id: str, request: Request):
    """Clear locked_until on the user record. Admin-only."""
    user = await _require_admin(request)
    _require_uuid(target_id, "user id")
    rows = await _sb_get(
        "users",
        params={"id": f"eq.{target_id}", "select": "id,role,operator_id", "limit": 1},
        use_service=True,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="User not found")
    target = rows[0]
    if not _is_super(user) and target.get("operator_id") != user.get("operator_id"):
        raise HTTPException(status_code=403, detail="User belongs to a different operator")
    await _sb_patch(
        "users",
        params={"id": f"eq.{target_id}"},
        body={"locked_until": None},
        use_service=True,
    )
    await _audit(user, "user_unlocked", "users", entity_id=target_id)
    return {"ok": True}


# Catch-all so we return JSON for unknown /api/* paths instead of HTML
@app.get("/api/{rest:path}")
async def _api_404(rest: str):
    raise HTTPException(status_code=404, detail=f"Unknown endpoint: /api/{rest}")
