import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';

import '../../core/api_client.dart';
import '../../core/theme.dart';
import '../routes/route_repository.dart';

/// Claude-styled "stops near me".
///
/// Cream cream-paper list, hairline dividers, serif headline,
/// muted secondary text. Distance is the visual anchor on the trailing edge.
class NearestStopsScreen extends ConsumerStatefulWidget {
  const NearestStopsScreen({super.key});
  @override
  ConsumerState<NearestStopsScreen> createState() => _NearestStopsScreenState();
}

class _NearestStopsScreenState extends ConsumerState<NearestStopsScreen> {
  AsyncValue<List<_NearStop>> _state = const AsyncValue<List<_NearStop>>.loading();

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    setState(() => _state = const AsyncValue<List<_NearStop>>.loading());
    try {
      final LocationPermission perm = await Geolocator.requestPermission();
      double lat = 33.513, lon = 36.291;
      if (perm == LocationPermission.always ||
          perm == LocationPermission.whileInUse) {
        try {
          final Position p = await Geolocator.getCurrentPosition(
              locationSettings:
                  const LocationSettings(accuracy: LocationAccuracy.medium));
          lat = p.latitude;
          lon = p.longitude;
        } catch (_) {/* fall back to Damascus centre */}
      }
      final Response<dynamic> r = await ref
          .read(dioProvider)
          .get<dynamic>('/api/stops/nearest', queryParameters: <String, Object>{
        'lat': lat,
        'lon': lon,
        'radius_m': 1500,
      });
      final List<dynamic> rows = (r.data as List<dynamic>?) ?? const <dynamic>[];
      final List<_NearStop> stops = rows
          .whereType<Map<String, dynamic>>()
          .map<_NearStop>((Map<String, dynamic> j) => _NearStop(
                stop: Stop.fromJson(j),
                distanceM: ((j['distance_m'] ?? 0) as num).toDouble(),
                etaMin: (j['eta_min'] as num?)?.toDouble(),
                routeCode: j['route_code']?.toString(),
              ))
          .toList(growable: false);
      if (!mounted) return;
      setState(() => _state = AsyncValue<List<_NearStop>>.data(stops));
    } catch (e, st) {
      if (!mounted) return;
      setState(() => _state = AsyncValue<List<_NearStop>>.error(e, st));
    }
  }

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('قريب')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        color: AppTheme.brand600,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(24, 16, 24, 48),
          physics: const AlwaysScrollableScrollPhysics(),
          children: <Widget>[
            // Header
            Text('أقرب المحطات', style: theme.textTheme.displaySmall),
            const SizedBox(height: 6),
            Text(
              'ضمن ١٫٥ كم من موقعك الحالي. اسحب للأسفل للتحديث.',
              style: theme.textTheme.bodyLarge?.copyWith(
                  color: AppTheme.textMuteLight),
            ),
            const SizedBox(height: 28),
            _state.when(
              loading: () => const _Skeleton(),
              error: (Object e, _) => _ErrorRow(message: 'تعذّر تحميل القائمة. $e'),
              data: (List<_NearStop> stops) {
                if (stops.isEmpty) return const _EmptyRow();
                return Container(
                  decoration: BoxDecoration(
                    color: AppTheme.surfaceLight,
                    border: Border.all(color: AppTheme.borderLight),
                    borderRadius: BorderRadius.circular(18),
                  ),
                  child: Column(
                    children: <Widget>[
                      for (int i = 0; i < stops.length; i++) ...<Widget>[
                        if (i > 0)
                          Container(
                            height: 1,
                            margin: const EdgeInsets.symmetric(horizontal: 18),
                            color: AppTheme.borderLight.withOpacity(.7),
                          ),
                        _StopRow(s: stops[i]),
                      ],
                    ],
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}

class _NearStop {
  const _NearStop({required this.stop, required this.distanceM, this.etaMin, this.routeCode});
  final Stop stop;
  final double distanceM;
  final double? etaMin;
  final String? routeCode;
}

class _StopRow extends StatelessWidget {
  const _StopRow({required this.s});
  final _NearStop s;
  @override
  Widget build(BuildContext context) {
    final String dist = s.distanceM >= 1000
        ? '${(s.distanceM / 1000).toStringAsFixed(1)} كم'
        : '${s.distanceM.round()} م';
    return InkWell(
      onTap: () {},
      child: Padding(
        padding: const EdgeInsets.fromLTRB(18, 18, 18, 18),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: <Widget>[
            // Numeric anchor — distance, set in serif
            SizedBox(
              width: 64,
              child: Text(
                dist,
                style: const TextStyle(
                  fontFamily: AppTheme.fontSerif,
                  fontFamilyFallback: <String>['Georgia', 'serif'],
                  fontSize: 18,
                  color: AppTheme.brand700,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(s.stop.nameAr ?? s.stop.name,
                      style: const TextStyle(
                          fontSize: 16, fontWeight: FontWeight.w600)),
                  if (s.routeCode != null) ...<Widget>[
                    const SizedBox(height: 4),
                    Text('خط ${s.routeCode}',
                        style: const TextStyle(
                            color: AppTheme.textMuteLight, fontSize: 13)),
                  ],
                ],
              ),
            ),
            if (s.etaMin != null)
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: AppTheme.brand100,
                  borderRadius: BorderRadius.circular(999),
                  border: Border.all(color: AppTheme.brand500),
                ),
                child: Text(
                  '~${s.etaMin!.round()} د',
                  style: const TextStyle(
                      color: AppTheme.brand700,
                      fontWeight: FontWeight.w600,
                      fontSize: 12),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _Skeleton extends StatelessWidget {
  const _Skeleton();
  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.surfaceLight,
        border: Border.all(color: AppTheme.borderLight),
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        children: List<Widget>.generate(4, (int i) => const Padding(
          padding: EdgeInsets.symmetric(horizontal: 18, vertical: 18),
          child: Row(
            children: <Widget>[
              SizedBox(width: 64, child: _Bar(w: 38)),
              Expanded(child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[ _Bar(w: 180), SizedBox(height: 8), _Bar(w: 100) ],
              )),
              _Bar(w: 38),
            ],
          ),
        )),
      ),
    );
  }
}

class _Bar extends StatelessWidget {
  const _Bar({this.w = 100});
  final double w;
  @override
  Widget build(BuildContext context) => Container(
        width: w,
        height: 10,
        decoration: BoxDecoration(
            color: AppTheme.borderLight.withOpacity(.7),
            borderRadius: BorderRadius.circular(4)),
      );
}

class _EmptyRow extends StatelessWidget {
  const _EmptyRow();
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 32),
        child: Center(
          child: Text(
            'لا توجد محطات قريبة ضمن ١٫٥ كم.',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppTheme.textMuteLight),
          ),
        ),
      );
}

class _ErrorRow extends StatelessWidget {
  const _ErrorRow({required this.message});
  final String message;
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF1ED),
        border: Border.all(color: const Color(0xFFE5B8B0)),
        borderRadius: BorderRadius.circular(18),
      ),
      child: Text(message, style: const TextStyle(color: Color(0xFF6A1F18))),
    );
  }
}
