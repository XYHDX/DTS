import 'dart:async';
import 'dart:convert';

import 'package:flutter_client_sse/constants/sse_request_type_enum.dart';
import 'package:flutter_client_sse/flutter_client_sse.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_client.dart';

class VehiclePosition {
  const VehiclePosition({
    required this.vehicleId,
    required this.lat,
    required this.lon,
    this.routeId,
    this.speedKph,
    this.heading,
    this.updatedAt,
  });
  final String vehicleId;
  final double lat;
  final double lon;
  final String? routeId;
  final double? speedKph;
  final double? heading;
  final DateTime? updatedAt;

  static VehiclePosition? tryFromJson(Map<String, dynamic> j) {
    final num? lat = (j['lat'] ?? j['latitude']) as num?;
    final num? lon = (j['lon'] ?? j['longitude']) as num?;
    if (lat == null || lon == null) return null;
    return VehiclePosition(
      vehicleId: (j['vehicle_id'] ?? j['id'] ?? '').toString(),
      lat: lat.toDouble(),
      lon: lon.toDouble(),
      routeId: j['route_id']?.toString(),
      speedKph: (j['speed'] as num?)?.toDouble(),
      heading: (j['heading'] as num?)?.toDouble(),
      updatedAt: j['ts'] != null
          ? DateTime.tryParse(j['ts'].toString())
          : null,
    );
  }
}

/// Long-lived SSE consumer keyed against /api/stream.
///
/// The backend publishes a "vehicles" event with a JSON payload of the form
/// { positions: [{vehicle_id, lat, lon, speed, ...}, ...] }
/// (also accepts top-level array). We snapshot the most recent payload and
/// keep this provider auto-reconnecting on disconnect.
final vehicleStreamProvider =
    StreamProvider<List<VehiclePosition>>((Ref ref) async* {
  final String base = ref.read(dioProvider).options.baseUrl;
  final StreamController<List<VehiclePosition>> controller =
      StreamController<List<VehiclePosition>>.broadcast();

  // Step 33 — capped exponential backoff with jitter.
  // 1s → 2s → 4s → 8s → 16s → 30s ceiling, ±20% jitter to spread reconnects
  // when many clients see the same outage.
  int backoffMs = 1000;
  const int maxBackoffMs = 30000;
  bool disposed = false;
  late StreamSubscription<SSEModel> sub;

  void open() {
    if (disposed) return;
    sub = SSEClient.subscribeToSSE(
      method: SSERequestType.GET,
      url: '$base/api/stream',
      header: <String, String>{'Accept': 'text/event-stream'},
    ).listen((SSEModel event) {
      if (event.event != 'vehicles' && event.event != null) return;
      final String raw = event.data ?? '';
      if (raw.isEmpty) return;
      // Successful frame → reset backoff window.
      backoffMs = 1000;
      try {
        final dynamic decoded = jsonDecode(raw);
        final List<dynamic> list = decoded is Map
            ? ((decoded['positions'] ?? decoded['vehicles'] ?? const <dynamic>[])
                as List<dynamic>)
            : decoded as List<dynamic>;
        final List<VehiclePosition> parsed = list
            .whereType<Map<String, dynamic>>()
            .map(VehiclePosition.tryFromJson)
            .whereType<VehiclePosition>()
            .toList(growable: false);
        controller.add(parsed);
      } catch (_) {
        // Ignore malformed frames; a fresh one will arrive shortly.
      }
    }, onError: (Object _) {
      if (disposed) return;
      controller.add(const <VehiclePosition>[]);
      // Jittered wait, then reconnect.
      final double jitter = 0.8 + (DateTime.now().millisecondsSinceEpoch % 400) / 1000;
      final int waitMs = (backoffMs * jitter).round();
      Future<void>.delayed(Duration(milliseconds: waitMs), open);
      backoffMs = (backoffMs * 2).clamp(1000, maxBackoffMs);
    });
  }

  open();
  ref.onDispose(() {
    disposed = true;
  });
  ref.onDispose(() async {
    await sub.cancel();
    await controller.close();
  });

  yield* controller.stream;
});
