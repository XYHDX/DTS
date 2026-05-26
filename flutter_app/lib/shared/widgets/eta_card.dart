import 'package:flutter/material.dart';

import '../../core/theme.dart';

/// A friendly, calm "next arrival" card.
///
/// Claude-styled: warm cream surface, serif numeric anchor, soft border,
/// secondary line with the human-readable relative time. No animation chrome.
///
/// Usage:
///   EtaCard(
///     stopName: 'ساحة الأمويين',
///     etaMinutes: 4,
///     routeCode: 'R-12',
///   )
class EtaCard extends StatelessWidget {
  const EtaCard({
    super.key,
    required this.stopName,
    required this.etaMinutes,
    this.routeCode,
    this.headsign,
    this.onTap,
    this.compact = false,
  });

  final String stopName;
  final int etaMinutes;
  final String? routeCode;
  final String? headsign;
  final VoidCallback? onTap;
  final bool compact;

  String get _arNum {
    if (etaMinutes < 0) return 'فات';
    if (etaMinutes == 0) return 'الآن';
    return '${etaMinutes}';
  }

  String get _label {
    if (etaMinutes < 0) return 'فات الموعد المتوقع';
    if (etaMinutes == 0) return 'يصل الآن';
    if (etaMinutes == 1) return 'دقيقة';
    if (etaMinutes < 11) return 'دقائق';
    return 'دقيقة';
  }

  bool get _isNow => etaMinutes <= 0;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    final Color surface = _isNow ? AppTheme.brand100.withOpacity(.55) : AppTheme.surfaceLight;
    final Color borderColor = _isNow ? const Color(0xFFF6D4C2) : AppTheme.borderLight;
    final Color anchorColor = _isNow ? AppTheme.brand700 : AppTheme.brand600;

    final Widget content = Padding(
      padding: EdgeInsets.symmetric(
          horizontal: compact ? 14 : 18, vertical: compact ? 12 : 16),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: <Widget>[
          // Serif numeric anchor
          SizedBox(
            width: compact ? 64 : 78,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Text(
                  _arNum,
                  style: TextStyle(
                    fontFamily: AppTheme.fontSerif,
                    fontFamilyFallback: const <String>['Georgia', 'serif'],
                    fontSize: compact ? 32 : 42,
                    fontWeight: FontWeight.w500,
                    color: anchorColor,
                    letterSpacing: -1.2,
                    height: 1.0,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  _label,
                  style: theme.textTheme.bodySmall
                      ?.copyWith(color: AppTheme.textMuteLight),
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Text(
                  stopName,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: theme.textTheme.titleMedium,
                ),
                if (routeCode != null || headsign != null) ...<Widget>[
                  const SizedBox(height: 4),
                  Wrap(
                    spacing: 8,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: <Widget>[
                      if (routeCode != null)
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: AppTheme.brand100,
                            borderRadius: BorderRadius.circular(999),
                            border: Border.all(color: const Color(0xFFF6D4C2)),
                          ),
                          child: Text(
                            routeCode!,
                            style: const TextStyle(
                              color: AppTheme.brand700,
                              fontWeight: FontWeight.w700,
                              fontSize: 11,
                            ),
                          ),
                        ),
                      if (headsign != null)
                        Text(
                          headsign!,
                          style: theme.textTheme.bodySmall
                              ?.copyWith(color: AppTheme.textMuteLight),
                        ),
                    ],
                  ),
                ],
              ],
            ),
          ),
          if (onTap != null) ...<Widget>[
            const SizedBox(width: 8),
            const Icon(Icons.chevron_left,
                color: AppTheme.textMuteLight, size: 20),
          ],
        ],
      ),
    );

    return Container(
      decoration: BoxDecoration(
        color: surface,
        border: Border.all(color: borderColor),
        borderRadius: BorderRadius.circular(16),
      ),
      child: onTap == null
          ? content
          : Material(
              color: Colors.transparent,
              child: InkWell(
                onTap: onTap,
                borderRadius: BorderRadius.circular(16),
                child: content,
              ),
            ),
    );
  }
}
