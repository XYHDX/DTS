# DamascusTransit — Flutter app

Native Android/iOS client for the DamascusTransit platform.

This app talks to the existing FastAPI backend (`/api/...`) — it does **not** replace it. It replaces the `public/passenger/` and `public/driver/` web PWAs with a typed Dart codebase.

## Status

Scaffold: complete. The following are wired against the live API and work today:

- JWT auth (login + secure storage + 401-aware Dio interceptor)
- Passenger home with live search, OSM map via `flutter_map`, route list
- Live vehicle stream via SSE (`/api/stream`) with auto-reconnect
- Route detail with polyline + stops + live vehicles on that route
- Driver home with start/stop trip, passenger counter, GPS streaming to backend
- Local biometric prompt (`local_auth`)
- Role-based route guard
- Material 3 theme aligned with `public/lib/design-system.css`
- RTL by default, Arabic locale primary

## Run locally

```bash
cd flutter_app
flutter pub get
flutter run --dart-define=API_BASE=http://10.0.2.2:8000     # Android emulator
flutter run --dart-define=API_BASE=http://localhost:8000    # iOS simulator
```

## Build for release

```bash
# Android AAB
flutter build appbundle --dart-define=API_BASE=https://syrian-transit-system.vercel.app

# iOS archive
flutter build ipa --dart-define=API_BASE=https://syrian-transit-system.vercel.app
```

## Project layout

```
lib/
  main.dart                       App bootstrap, MaterialApp.router
  core/
    api_client.dart              Dio + secure storage + JWT interceptor
    router.dart                  GoRouter declarations + auth redirect
    theme.dart                   AppTheme — palette mirrors design-system.css
  features/
    auth/
      auth_controller.dart       Riverpod Notifier for AuthState
      login_screen.dart
    passenger/
      passenger_home.dart        Hero search + live map + route list
      route_detail_screen.dart
    routes/
      route_repository.dart      Routes + Stops API providers
      routes_list_screen.dart
    map/
      vehicle_stream.dart        SSE consumer with backoff
    driver/
      driver_home.dart           Trip controls + pax counter + GPS streamer
  shared/widgets/
    role_gate.dart               RBAC wrapper
```

## What's deliberately deferred

- Background geolocation for the driver (`flutter_background_geolocation`
  from transistorsoft). The scaffold uses `geolocator` for foreground GPS only.
  The plugin requires a licence — wire it up before production.
- Firebase push (FCM/APNs) — `firebase_messaging` is in `pubspec.yaml`; native
  Firebase config files (`google-services.json`, `GoogleService-Info.plist`)
  must be added before push works.
- Drift offline cache. Schema can be modelled directly from `db/schema.sql`.

## Sharing identity with the web

The Material 3 palette in `core/theme.dart` mirrors the CSS tokens in
`public/lib/design-system.css`. When you change a brand colour, change both.
