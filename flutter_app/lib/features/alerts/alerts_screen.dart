import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../core/api_client.dart';
import '../../core/theme.dart';
import '../../shared/widgets/empty_state.dart';

/// Claude-styled service-alert inbox.
///
/// Reads `/api/admin/alerts?limit=…` if authenticated, else `/api/alerts`
/// (the public passenger-facing feed). Severity becomes a quiet badge.
/// Empty state is warm rather than apologetic — "no alerts today" reads
/// like good news.
class AlertsScreen extends ConsumerStatefulWidget {
  const AlertsScreen({super.key});
  @override
  ConsumerState<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends ConsumerState<AlertsScreen> {
  AsyncValue<List<_Alert>> _state = const AsyncValue<List<_Alert>>.loading();

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    setState(() => _state = const AsyncValue<List<_Alert>>.loading());
    try {
      Response<dynamic> r;
      try {
        r = await ref.read(dioProvider).get<dynamic>('/api/alerts');
      } on DioException {
        r = await ref
            .read(dioProvider)
            .get<dynamic>('/api/admin/alerts?limit=50');
      }
      final List<dynamic> rows = (r.data is List)
          ? r.data as List<dynamic>
          : ((r.data as Map<String, dynamic>?)?['alerts'] as List<dynamic>?) ??
              const <dynamic>[];
      final List<_Alert> alerts = rows
          .whereType<Map<String, dynamic>>()
          .map<_Alert?>(_Alert.tryFromJson)
          .whereType<_Alert>()
          .toList(growable: false)
        ..sort((_Alert a, _Alert b) => b.createdAt.compareTo(a.createdAt));
      if (!mounted) return;
      setState(() => _state = AsyncValue<List<_Alert>>.data(alerts));
    } catch (e, st) {
      if (!mounted) return;
      setState(() => _state = AsyncValue<List<_Alert>>.error(e, st));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('التنبيهات')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        color: AppTheme.brand600,
        child: _state.when(
          loading: () => ListView(
            padding: const EdgeInsets.all(24),
            children: List<Widget>.generate(
              4,
              (int i) => Container(
                margin: const EdgeInsets.only(bottom: 12),
                height: 72,
                decoration: BoxDecoration(
                  color: AppTheme.borderLight.withOpacity(.4),
                  borderRadius: BorderRadius.circular(14),
                ),
              ),
            ),
          ),
          error: (Object e, _) => ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            children: <Widget>[
              SizedBox(
                height: MediaQuery.of(context).size.height * 0.7,
                child: EmptyState(
                  illustration: EmptyKind.offline,
                  title: 'تعذّر تحميل التنبيهات',
                  body: 'تحقّق من اتصالك ثم اسحب للتحديث.',
                  actionLabel: 'إعادة المحاولة',
                  onAction: _refresh,
                ),
              ),
            ],
          ),
          data: (List<_Alert> alerts) {
            if (alerts.isEmpty) {
              return ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                children: <Widget>[
                  SizedBox(
                    height: MediaQuery.of(context).size.height * 0.7,
                    child: const EmptyState(
                      illustration: EmptyKind.inbox,
                      title: 'لا تنبيهات اليوم',
                      body: 'كل الخطوط تعمل بسلاسة. حين يستجدّ شيء سنرسل تنبيهاً.',
                    ),
                  ),
                ],
              );
            }
            return ListView.separated(
              padding: const EdgeInsets.fromLTRB(24, 16, 24, 32),
              physics: const AlwaysScrollableScrollPhysics(),
              itemCount: alerts.length,
              separatorBuilder: (_, __) => const SizedBox(height: 10),
              itemBuilder: (BuildContext _, int i) =>
                  _AlertCard(alert: alerts[i]),
            );
          },
        ),
      ),
    );
  }
}

class _Alert {
  const _Alert({
    required this.id,
    required this.severity,
    required this.title,
    required this.body,
    required this.createdAt,
    this.routeCode,
  });
  final String id;
  final _Severity severity;
  final String title;
  final String body;
  final DateTime createdAt;
  final String? routeCode;

  static _Alert? tryFromJson(Map<String, dynamic> j) {
    final String? id = j['id']?.toString();
    if (id == null) return null;
    final DateTime created = DateTime.tryParse(
            (j['created_at'] ?? j['ts'] ?? '').toString()) ??
        DateTime.now();
    final String sev = (j['severity'] ?? 'info').toString();
    return _Alert(
      id: id,
      severity: _Severity.parse(sev),
      title: (j['title_ar'] ??
              j['title'] ??
              j['type'] ??
              'تنبيه')
          .toString(),
      body: (j['body_ar'] ?? j['body'] ?? j['description'] ?? '').toString(),
      createdAt: created,
      routeCode: j['route_code']?.toString() ?? j['route_id']?.toString(),
    );
  }
}

enum _Severity {
  critical,
  high,
  medium,
  low,
  info;

  static _Severity parse(String s) {
    switch (s.toLowerCase()) {
      case 'critical': return _Severity.critical;
      case 'high':     return _Severity.high;
      case 'medium':   return _Severity.medium;
      case 'low':      return _Severity.low;
      default:         return _Severity.info;
    }
  }
}

extension on _Severity {
  (Color bg, Color fg, Color border, String label) get visual {
    switch (this) {
      case _Severity.critical: return (
          const Color(0xFFFFE0DA),
          const Color(0xFF7A1F18),
          const Color(0xFFE5B8B0),
          'عاجل',
        );
      case _Severity.high: return (
          const Color(0xFFF5DEDA),
          const Color(0xFF6A1F18),
          const Color(0xFFE5B8B0),
          'مرتفع',
        );
      case _Severity.medium: return (
          const Color(0xFFF5E4D2),
          const Color(0xFF6F3B0F),
          const Color(0xFFE5C8A8),
          'متوسط',
        );
      case _Severity.low: return (
          const Color(0xFFE4ECE7),
          const Color(0xFF2C5A3E),
          const Color(0xFFC9D9CD),
          'منخفض',
        );
      case _Severity.info: return (
          const Color(0xFFDDE6EE),
          const Color(0xFF2C4356),
          const Color(0xFFBFCFDF),
          'معلومات',
        );
    }
  }
}

class _AlertCard extends StatelessWidget {
  const _AlertCard({required this.alert});
  final _Alert alert;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    final (Color bg, Color fg, Color border, String label) = alert.severity.visual;
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.surfaceLight,
        border: Border.all(color: AppTheme.borderLight),
        borderRadius: BorderRadius.circular(16),
      ),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: bg,
                  border: Border.all(color: border),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(label,
                    style: TextStyle(
                        color: fg, fontSize: 11, fontWeight: FontWeight.w600)),
              ),
              const SizedBox(width: 8),
              if (alert.routeCode != null)
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: AppTheme.brand100,
                    border: Border.all(color: const Color(0xFFF6D4C2)),
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    'خط ${alert.routeCode}',
                    style: const TextStyle(
                        color: AppTheme.brand700,
                        fontSize: 11,
                        fontWeight: FontWeight.w600),
                  ),
                ),
              const Spacer(),
              Text(
                DateFormat('d MMM · HH:mm', 'ar').format(alert.createdAt),
                style: theme.textTheme.bodySmall
                    ?.copyWith(color: AppTheme.textMuteLight),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(alert.title, style: theme.textTheme.titleMedium),
          if (alert.body.isNotEmpty) ...<Widget>[
            const SizedBox(height: 4),
            Text(alert.body,
                style: theme.textTheme.bodyMedium
                    ?.copyWith(color: AppTheme.textMuteLight, height: 1.55)),
          ],
        ],
      ),
    );
  }
}
