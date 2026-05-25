# Flutter app architecture

> Companion to `README.md`. Documents the layering, state model, and data flow inside `flutter_app/`. Updated 2026-05-24 (roadmap step 67).

## Goals

- **One Dart codebase → Android + iOS.** Web is served by the existing FastAPI/HTML stack; the Flutter app does not target Flutter Web.
- **Backend is the source of truth.** The app caches but never owns canonical data.
- **Offline-tolerant.** All read paths must function with a cold network for at least one app session.
- **Typed, null-safe, side-effects in providers.** No `setState` in feature widgets except for local UI gates.

## Layers

```
┌────────────────────────────────────────────────────────────────────┐
│ Presentation                                                        │
│   lib/features/**/passenger_home.dart, driver_home.dart, …          │
│   lib/shared/widgets/role_gate.dart                                 │
│                                                                     │
│   Pulls state from Riverpod providers. Stateless widgets prefered.  │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ ref.watch / ref.read
┌──────────────────────────▼──────────────────────────────────────────┐
│ Application (Riverpod state)                                        │
│   lib/features/auth/auth_controller.dart      (NotifierProvider)    │
│   lib/features/routes/route_repository.dart   (FutureProvider)      │
│   lib/features/map/vehicle_stream.dart        (StreamProvider)      │
│   lib/features/push/push_service.dart         (Provider)            │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ Dio / SSE / FirebaseMessaging
┌──────────────────────────▼──────────────────────────────────────────┐
│ Infrastructure                                                      │
│   lib/core/api_client.dart    Dio + JWT interceptor + 401 handling │
│   lib/core/router.dart        GoRouter + auth redirect             │
│   lib/core/theme.dart         Material 3 theme (mirrors web tokens)│
│   FlutterSecureStorage         keychain / encrypted shared prefs   │
└─────────────────────────────────────────────────────────────────────┘
```

## State management

We use **Riverpod 2** exclusively. Three categories of provider:

1. **Synchronous Provider** — wires up shared singletons (`dioProvider`, `tokenStorageProvider`, `pushServiceProvider`).
2. **FutureProvider** — one-shot async fetches (`routesProvider`, `stopsByRouteProvider`).
3. **StreamProvider** — long-lived streams (`vehicleStreamProvider`).
4. **NotifierProvider** — stateful controllers with explicit transitions (`authControllerProvider`).

State is **never** mutated from the widget tree. Widgets call methods on the controller (e.g. `ref.read(authControllerProvider.notifier).login()`), which updates the immutable state, which Riverpod broadcasts to all watchers.

## Navigation

`go_router` declares the routing graph in `lib/core/router.dart`. A `redirect` callback enforces:

- Unauthenticated users hitting `/driver` are bounced to `/login?next=…`.
- Authenticated users at `/login` are bounced to `/`.

Role-based access for the driver experience is gated by the `RoleGate` widget (`lib/shared/widgets/role_gate.dart`), which checks `authControllerProvider.role` against an allow-list.

## Networking

A single Dio instance is configured in `core/api_client.dart`:

- Base URL injected at build time via `--dart-define=API_BASE=…`.
- Interceptor pulls the JWT from secure storage and adds `Authorization: Bearer …`.
- On HTTP 401 the JWT is wiped, which causes the router redirect to fire on the next navigation tick.
- Debug builds attach `pretty_dio_logger` for inspection; release builds drop it.

The Retrofit dependency is in `pubspec.yaml` for future codegen against `openapi.json`. Today's repositories hand-write the parsing in `route_repository.dart` so the app remains buildable without `build_runner` having to be invoked first.

## Real-time

`vehicle_stream.dart` opens an `EventSource`-compatible SSE connection to `/api/stream`. The contract is documented in `markdown-files/technical/SSE_Contract.md`.

Reconnect strategy (step 33): capped exponential backoff with jitter, 1 s → 30 s. Disposed when the provider is torn down (Riverpod `onDispose`).

## Auth flow

1. User submits credentials in `LoginScreen`.
2. `AuthController.login()` posts to `/api/auth/login`, receives a JWT.
3. Token written to `flutter_secure_storage` (`first_unlock` accessibility on iOS).
4. `AuthState` updates; router observers (via `redirect`) push to `/`.
5. `PushService.registerToken()` is fired-and-forgotten to pair the FCM token with the backend.

Logout reverses steps 3 + 4 and notifies the backend (best-effort).

## Offline strategy (planned)

`pubspec.yaml` includes `drift` and `sqlite3_flutter_libs`. The plan documented in `ROADMAP_100.md` steps 21–23 is:

- `routes` and `stops` tables mirror the backend.
- On boot, `OfflineRouteRepository` reads from Drift; a background task fetches from `/api/routes` and reconciles.
- `vehicle_stream.dart` always opens live but falls through to a "last known positions" cache when the stream is silent for more than 60 s.

Today, repositories fail soft and return empty lists; the UI shows skeleton states.

## Crash and performance reporting

Sentry is initialised in `main.dart` only when `--dart-define=SENTRY_DSN=…` is set. In dev builds and CI it is a no-op so tests do not need the SDK to be online. Release builds also pass `--dart-define=APP_RELEASE=…` and `--dart-define=APP_ENV=production` which Sentry surfaces as tags.

The `beforeSend` hook drops handled `DioException(401)` errors — they are routine and already trigger the JWT eviction path.

## Theming

`core/theme.dart` mirrors the CSS custom properties in `public/lib/design-system.css`. When you change a brand colour, **change both**. A Lighthouse / a11y check should pass at AA contrast on either surface.

The app is **RTL by default**. `MaterialApp.builder` wraps the tree in `Directionality(TextDirection.rtl)` so even widgets that ignore locale follow the Arabic layout.

## Testing

- `test/auth_controller_test.dart` — `_MemoryStorage` + scripted Dio adapter cover login success/failure and logout.
- `test/route_repository_test.dart` — JSON-shape robustness for `TransitRoute` and `Stop`.
- `test/widget_test.dart` — smoke that the theme renders without exceptions.

CI (`.github/workflows/flutter.yml`) runs `flutter analyze --fatal-infos` then `flutter test --coverage` then a debug APK build on every PR.

## Build flags reference

| Flag | Default | Purpose |
|---|---|---|
| `API_BASE` | `http://10.0.2.2:8000` | Backend origin. Use the LAN IP of your dev host for physical-device testing. |
| `SENTRY_DSN` | empty | When set, enables Sentry. |
| `APP_RELEASE` | `damascus-transit@dev` | Sentry release tag. |
| `APP_ENV` | `development` | Sentry environment tag. |

Example release build:

```
flutter build appbundle \
  --release \
  --dart-define=API_BASE=https://api.damascustransit.sy \
  --dart-define=SENTRY_DSN=$SENTRY_DSN \
  --dart-define=APP_RELEASE=damascus-transit@1.0.0 \
  --dart-define=APP_ENV=production
```
