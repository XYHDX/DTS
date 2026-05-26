import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/auth/auth_controller.dart';

/// Allows the wrapped widget only when the current user's role is in [allow].
/// Otherwise renders a polite block screen with a login redirect.
class RoleGate extends ConsumerWidget {
  const RoleGate({super.key, required this.allow, required this.child});
  final List<String> allow;
  final Widget child;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AuthState a = ref.watch(authControllerProvider);
    if (!a.isAuthenticated) {
      WidgetsBinding.instance.addPostFrameCallback(
          (_) => context.go('/login?next=${Uri.encodeComponent('/driver')}'));
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (!allow.contains(a.role)) {
      return Scaffold(
        appBar: AppBar(title: const Text('غير مسموح')),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                const Icon(Icons.lock_outline, size: 48, color: Colors.black38),
                const SizedBox(height: 12),
                Text('لا تملك صلاحية الوصول إلى هذه الصفحة.',
                    style: Theme.of(context).textTheme.bodyLarge,
                    textAlign: TextAlign.center),
                const SizedBox(height: 16),
                FilledButton(
                    onPressed: () => context.go('/'),
                    child: const Text('العودة للرئيسية')),
              ],
            ),
          ),
        ),
      );
    }
    return child;
  }
}
