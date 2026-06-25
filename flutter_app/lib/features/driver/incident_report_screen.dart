import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';

import '../../core/api_client.dart';
import '../../core/theme.dart';

enum IncidentKind { breakdown, road_block, accident, security, other }

extension on IncidentKind {
  String get arLabel => switch (this) {
        IncidentKind.breakdown  => 'عطل ميكانيكي',
        IncidentKind.road_block => 'إغلاق طريق',
        IncidentKind.accident   => 'حادث',
        IncidentKind.security   => 'حدث أمني',
        IncidentKind.other      => 'أخرى',
      };
  String get arDescription => switch (this) {
        IncidentKind.breakdown  => 'الحافلة عاجزة عن الحركة.',
        IncidentKind.road_block => 'الطريق مغلق أو ازدحام شديد.',
        IncidentKind.accident   => 'حادث مع سيارة أو راجل.',
        IncidentKind.security   => 'حدث يستدعي تدخّل الشرطة.',
        IncidentKind.other      => 'وصف يدوي.',
      };
  String get serverValue => name;
}

/// Three-step incident flow:
///   1) pick a kind
///   2) (optional) add a free-text note
///   3) confirm + submit
///
/// Claude-styled: serif eyebrow + headline, ChoiceChips for the kind, calm
/// summary card on the confirm step, single coral CTA.
class IncidentReportScreen extends ConsumerStatefulWidget {
  const IncidentReportScreen({super.key, this.tripId});
  final String? tripId;
  @override
  ConsumerState<IncidentReportScreen> createState() => _IncidentReportScreenState();
}

class _IncidentReportScreenState extends ConsumerState<IncidentReportScreen> {
  int _step = 0;
  IncidentKind? _kind;
  final TextEditingController _noteCtl = TextEditingController();
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _noteCtl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() {
      _submitting = true;
      _error = null;
    });
    Position? p;
    try {
      p = await Geolocator.getCurrentPosition(
              desiredAccuracy: LocationAccuracy.high)
          .timeout(const Duration(seconds: 5));
    } catch (_) {/* without GPS still acceptable */}
    try {
      await ref.read(dioProvider).post<dynamic>('/api/driver/incident',
          data: <String, Object?>{
            'trip_id': widget.tripId,
            'kind': _kind!.serverValue,
            'note': _noteCtl.text.trim().isEmpty ? null : _noteCtl.text.trim(),
            'lat': p?.latitude,
            'lon': p?.longitude,
            'ts': DateTime.now().toUtc().toIso8601String(),
          });
      if (!mounted) return;
      HapticFeedback.mediumImpact();
      Navigator.of(context).pop(true);
    } on DioException catch (e) {
      if (!mounted) return;
      setState(() => _error = 'تعذّر الإرسال. ${e.response?.statusCode ?? 'لا اتصال'}');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('الإبلاغ عن حدث'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => Navigator.of(context).pop(false),
          tooltip: 'إغلاق',
        ),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              _ProgressDots(current: _step),
              const SizedBox(height: 24),
              Expanded(child: _stepBody(theme)),
              if (_error != null) ...<Widget>[
                Container(
                  margin: const EdgeInsets.only(bottom: 12),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: const Color(0xFFFFF1ED),
                    border: Border.all(color: const Color(0xFFE5B8B0)),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(_error!, style: const TextStyle(color: Color(0xFF6A1F18))),
                ),
              ],
              _Footer(
                step: _step,
                canAdvance: _kind != null,
                submitting: _submitting,
                onBack: _step == 0 ? null : () => setState(() => _step -= 1),
                onNext: () {
                  if (_step < 2) {
                    setState(() => _step += 1);
                  } else {
                    _submit();
                  }
                },
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _stepBody(ThemeData theme) {
    switch (_step) {
      case 0:
        return _StepKind(
          selected: _kind,
          onSelect: (IncidentKind k) => setState(() => _kind = k),
        );
      case 1:
        return _StepNote(controller: _noteCtl, kind: _kind!);
      case 2:
      default:
        return _StepConfirm(kind: _kind!, note: _noteCtl.text.trim());
    }
  }
}

// --- pieces ------------------------------------------------------------------

class _ProgressDots extends StatelessWidget {
  const _ProgressDots({required this.current});
  final int current;
  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: <Widget>[
        for (int i = 0; i < 3; i++)
          Container(
            margin: const EdgeInsets.symmetric(horizontal: 4),
            width: i == current ? 28 : 8,
            height: 8,
            decoration: BoxDecoration(
              color: i <= current ? AppTheme.brand600 : AppTheme.borderLight,
              borderRadius: BorderRadius.circular(999),
            ),
          ),
      ],
    );
  }
}

class _StepKind extends StatelessWidget {
  const _StepKind({required this.selected, required this.onSelect});
  final IncidentKind? selected;
  final ValueChanged<IncidentKind> onSelect;
  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    return ListView(
      children: <Widget>[
        Text('ما الذي حدث؟', style: theme.textTheme.headlineMedium),
        const SizedBox(height: 4),
        Text(
          'اختر النوع الأقرب. التفاصيل في الخطوة التالية.',
          style: theme.textTheme.bodyLarge?.copyWith(color: AppTheme.textMuteLight),
        ),
        const SizedBox(height: 20),
        for (final IncidentKind k in IncidentKind.values)
          _Tile(
            label: k.arLabel,
            description: k.arDescription,
            selected: k == selected,
            onTap: () => onSelect(k),
          ),
      ],
    );
  }
}

class _Tile extends StatelessWidget {
  const _Tile({
    required this.label,
    required this.description,
    required this.selected,
    required this.onTap,
  });
  final String label;
  final String description;
  final bool selected;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(14),
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: selected ? AppTheme.brand100.withOpacity(.5) : AppTheme.surfaceLight,
              border: Border.all(
                color: selected ? AppTheme.brand500 : AppTheme.borderLight,
                width: selected ? 1.5 : 1,
              ),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Row(
              children: <Widget>[
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(label,
                          style: TextStyle(
                              fontWeight: FontWeight.w600,
                              color: selected
                                  ? AppTheme.brand700
                                  : AppTheme.textLight)),
                      const SizedBox(height: 2),
                      Text(description,
                          style: const TextStyle(
                              color: AppTheme.textMuteLight, fontSize: 13)),
                    ],
                  ),
                ),
                if (selected)
                  const Icon(Icons.check_rounded,
                      color: AppTheme.brand600, size: 22),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _StepNote extends StatelessWidget {
  const _StepNote({required this.controller, required this.kind});
  final TextEditingController controller;
  final IncidentKind kind;
  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    return ListView(
      children: <Widget>[
        Text('أضف ملاحظة', style: theme.textTheme.headlineMedium),
        const SizedBox(height: 4),
        Text(
          'وصف موجز يساعد المركز. اختياري.',
          style: theme.textTheme.bodyLarge?.copyWith(color: AppTheme.textMuteLight),
        ),
        const SizedBox(height: 16),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: AppTheme.brand100.withOpacity(.45),
            borderRadius: BorderRadius.circular(999),
            border: Border.all(color: const Color(0xFFF6D4C2)),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              const Icon(Icons.label_important_outline,
                  size: 14, color: AppTheme.brand700),
              const SizedBox(width: 6),
              Text(kind.arLabel,
                  style: const TextStyle(
                      color: AppTheme.brand700,
                      fontWeight: FontWeight.w600,
                      fontSize: 12)),
            ],
          ),
        ),
        const SizedBox(height: 20),
        TextField(
          controller: controller,
          maxLines: 5,
          maxLength: 300,
          textAlignVertical: TextAlignVertical.top,
          decoration: const InputDecoration(
            hintText: 'مثال: الطريق مغلق نتيجة عمل عسكري، تحويلة عبر شارع …',
            alignLabelWithHint: true,
          ),
        ),
      ],
    );
  }
}

class _StepConfirm extends StatelessWidget {
  const _StepConfirm({required this.kind, required this.note});
  final IncidentKind kind;
  final String note;
  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    return ListView(
      children: <Widget>[
        Text('راجع الإرسال', style: theme.textTheme.headlineMedium),
        const SizedBox(height: 4),
        Text(
          'سيُرسل بلاغك مع موقعك الحالي والوقت.',
          style: theme.textTheme.bodyLarge?.copyWith(color: AppTheme.textMuteLight),
        ),
        const SizedBox(height: 20),
        Container(
          decoration: BoxDecoration(
            color: AppTheme.surfaceLight,
            border: Border.all(color: AppTheme.borderLight),
            borderRadius: BorderRadius.circular(18),
          ),
          child: Column(
            children: <Widget>[
              _Row(label: 'النوع', value: kind.arLabel),
              const _Sep(),
              _Row(label: 'الوصف', value: note.isEmpty ? 'لا يوجد' : note),
              const _Sep(),
              _Row(label: 'الموقع', value: 'سيُرفق تلقائياً'),
              const _Sep(),
              _Row(
                label: 'الوقت',
                value: TimeOfDay.fromDateTime(DateTime.now()).format(context),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.label, required this.value});
  final String label;
  final String value;
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          SizedBox(
            width: 90,
            child: Text(label,
                style: const TextStyle(
                    color: AppTheme.textSoftLight, fontWeight: FontWeight.w500)),
          ),
          Expanded(
            child: Text(value,
                style: const TextStyle(
                    color: AppTheme.textLight, fontWeight: FontWeight.w500)),
          ),
        ],
      ),
    );
  }
}

class _Sep extends StatelessWidget {
  const _Sep();
  @override
  Widget build(BuildContext context) => Container(
        height: 1,
        margin: const EdgeInsets.symmetric(horizontal: 18),
        color: AppTheme.borderLight.withOpacity(.7),
      );
}

class _Footer extends StatelessWidget {
  const _Footer({
    required this.step,
    required this.canAdvance,
    required this.submitting,
    required this.onBack,
    required this.onNext,
  });
  final int step;
  final bool canAdvance;
  final bool submitting;
  final VoidCallback? onBack;
  final VoidCallback onNext;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: <Widget>[
        if (onBack != null)
          Expanded(
            child: OutlinedButton(
              onPressed: submitting ? null : onBack,
              child: const Text('السابق'),
            ),
          ),
        if (onBack != null) const SizedBox(width: 12),
        Expanded(
          flex: 2,
          child: FilledButton(
            onPressed: (submitting || (step == 0 && !canAdvance)) ? null : onNext,
            child: submitting
                ? const SizedBox(
                    height: 18,
                    width: 18,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: Colors.white))
                : Text(step < 2 ? 'التالي' : 'إرسال البلاغ'),
          ),
        ),
      ],
    );
  }
}
