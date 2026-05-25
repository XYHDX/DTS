import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../core/api_client.dart';
import '../../core/theme.dart';

/// Claude-styled departure board for a single route.
///
/// Serif headline, tabular figures for arrival times, calm hairline rows,
/// next-departure callout at the top, soft "now" indicator that moves with
/// the clock. No animation noise — the room is the message.
class ScheduleScreen extends ConsumerStatefulWidget {
  const ScheduleScreen({super.key, required this.routeId, this.routeName});
  final String routeId;
  final String? routeName;
  @override
  ConsumerState<ScheduleScreen> createState() => _ScheduleScreenState();
}

class _ScheduleScreenState extends ConsumerState<ScheduleScreen> {
  AsyncValue<List<_Departure>> _state = const AsyncValue<List<_Departure>>.loading();
  Timer? _nowTimer;
  DateTime _now = DateTime.now();

  @override
  void initState() {
    super.initState();
    _refresh();
    _nowTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      if (mounted) setState(() => _now = DateTime.now());
    });
  }

  @override
  void dispose() {
    _nowTimer?.cancel();
    super.dispose();
  }

  Future<void> _refresh() async {
    setState(() => _state = const AsyncValue<List<_Departure>>.loading());
    try {
      final Response<dynamic> r = await ref
          .read(dioProvider)
          .get<dynamic>('/api/schedules/${widget.routeId}');
      final List<dynamic> rows = (r.data is List)
          ? r.data as List<dynamic>
          : ((r.data as Map<String, dynamic>?)?['departures'] as List<dynamic>?) ??
              const <dynamic>[];
      final List<_Departure> deps = rows
          .whereType<Map<String, dynamic>>()
          .map<_Departure?>(_Departure.tryFromJson)
          .whereType<_Departure>()
          .toList(growable: false);
      if (!mounted) return;
      setState(() => _state = AsyncValue<List<_Departure>>.data(deps));
    } catch (e, st) {
      if (!mounted) return;
      setState(() => _state = AsyncValue<List<_Departure>>.error(e, st));
    }
  }

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(widget.routeName ?? 'الجدول')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        color: AppTheme.brand600,
        child: _state.when(
          loading: () => _loadingScaffold(theme),
          error: (Object e, _) => _errorScaffold(theme, '$e'),
          data: (List<_Departure> deps) => _content(theme, deps),
        ),
      ),
    );
  }

  Widget _content(ThemeData theme, List<_Departure> deps) {
    final List<_Departure> upcoming = deps
        .where((_Departure d) => d.time.isAfter(_now.subtract(const Duration(minutes: 1))))
        .toList()
      ..sort((_Departure a, _Departure b) => a.time.compareTo(b.time));
    final _Departure? next = upcoming.isEmpty ? null : upcoming.first;

    return ListView(
      padding: const EdgeInsets.fromLTRB(24, 8, 24, 48),
      physics: const AlwaysScrollableScrollPhysics(),
      children: <Widget>[
        // Eyebrow + headline
        Text('الجدول',
            style: TextStyle(
                fontSize: 11,
                letterSpacing: 1.4,
                fontWeight: FontWeight.w600,
                color: AppTheme.brand600)),
        const SizedBox(height: 4),
        Text(widget.routeName ?? 'الخط ${widget.routeId}',
            style: theme.textTheme.displaySmall),
        const SizedBox(height: 4),
        Text(
          'مواعيد الانطلاق من بداية الخط · تحديث ${DateFormat.Hm("ar").format(_now)}',
          style: theme.textTheme.bodyMedium?.copyWith(color: AppTheme.textMuteLight),
        ),

        const SizedBox(height: 24),

        if (next != null) _NextCallout(dep: next, now: _now),

        const SizedBox(height: 28),

        Text('قادم',
            style: TextStyle(
                fontSize: 11,
                letterSpacing: 1.4,
                fontWeight: FontWeight.w600,
                color: AppTheme.brand600)),
        const SizedBox(height: 10),
        if (upcoming.length <= 1)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 24),
            child: Center(
              child: Text(
                'لا مزيد من الرحلات لليوم.',
                style: theme.textTheme.bodyMedium?.copyWith(color: AppTheme.textMuteLight),
              ),
            ),
          )
        else
          Container(
            decoration: BoxDecoration(
              color: AppTheme.surfaceLight,
              border: Border.all(color: AppTheme.borderLight),
              borderRadius: BorderRadius.circular(18),
            ),
            child: Column(
              children: <Widget>[
                for (int i = 1; i < upcoming.length; i++) ...<Widget>[
                  if (i > 1)
                    Container(
                      height: 1,
                      margin: const EdgeInsets.symmetric(horizontal: 18),
                      color: AppTheme.borderLight.withOpacity(.7),
                    ),
                  _ScheduleRow(dep: upcoming[i], now: _now),
                ],
              ],
            ),
          ),

        const SizedBox(height: 28),
        Text(
          '${deps.length} رحلة مجدوّلة اليوم · بتوقيت دمشق.',
          style: theme.textTheme.bodySmall
              ?.copyWith(color: AppTheme.textMuteLight),
        ),
      ],
    );
  }

  Widget _loadingScaffold(ThemeData theme) => ListView(
        padding: const EdgeInsets.all(24),
        children: List<Widget>.generate(
          6,
          (int i) => Container(
            margin: const EdgeInsets.only(bottom: 12),
            height: 56,
            decoration: BoxDecoration(
                color: AppTheme.borderLight.withOpacity(.4),
                borderRadius: BorderRadius.circular(12)),
          ),
        ),
      );

  Widget _errorScaffold(ThemeData theme, String msg) => ListView(
        padding: const EdgeInsets.all(24),
        physics: const AlwaysScrollableScrollPhysics(),
        children: <Widget>[
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: const Color(0xFFFFF1ED),
              border: Border.all(color: const Color(0xFFE5B8B0)),
              borderRadius: BorderRadius.circular(18),
            ),
            child: Text('تعذّر تحميل الجدول. $msg',
                style: const TextStyle(color: Color(0xFF6A1F18))),
          ),
        ],
      );
}

class _Departure {
  const _Departure({required this.time, this.platform, this.headsign});
  final DateTime time;
  final String? platform;
  final String? headsign;
  static _Departure? tryFromJson(Map<String, dynamic> j) {
    final String raw = (j['time'] ?? j['departure'] ?? j['scheduled_at'] ?? '').toString();
    final DateTime? t = DateTime.tryParse(raw);
    if (t == null) return null;
    return _Departure(
      time: t,
      platform: j['platform']?.toString(),
      headsign: (j['headsign'] ?? j['destination']) as String?,
    );
  }
}

class _NextCallout extends StatelessWidget {
  const _NextCallout({required this.dep, required this.now});
  final _Departure dep;
  final DateTime now;
  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    final Duration delta = dep.time.difference(now);
    final String relative = _relative(delta);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: AppTheme.brand100.withOpacity(.55),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: const Color(0xFFF6D4C2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text('الانطلاق القادم',
              style: TextStyle(
                  fontSize: 11,
                  letterSpacing: 1.4,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.brand700)),
          const SizedBox(height: 4),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: <Widget>[
              Text(
                DateFormat.Hm('ar').format(dep.time),
                style: const TextStyle(
                  fontFamily: AppTheme.fontSerif,
                  fontFamilyFallback: <String>['Georgia', 'serif'],
                  fontSize: 56,
                  height: 1.05,
                  fontWeight: FontWeight.w500,
                  color: AppTheme.brand700,
                  fontFeatures: <FontFeature>[FontFeature.tabularFigures()],
                ),
              ),
              const SizedBox(width: 12),
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Text(relative,
                    style: theme.textTheme.bodyLarge
                        ?.copyWith(color: AppTheme.textSoftLight)),
              ),
            ],
          ),
          if (dep.headsign != null) ...<Widget>[
            const SizedBox(height: 4),
            Text(dep.headsign!,
                style: theme.textTheme.bodyMedium
                    ?.copyWith(color: AppTheme.textMuteLight)),
          ],
        ],
      ),
    );
  }

  String _relative(Duration d) {
    if (d.inSeconds <= 0) return 'الآن';
    if (d.inMinutes < 1) return 'بعد لحظات';
    if (d.inMinutes < 60) return 'بعد ${d.inMinutes} د';
    final int h = d.inHours;
    final int m = d.inMinutes.remainder(60);
    return m == 0 ? 'بعد $h س' : 'بعد $h س $m د';
  }
}

class _ScheduleRow extends StatelessWidget {
  const _ScheduleRow({required this.dep, required this.now});
  final _Departure dep;
  final DateTime now;
  @override
  Widget build(BuildContext context) {
    final bool soon = dep.time.difference(now).inMinutes <= 5;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
      child: Row(
        children: <Widget>[
          SizedBox(
            width: 72,
            child: Text(
              DateFormat.Hm('ar').format(dep.time),
              style: TextStyle(
                fontFeatures: const <FontFeature>[FontFeature.tabularFigures()],
                fontSize: 17,
                color: soon ? AppTheme.brand700 : AppTheme.textLight,
                fontWeight: soon ? FontWeight.w600 : FontWeight.w500,
              ),
            ),
          ),
          Expanded(
            child: Text(
              dep.headsign ?? '—',
              style: const TextStyle(color: AppTheme.textSoftLight),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          if (dep.platform != null)
            Text('رصيف ${dep.platform}',
                style: const TextStyle(
                    color: AppTheme.textMuteLight, fontSize: 12)),
        ],
      ),
    );
  }
}
