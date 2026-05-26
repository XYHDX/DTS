import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';

import '../../core/theme.dart';
import '../map/vehicle_stream.dart';
import '../routes/route_repository.dart';

class RouteDetailScreen extends ConsumerWidget {
  const RouteDetailScreen({super.key, required this.routeId});
  final String routeId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<List<Stop>> stops = ref.watch(stopsByRouteProvider(routeId));
    final AsyncValue<List<VehiclePosition>> vehicles =
        ref.watch(vehicleStreamProvider);

    return Scaffold(
      appBar: AppBar(title: Text('الخط $routeId')),
      body: stops.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (Object e, _) => Center(child: Text('تعذّر تحميل المحطات: $e')),
        data: (List<Stop> list) {
          final List<LatLng> points = <LatLng>[
            for (final Stop s in list) LatLng(s.lat, s.lon),
          ];
          final LatLng centre = points.isEmpty
              ? const LatLng(33.513, 36.291)
              : points.first;
          final List<VehiclePosition> onRoute = vehicles.maybeWhen(
            data: (List<VehiclePosition> v) =>
                v.where((VehiclePosition p) => p.routeId == routeId).toList(),
            orElse: () => const <VehiclePosition>[],
          );

          return Column(
            children: <Widget>[
              SizedBox(
                height: 280,
                child: FlutterMap(
                  options: MapOptions(initialCenter: centre, initialZoom: 13),
                  children: <Widget>[
                    TileLayer(
                      urlTemplate:
                          'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                      userAgentPackageName: 'sy.gov.damascus.transit',
                    ),
                    // Step 34 — softer two-layer polyline so the route reads
                    // even on light raster tiles. Cream halo underneath,
                    // coral spine on top.
                    PolylineLayer(polylines: <Polyline>[
                      Polyline(
                        points: points,
                        strokeWidth: 10,
                        color: const Color(0xFFFFF8F3),
                        borderStrokeWidth: 0,
                      ),
                      Polyline(
                        points: points,
                        strokeWidth: 5,
                        color: AppTheme.brand500,
                      ),
                    ]),
                    MarkerLayer(markers: <Marker>[
                      for (final Stop s in list)
                        Marker(
                          point: LatLng(s.lat, s.lon),
                          width: 14,
                          height: 14,
                          child: Container(
                            decoration: BoxDecoration(
                              color: AppTheme.gold600,
                              shape: BoxShape.circle,
                              border: Border.all(color: Colors.white, width: 2),
                            ),
                          ),
                        ),
                      for (final VehiclePosition v in onRoute)
                        Marker(
                          point: LatLng(v.lat, v.lon),
                          width: 18,
                          height: 18,
                          child: Container(
                            decoration: BoxDecoration(
                              color: AppTheme.brand500,
                              shape: BoxShape.circle,
                              border: Border.all(color: Colors.white, width: 2),
                              boxShadow: const <BoxShadow>[
                                BoxShadow(color: Color(0x33000000), blurRadius: 4),
                              ],
                            ),
                          ),
                        ),
                    ]),
                  ],
                ),
              ),
              Expanded(
                child: ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: list.length,
                  itemBuilder: (BuildContext _, int i) {
                    final Stop s = list[i];
                    return Card(
                      margin: const EdgeInsets.only(bottom: 8),
                      child: ListTile(
                        title: Text(s.nameAr ?? s.name,
                            style: const TextStyle(fontWeight: FontWeight.w700)),
                        subtitle: Text('${s.lat.toStringAsFixed(4)}, ${s.lon.toStringAsFixed(4)}',
                            style: const TextStyle(color: Colors.black54, fontSize: 12)),
                        trailing: Text('#${i + 1}',
                            style: const TextStyle(color: Colors.black45)),
                      ),
                    );
                  },
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}
