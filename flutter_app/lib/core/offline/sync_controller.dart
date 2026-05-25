import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api_client.dart';
import 'database.dart';

/// Orchestrates pulls from the canonical API into the Drift cache.
///
/// Designed to be called from app boot and from a pull-to-refresh gesture.
/// All errors are swallowed — a failed sync leaves the previous cache intact.
class SyncController {
  SyncController(this._db, this._dio);
  final AppDatabase _db;
  final Dio _dio;

  /// Top-level sync — routes first, then a stops fan-out (cheap because the
  /// /api/routes/:id endpoint returns the embedded stops array).
  Future<void> syncAll() async {
    await syncRoutes();
  }

  Future<void> syncRoutes() async {
    try {
      final Response<dynamic> r = await _dio.get<dynamic>('/api/routes');
      final List<dynamic> rows = (r.data as List<dynamic>?) ?? const <dynamic>[];
      final DateTime now = DateTime.now().toUtc();

      final List<CachedRoute> routes = rows
          .whereType<Map<String, dynamic>>()
          .map<CachedRoute>((Map<String, dynamic> j) => CachedRoute(
                id: j['id'].toString(),
                code: (j['code'] ?? j['short_name'] ?? j['id']).toString(),
                name: (j['name'] ?? j['long_name'] ?? '').toString(),
                nameAr: j['name_ar'] as String?,
                fromName: j['from'] as String?,
                toName: j['to'] as String?,
                stopsCount: (j['stops_count'] is int)
                    ? j['stops_count'] as int
                    : int.tryParse('${j['stops_count']}'),
                updatedAt: now,
              ))
          .toList(growable: false);

      if (routes.isNotEmpty) await _db.upsertRoutes(routes);

      // Fan-out for stops — capped to avoid hammering the API on cold boot.
      const int maxFanOut = 12;
      for (int i = 0; i < routes.length && i < maxFanOut; i++) {
        await _syncStopsForRoute(routes[i].id);
      }
    } on DioException {
      // Soft-fail.
    }
  }

  Future<void> _syncStopsForRoute(String routeId) async {
    try {
      final Response<dynamic> r =
          await _dio.get<dynamic>('/api/routes/$routeId');
      final dynamic stops = (r.data as Map<String, dynamic>?)?['stops'];
      if (stops is! List) return;
      final DateTime now = DateTime.now().toUtc();
      final List<CachedStop> rows = <CachedStop>[];
      int i = 0;
      for (final dynamic s in stops) {
        if (s is! Map<String, dynamic>) continue;
        final num? lat = (s['lat'] ?? s['latitude']) as num?;
        final num? lon = (s['lon'] ?? s['longitude']) as num?;
        if (lat == null || lon == null) continue;
        rows.add(CachedStop(
          id: s['id'].toString(),
          routeId: routeId,
          seq: (s['seq'] as num?)?.toInt() ?? i++,
          name: (s['name'] ?? '').toString(),
          nameAr: s['name_ar'] as String?,
          lat: lat.toDouble(),
          lon: lon.toDouble(),
          updatedAt: now,
        ));
      }
      if (rows.isNotEmpty) await _db.upsertStops(rows);
    } on DioException {/* soft-fail */}
  }

  /// Called from the SSE consumer whenever a valid frame is parsed so we
  /// always have a recent set of "last known positions" to fall back to.
  Future<void> rememberPositions(Iterable<CachedPosition> positions) async {
    for (final CachedPosition p in positions) {
      await _db.upsertPosition(p);
    }
  }
}

final syncControllerProvider = Provider<SyncController>(
  (Ref ref) => SyncController(ref.read(databaseProvider), ref.read(dioProvider)),
);
