import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../../core/api_client.dart';
import '../push/push_service.dart';

/// Outcome of a [AuthController.login] attempt.
///
/// Distinguishes a genuine credential rejection (HTTP 401) from a transport
/// failure (timeouts, connection errors, 5xx) so the UI can show the right
/// message instead of blaming the user for a server outage.
enum LoginResult {
  /// Login succeeded; a token was stored.
  success,

  /// The server rejected the email/password pair (HTTP 401, or no token).
  invalidCredentials,

  /// The server could not be reached or returned a server-side error.
  serverUnreachable,
}

/// Auth state — null when logged out.
class AuthState {
  const AuthState({this.token, this.user});
  final String? token;
  final Map<String, dynamic>? user;

  bool get isAuthenticated => token != null && token!.isNotEmpty;
  String? get role => user?['role'] as String?;

  AuthState copyWith({String? token, Map<String, dynamic>? user}) =>
      AuthState(token: token ?? this.token, user: user ?? this.user);
}

class AuthController extends Notifier<AuthState> {
  late final FlutterSecureStorage _storage;
  late final Dio _dio;

  @override
  AuthState build() {
    _storage = ref.read(tokenStorageProvider);
    _dio = ref.read(dioProvider);
    _restore();
    return const AuthState();
  }

  Future<void> _restore() async {
    final String? token = await _storage.read(key: 'jwt');
    if (token != null && token.isNotEmpty) {
      state = state.copyWith(token: token);
    }
  }

  bool get isAuthenticated => state.isAuthenticated;

  Future<LoginResult> login(String email, String password) async {
    try {
      final Response<dynamic> r = await _dio.post<dynamic>('/api/auth/login',
          data: <String, String>{'email': email, 'password': password});
      final Map<String, dynamic> data = (r.data as Map).cast<String, dynamic>();
      final String? token =
          (data['token'] ?? data['access_token']) as String?;
      if (token == null) return LoginResult.invalidCredentials;
      await _storage.write(key: 'jwt', value: token);
      state = AuthState(
        token: token,
        user: (data['user'] as Map?)?.cast<String, dynamic>() ?? data,
      );
      // Fire-and-forget: pair the FCM push token with the user.
      // Soft-fails if Firebase isn't configured yet.
      unawaited(ref.read(pushServiceProvider).registerToken());
      return LoginResult.success;
    } on DioException catch (e) {
      // A 401 is a real credential rejection; everything else (timeouts,
      // connection errors, 5xx) means the server is unreachable / faulty.
      final int? status = e.response?.statusCode;
      if (status == 401) return LoginResult.invalidCredentials;
      switch (e.type) {
        case DioExceptionType.connectionTimeout:
        case DioExceptionType.receiveTimeout:
        case DioExceptionType.connectionError:
          return LoginResult.serverUnreachable;
        default:
          if (status != null && status >= 500) {
            return LoginResult.serverUnreachable;
          }
          return LoginResult.invalidCredentials;
      }
    }
  }

  Future<void> logout() async {
    await _storage.delete(key: 'jwt');
    state = const AuthState();
  }
}

final authControllerProvider =
    NotifierProvider<AuthController, AuthState>(AuthController.new);
