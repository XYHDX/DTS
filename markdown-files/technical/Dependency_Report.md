# Dependency Report

## Last Updated: 2026-04-18

## Audit Summary

**Security vulnerabilities:** None found (`pip-audit` — clean)

**Updates available:** 9 of 11 packages have newer versions

---

## Package Status

| Package | Current | Latest | Status |
|---------|---------|--------|--------|
| fastapi | >=0.115.12 | 0.136.0 | Update available |
| httpx | 0.28.1 | 0.28.1 | Up to date |
| PyJWT | 2.12.0 | 2.12.1 | Minor update |
| bcrypt | 4.2.1 | 5.0.0 | **Major update** |
| pydantic | 2.10.6 | 2.13.2 | Update available |
| python-dotenv | 1.0.1 | 1.2.2 | Update available |
| upstash-redis | 1.1.0 | 1.7.0 | Update available |
| gtfs-realtime-bindings | >=1.0.0 | 2.0.0 | **Major update** |
| sentry-sdk | >=2.0.0 | 2.58.0 | Update available |
| pywebpush | >=2.0.0 | 2.3.0 | Update available |
| protobuf | >=4.21.0 | (pinned by gtfs) | — |

---

## Security Assessment

`pip-audit` found **no known CVEs** in the current pinned versions. No critical security patches are required at this time.

---

## Recommendations

**No immediate action required** — no security vulnerabilities detected.

For routine maintenance, consider updating in a future sprint:

- **bcrypt 5.0.0** — major version; review changelog for breaking changes before upgrading
- **gtfs-realtime-bindings 2.0.0** — major version; verify GTFS API compatibility
- **fastapi 0.136.0** — significant feature release; test against existing routes
- **pydantic 2.13.2**, **sentry-sdk 2.58.0**, **upstash-redis 1.7.0** — safe minor/patch updates

---

## History

| Date | Vulnerabilities | Notes |
|------|----------------|-------|
| 2026-04-18 | 0 | Initial report — all clear |
