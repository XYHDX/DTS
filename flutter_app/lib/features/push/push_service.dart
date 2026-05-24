import 'package:dio/dio.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_client.dart';

/// Lifecycle:
///   1. App boot: ensure Firebase is initialised (no-op if already done elsewhere).
///   2. After login: call [PushService.registerToken] from the auth controller
///      so the FCM token is paired with the user on the backend.
///   3. Handle token refresh by listening to [FirebaseMessaging.onTokenRefresh].
///
/// All methods fail soft so a missing Firebase config (no google-services.json
/// or GoogleService-Info.plist) does not crash the app — push simply stays off.
class PushService {
  PushService(this._dio);
  final Dio _dio;

  Future<bool> _initFirebase() async {
    try {
      if (Firebase.apps.isEmpty) {
        await Firebase.initializeApp();
      }
      return true;
    } catch (e) {
      if (kDebugMode) debugPrint('[PushService] Firebase init failed: $e');
      return false;
    }
  }

  /// Requests notification permission (iOS) and returns the current FCM token.
  Future<String?> currentToken() async {
    if (!await _initFirebase()) return null;
    try {
      final FirebaseMessaging fm = FirebaseMessaging.instance;
      final NotificationSettings settings =
          await fm.requestPermission(alert: true, badge: true, sound: true);
      if (settings.authorizationStatus == AuthorizationStatus.denied) {
        return null;
      }
      return fm.getToken();
    } catch (e) {
      if (kDebugMode) debugPrint('[PushService] token fetch failed: $e');
      return null;
    }
  }

  /// Calls after login. Pairs the FCM token with the JWT-identified user.
  Future<void> registerToken({String? platformHint}) async {
    final String? token = await currentToken();
    if (token == null) return;
    try {
      await _dio.post<dynamic>('/api/push/register', data: <String, Object?>{
        'token': token,
        'platform': platformHint ?? defaultTargetPlatform.name.toLowerCase(),
      });
    } on DioException {
      // Backend may be offline; the token will be re-sent on next login.
    }

    // React to background token rotation by re-registering automatically.
    FirebaseMessaging.instance.onTokenRefresh.listen((String newToken) async {
      try {
        await _dio.post<dynamic>('/api/push/register', data: <String, Object?>{
          'token': newToken,
          'platform': platformHint ?? defaultTargetPlatform.name.toLowerCase(),
        });
      } on DioException {/* same — best-effort */}
    });
  }

  /// Called on logout to drop the device from broadcast lists.
  Future<void> unregister() async {
    final String? token = await currentToken();
    if (token == null) return;
    try {
      await _dio.post<dynamic>('/api/push/unregister', data: <String, String>{
        'token': token,
      });
    } on DioException {/* tolerated */}
  }
}

final pushServiceProvider = Provider<PushService>(
  (Ref ref) => PushService(ref.read(dioProvider)),
);
