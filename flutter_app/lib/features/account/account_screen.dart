import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme.dart';
import '../auth/auth_controller.dart';

/// Claude-styled account / profile screen.
///
/// A large initial-avatar set on warm cream, a tabular details list with
/// hairline dividers, and a single destructive action at the bottom. No
/// gradients, no shadows, no clutter.
class AccountScreen extends ConsumerWidget {
  const AccountScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ThemeData theme = Theme.of(context);
    final AuthState auth = ref.watch(authControllerProvider);
    final Map<String, dynamic>? u = auth.user;

    final String displayName = (u?['name'] ?? u?['email'] ?? '—').toString();
    final String email = (u?['email'] ?? '—').toString();
    final String role = (u?['role'] ?? 'viewer').toString();
    final String? operator = u?['operator_name'] as String? ?? u?['operator_id'] as String?;

    return Scaffold(
      appBar: AppBar(title: const Text('حسابي')),
      body: !auth.isAuthenticated
          ? _SignedOutState()
          : ListView(
              padding: const EdgeInsets.fromLTRB(24, 8, 24, 48),
              children: <Widget>[
                const SizedBox(height: 8),
                // Identity block
                Row(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: <Widget>[
                    _InitialAvatar(label: displayName),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Text(displayName, style: theme.textTheme.headlineSmall),
                          const SizedBox(height: 4),
                          Text(email,
                              style: theme.textTheme.bodyMedium?.copyWith(
                                  color: AppTheme.textMuteLight)),
                        ],
                      ),
                    ),
                  ],
                ),

                const SizedBox(height: 28),

                // Role chips
                Wrap(
                  spacing: 8,
                  children: <Widget>[
                    _Tag(label: _arabicRole(role), tone: _toneForRole(role)),
                    if (operator != null) _Tag(label: operator, tone: _Tone.neutral),
                  ],
                ),

                const SizedBox(height: 24),

                _Section(title: 'التفاصيل', rows: <_DetailRow>[
                  _DetailRow(label: 'الاسم',        value: displayName),
                  _DetailRow(label: 'البريد',        value: email),
                  _DetailRow(label: 'الدور',         value: _arabicRole(role)),
                  if (operator != null)
                    _DetailRow(label: 'الجهة',     value: operator),
                  _DetailRow(label: 'الإصدار',      value: '1.0.0+1'),
                ]),

                const SizedBox(height: 28),

                _Section(title: 'الأمان', rows: <_DetailRow>[
                  _DetailRow(
                    label: 'كلمة المرور',
                    value: 'تغيير',
                    onTap: () => ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('سيُفتح تدفّق إعادة التعيين قريباً.')),
                    ),
                  ),
                  _DetailRow(
                    label: 'البصمة',
                    value: 'تفعيل',
                    onTap: () => ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('شاشة إقران البصمة قيد التطوير.')),
                    ),
                  ),
                ]),

                const SizedBox(height: 36),

                Center(
                  child: TextButton(
                    onPressed: () async {
                      await ref.read(authControllerProvider.notifier).logout();
                      if (context.mounted) context.go('/');
                    },
                    style: TextButton.styleFrom(
                      foregroundColor: AppTheme.danger,
                      textStyle: const TextStyle(fontWeight: FontWeight.w600),
                    ),
                    child: const Text('تسجيل الخروج'),
                  ),
                ),
              ],
            ),
    );
  }

  String _arabicRole(String r) => switch (r) {
        'admin' => 'مدير',
        'super_admin' => 'مدير عام',
        'dispatcher' => 'موزّع',
        'driver' => 'سائق',
        'viewer' => 'مشاهد',
        _ => r,
      };

  _Tone _toneForRole(String r) => switch (r) {
        'super_admin' => _Tone.brand,
        'admin' => _Tone.brand,
        'dispatcher' => _Tone.info,
        'driver' => _Tone.sage,
        _ => _Tone.neutral,
      };
}

class _SignedOutState extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            const Icon(Icons.person_outline, size: 56, color: AppTheme.textMuteLight),
            const SizedBox(height: 16),
            Text('لست مسجَّلاً للدخول',
                style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 8),
            Text('سجّل الدخول للوصول إلى رحلاتك وتنبيهاتك.',
                style: Theme.of(context).textTheme.bodyMedium,
                textAlign: TextAlign.center),
            const SizedBox(height: 24),
            FilledButton(
              onPressed: () => GoRouter.of(context).go('/login'),
              child: const Text('دخول'),
            ),
          ],
        ),
      ),
    );
  }
}

class _InitialAvatar extends StatelessWidget {
  const _InitialAvatar({required this.label});
  final String label;
  @override
  Widget build(BuildContext context) {
    final String letter = label.isEmpty ? '؟' : label.characters.first.toUpperCase();
    return Container(
      width: 64,
      height: 64,
      decoration: const BoxDecoration(
        color: AppTheme.brand100,
        shape: BoxShape.circle,
      ),
      alignment: Alignment.center,
      child: Text(
        letter,
        style: const TextStyle(
          fontSize: 26,
          color: AppTheme.brand700,
          fontFamily: AppTheme.fontSerif,
          fontFamilyFallback: <String>['Georgia', 'serif'],
        ),
      ),
    );
  }
}

enum _Tone { brand, info, sage, neutral }

class _Tag extends StatelessWidget {
  const _Tag({required this.label, this.tone = _Tone.neutral});
  final String label;
  final _Tone tone;
  @override
  Widget build(BuildContext context) {
    final (Color bg, Color fg, Color border) = switch (tone) {
      _Tone.brand   => (AppTheme.brand100, AppTheme.brand700, AppTheme.brand500),
      _Tone.info    => (Color(0xFFDDE6EE), Color(0xFF2C4356), Color(0xFFBFCFDF)),
      _Tone.sage    => (Color(0xFFE4ECE7), Color(0xFF4A6B58), Color(0xFFC0D2C7)),
      _Tone.neutral => (AppTheme.surfaceLight, AppTheme.textSoftLight, AppTheme.borderLight),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        border: Border.all(color: border),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(label,
          style: TextStyle(color: fg, fontSize: 12, fontWeight: FontWeight.w600)),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({required this.title, required this.rows});
  final String title;
  final List<_DetailRow> rows;
  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Padding(
          padding: const EdgeInsets.only(left: 4, right: 4, bottom: 10),
          child: Text(
            title.toUpperCase(),
            style: const TextStyle(
                fontSize: 11,
                letterSpacing: 1.4,
                fontWeight: FontWeight.w600,
                color: AppTheme.brand600),
          ),
        ),
        Container(
          decoration: BoxDecoration(
            color: AppTheme.surfaceLight,
            border: Border.all(color: AppTheme.borderLight),
            borderRadius: BorderRadius.circular(18),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 14),
          child: Column(
            children: <Widget>[
              for (int i = 0; i < rows.length; i++) ...<Widget>[
                if (i > 0) Container(height: 1, color: AppTheme.borderLight.withOpacity(.7)),
                rows[i],
              ],
            ],
          ),
        ),
      ],
    );
  }
}

class _DetailRow extends StatelessWidget {
  const _DetailRow({required this.label, required this.value, this.onTap});
  final String label;
  final String value;
  final VoidCallback? onTap;
  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 14),
        child: Row(
          children: <Widget>[
            Expanded(
              child: Text(label,
                  style: const TextStyle(color: AppTheme.textSoftLight, fontWeight: FontWeight.w500)),
            ),
            Text(
              value,
              style: TextStyle(
                color: onTap == null ? AppTheme.textMuteLight : AppTheme.brand600,
                fontWeight: onTap == null ? FontWeight.w500 : FontWeight.w600,
              ),
            ),
            if (onTap != null) const SizedBox(width: 6),
            if (onTap != null)
              const Icon(Icons.chevron_left, size: 18, color: AppTheme.textMuteLight),
          ],
        ),
      ),
    );
  }
}
