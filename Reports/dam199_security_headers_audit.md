# DAM-199 Security Headers & CORS Audit
**Date:** 2026-04-02
**Target:** https://syrian-transit-system.vercel.app

---

## CORS Configuration

### Allowed Origin (same domain)
```
Origin: https://syrian-transit-system.vercel.app
→ HTTP 200
   access-control-allow-origin: https://syrian-transit-system.vercel.app
   access-control-allow-credentials: true
   access-control-allow-methods: GET, POST, PUT, DELETE, OPTIONS
   access-control-allow-headers: Accept, Accept-Language, Authorization, Content-Language, Content-Type
   access-control-max-age: 600
```
**PASS** — origin is correctly pinned, not wildcard.

### Disallowed Origin
```
Origin: https://evil.example.com
→ HTTP 400
   (no access-control-allow-origin echoed back)
```
**PASS** — disallowed origins are rejected with 400.

### Main Page (`/`)
```
access-control-allow-origin: *
```
**WARN** — the main HTML page uses wildcard CORS. Acceptable for a public HTML page, but inconsistent with the API's stricter policy. Keep an eye on this if any sensitive data is ever served from the root.

---

## Security Headers Audit

| Header | Status | Value |
|---|---|---|
| `Strict-Transport-Security` | ✅ PASS | `max-age=63072000; includeSubDomains; preload` (2-year HSTS, preload-ready) |
| HTTPS redirect | ✅ PASS | HTTP 308 → HTTPS enforced |
| `Content-Security-Policy` | ❌ MISSING | Not set on any endpoint |
| `X-Frame-Options` | ❌ MISSING | Not set (clickjacking risk) |
| `X-Content-Type-Options` | ❌ MISSING | `nosniff` not set (MIME-sniff risk) |
| `Referrer-Policy` | ❌ MISSING | Not set |
| `Permissions-Policy` | ❌ MISSING | Not set |
| Server version | ✅ PASS | Only "Vercel" exposed, no version |
| API key / token leakage | ✅ PASS | Checked response bodies — none found |

---

## Additional Observations

### Low-Risk Information Disclosure
Response headers expose internal API versioning details:
```
deprecation: true
link: </api/v1/vehicles>; rel="successor-version"
sunset: 2026-09-30
x-api-version: v1
x-vercel-id: fra1::iad1::...   ← Vercel region (fra1=Frankfurt, iad1=US East)
```
- The `sunset` date reveals when the current API version will be deprecated (2026-09-30).
- `x-vercel-id` reveals hosting region. Low risk but unnecessary disclosure.

### `access-control-allow-credentials: true`
Credentials are allowed on CORS. Since origin is pinned (not `*`), this is acceptable — but if CORS origin validation ever regresses to wildcard, this combination would create a serious vulnerability. Worth monitoring.

---

## Recommendations

### P0 — Add `X-Content-Type-Options: nosniff`
One-line header addition in `next.config.js` or Vercel headers config. Prevents MIME-type confusion attacks.

### P1 — Add `X-Frame-Options: DENY` (or `SAMEORIGIN`)
Prevents clickjacking. The transit app UI doesn't need to be embedded in foreign frames.

### P1 — Add `Content-Security-Policy`
Start with a restrictive policy. Suggested starting point:
```
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' https://syrian-transit-system.vercel.app
```
Test thoroughly — inline scripts/styles may require `'unsafe-inline'` adjustments.

### P2 — Add `Referrer-Policy: strict-origin-when-cross-origin`
Prevents full URL leakage in Referer headers to third-party domains.

### P2 — Add `Permissions-Policy`
Disable unused browser features:
```
Permissions-Policy: geolocation=(), camera=(), microphone=()
```

### P2 — Remove or suppress `deprecation`, `sunset`, `x-api-version` headers in public responses
These expose internal roadmap information unnecessarily.

---

## How to Apply (Next.js / Vercel)

Add to `next.config.js`:
```js
const securityHeaders = [
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'X-Frame-Options', value: 'DENY' },
  { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
  { key: 'Permissions-Policy', value: 'geolocation=(), camera=(), microphone=()' },
];

module.exports = {
  async headers() {
    return [{ source: '/(.*)', headers: securityHeaders }];
  },
};
```
CSP requires its own tuning pass — add separately after testing.
