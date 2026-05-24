import 'package:flutter/material.dart';

import '../../core/theme.dart';

/// A calm, friendly empty-state block.
///
/// Claude-styled: cream-circle illustration, serif headline, one-sentence
/// body, and a single coral text-button if an action makes sense. Never
/// uses the word "error" — empty states are about possibility, not failure.
///
/// Usage:
///   EmptyState(
///     illustration: EmptyKind.noResults,
///     title: 'لا توجد محطات قريبة',
///     body: 'جرّب الاقتراب من شارع رئيسي أو البحث عن خط بالاسم.',
///     actionLabel: 'بحث عن خط',
///     onAction: () => …,
///   )
enum EmptyKind { noResults, offline, inbox, empty, noLocation }

class EmptyState extends StatelessWidget {
  const EmptyState({
    super.key,
    required this.title,
    required this.body,
    this.illustration = EmptyKind.empty,
    this.actionLabel,
    this.onAction,
  });

  final String title;
  final String body;
  final EmptyKind illustration;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 360),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.center,
            children: <Widget>[
              SizedBox(
                width: 120,
                height: 120,
                child: CustomPaint(painter: _EmptyPainter(illustration)),
              ),
              const SizedBox(height: 16),
              Text(
                title,
                style: theme.textTheme.titleLarge,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 6),
              Text(
                body,
                style: theme.textTheme.bodyMedium
                    ?.copyWith(color: AppTheme.textMuteLight, height: 1.55),
                textAlign: TextAlign.center,
              ),
              if (actionLabel != null && onAction != null) ...<Widget>[
                const SizedBox(height: 16),
                TextButton(
                  onPressed: onAction,
                  style: TextButton.styleFrom(
                    foregroundColor: AppTheme.brand600,
                    textStyle: const TextStyle(fontWeight: FontWeight.w600),
                  ),
                  child: Text(actionLabel!),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _EmptyPainter extends CustomPainter {
  _EmptyPainter(this.kind);
  final EmptyKind kind;

  @override
  void paint(Canvas canvas, Size size) {
    final Offset center = size.center(Offset.zero);
    canvas.drawCircle(center, size.width * 0.5,
        Paint()..color = const Color(0xFFFBE7DB));

    final Paint coral = Paint()
      ..color = AppTheme.brand600
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.6
      ..strokeCap = StrokeCap.round;
    final Paint sage = Paint()..color = AppTheme.gold600;

    switch (kind) {
      case EmptyKind.noResults:
        canvas.drawCircle(center.translate(-6, -8), 22, coral);
        canvas.drawLine(center.translate(10, 8),
            center.translate(28, 26), coral);
      case EmptyKind.offline:
        // cloud + slash
        final Path cloud = Path()
          ..addOval(Rect.fromCircle(center: center.translate(-14, 0), radius: 14))
          ..addOval(Rect.fromCircle(center: center.translate(14, 0), radius: 16))
          ..addOval(Rect.fromCircle(center: center.translate(0, -10), radius: 16));
        canvas.drawPath(cloud, sage..color = AppTheme.gold500);
        canvas.drawLine(center.translate(-26, 22),
            center.translate(26, -22), coral..strokeWidth = 3);
      case EmptyKind.inbox:
        final Rect tray = Rect.fromCenter(
            center: center.translate(0, 4), width: 70, height: 36);
        canvas.drawRRect(
            RRect.fromRectAndRadius(tray, const Radius.circular(8)), coral);
        canvas.drawLine(center.translate(-26, -10),
            center.translate(26, -10), coral);
      case EmptyKind.empty:
        canvas.drawCircle(center, 22,
            Paint()..color = AppTheme.brand600.withOpacity(.25));
        canvas.drawCircle(center, 8, sage);
      case EmptyKind.noLocation:
        // pin
        final Path pin = Path()
          ..moveTo(center.dx, center.dy + 20)
          ..quadraticBezierTo(center.dx - 22, center.dy - 4,
              center.dx, center.dy - 28)
          ..quadraticBezierTo(center.dx + 22, center.dy - 4,
              center.dx, center.dy + 20);
        canvas.drawPath(pin, sage..color = AppTheme.brand600);
        canvas.drawCircle(center.translate(0, -12), 6,
            Paint()..color = const Color(0xFFFFF8F3));
    }
  }

  @override
  bool shouldRepaint(_EmptyPainter old) => old.kind != kind;
}
