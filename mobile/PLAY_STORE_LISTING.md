# Play Store listing — نقل دمشق (Damascus Transit)

> Updated 2026-05-24 to reflect the Claude-designed UI, the eight CI workflows, the dual mobile-shell strategy (Capacitor v1.0 / Flutter v2.0), and the post-revival feature set.

## App details

| Field | Value |
|---|---|
| **Package** | `sy.gov.damascus.transit` |
| **App name (AR)** | نقل دمشق |
| **App name (EN)** | Damascus Transit |
| **Category** | Maps & Navigation → Public Transport |
| **Content rating** | Everyone |
| **Target countries** | Syria (SY) + MENA region |
| **Default language** | Arabic (ar-SY) |
| **Additional languages** | English (en) |

## Short description (80 chars)

- **AR:** تتبع حافلات دمشق لحظياً — للركاب والسائقين، بدون إعلانات.
- **EN:** Real-time Damascus bus tracking for passengers and drivers — ad-free.

## Full description

### Arabic (primary)

نقل دمشق هو التطبيق الرسمي لتتبّع حافلات النقل العام في مدينة دمشق. مفتوح المصدر، بدون إعلانات، ومُصمَّم ليكون مرافقاً يومياً يحترم وقتك.

**للركاب:**
- خريطة لحظية تعرض الحافلات أثناء حركتها (تحديث كل ٥ ثوانٍ).
- معرفة الموعد المتوقع لوصول الحافلة إلى محطتك.
- البحث عن الخطوط بالاسم العربي أو رقم الخط.
- يعمل دون اتصال — الخطوط والمحطات محفوظة محلياً.
- إشعارات اختيارية حين تقترب الحافلة من محطتك.

**للسائقين:**
- بدء الرحلة بزرّ واحد، عداد ركاب مريح.
- مشاركة الموقع تلقائياً مع المركز.
- دخول آمن ببصمة الإصبع أو Face ID.
- إبلاغ سريع عن الحوادث بثلاث خطوات.
- ملخّص لكل وردية: المسافة، المدة، عدد الركاب، الالتزام بالموعد.

**للمدراء والموزّعين:**
- لوحة تحكم بالأسطول وأدوات حلّ التنبيهات.
- تحليلات أسبوعية لأداء الخطوط والإشغال.
- إدارة الحسابات والصلاحيات.

نقل دمشق مفتوح المصدر تحت رخصة MIT. لا نبيع بياناتك ولا نعرض إعلانات. الموقع المُشارك من السائقين مُجمَّع ومُحايد — لا نعرف اسم الراكب.

### English

Damascus Transit is the open-source companion app for the city's public bus network. Ad-free by design, built to respect your time.

**For passengers**
- A live map of every bus in service, refreshed every five seconds.
- Accurate ETA for every stop, calculated from real GPS positions.
- Route search in Arabic or English.
- Works offline — routes and stops are cached on your device.
- Optional notifications when your bus is getting close.

**For drivers**
- One-tap trip start and a comfortable passenger counter.
- Automatic background GPS reporting.
- Biometric sign-in (fingerprint or Face ID).
- A three-step incident report flow with photos.
- A shift summary at the end of every trip — distance, duration, passengers, on-time rate.

**For dispatchers and admins**
- A fleet dashboard with live map and alert queue.
- Weekly analytics on route performance and occupancy.
- User and permission management.

Damascus Transit is MIT-licensed open source. We don't sell your data and we never show ads. Driver positions are aggregated and anonymous — we don't know who the passenger is.

## What's new (release v1.0.0)

- Claude-designed UI: warm cream surface, calm coral accent, serif headlines, generous whitespace.
- Onboarding flow that explains the app in three friendly screens.
- Driver shift summary with reflective end-of-trip copy.
- New Account, Settings, Nearby, Schedule, and Alerts screens.
- Offline cache via Drift — routes and stops survive a flaky connection.
- Stronger backend security: JWT revocation on password change, rate limiter with in-memory fallback.

## Screenshots

Required: 5 portrait screenshots minimum, 1080 × 1920 or larger, PNG.

Recommended order (English copy underneath each — translate in the console):

1. **Live map** — vehicle markers, live dot indicator, calm warm UI.
2. **Nearest stops** — distance anchor in serif, friendly route chips.
3. **Schedule** — next-departure callout, upcoming list.
4. **Driver trip controls** — passenger counter, four-tile metrics.
5. **Shift summary** — large serif passenger count, reflective copy.
6. **Onboarding** — calm cream illustrations, warm intro text.

Capture once you've built a release APK and run the app on a Pixel-class screen at 1080 × 2400. The Lighthouse CI workflow checks colour-contrast at AA on every PR so the screenshots will reflect the actual ship state.

## Feature graphic (1024 × 500)

Solid cream background `#F5F1EA`. Single coral wordmark **نقل دمشق** in serif on the right, three calm illustrated icons (compass, pulse, offline) on the left. No people, no buses — calm is the message.

## Privacy

- **Data collected:** account email, optional name, role.
- **Sensitive permissions:**
  - Location (foreground + background) — drivers only, for sharing the bus position. Passengers can opt in for proximity notifications.
  - Camera — drivers only, for incident photos. Optional.
  - Biometric — drivers only, to unlock the app.
  - Push (FCM/APNs) — optional for all users.
- **Data shared:** none with third parties. GPS positions are stored anonymously in our database and broadcast via SSE without user identifiers.
- **Privacy policy:** https://damascustransit.sy/privacy
- **Data deletion:** https://damascustransit.sy/delete-account

## Target API / SDKs

| Item | Value |
|---|---|
| **Min SDK** | Android 8 (API 26) |
| **Target SDK** | Android 14 (API 34) |
| **Build SDK** | 34 |
| **Architectures** | arm64-v8a, armeabi-v7a, x86_64 |
| **Output** | Android App Bundle (.aab) |

## Signing

Signing keystore is **not** in the repository. It lives in 1Password under `DamascusTransit / Android signing`. Build environment loads it via the four env vars in `mobile/BUILD.md`.

## Release channels

- **Internal testing** — used continuously during the v1.0 stabilisation window.
- **Closed testing** — pilot drivers and passengers (≤200) for two weeks.
- **Open testing** — once Sentry shows no new HIGH issues for seven days.
- **Production** — full rollout, 10% → 50% → 100% over five days.

## Country availability

Initial release: Syria only. Expansion to MENA region tracked in `ROADMAP_100.md` step 100.

## Contact

- Developer: 3D Titans
- Support: support@damascustransit.sy
- Repo: https://github.com/actuatorsos/SyrianTransitSystem
