import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:damascus_transit/core/api_client.dart';
import 'package:damascus_transit/features/auth/auth_controller.dart';

/// In-memory FlutterSecureStorage stub so tests do not touch the real keychain.
class _MemoryStorage extends FlutterSecureStorage {
  _MemoryStorage() : super();
  final Map<String, String> _store = <String, String>{};

  @override
  Future<void> write({
    required String key,
    required String? value,
    IOSOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
  }) async {
    if (value == null) {
      _store.remove(key);
    } else {
      _store[key] = value;
    }
  }

  @override
  Future<String?> read({
    required String key,
    IOSOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
  }) async => _store[key];

  @override
  Future<void> delete({
    required String key,
    IOSOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
  }) async => _store.remove(key);
}

/// Lightweight Dio that returns canned responses based on the request URL.
class _ScriptedAdapter implements HttpClientAdapter {
  _ScriptedAdapter(this._handler);
  final Future<ResponseBody> Function(RequestOptions opts) _handler;
  @override
  void close({bool force = false}) {}
  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<List<int>>? requestStream,
    Future<void>? cancelFuture,
  ) =>
      _handler(options);
}

void main() {
  group('AuthController', () {
    late ProviderContainer container;
    late _MemoryStorage storage;

    setUp(() {
      storage = _MemoryStorage();
    });

    tearDown(() {
      container.dispose();
    });

    test('starts unauthenticated', () {
      container = ProviderContainer(overrides: <Override>[
        tokenStorageProvider.overrideWithValue(storage),
      ]);
      final AuthState s = container.read(authControllerProvider);
      expect(s.isAuthenticated, isFalse);
      expect(s.token, isNull);
    });

    test('successful login stores token and updates state', () async {
      final Dio dio = Dio()
        ..httpClientAdapter = _ScriptedAdapter((RequestOptions o) async {
          expect(o.path, '/api/auth/login');
          return ResponseBody.fromString(
            '{"token":"abc.def.ghi","user":{"id":"u1","email":"a@b","role":"admin"}}',
            200,
            headers: <String, List<String>>{
              'content-type': <String>['application/json'],
            },
          );
        });
      container = ProviderContainer(overrides: <Override>[
        tokenStorageProvider.overrideWithValue(storage),
        dioProvider.overrideWithValue(dio),
      ]);
      final AuthController c = container.read(authControllerProvider.notifier);
      final LoginResult ok = await c.login('a@b', 'pw');
      expect(ok, LoginResult.success);
      expect(container.read(authControllerProvider).token, 'abc.def.ghi');
      expect(await storage.read(key: 'jwt'), 'abc.def.ghi');
    });

    test('non-200 login returns false and leaves state unauthenticated',
        () async {
      final Dio dio = Dio()
        ..httpClientAdapter = _ScriptedAdapter((_) async =>
            ResponseBody.fromString('{"detail":"bad"}', 401));
      container = ProviderContainer(overrides: <Override>[
        tokenStorageProvider.overrideWithValue(storage),
        dioProvider.overrideWithValue(dio),
      ]);
      final AuthController c = container.read(authControllerProvider.notifier);
      final LoginResult ok = await c.login('a@b', 'wrong');
      expect(ok, LoginResult.invalidCredentials);
      expect(container.read(authControllerProvider).isAuthenticated, isFalse);
    });

    test('logout clears persisted token', () async {
      await storage.write(key: 'jwt', value: 'stale');
      container = ProviderContainer(overrides: <Override>[
        tokenStorageProvider.overrideWithValue(storage),
      ]);
      await container.read(authControllerProvider.notifier).logout();
      expect(await storage.read(key: 'jwt'), isNull);
      expect(container.read(authControllerProvider).isAuthenticated, isFalse);
    });
  });
}
