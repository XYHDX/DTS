import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_client.dart';
import '../../core/offline/database.dart';
import '../../core/offline/sync_controller.dart';
import 'route_repository.dart';

/// Read path that prefers fresh API data but falls back to the Drift cache
/// when the network is unavailable. Writes flow through [SyncController] so
/// every successful API hit silently warms the cache.
class OfflineRouteRepository {
  OfflineRouteRepository(this._dio, this._db, this._sync);
  final Dio _dio;
  final AppDatabase _db;
  final SyncController _sync;

  /// Hot path: API → cache → return. Cold path: cache → return. Empty path: [].
  Future<List<TransitRoute>> listRoutes({Duration networkTimeout =
      const Duration(seconds: 4)}) async {
    try {
      final Response<dynamic> r = await _dio
          .get<dynamic>('/api/routes')
          .timeout(networkTimeout);
      final List<dynamic> rows = (r.data as List<dynamic>?) ?? const <dynamic>[];
      final List<TransitRoute> live = rows
          .whereType<Map<String, dynamic>>()
          .map(TransitRoute.fromJson)
          .toList(growable: false);
      // Warm the cache opportunistically.
      unawaited(_sync.syncRoutes());
      if (live.isNotEmpty) return live;
    } catch (_) {/* fall through to cache */}

    final List<CachedRoute> rows = await _db.allRoutes();
    return rows
        .map<TransitRoute>((CachedRoute r) => TransitRoute(
              id: r.id,
              code: r.code,
              name: r.name,
              nameAr: r.nameAr,
              from: r.fromName,
              to: r.toName,
              stopsCount: r.stopsCount,
            ))
        .toList(growable: false);
  }

  /// Same pattern for stops on a given route.
  Future<List<Stop>> stopsForRoute(String routeId) async {
    try {
      final Response<dynamic> r = await _dio
          .get<dynamic>('/api/routes/$routeId')
          .timeout(const Duration(seconds: 4));
      final dynamic stops = (r.data as Map<String, dynamic>?)?['stops'];
      if (stops is List) {
        final List<Stop> live = stops
            .whereType<Map<String, dynamic>>()
            .map(Stop.fromJson)
            .toList(growable: false);
        if (live.isNotEmpty) return live;
      }
    } catch (_) {/* fall through */}

    final List<CachedStop> cached = await _db.stopsForRoute(routeId);
    return cached
        .map<Stop>((CachedStop s) => Stop(
              id: s.id,
              name: s.name,
              nameAr: s.nameAr,
              lat: s.lat,
              lon: s.lon,
            ))
        .toList(growable: false);
  }
}

void unawaited(Future<void> f) {
  // ignore: unawaited_futures
  f;
}

final offlineRoutesProvider = Provider<OfflineRouteRepository>((Ref ref) =>
    OfflineRouteRepository(
      ref.read(dioProvider),
      ref.read(databaseProvider),
      ref.read(syncControllerProvider),
    ));

/// Drop-in async data — preferred by the UI now.
final offlineRoutesListProvider =
    FutureProvider<List<TransitRoute>>((Ref ref) async {
  return ref.read(offlineRoutesProvider).listRoutes();
});

final offlineStopsProvider =
    FutureProvider.family<List<Stop>, String>((Ref ref, String routeId) async {
  return ref.read(offlineRoutesProvider).stopsForRoute(routeId);
});
