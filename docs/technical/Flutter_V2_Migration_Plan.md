# Flutter v2.0 migration plan

> Step 100 of the roadmap. The GitHub milestone "v2.0" is reserved for this work. It stays **open and inactive** until one of the trigger metrics in ADR-001 fires.

## When this milestone opens

Per ADR-001, we move from "Capacitor primary / Flutter parallel" to "Flutter primary" if **any** of the following is true after 30 days of v1.0 pilot:

- More than 5 % of driver shifts lose GPS contact for over 30 seconds on iOS.
- Median map FPS on Android API 28 devices falls below 30.
- Apple rejects the build twice under guideline 4.2.
- iOS crash-free sessions fall below 99 %.

Until at least one fires we are **not** migrating. Keep the Flutter scaffold buildable and current, but ship product on the Capacitor track.

## What "Flutter primary" actually means

1. The marketed Android app on the Play Store is the Flutter build.
2. The marketed iOS app on the App Store is the Flutter build.
3. The Capacitor wrapper enters maintenance mode — security fixes only, no new features.
4. The `mobile/` directory remains in the repository for ~3 months as a rollback option, then is moved to a frozen branch.
5. The web admin, dashboard, and analytics pages (`public/admin/`, `public/dashboard/`) stay on HTML/JS unchanged — they were never going to be Flutter.

## Checklist — what must be true before flipping

### Code parity

- [ ] Login flow with biometric, JWT storage, and 401-driven eviction.
- [ ] Passenger home — search, live map, route list, ETAs.
- [ ] Stop nearest list with geolocation permission flow.
- [ ] Schedule view with next-departure callout.
- [ ] Driver home — start/stop trip, passenger counter, four metrics.
- [ ] Driver background GPS using `flutter_background_geolocation` (paid transistorsoft licence acquired).
- [ ] Driver incident-report three-step flow with camera capture.
- [ ] Driver shift summary with reflective copy.
- [ ] Account screen + Settings screen + Alerts inbox.
- [ ] Offline cache via Drift, with sync controller wired from app boot.
- [ ] Push notifications via `firebase_messaging` with `google-services.json` / `GoogleService-Info.plist` in place.
- [ ] Deep links: `damascustransit://` + universal links (Android App Links + iOS associated-domains).
- [ ] AR + EN ARB localisation generated via `flutter gen-l10n`.
- [ ] RTL verified on every screen including dialogs and bottom sheets.

The scaffold already covers the first ~70 % of this list. Verify by running the Playwright equivalent screens for `flutter_app` (a separate `integration_test/` suite — not in this repo yet) on a real device.

### Build + signing

- [ ] Android signing keystore generated, stored in 1Password, env-var injected via the snippet at `mobile/android/app/build.gradle.snippet` (also applies to `flutter_app/android/`).
- [ ] iOS signing identity + provisioning profile created in Apple Developer.
- [ ] Firebase project shared between Capacitor and Flutter so token-to-user pairings survive the migration.
- [ ] CI workflow `.github/workflows/flutter.yml` extended with a release-build matrix on tags.

### Verification

- [ ] Side-by-side spike on a real Pixel 5 + iPhone XR: map FPS, cold start, memory ceiling, background-GPS reliability.
- [ ] Real-world A/B with 50 drivers on Flutter and 50 on Capacitor for two weeks. Compare crash-free rate, incident rate, GPS continuity.
- [ ] Driver focus group of 5 — does the native UX feel better? (Subjective but mandatory.)
- [ ] Sentry release tagging set up for `damascus-transit-flutter@N.N.N` distinct from the Capacitor build.

### Store transition

- [ ] Capacitor build version bumped to a high number (e.g. `1.99.x`) so it remains updatable but cannot conflict with the Flutter v2.0.0 release on the store.
- [ ] Play Store + App Store listings updated with v2 screenshots from the Flutter build (the screenshot order in `mobile/PLAY_STORE_LISTING.md` still applies; the visual identity carries over because the Claude design language is in both).
- [ ] In-app "what's new" sheet for v2.0 explains the rebuild and asks users to report any regressions for two weeks before we sunset Capacitor.

## Estimated work

| Phase | Calendar | Notes |
|---|---|---|
| Parity sprint | 4 weeks | Mostly already done in the scaffold; cover the unchecked items above. |
| Hardening | 2 weeks | Background GPS + push + offline cache stress testing. |
| A/B pilot | 2 weeks | 50/50 split via Play Store + TestFlight internal tracks. |
| Store transition | 1 week | Submission, review, staged rollout. |
| Sunset Capacitor | 12 weeks | Keep `mobile/` updatable on the existing track. |

About **9 calendar weeks** of focused work + 12 weeks of overlap. ~3 months from "we triggered the switch" to "Flutter is the only mobile shell shipping new features".

## What stays the same

The FastAPI backend, the Supabase schema, the web admin, the design system in `public/lib/design-system.css`, the eight CI workflows, the four runbooks, and the entire `ROADMAP_100.md` track stay unchanged across the migration. That is the whole point of the dual-shell strategy: the durable assets are the backend and the design language, both of which are framework-agnostic.

## How to open the milestone in GitHub

```
gh api repos/actuatorsos/SyrianTransitSystem/milestones \
   -f title='v2.0 — Flutter migration' \
   -f description='Tracked plan: markdown-files/technical/Flutter_V2_Migration_Plan.md. Opens when an ADR-001 trigger fires.' \
   -f state=open
```

Then attach the existing `v2.0` label (defined in `.github/labels.yml`) to every issue that becomes blocking for the migration.
