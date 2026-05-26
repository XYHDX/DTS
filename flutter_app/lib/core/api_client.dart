import 'dart:async';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:pretty_dio_logger/pretty_dio_logger.dart';

/// Single source of truth for the API base URL.
/// Override at build time:  --dart-define=API_BASE=https://api.example.com
const String kDefaultApiBase = String.fromEnvironment(
  'API_BASE',
  defaultValue: 'http://10.0.2.2:8000', // Android emulator -> host machine
);

/// JWT storage (refreshable across cold starts).
final tokenStorageProvider = Provider<FlutterSecureStorage>(
  (_) => const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
    iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock),
  ),
);

/// Authoritative Dio instance with JWT interceptor + retry/backoff.
final dioProvider = Provider<Dio>((Ref ref) {
  final FlutterSecureStorage storage = ref.watch(tokenStorageProvider);
  final Dio dio = Dio(BaseOptions(
    baseUrl: kDefaultApiBase,
    connectTimeout: const Duration(seconds: 10),
    receiveTimeout: const Duration(seconds: 20),
    sendTimeout: const Duration(seconds: 15),
    headers: <String, String>{
      'Accept': 'application/json',
      'Content-Type': 'application/json',
    },
  ));

  dio.interceptors.add(InterceptorsWrapper(
    onRequest: (RequestOptions opts, RequestInterceptorHandler next) async {
      final String? jwt = await storage.read(key: 'jwt');
      if (jwt != null && jwt.isNotEmpty) {
        opts.headers['Authorization'] = 'Bearer $jwt';
      }
      next.next(opts);
    },
    onError: (DioException err, ErrorInterceptorHandler next) async {
      // Clear JWT on hard auth failures so the user is bounced to login
      if (err.response?.statusCode == 401) {
        await storage.delete(key: 'jwt');
      }
      next.next(err);
    },
  ));

  if (kDebugMode) {
    dio.interceptors.add(PrettyDioLogger(
      requestBody: true,
      responseBody: false,
      requestHeader: false,
      compact: true,
    ));
  }

  return dio;
});

/// Convenience: thin connectivity ping.
final apiHealthProvider = FutureProvider<bool>((Ref ref) async {
  try {
    final Response<dynamic> r = await ref
        .read(dioProvider)
        .get<dynamic>('/api/health');
    return r.statusCode == 200;
  } on SocketException {
    return false;
  } on DioException {
    return false;
  }
});
