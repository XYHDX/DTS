import 'package:flutter/material.dart';

import '../../core/theme.dart';

/// Claude-styled driver shift summary.
///
/// Shown when the driver ends a trip. Large serif numerals on a calm
/// cream surface; secondary metrics in a tabular grid; one primary CTA.
class ShiftSummary {
  const ShiftSummary({
    required this.tripId,
    required this.routeName,
    required this.passengers,
    required this.distanceKm,
    required this.durationMinutes,
    required this.maxSpeedKph,
    required this.onTimePercentage,
    required this.incidents,
  });
  final String tripId;
  final String routeName;
  final int passengers;
  final double distanceKm;
  final int durationMinutes;
  final int maxSpeedKph;
  final int onTimePercentage;
  final int incidents;
}

class ShiftSummaryScreen extends StatelessWidget {
  const ShiftSummaryScreen({super.key, required this.summary, this.onDone});
  final ShiftSummary summary;
  final VoidCallback? onDone;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    final String duration = summary.durationMinutes >= 60
        ? '${summary.durationMinutes ~/ 60} س ${summary.durationMinutes % 60} د'
        : '${summary.durationMinutes} د';

    return Scaffold(
      appBar: AppBar(
        leading: const SizedBox.shrink(),
        title: const Text('ملخّص الرحلة'),
        automaticallyImplyLeading: false,
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(24, 16, 24, 48),
        children: <Widget>[
          // Eyebrow
          Text(
            'انتهت الرحلة',
            style: TextStyle(
              fontSize: 11,
              letterSpacing: 1.4,
              fontWeight: FontWeight.w600,
              color: AppTheme.brand600,
            ),
          ),
          const SizedBox(height: 8),

          // Display number — passengers carried, set in serif
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: <Widget>[
              Text(
                '${summary.passengers}',
                style: const TextStyle(
                  fontFamily: AppTheme.fontSerif,
                  fontFamilyFallback: <String>['Georgia', 'serif'],
                  fontSize: 96,
                  height: 0.95,
                  fontWeight: FontWeight.w500,
                  color: AppTheme.brand700,
                  letterSpacing: -2,
                ),
              ),
              const SizedBox(width: 12),
              Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: Text(
                  'راكب',
                  style: theme.textTheme.titleLarge?.copyWith(
                      color: AppTheme.textSoftLight,
                      fontWeight: FontWeight.w500),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          Text(summary.routeName, style: theme.textTheme.titleMedium),
          const SizedBox(height: 4),
          Text(
            'استمرت الرحلة $duration وقطعت ${summary.distanceKm.toStringAsFixed(1)} كم.',
            style: theme.textTheme.bodyLarge?.copyWith(color: AppTheme.textMuteLight),
          ),

          const SizedBox(height: 32),

          // Detail grid — Claude-like tabular spec list
          Container(
            decoration: BoxDecoration(
              color: AppTheme.surfaceLight,
              border: Border.all(color: AppTheme.borderLight),
              borderRadius: BorderRadius.circular(18),
            ),
            child: Column(
              children: <Widget>[
                _SpecRow(label: 'المسافة', value: '${summary.distanceKm.toStringAsFixed(1)} كم'),
                const _Hairline(),
                _SpecRow(label: 'المدة',   value: duration),
                const _Hairline(),
                _SpecRow(label: 'الذروة',  value: '${summary.maxSpeedKph} كم/س'),
                const _Hairline(),
                _SpecRow(
                  label: 'الالتزام بالموعد',
                  value: '${summary.onTimePercentage}%',
                  valueColor: _onTimeColor(summary.onTimePercentage),
                ),
                const _Hairline(),
                _SpecRow(
                  label: 'حوادث',
                  value: summary.incidents == 0
                      ? 'لا شيء'
                      : '${summary.incidents}',
                  valueColor: summary.incidents == 0
                      ? AppTheme.success
                      : AppTheme.danger,
                ),
              ],
            ),
          ),

          const SizedBox(height: 24),

          // A reflective note — Claude likes a single, calm sentence
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: AppTheme.brand100.withOpacity(0.55),
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: const Color(0xFFF6D4C2)),
            ),
            child: Text(
              _reflection(summary),
              style: theme.textTheme.bodyLarge?.copyWith(
                color: AppTheme.brand700,
                fontStyle: FontStyle.italic,
                height: 1.55,
              ),
            ),
          ),

          const SizedBox(height: 32),

          FilledButton(
            onPressed: onDone ?? () => Navigator.of(context).pop(),
            child: const Text('انتهيت'),
          ),
          const SizedBox(height: 12),
          TextButton(
            onPressed: () {},
            style: TextButton.styleFrom(foregroundColor: AppTheme.textSoftLight),
            child: const Text('تنزيل سجل الرحلة'),
          ),

          const SizedBox(height: 32),
          Center(
            child: Text(
              'رقم الرحلة · ${summary.tripId}',
              style: theme.textTheme.bodySmall
                  ?.copyWith(color: AppTheme.textMuteLight),
            ),
          ),
        ],
      ),
    );
  }

  Color _onTimeColor(int pct) {
    if (pct >= 90) return AppTheme.success;
    if (pct >= 75) return AppTheme.brand700;
    return AppTheme.warning;
  }

  String _reflection(ShiftSummary s) {
    if (s.incidents > 0) return 'شكراً على عملك. لاحقت ${s.incidents} حادثة هذه المرة — راجع التفاصيل لاحقاً.';
    if (s.onTimePercentage >= 90) return 'أداء ممتاز — وصلت في الموعد لـ ${s.onTimePercentage}% من المحطات. أحسنت.';
    if (s.passengers >= 60) return 'رحلة مزدحمة — ${s.passengers} راكباً. وقت يومك وقت ثمين.';
    return 'رحلة هادئة. شكراً لخدمتك مدينة دمشق.';
  }
}

class _SpecRow extends StatelessWidget {
  const _SpecRow({required this.label, required this.value, this.valueColor});
  final String label;
  final String value;
  final Color? valueColor;
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
      child: Row(
        children: <Widget>[
          Expanded(
            child: Text(label,
                style: const TextStyle(
                    color: AppTheme.textSoftLight,
                    fontWeight: FontWeight.w500)),
          ),
          Text(
            value,
            style: TextStyle(
              fontFeatures: const <FontFeature>[FontFeature.tabularFigures()],
              fontWeight: FontWeight.w600,
              color: valueColor ?? AppTheme.textLight,
            ),
          ),
        ],
      ),
    );
  }
}

class _Hairline extends StatelessWidget {
  const _Hairline();
  @override
  Widget build(BuildContext context) => Container(
        height: 1,
        margin: const EdgeInsets.symmetric(horizontal: 18),
        color: AppTheme.borderLight.withOpacity(.7),
      );
}

