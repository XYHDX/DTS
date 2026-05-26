import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../../core/theme.dart';

/// A polite, Claude-styled crash gate.
///
/// Wraps a child widget tree and reports any uncaught build/render errors
/// to a calm fallback UI instead of the red error screen. In debug builds
/// it still rethrows so you see stack traces; in release builds it logs and
/// shows the fallback.
class ErrorBoundary extends StatefulWidget {
  const ErrorBoundary({
    super.key,
    required this.child,
    this.onError,
    this.fallback,
  });

  final Widget child;
  final void Function(Object error, StackTrace stack)? onError;
  final Widget Function(BuildContext context, VoidCallback retry)? fallback;

  @override
  State<ErrorBoundary> createState() => _ErrorBoundaryState();
}

class _ErrorBoundaryState extends State<ErrorBoundary> {
  Object? _error;
  StackTrace? _stack;
  late FlutterExceptionHandler? _previousOnError;

  @override
  void initState() {
    super.initState();
    _previousOnError = FlutterError.onError;
    FlutterError.onError = (FlutterErrorDetails details) {
      _previousOnError?.call(details);
      _capture(details.exception, details.stack ?? StackTrace.current);
    };
  }

  @override
  void dispose() {
    FlutterError.onError = _previousOnError;
    super.dispose();
  }

  void _capture(Object e, StackTrace st) {
    widget.onError?.call(e, st);
    if (kReleaseMode) {
      if (!mounted) return;
      setState(() {
        _error = e;
        _stack = st;
      });
    }
  }

  void _retry() {
    setState(() {
      _error = null;
      _stack = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_error != null) {
      if (widget.fallback != null) {
        return widget.fallback!(context, _retry);
      }
      return _DefaultFallback(error: _error!, onRetry: _retry);
    }
    return widget.child;
  }
}

class _DefaultFallback extends StatelessWidget {
  const _DefaultFallback({required this.error, required this.onRetry});
  final Object error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    return Scaffold(
      backgroundColor: AppTheme.bgLight,
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Padding(
              padding: const EdgeInsets.all(32),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text('شيءٌ ما تعطّل',
                      style: theme.textTheme.displaySmall),
                  const SizedBox(height: 8),
                  Text(
                    'اعتذرنا. حدث خطأ غير متوقّع. أعد المحاولة، أو ارجع إلى الرئيسية.',
                    style: theme.textTheme.bodyLarge
                        ?.copyWith(color: AppTheme.textMuteLight),
                  ),
                  const SizedBox(height: 24),
                  if (!kReleaseMode)
                    Container(
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: AppTheme.surfaceLight,
                        border: Border.all(color: AppTheme.borderLight),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        error.toString(),
                        style: const TextStyle(
                          fontFamily: 'monospace',
                          fontSize: 12,
                          color: AppTheme.textSoftLight,
                        ),
                        maxLines: 6,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  const SizedBox(height: 24),
                  FilledButton(
                    onPressed: onRetry,
                    child: const Text('إعادة المحاولة'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
