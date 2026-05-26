# Security Scan Report — 2026-04-13

**Audit performed by:** Debug Tester Agent ([DAM-410](/DAM/issues/DAM-410))
**Codebase:** `/Users/yahya/Desktop/TransitSystem`
**Date:** 2026-04-13
**Previous scan:** [Security_Scan_2026-04-06.md](Security_Scan_2026-04-06.md) (DAM-318)

---

## Executive Summary

This is the second weekly security audit. Since the 2026-04-06 scan, **three of six critical/high findings have been resolved**. Two persistent highs remain open (X-Forwarded-For bypass, rate limit fails open). Two new medium findings were identified. No new critical findings were introduced.

**Dependency audit (pip-audit):** No known CVEs found in `requirements.txt`.

---

## Fix Status from 2026-04-06 Scan

| ID | Finding | Status |
|----|---------|--------|
| C1 | Error info disclosure via `str(e)` | **FIXED** — `api/core/database.py` now returns "Internal server error" |
| C2 | Traccar webhook bypass (`return True`) | **FIXED** — `api/routers/traccar.py` now raises HTTP 503 if secret not configured |
| C3 | Temporary password sent plaintext via email | **FIXED** — `api/routers/auth.py` uses time-limited reset token + SHA-256 hash |
| H1 | X-Forwarded-For spoofing bypasses rate limits | **OPEN** — `api/core/cache.py:104–107` unchanged |
| H2 | Rate limit fails open when Redis unavailable | **OPEN** — `api/core/cache.py:77–100` still returns `True` on exception |
| H3 | JWT secret startup validation too weak (32-char min, no startup halt) | **PARTIAL** — validation present at request time, still no hard startup failure |
| H4 | Traccar webhook errors expose internal details | **FIXED** — webhook errors are now generic |
| M1 | No token revocation on password change | **OPEN** |
| M2 | HTTP localhost in CORS (damascus-transit-platform) | **N/A** — not applicable to main app |
| M3 | Operator ID not validated against current user | **OPEN** |
| M4 | Optional auth may hide authorization gaps | **OPEN** |
| L1–L4 | Low findings | **OPEN** |

---

## Summary of Current State

| Severity | Count |
|----------|-------|
| HIGH | 2 (persistent from last scan) |
| MEDIUM | 4 (2 persistent + 2 new) |
| LOW | 3 (persistent) |
| **Total open** | **9** |
| **Fixed since last scan** | **5** |

---

## HIGH Findings (Persistent)

### H1 — Rate Limiting Bypass via X-Forwarded-For Spoofing
- **File:** `api/core/cache.py:104–107`
- **Status:** OPEN (unchanged since 2026-04-06)
- **Issue:**
  ```python
  forwarded_for = request.headers.get("x-forwarded-for", "")
  if forwarded_for:
      return forwarded_for.split(",")[0].strip()
  ```
  The first IP in `X-Forwarded-For` is used for rate-limit key construction without verifying it came from a trusted proxy. Any client can spoof this header.
- **Risk:** Brute-force on login, registration, and password reset endpoints by cycling through fake source IPs.
- **Fix:** Configure FastAPI's `trusted_proxies` or validate against a known Vercel proxy IP range. Only trust the rightmost IP added by a known proxy.

### H2 — Rate Limit Fails Open When Redis is Unavailable
- **File:** `api/core/cache.py:77–100`
- **Status:** OPEN (unchanged since 2026-04-06)
- **Issue:** When Redis is unreachable, all rate limiting silently disables (`return True`).
- **Risk:** Redis outage disables all brute-force protections across login, registration, password reset, and feedback endpoints.
- **Fix:** Return HTTP 503 or use a thread-local in-memory fallback `defaultdict(deque)` with a short window instead of failing open.

---

## MEDIUM Findings

### M1 — No Token Revocation on Password Change (Persistent)
- **File:** `api/routers/auth.py` (change-password endpoint)
- **Status:** OPEN
- **Issue:** After changing password, existing JWTs remain valid for up to 24 hours.
- **Risk:** A stolen token cannot be invalidated by a user changing their password.
- **Fix:** Add `password_changed_at` to JWT claims; reject tokens where the stored `password_changed_at` timestamp is newer than the token's `iat`.

### M3 — Operator ID Not Validated Against Current User (Persistent)
- **File:** `api/core/tenancy.py:86–87`, multiple routers
- **Status:** OPEN
- **Issue:** `_op_filter()` filters by operator but does not assert that the requesting user belongs to that operator. A dispatched user with operator A's JWT can potentially craft a query for operator B's data if upstream filtering is incomplete.
- **Fix:** Enforce `current_user.operator_id == requested_operator_id` or `role == "super_admin"` explicitly in each sensitive endpoint.

### M5 — CRON_SECRET Not Documented in `.env.example` (New)
- **File:** `api/routers/cron.py:10`, `.env.example`
- **Issue:** `CRON_SECRET` is used to protect the `/api/cron/simulate` endpoint but is not listed in `.env.example`. New deployments may leave it empty, causing the endpoint to reject all requests **or** accept requests if the condition logic is misread.
  ```python
  CRON_SECRET = os.getenv("CRON_SECRET", "")
  if not CRON_SECRET or auth != f"Bearer {CRON_SECRET}":
      raise HTTPException(status_code=401, detail="Invalid cron secret")
  ```
  When `CRON_SECRET=""`, the condition `not CRON_SECRET` is `True` → always 401. This silently disables the cron job in unconfigured deployments rather than failing loudly.
- **Risk:** Operators may miss configuring this secret and silently break the simulation cron job. Medium risk — the endpoint is protected, but the silent failure mode is confusing.
- **Fix:** Add `CRON_SECRET` to `.env.example` with a generation note. Optionally log a warning at startup if empty.

### M6 — JWT Secret Minimum Length Below Recommendation (New)
- **File:** `api/core/auth.py:25`
- **Status:** PARTIAL (H3 from last scan — downgraded to medium as bypass is validated, not startup-fatal)
- **Issue:** The JWT secret requires only 32 characters, but NIST SP 800-131A recommends 256-bit (32-byte) minimum for HMAC-SHA256 in high-value tokens. 32 ASCII chars ≈ 190 bits of entropy, which is below the 256-bit recommendation. Additionally, the check runs at request time, not at startup — a misconfigured deployment won't fail immediately.
- **Fix:** Raise minimum to 64 characters. Add a startup check:
  ```python
  import sys
  _secret = os.getenv("JWT_SECRET", "")
  if not _secret or len(_secret) < 64:
      print("FATAL: JWT_SECRET must be at least 64 characters", file=sys.stderr)
      sys.exit(1)
  ```

---

## LOW Findings (Persistent)

### L1 — PostgREST Queries Built with String Formatting
- **File:** `api/routers/auth.py:49, 115, 186`
- **Status:** MITIGATED via `urllib.parse.quote()`, but pattern remains
- **Risk:** Low — `quote()` is applied consistently. Pattern is a maintenance liability.
- **Fix:** Migrate to Supabase Python client for parameterized query support.

### L3 — No CSRF Protection
- **File:** Global
- **Status:** OPEN (Low risk given JWT-only auth; mitigated by `SameSite` defaults)
- **Fix:** Confirm cookies (if any) use `SameSite=Strict`. Consider CSRF double-submit cookie pattern for any cookie-based flows.

### L4 — No Content Security Policy Headers
- **File:** `api/index.py` middleware
- **Status:** OPEN
- **Fix:** Add CSP and security headers in the response middleware:
  ```python
  response.headers["X-Content-Type-Options"] = "nosniff"
  response.headers["X-Frame-Options"] = "DENY"
  response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
  response.headers["Content-Security-Policy"] = "default-src 'self'"
  ```

---

## Informational

### I1 — No Secrets Committed to Git
- **Status:** GOOD — `.env`, `.env.local`, `.env.production` are all in `.gitignore`. Only template files (`.env.example`, `.env.ministry.example`) are tracked. No actual credentials found in any committed files.

### I2 — Dependency Audit: No Known CVEs
- **Tool:** pip-audit 2.10.0
- **Requirements:** `requirements.txt` (fastapi, httpx, PyJWT, bcrypt, pydantic, etc.)
- **Result:** No known vulnerabilities found.
- **Status:** GOOD — all dependencies are current.

### I3 — Auth Module: Good Practices Observed
- bcrypt used for password hashing (good, not MD5/SHA1)
- Constant-time comparison (`hmac.compare_digest`) used in Traccar webhook verification
- Password reset tokens hashed with SHA-256 before storage (raw token sent only via email)
- Login returns generic "Invalid credentials" regardless of whether user/password is wrong (no user enumeration)

---

## Priority Action Plan

| Priority | ID | Finding | Owner |
|----------|----|---------|-------|
| 1 — High | H1 | X-Forwarded-For rate limit bypass | Backend |
| 2 — High | H2 | Rate limit fails open on Redis outage | Backend |
| 3 — Medium | M6 | JWT secret length minimum + startup check | Backend |
| 4 — Medium | M1 | Token revocation on password change | Backend |
| 5 — Medium | M5 | CRON_SECRET missing from .env.example | DevOps |
| 6 — Medium | M3 | Operator isolation enforcement | Backend |
| 7 — Low | L4 | Add security response headers | Backend |
| 8 — Low | L1 | Migrate to Supabase client | Backlog |
| 9 — Low | L3 | CSRF hardening | Backlog |
