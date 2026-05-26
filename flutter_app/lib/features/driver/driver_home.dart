import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:go_router/go_router.dart';

import '../../core/api_client.dart';
import '../../core/theme.dart';
import '../auth/auth_controller.dart';

class DriverHome extends ConsumerStatefulWidget {
  const DriverHome({super.key});
  @override
  ConsumerState<DriverHome> createState() => _DriverHomeState();
}

class _DriverHomeState extends ConsumerState<DriverHome> {
  bool _onTrip = false;
  String? _tripId;
  int _pax = 0;
  double _kpH = 0;
  double _kmTotal = 0;
  Position? _last;
  StreamSubscription<Position>? _gpsSub;
  Duration _elapsed = Duration.zero;
  Timer? _ticker;

  @override
  void dispose() {
    _gpsSub?.cancel();
    _ticker?.cancel();
    super.dispose();
  }

  Future<void> _startTrip() async {
    final Dio dio = ref.read(dioProvider);
    String? id;
    try {
      final Response<dynamic> r = await dio.post<dynamic>('/api/driver/trip/start');
      id = (r.data is Map ? (r.data as Map)['trip_id'] : null) as String?;
    } on DioException {
      id = 'local-${DateTime.now().millisecondsSinceEpoch}';
    }
    setState(() {
      _tripId = id ?? 'local-${DateTime.now().millisecondsSinceEpoch}';
      _onTrip = true;
      _pax = 0;
      _kmTotal = 0;
      _last = null;
      _elapsed = Duration.zero;
    });
    _ticker = Timer.periodic(const Duration(seconds: 1),
        (_) => setState(() => _elapsed += const Duration(seconds: 1)));
    _gpsSub = Geolocator.getPositionStream(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.bestForNavigation,
        distanceFilter: 8,
      ),
    ).listen(_onPosition);
  }

  Future<void> _endTrip() async {
    _ticker?.cancel();
    await _gpsSub?.cancel();
    final Dio dio = ref.read(dioProvider);
    try {
      await dio.post<dynamic>('/api/driver/trip/end', data: <String, Object?>{
        'trip_id': _tripId,
        'passengers': _pax,
        'distance_km': _kmTotal,
      });
    } on DioException {/* keep silent — sync queue later */}
    setState(() => _onTrip = false);
  }

  Future<void> _onPosition(Position p) async {
    if (_last != null) {
      final double m = Geolocator.distanceBetween(
          _last!.latitude, _last!.longitude, p.latitude, p.longitude);
      if (m < 1000) _kmTotal += m / 1000;
    }
    _last = p;
    setState(() => _kpH = (p.speed * 3.6).clamp(0, 200));
    HapticFeedback.selectionClick();
    try {
      await ref.read(dioProvider).post<dynamic>('/api/driver/position',
          data: <String, Object?>{
            'lat': p.latitude,
            'lon': p.longitude,
            'speed': _kpH,
            'heading': p.heading,
          });
    } on DioException {/* keep silent — backend tolerates retries */}
  }

  Future<void> _bumpPax(int delta) async {
    setState(() => _pax = (_pax + delta).clamp(0, 120));
    HapticFeedback.lightImpact();
    if (_tripId == null) return;
    try {
      await ref.read(dioProvider).post<dynamic>(
        '/api/driver/trip/passenger-count',
        data: <String, Object?>{'trip_id': _tripId, 'count': _pax},
      );
    } on DioException {/* offline-tolerant */}
  }

  @override
  Widget build(BuildContext context) {
    final AuthState a = ref.watch(authControllerProvider);
    return Scaffold(
      appBar: AppBar(
        title: const Text('وضع السائق'),
        actions: <Widget>[
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () async {
              await ref.read(authControllerProvider.notifier).logout();
              if (context.mounted) context.go('/');
            },
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  begin: Alignment.topRight,
                  end: Alignment.bottomLeft,
                  colors: <Color>[AppTheme.brand800, AppTheme.brand700],
                ),
                borderRadius: BorderRadius.circular(16),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text('السائق ${a.user?['name'] ?? a.user?['email'] ?? ''}',
                      style: const TextStyle(color: Colors.white70)),
                  const SizedBox(height: 4),
                  Text('الخط: ${a.user?['route_name'] ?? '—'}',
                      style: const TextStyle(
                          color: Colors.white,
                          fontSize: 22,
                          fontWeight: FontWeight.w700)),
                ],
              ),
            ),
            const SizedBox(height: 16),
            SizedBox(
              height: 72,
              child: FilledButton(
                style: FilledButton.styleFrom(
                  backgroundColor: _onTrip ? AppTheme.danger : AppTheme.brand500,
                ),
                onPressed: _onTrip ? _endTrip : _startTrip,
                child: Text(_onTrip ? '■ إنهاء الرحلة' : '▶ بدء الرحلة',
                    style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
              ),
            ),
            const SizedBox(height: 16),
            if (_onTrip) ...<Widget>[
              Card(
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
                  child: Row(
                    children: <Widget>[
                      _RoundButton(label: '−', onTap: () => _bumpPax(-1)),
                      Expanded(
                        child: Column(
                          children: <Widget>[
                            Text('$_pax',
                                style: const TextStyle(
                                    fontSize: 48, fontWeight: FontWeight.w700)),
                            const Text('عدد الركاب',
                                style: TextStyle(color: Colors.black54)),
                          ],
                        ),
                      ),
                      _RoundButton(label: '+', onTap: () => _bumpPax(1)),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 12),
              GridView.count(
                crossAxisCount: 2,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                childAspectRatio: 2.2,
                crossAxisSpacing: 12,
                mainAxisSpacing: 12,
                children: <Widget>[
                  _MetricTile(label: 'السرعة', value: '${_kpH.round()} كم/س'),
                  _MetricTile(label: 'المسافة', value: '${_kmTotal.toStringAsFixed(1)} كم'),
                  _MetricTile(label: 'المدة', value: _fmtDuration(_elapsed)),
                  _MetricTile(
                      label: 'الإشغال',
                      value: '${((_pax / 60) * 100).round()}٪'),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  String _fmtDuration(Duration d) {
    final int h = d.inHours;
    final int m = d.inMinutes.remainder(60);
    if (h == 0) return '$m د';
    return '$h:${m.toString().padLeft(2, '0')}';
  }
}

class _RoundButton extends StatelessWidget {
  const _RoundButton({required this.label, required this.onTap});
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkResponse(
      onTap: onTap,
      child: Container(
        width: 64,
        height: 64,
        decoration: BoxDecoration(
            color: AppTheme.brand100,
            borderRadius: BorderRadius.circular(12)),
        alignment: Alignment.center,
        child: Text(label,
            style: const TextStyle(
                fontSize: 32,
                fontWeight: FontWeight.w700,
                color: AppTheme.brand700)),
      ),
    );
  }
}

class _MetricTile extends StatelessWidget {
  const _MetricTile({required this.label, required this.value});
  final String label;
  final String value;
  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(label,
                style: const TextStyle(
                    color: Colors.black54,
                    fontSize: 12,
                    fontWeight: FontWeight.w600)),
            const SizedBox(height: 4),
            Text(value,
                style: const TextStyle(
                    fontSize: 20, fontWeight: FontWeight.w700)),
          ],
        ),
      ),
    );
  }
}
