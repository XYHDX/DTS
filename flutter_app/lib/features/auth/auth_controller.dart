import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../../core/api_client.dart';
import '../push/push_service.dart';

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

  Future<bool> login(String email, String password) async {
    try {
      final Response<dynamic> r = await _dio.post<dynamic>('/api/auth/login',
          data: <String, String>{'email': email, 'password': password});
      final Map<String, dynamic> data = (r.data as Map).cast<String, dynamic>();
      final String? token =
          (data['token'] ?? data['access_token']) as String?;
      if (token == null) return false;
      await _storage.write(key: 'jwt', value: token);
      state = AuthState(
        token: token,
        user: (data['user'] as Map?)?.cast<String, dynamic>() ?? data,
      );
      // Fire-and-forget: pair the FCM push token with the user.
      // Soft-fails if Firebase isn't configured yet.
      unawaited(ref.read(pushServiceProvider).registerToken());
      return true;
    } on DioException {
      return false;
    }
  }

  Future<void> logout() async {
    await _storage.delete(key: 'jwt');
    state = const AuthState();
  }
}

final authControllerProvider =
    NotifierProvider<AuthController, AuthState>(AuthController.new);
