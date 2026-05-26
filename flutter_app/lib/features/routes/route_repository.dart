import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_client.dart';

class TransitRoute {
  const TransitRoute({
    required this.id,
    required this.code,
    required this.name,
    this.nameAr,
    this.from,
    this.to,
    this.stopsCount,
  });
  final String id;
  final String code;
  final String name;
  final String? nameAr;
  final String? from;
  final String? to;
  final int? stopsCount;

  factory TransitRoute.fromJson(Map<String, dynamic> json) => TransitRoute(
        id: json['id'].toString(),
        code: (json['code'] ?? json['short_name'] ?? json['id'].toString()).toString(),
        name: (json['name'] ?? json['long_name'] ?? '').toString(),
        nameAr: json['name_ar'] as String?,
        from: json['from'] as String?,
        to:   json['to']   as String? ?? json['name_en'] as String?,
        stopsCount: (json['stops_count'] is int)
            ? json['stops_count'] as int
            : int.tryParse('${json['stops_count']}'),
      );
}

final routesProvider = FutureProvider<List<TransitRoute>>((Ref ref) async {
  final dio = ref.read(dioProvider);
  final response = await dio.get<List<dynamic>>('/api/routes');
  final List<dynamic> data = response.data ?? const <dynamic>[];
  return data
      .whereType<Map<String, dynamic>>()
      .map(TransitRoute.fromJson)
      .toList(growable: false);
});

class Stop {
  const Stop({required this.id, required this.name, required this.lat, required this.lon, this.nameAr});
  final String id;
  final String name;
  final String? nameAr;
  final double lat;
  final double lon;

  factory Stop.fromJson(Map<String, dynamic> j) => Stop(
        id: j['id'].toString(),
        name: (j['name'] ?? '').toString(),
        nameAr: j['name_ar'] as String?,
        lat: ((j['lat'] ?? j['latitude']) as num).toDouble(),
        lon: ((j['lon'] ?? j['longitude']) as num).toDouble(),
      );
}

final stopsByRouteProvider =
    FutureProvider.family<List<Stop>, String>((Ref ref, String routeId) async {
  final dio = ref.read(dioProvider);
  final response =
      await dio.get<Map<String, dynamic>>('/api/routes/$routeId');
  final dynamic stops = response.data?['stops'];
  if (stops is List) {
    return stops
        .whereType<Map<String, dynamic>>()
        .map(Stop.fromJson)
        .toList(growable: false);
  }
  return const <Stop>[];
});
