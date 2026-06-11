# ADR-001 — Mobile shell strategy: Capacitor for v1.0, Flutter as v2.0 candidate

> **STATUS UPDATE (2026-06-11): SUPERSEDED.** Flutter (`flutter_app/`) was chosen as the single official mobile app; the Capacitor shell was retired to `archives/legacy-snapshots-2026-06-11.zip`. The analysis below is kept for the record.

- **Status:** Accepted
- **Date:** 2026-05-24
- **Deciders:** 3dtitans (project owner), Claude (advisory)
- **Supersedes:** —

## Context

DamascusTransit needs native Android and iOS apps for passengers and drivers. Three credible paths exist:

1. **Capacitor 6 wrap** of the existing PWAs (already 70 % scaffolded in `mobile/`).
2. **Flutter 3.22 rewrite** of the passenger and driver clients (scaffolded in `flutter_app/`).
3. **PWA only** — no native shell.

A full head-to-head benchmark lives in `Benchmark_Report.docx`. The key tradeoffs:

- Capacitor reaches the Play Store in 3–4 weeks because the bridge layer, manifests, and native projects already exist. Flutter takes 9–12 weeks of focused work to reach parity.
- Flutter rendering and background-GPS reliability on iOS are measurably better, particularly on low-end devices and during long driver shifts.
- The web admin (`public/admin/`) and public dashboard (`public/index.html`) stay on HTML/JS under any path. A Flutter rewrite does not eliminate JavaScript from the project.
- Distribution friction from Syria (Apple/Google developer billing) is identical across paths — it does not motivate the choice.

## Decision

Adopt a **two-stage** strategy:

- **v1.0 ships on Capacitor.** Finish `mobile/` and submit to the Play Store. iOS distribution starts via TestFlight once Apple Developer Program enrolment clears, which is independent of framework.
- **`flutter_app/` is preserved as a parallel, working scaffold.** It does not ship in v1.0 but is exercised in CI (`.github/workflows/flutter.yml`) and kept buildable.
- **The trigger to switch to Flutter as primary mobile client is pre-committed** so the decision is not framework-aesthetic. Switch if, during the first 30 days of v1.0 pilot, any of the following is true:
  - more than 5 % of driver shifts lose GPS contact for over 30 seconds on iOS,
  - median map FPS on Android API 28 devices falls below 30,
  - Apple rejects the build twice under guideline 4.2,
  - iOS crash-free sessions fall below 99 %.

## Consequences

### Positive

- Time-to-market is measured in weeks rather than months.
- The Capacitor work in `mobile/` is no longer sunk cost.
- The FastAPI backend, Supabase schema, and admin UI are unchanged under any future framework switch — the decision is reversible.
- Flutter remains a credible v2.0 path with a real codebase to point at, not just a plan.

### Negative

- Two mobile codebases briefly co-exist in the repository. CI runs both build pipelines, increasing CI minutes.
- Drivers using older iPhones may see WebView GPU memory pressure under long shifts. This is the leading reason we may flip to Flutter later.
- Hiring profile favours web developers, which is consistent with the rest of the codebase but biases against a future Dart-heavy direction.

## Alternatives considered

- **Flutter first.** Rejected on time-to-market and the existence of the working Capacitor scaffold. Would have discarded ~1,300 LOC of JS/HTML that already powers the PWAs.
- **PWA only.** Rejected because driver background GPS on iOS Safari is unreliable and store presence matters for passenger discovery.
- **React Native.** Not considered seriously because no existing scaffolding exists, the team has no RN experience, and Flutter's map ecosystem is stronger for our use case.

## Follow-up

- ADR-002 will cover the SSE-vs-WebSocket choice (currently SSE).
- ADR-003 will cover the rate-limiter fail-closed semantics (currently in-memory fallback when Redis is unreachable).
- A v2.0 milestone is created in GitHub with the Flutter migration checklist; it remains open until one of the switch triggers fires.
