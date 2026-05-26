import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../core/theme.dart';

/// Three-card welcome. Shown once on first launch, then never again.
///
/// Claude-styled: warm cream surface, calm illustrations rendered as inline
/// SVG (no external asset bundle needed), serif headlines, prose-friendly
/// bodies. Persists "seen" via SharedPreferences so a router redirect can
/// skip this on returning users.
///
/// Wire-up:
///   final seen = await OnboardingState.hasSeen();
///   if (!seen) context.go('/welcome');
class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key, this.onDone});
  final VoidCallback? onDone;
  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  final PageController _controller = PageController();
  int _page = 0;

  static const List<_Slide> _slides = <_Slide>[
    _Slide(
      eyebrow: 'مرحباً',
      headline: 'نقل دمشق\nبين يديك',
      body: 'تتبّع الحافلات في الوقت الحقيقي، اعرف موعد وصولها، '
          'واختر خطك بسهولة — كل ذلك بدون إعلانات.',
      illustration: _IllustrationKind.compass,
    ),
    _Slide(
      eyebrow: 'لحظياً',
      headline: 'مواقع الحافلات\nتُحدَّث كل ٥ ثوانٍ',
      body: 'الخريطة تبيّن لك الحافلات أثناء حركتها، ودقيقة الوصول '
          'محسوبة من مواقعها الفعلية.',
      illustration: _IllustrationKind.pulse,
    ),
    _Slide(
      eyebrow: 'دون اتصال',
      headline: 'يعمل أيضاً\nبدون إنترنت',
      body: 'نخزّن الخطوط والمحطات على هاتفك. إن انقطعت الشبكة، '
          'يبقى التطبيق نافعاً ويعرض آخر المواقع المعروفة.',
      illustration: _IllustrationKind.offline,
    ),
  ];

  Future<void> _finish() async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    await prefs.setBool('onboarding_seen', true);
    if (!mounted) return;
    if (widget.onDone != null) {
      widget.onDone!();
    } else {
      context.go('/');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: <Widget>[
            // Skip button — top inline-end. Never hidden — Claude design respects user agency.
            Align(
              alignment: AlignmentDirectional.topEnd,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(8, 8, 16, 0),
                child: TextButton(
                  onPressed: _finish,
                  style: TextButton.styleFrom(
                      foregroundColor: AppTheme.textSoftLight,
                      textStyle: const TextStyle(fontWeight: FontWeight.w500)),
                  child: const Text('تخطّي'),
                ),
              ),
            ),
            Expanded(
              child: PageView.builder(
                controller: _controller,
                itemCount: _slides.length,
                onPageChanged: (int i) => setState(() => _page = i),
                itemBuilder: (BuildContext _, int i) => _SlideView(slide: _slides[i]),
              ),
            ),
            const SizedBox(height: 12),
            _Dots(count: _slides.length, current: _page),
            const SizedBox(height: 28),
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 0, 24, 28),
              child: SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: () {
                    if (_page == _slides.length - 1) {
                      _finish();
                    } else {
                      _controller.nextPage(
                        duration: const Duration(milliseconds: 260),
                        curve: Curves.easeOutCubic,
                      );
                    }
                  },
                  child: Text(_page == _slides.length - 1 ? 'لنبدأ' : 'التالي'),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class OnboardingState {
  static Future<bool> hasSeen() async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    return prefs.getBool('onboarding_seen') ?? false;
  }

  static Future<void> reset() async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    await prefs.remove('onboarding_seen');
  }
}

// --- Slide model + view ------------------------------------------------------

enum _IllustrationKind { compass, pulse, offline }

class _Slide {
  const _Slide({
    required this.eyebrow,
    required this.headline,
    required this.body,
    required this.illustration,
  });
  final String eyebrow;
  final String headline;
  final String body;
  final _IllustrationKind illustration;
}

class _SlideView extends StatelessWidget {
  const _SlideView({required this.slide});
  final _Slide slide;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(28, 4, 28, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Expanded(
            flex: 5,
            child: Center(
              child: _Illustration(kind: slide.illustration),
            ),
          ),
          Expanded(
            flex: 4,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  slide.eyebrow.toUpperCase(),
                  style: const TextStyle(
                    fontSize: 12,
                    letterSpacing: 1.6,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.brand600,
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  slide.headline,
                  style: theme.textTheme.displaySmall?.copyWith(height: 1.15),
                ),
                const SizedBox(height: 12),
                Text(
                  slide.body,
                  style: theme.textTheme.bodyLarge?.copyWith(
                      color: AppTheme.textMuteLight, height: 1.65),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Inline-painted illustration — no external SVG asset to ship.
/// Calm geometry, brand-coral fills, sage accents. Friendly without being cute.
class _Illustration extends StatelessWidget {
  const _Illustration({required this.kind});
  final _IllustrationKind kind;
  @override
  Widget build(BuildContext context) {
    return AspectRatio(
      aspectRatio: 1,
      child: CustomPaint(painter: _IllustrationPainter(kind)),
    );
  }
}

class _IllustrationPainter extends CustomPainter {
  _IllustrationPainter(this.kind);
  final _IllustrationKind kind;

  @override
  void paint(Canvas canvas, Size size) {
    final Paint cream = Paint()..color = const Color(0xFFFBE7DB);
    final Paint coral = Paint()..color = AppTheme.brand600;
    final Paint sage  = Paint()..color = AppTheme.gold600;
    final Paint stroke = Paint()
      ..color = AppTheme.brand700
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.4
      ..strokeCap = StrokeCap.round;

    // Soft circle backdrop
    canvas.drawCircle(size.center(Offset.zero), size.width * 0.42, cream);

    switch (kind) {
      case _IllustrationKind.compass:
        _paintCompass(canvas, size, coral, sage, stroke);
      case _IllustrationKind.pulse:
        _paintPulse(canvas, size, coral, sage, stroke);
      case _IllustrationKind.offline:
        _paintOffline(canvas, size, coral, sage, stroke);
    }
  }

  void _paintCompass(Canvas c, Size s, Paint coral, Paint sage, Paint stroke) {
    final Offset center = s.center(Offset.zero);
    final double r = s.width * 0.30;
    // Outer ring
    c.drawCircle(center, r, stroke);
    // Cardinal ticks
    for (int i = 0; i < 8; i++) {
      final double a = i * 3.14159265 / 4;
      final Offset from = center + Offset.fromDirection(a, r - 6);
      final Offset to   = center + Offset.fromDirection(a, r + 6);
      c.drawLine(from, to, stroke);
    }
    // North arrow
    final Path arrow = Path()
      ..moveTo(center.dx, center.dy - r + 12)
      ..lineTo(center.dx - 14, center.dy + 6)
      ..lineTo(center.dx, center.dy)
      ..lineTo(center.dx + 14, center.dy + 6)
      ..close();
    c.drawPath(arrow, coral);
    // Dot
    c.drawCircle(center, 5, sage);
  }

  void _paintPulse(Canvas c, Size s, Paint coral, Paint sage, Paint stroke) {
    final Offset center = s.center(Offset.zero);
    // Concentric pulse rings
    for (int i = 1; i <= 3; i++) {
      final Paint p = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.2
        ..color = const Color(0xFFC96442).withOpacity(0.18 * (4 - i));
      c.drawCircle(center, s.width * (0.10 + i * 0.085), p);
    }
    // Inner bus marker — sage circle
    c.drawCircle(center, 14, sage);
    // Coral road below
    final Path road = Path()
      ..moveTo(s.width * 0.18, s.height * 0.72)
      ..quadraticBezierTo(s.width * 0.5, s.height * 0.60,
                          s.width * 0.82, s.height * 0.78);
    c.drawPath(road, Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 4
      ..strokeCap = StrokeCap.round
      ..color = AppTheme.brand500.withOpacity(.55));
  }

  void _paintOffline(Canvas c, Size s, Paint coral, Paint sage, Paint stroke) {
    final Offset center = s.center(Offset.zero);
    // A phone outline
    final Rect phone = Rect.fromCenter(
      center: center,
      width: s.width * 0.32,
      height: s.width * 0.50,
    );
    final RRect r = RRect.fromRectAndRadius(phone, const Radius.circular(18));
    c.drawRRect(r, Paint()..color = const Color(0xFFFFF8F3));
    c.drawRRect(r, stroke);
    // Screen content — three rounded lines
    for (int i = 0; i < 3; i++) {
      final Rect line = Rect.fromLTWH(
        phone.left + 14, phone.top + 22 + i * 18,
        phone.width - 28, 8,
      );
      c.drawRRect(RRect.fromRectAndRadius(line, const Radius.circular(4)),
          Paint()..color = AppTheme.brand100);
    }
    // Cloud-with-slash hint above
    final Path cloud = Path()
      ..addOval(Rect.fromCircle(center: Offset(center.dx - 12, phone.top - 18), radius: 12))
      ..addOval(Rect.fromCircle(center: Offset(center.dx + 14, phone.top - 18), radius: 14))
      ..addOval(Rect.fromCircle(center: Offset(center.dx, phone.top - 24), radius: 14));
    c.drawPath(cloud, sage..color = AppTheme.gold500);
    // Slash
    c.drawLine(
      Offset(center.dx - 28, phone.top - 34),
      Offset(center.dx + 28, phone.top - 4),
      Paint()
        ..color = AppTheme.brand600
        ..strokeWidth = 3
        ..strokeCap = StrokeCap.round,
    );
  }

  @override
  bool shouldRepaint(_IllustrationPainter old) => old.kind != kind;
}

class _Dots extends StatelessWidget {
  const _Dots({required this.count, required this.current});
  final int count;
  final int current;
  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: <Widget>[
        for (int i = 0; i < count; i++)
          AnimatedContainer(
            duration: const Duration(milliseconds: 220),
            curve: Curves.easeOut,
            margin: const EdgeInsets.symmetric(horizontal: 4),
            width: i == current ? 26 : 7,
            height: 7,
            decoration: BoxDecoration(
              color: i == current ? AppTheme.brand600 : AppTheme.borderLight,
              borderRadius: BorderRadius.circular(999),
            ),
          ),
      ],
    );
  }
}
