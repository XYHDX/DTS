# Mobile Build Guide — Damascus Transit (Capacitor 6)

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Node.js | ≥18 | `nvm install 18` |
| Android Studio | Hedgehog (2023.1.1) or later | [developer.android.com](https://developer.android.com/studio) |
| Xcode | ≥15.0 | Mac App Store |
| CocoaPods | ≥1.14 | `sudo gem install cocoapods` |
| JDK | 17 | `brew install openjdk@17` |

---

## First-time setup

```bash
# 1. Install JS dependencies from the mobile/ directory
cd mobile
npm install

# 2. Sync Capacitor (copies web assets + plugins into native projects)
npx cap sync android
npx cap sync ios

# 3. Install iOS CocoaPods
cd ios/App && pod install && cd ../..
```

---

## Firebase setup (required for push notifications)

### Android
1. Go to [Firebase Console](https://console.firebase.google.com) → damascus-transit project
2. Add Android app: package `sy.gov.damascus.transit`
3. Download `google-services.json`
4. Place at `android/app/google-services.json` (gitignored)

### iOS
1. Same Firebase project → Add iOS app: bundle `sy.gov.damascus.transit`
2. Download `GoogleService-Info.plist`
3. Place at `ios/App/App/GoogleService-Info.plist` (gitignored)
4. Enable Push Notifications capability in Xcode → App target → Signing & Capabilities

---

## Android builds

### Debug APK (for local testing)
```bash
cd mobile
npx cap sync android
cd android
./gradlew assembleDebug
# Output: android/app/build/outputs/apk/debug/app-debug.apk
```

### Release APK (sideload / direct distribution)
```bash
# Set keystore env vars (or configure in android/app/build.gradle signingConfigs)
export KEYSTORE_PATH=/path/to/damascus-transit.jks
export KEYSTORE_PASSWORD=...
export KEY_ALIAS=damascus-transit
export KEY_PASSWORD=...

cd mobile/android
./gradlew assembleRelease
# Output: android/app/build/outputs/apk/release/app-release.apk
```

### Release AAB (Play Store submission)
```bash
cd mobile/android
./gradlew bundleRelease
# Output: android/app/build/outputs/bundle/release/app-release.aab
```

---

## iOS builds

### Open in Xcode
```bash
cd mobile
npx cap open ios
# This opens ios/App/App.xcworkspace in Xcode (use .xcworkspace, not .xcodeproj)
```

### Archive for TestFlight / App Store
1. In Xcode: Product → Archive
2. Distribute App → App Store Connect
3. Upload

### Export IPA (Ad Hoc)
1. Product → Archive → Distribute App → Ad Hoc
2. Select distribution certificate and provisioning profile
3. Export IPA

---

## After web changes

Run `npx cap sync` (from `mobile/`) after any changes to `public/`:

```bash
cd mobile
npx cap sync android   # or: npx cap sync (syncs both)
npx cap sync ios
```

---

## Permissions rationale (shown to users)

| Permission | Platform | When shown |
|---|---|---|
| Precise location | Both | First launch of driver/passenger map |
| Background location | Both | Separate rationale after foreground permission |
| Camera | Both | First incident report |
| Biometric (Face ID / fingerprint) | Both | First driver login |
| Notifications | Both | First launch (iOS) or app request (Android 13+) |

---

## RTL verification checklist

- [ ] Open app on an Arabic-locale device (Settings → Language → العربية)
- [ ] Verify layout mirrors: nav back arrow points right, lists flow RTL
- [ ] Push notification body renders Arabic text correctly
- [ ] Biometric prompt label is in Arabic
- [ ] Splash screen centered (not offset by RTL)
- [ ] Camera preview and captured photo orientation correct

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `cap sync` fails with "webDir not found" | Run `npx cap sync` from `mobile/` not project root |
| Background location not updating | Check `ACCESS_BACKGROUND_LOCATION` in AndroidManifest + allow "All the time" in device settings |
| FCM not received | Verify `google-services.json` is present and matches `applicationId` |
| Biometric prompt not showing | API level < 23 or device has no enrolled biometric — handle with password fallback |
| Arabic text bidi issues | Ensure `android:supportsRtl="true"` in manifest and `layoutDirection: rtl` in styles |
