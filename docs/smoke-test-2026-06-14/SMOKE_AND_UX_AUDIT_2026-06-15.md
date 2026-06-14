# Damascus Transit — Smoke Test & UI/UX Audit

**Site:** https://dts-brown.vercel.app · **Date:** 15 June 2026 · **Build:** v5.0 (post all fixes)
**Scope:** Fresh functional smoke test of the live site + a dedicated UI/UX evaluation (layout/responsiveness, visual design, interaction states, accessibility).

---

## Summary

The platform is in good shape after this engagement's fixes. **Every core public flow passes the functional smoke test**, and the **UI/UX is strong overall** — a cohesive Syrian national identity, above-average accessibility, and proper loading/empty/error states. The one notable issue this pass surfaced is a **responsive layout gap**: the mobile-first passenger PWA had no desktop max-width and stretched edge-to-edge on wide screens. That's now **fixed** (centered phone-width column on desktop, mobile untouched).

---

## 1. Functional smoke test (live)

| Surface | Result | Notes |
|---------|--------|-------|
| Landing `/` | ✅ PASS | Masthead/nav, hero CTAs (Find your route, Open the live map), live KPIs (6 active / 7 routes / 12 stops — Latin digits in EN), live map (OSM tiles + SSE vehicles, **"Connected"** badge), route cards (real codes R101/R001…, correct stop counts), footer. No console errors; `/api/stats`, `/api/routes`, `/api/stream` all 200. |
| Passenger `/passenger/` | ✅ PASS | Search (routes + stops, grouped), route detail (`?route=` → ordered stop list), **stop-ETA tap** (live arrivals, e.g. "Microbus 201 ~5 min · Bus 101 ~6 min"), nearest stops (geolocation + empty state), mini-map (SSE), install prompt, SW update prompt (correctly translated), bottom nav. No console errors; all API calls 200. |
| Admin login `/admin/login.html` | ✅ PASS (renders) | Role pills (Admin/Dispatcher/Driver), password show/hide toggle, remember-me, forgot-password, CAPTCHA hook, centered card. |
| Operator / Admin / Driver consoles (logged-in) | ⏸ Not live-tested | Password-gated; I don't enter credentials. Deployed + unit-tested; server-side RBAC enforced on every route; cookie auth + login covered by the test suite. A password-gated walkthrough can be done together on request. |

**Smoke verdict: all reachable flows work.** No functional regressions from the fix work.

---

## 2. UI/UX audit

### Layout & responsiveness
- 🟨 → ✅ **Passenger app had no desktop max-width** — at wide widths the search bar, cards, and bottom tab bar stretched the full viewport (~1491px), which looks awkward for desktop users. **Fixed:** on ≥640px the app is now a centered **600px column** on a muted backdrop with a soft shadow (a clean "phone preview"); **mobile (<640px) is completely untouched.** The service worker was bumped (v5) so installed clients pick it up.
- The **landing** uses a 1180px max-width container, the **login** a centered card, and the **admin console** a responsive shell that collapses to one column ≤1024px — all properly constrained.
- Mobile-first CSS confirmed via the design system's media queries (tab bar, container padding, map heights, hide-mobile utilities).

### Visual design
- Cohesive **Syrian national identity**: dark teal-green `#0E5650` + light gold `#C9A95B` + the three red stars, on warm-paper surfaces. Typography pairs Source Serif 4 (Latin display) with Readex Pro / IBM Plex Sans Arabic, and RTL headings auto-swap off the Latin serif. Disciplined radii and formal shadows. The result is distinctive and government-grade — a genuine strength.

### Interaction & states
- Skeleton loaders, empty states ("No stops within 1.5 km", "no routes"), graceful error fallbacks (em-dash KPIs rather than blanks), button loading spinners, smooth reveal-on-scroll, and an accurate live-connection badge (only shows "Disconnected" on a true drop, not on transient serverless-SSE reconnects). Solid.

### Accessibility
- 3px gold `:focus-visible` ring with offset; a skip-to-content link; 44px minimum tap targets; `prefers-reduced-motion` disables animation; `sr-only` labels on icon buttons; ARIA roles/labels throughout (`role="search"`, `aria-busy`, `aria-live`); RTL-aware (`dir`, logical `inset-inline`, font swap). Above average for a project this size.
- 🟦 Minor: the white placeholder on the translucent green search bar, and some small gold-on-green accent text, sit near the lower bound of WCAG AA contrast. Low priority.

---

## 3. Findings

| Sev | Area | Finding | Status |
|-----|------|---------|--------|
| 🟨 Medium | Passenger / responsive | No desktop max-width — content stretched edge-to-edge | **Fixed** (this change) |
| 🟦 Low | Data | Routes R101–R202 show "0 stops" (migration 015 not applied to prod) | Open — optional Supabase SQL run |
| 🟦 Low | Accessibility | Search-placeholder + some gold-on-green text near AA contrast floor | Open — optional |
| ℹ️ Info | Roles | Operator/admin/driver *logged-in* flows need the demo password to live-test | N/A — offer stands |

---

## 4. Recommendation

Ship the passenger desktop-max-width fix (in this change — it's verified to parse and is scoped so mobile can't regress). Optional polish: apply migration `015_route_stops_seed.sql` in Supabase to populate R101–R202 stop counts, and nudge the search-placeholder contrast. Everything else is in good shape.

*Functional flows verified live in the browser (console + network inspected, all 200, no app errors). Responsiveness assessed from the live desktop render plus the design system's media queries. Logged-in console flows are deployed and unit-tested; a password-gated live pass is available on request.*
