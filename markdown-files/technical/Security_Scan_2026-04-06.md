# Security Scan Report — 2026-04-06

**Audit performed by:** Debug Tester Agent (DAM-318)
**Codebase:** `/Users/yahya/Desktop/TransitSystem`
**Date:** 2026-04-06

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 3 |
| HIGH | 4 |
| MEDIUM | 4 |
| LOW | 4 |
| Informational | 2 |
| **Total** | **17** |

---

## CRITICAL Findings

### C1 — Error Information Disclosure
- **Files:** `api/core/database.py` lines 46, 61, 77, 88, 104 · `api/routers/auth.py` line 85 · `api/routers/routes.py` line 87
- **Issue:** Exception details are directly exposed to clients via `detail=str(e)` in HTTPException responses. Database errors, stack traces, and internal implementation details leak to clients.
- **Example:**
  ```python
  raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")
  ```
- **Risk:** Information disclosure allows attackers to understand system internals, database schema, and exploit patterns.
- **Fix:**
  ```python
  logger.error(f"Database error: {str(e)}", exc_info=True)
  raise HTTPException(status_code=500, detail="Internal server error")
  ```

### C2 — Traccar Webhook Signature Verification Bypass
- **File:** `damascus-transit-platform/api/routes/traccar.py` lines 27–28
- **Issue:** Signature verification is skipped when `TRACCAR_WEBHOOK_SECRET` is not set:
  ```python
  if not TRACCAR_WEBHOOK_SECRET:
      return True  # Skip verification if no secret configured
  ```
- **Risk:** Without a configured secret, any attacker can send spoofed Traccar webhook requests to inject false GPS positions, create fake alerts, or manipulate vehicle data.
- **Fix:** Make the secret mandatory — remove the bypass and raise an error on startup if not configured.

### C3 — Temporary Password Sent Plaintext via Email
- **File:** `api/routers/auth.py` lines 184–206
- **Issue:** The `forgot_password` endpoint generates a temporary password and emails it in plaintext. Emails are often logged, retained, and may be intercepted.
- **Risk:** Compromised email account = compromised transit system account. No expiry on the temporary password.
- **Fix:** Replace with time-limited reset tokens (UUID or signed JWT, valid 30 minutes). User clicks a link to set their own new password.

---

## HIGH Findings

### H1 — Rate Limiting Bypass via X-Forwarded-For Spoofing
- **File:** `api/core/cache.py` lines 103–109
- **Issue:** Rate limiting uses the first value of the `X-Forwarded-For` header without validating it came from a trusted proxy.
  ```python
  forwarded_for = request.headers.get("x-forwarded-for", "")
  if forwarded_for:
      return forwarded_for.split(",")[0].strip()
  ```
- **Risk:** Attackers can send arbitrary `X-Forwarded-For` values to bypass login rate limiting (5 attempts/min), password reset limiting, and other protections — enabling brute force.
- **Fix:** Only trust `X-Forwarded-For` from known proxy IPs. Validate IP format before use.

### H2 — Rate Limiting Fails Open When Redis is Unavailable
- **File:** `api/core/cache.py` lines 86–100
- **Issue:** Rate limiting silently disables itself if Redis is unreachable:
  ```python
  if client is None:
      return True  # No limit if Redis is down!
  ```
- **Risk:** Redis outage = all brute-force protections disabled on login and password reset.
- **Fix:** Either return HTTP 503 when Redis is unavailable, or use a local in-memory fallback with a short window.

### H3 — JWT Secret Validation Weakness
- **File:** `api/core/auth.py` lines 24–30
- **Issue:** JWT secret is only checked for length ≥ 32 and a small hardcoded placeholder list. Startup does not halt if the check fails.
- **Risk:** A misconfigured deployment could run with a weak or empty JWT secret, making all tokens forgeable.
- **Fix:** Add a hard startup assertion:
  ```python
  JWT_SECRET = os.getenv("JWT_SECRET")
  if not JWT_SECRET or len(JWT_SECRET) < 64:
      raise RuntimeError("JWT_SECRET must be at least 64 chars — run: openssl rand -hex 32")
  ```

### H4 — Traccar Webhook Errors Expose Internal Details
- **Files:** `api/routers/traccar.py` line 86 · `damascus-transit-platform/api/routes/traccar.py` line 162
- **Issue:** Exception messages are returned to callers in webhook error responses:
  ```python
  return {"status": "error", "detail": str(e)}
  ```
- **Fix:** Log internally; return only `{"status": "error"}` to callers.

---

## MEDIUM Findings

### M1 — No Token Revocation on Password Change
- **Files:** `api/routers/auth.py` lines 297–336 · `damascus-transit-platform/api/routes/auth.py` lines 75–125
- **Issue:** When a user changes their password, existing JWTs remain valid for up to 24 hours. A stolen token cannot be revoked by changing the password.
- **Fix:** Add `password_changed_at` timestamp to users. Embed it in the JWT. Reject tokens where `password_changed_at` has advanced since issuance.

### M2 — HTTP localhost Allowed in CORS Config
- **File:** `damascus-transit-platform/api/middleware.py` lines 217–226
- **Issue:** `http://localhost:3000`, `http://localhost:8000`, and `http://localhost:8080` are in the default CORS origins list. If `ALLOWED_ORIGINS` is not properly set in production, HTTP origins are active.
- **Fix:** Filter to HTTPS-only in production:
  ```python
  if os.getenv("ENVIRONMENT") == "production":
      origins = [o for o in origins if o.startswith("https://")]
  ```

### M3 — Operator ID Not Validated in All Endpoints
- **File:** `api/core/tenancy.py` lines 86–87
- **Issue:** `_op_filter()` generates operator filters but does not validate the requesting user belongs to that operator. A dispatcher from operator A could potentially craft requests for operator B's data if a filter is misapplied upstream.
- **Fix:** Explicitly assert `current_user.operator_id == requested_operator_id` or `role == "super_admin"` in all sensitive endpoints.

### M4 — Optional Authentication May Hide Authorization Gaps
- **Files:** Multiple routes using `optional_auth` dependency (alerts.py, stops.py, vehicles.py, routes.py)
- **Issue:** Endpoints accept both authenticated and unauthenticated requests. If filtering logic has a bug, unauthenticated users could see all operators' data.
- **Fix:** Audit each `optional_auth` endpoint to confirm results are correctly scoped. Add comments explaining the intent.

---

## LOW Findings

### L1 — SQL Queries Built with String Formatting (Mitigated)
- **File:** `api/routers/auth.py` lines 43, 107, 176
- **Issue:** PostgREST queries are built with f-strings using `urllib.parse.quote()`.
- **Status:** MITIGATED — `quote()` prevents injection for URL parameters. Not ideal pattern.
- **Fix:** Use the Supabase Python client library for queries instead of manual URL construction.

### L2 — Weak Password Minimum Length at Login
- **File:** `damascus-transit-platform/api/routes/auth.py` line 26
- **Issue:** Login accepts passwords as short as 1 character (`min_length=1`).
- **Fix:** Enforce `min_length=8` at minimum, or align with registration requirements.

### L3 — No CSRF Protection
- **File:** `damascus-transit-platform/api/middleware.py` lines 151–155
- **Issue:** No CSRF token validation. Mitigated somewhat by SameSite cookie behavior, but not explicitly set.
- **Fix:** Ensure cookies use `SameSite=Strict` or `SameSite=Lax`. Add CSRF double-submit cookie pattern if session cookies are used.

### L4 — No Content Security Policy Headers
- **Issue:** No CSP headers are set in API responses.
- **Fix:** Add to middleware:
  ```python
  response.headers["Content-Security-Policy"] = "default-src 'self'"
  ```

---

## Informational

### I1 — No Secrets Committed to Git
- **Status:** GOOD — `.env.example`, `.env.ministry.example`, and `damascus-transit-platform/.env.example` contain only templates. No actual credentials found in any committed files.

### I2 — Dependencies Are Reasonably Current
- FastAPI 0.115+, bcrypt 4.2.1, PyJWT 2.12.0, Pydantic 2.9–2.10 — all current as of audit date.
- **Recommendation:** Pin exact versions in production requirements for reproducibility.

---

## Priority Action Plan

| Priority | Finding | Action |
|----------|---------|--------|
| 1 — Immediate | C1: Error info disclosure | Replace `str(e)` in HTTPException with generic messages |
| 2 — Immediate | C2: Traccar webhook bypass | Make `TRACCAR_WEBHOOK_SECRET` mandatory; remove bypass |
| 3 — High | H1: Rate limit X-Forwarded-For bypass | Validate proxy source before trusting header |
| 4 — High | H2: Rate limit fails open | Fail closed or use in-memory fallback |
| 5 — High | C3: Temporary password via email | Replace with time-limited reset token flow |
| 6 — High | H3: JWT secret startup validation | Hard-fail startup if secret is missing or too short |
| 7 — Medium | M1: Token revocation on password change | Add `password_changed_at` JWT claim |
| 8 — Medium | M2: HTTP in CORS | Filter to HTTPS in production |
| 9 — Low | L1–L4 | Address in next sprint |
