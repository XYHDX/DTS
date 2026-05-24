import 'package:flutter/foundation.dart';
import 'package:flutter_background_geolocation/flutter_background_geolocation.dart'
    as bg;

/// Thin façade over flutter_background_geolocation (transistorsoft).
///
/// Used during driver trips. Foreground-only GPS uses `geolocator` for
/// passenger flows — this class is the heavy-duty long-shift path.
///
/// Lifecycle:
///   1. `BackgroundGps.configureOnce()` — call once at app boot. Idempotent.
///   2. `BackgroundGps.startTrip(onLocation: …)` — call when the trip begins.
///   3. `BackgroundGps.stopTrip()` — call when the trip ends. Frees resources.
///
/// On iOS this requires `UIBackgroundModes: location` in Info.plist (done).
/// On Android this requires `FOREGROUND_SERVICE_LOCATION` (done in manifest).
class BackgroundGps {
  static bool _configured = false;

  /// Idempotent setup. Call from `main.dart` after `WidgetsFlutterBinding.ensureInitialized()`.
  static Future<void> configureOnce() async {
    if (_configured) return;
    try {
      await bg.BackgroundGeolocation.ready(bg.Config(
        // Accuracy & sampling
        desiredAccuracy: bg.Config.DESIRED_ACCURACY_HIGH,
        distanceFilter: 15.0,          // metres between samples
        stopOnTerminate: false,        // survive app kill
        startOnBoot: false,            // we re-arm on trip start
        // Activity inference
        activityRecognitionInterval: 10000,
        stopTimeout: 5,
        // Battery
        preventSuspend: false,
        heartbeatInterval: 60,
        // Network — we hand-off through Dio, NOT the plugin's HTTP layer.
        url: '',
        autoSync: false,
        // Notifications (Android foreground service)
        notification: bg.Notification(
          title: 'نقل دمشق — رحلة جارية',
          text: 'يتم تحديث موقع الحافلة لتظهر للركاب.',
          channelName: 'driver-trip',
          priority: bg.Config.NOTIFICATION_PRIORITY_LOW,
        ),
        // Geofence / debug
        debug: kDebugMode,
        logLevel: kDebugMode ? bg.Config.LOG_LEVEL_VERBOSE : bg.Config.LOG_LEVEL_WARNING,
      ));
      _configured = true;
    } catch (e) {
      if (kDebugMode) debugPrint('[BackgroundGps] configure failed: $e');
    }
  }

  /// Begin emitting positions to [onLocation] until [stopTrip] is called.
  /// [onLocation] is invoked with (lat, lon, speedKph, heading).
  static Future<void> startTrip({
    required void Function(double lat, double lon, double? speedKph, double? heading) onLocation,
  }) async {
    if (!_configured) await configureOnce();
    if (!_configured) return; // plugin unavailable — caller falls back to geolocator

    bg.BackgroundGeolocation.onLocation((bg.Location loc) {
      onLocation(
        loc.coords.latitude,
        loc.coords.longitude,
        loc.coords.speed >= 0 ? loc.coords.speed * 3.6 : null, // m/s → km/h
        loc.coords.heading >= 0 ? loc.coords.heading : null,
      );
    });

    await bg.BackgroundGeolocation.start();
  }

  /// Stops emitting positions and releases the foreground-service / iOS task.
  static Future<void> stopTrip() async {
    try {
      await bg.BackgroundGeolocation.stop();
    } catch (_) {/* never throw from teardown */}
  }
}
