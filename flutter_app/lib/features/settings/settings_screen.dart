import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../core/theme.dart';

/// Claude-styled settings.
///
/// Quiet section headers, list rows with generous vertical padding, hairline
/// dividers, and a single coral accent. No icons in primary list rows — the
/// label carries the meaning.
class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});
  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  String _locale = 'ar';
  String _themeMode = 'system';
  String _units = 'metric';
  bool _highAccuracyGps = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    setState(() {
      _locale = prefs.getString('locale') ?? 'ar';
      _themeMode = prefs.getString('themeMode') ?? 'system';
      _units = prefs.getString('units') ?? 'metric';
      _highAccuracyGps = prefs.getBool('highAccuracyGps') ?? true;
    });
  }

  Future<void> _save(String key, Object value) async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    if (value is bool) {
      await prefs.setBool(key, value);
    } else {
      await prefs.setString(key, value.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('الإعدادات')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(24, 24, 24, 48),
        children: <Widget>[
          // Hero header
          Text('الإعدادات', style: theme.textTheme.displaySmall),
          const SizedBox(height: 6),
          Text(
            'خصّص اللغة والمظهر والقياسات لتجربة أكثر راحة.',
            style: theme.textTheme.bodyLarge?.copyWith(color: AppTheme.textMuteLight),
          ),

          const SizedBox(height: 32),
          _SectionHeader(label: 'العرض'),
          _Card(children: <Widget>[
            _RadioRow<String>(
              label: 'اللغة',
              value: _locale,
              options: const <_Opt<String>>[
                _Opt<String>('ar', 'العربية'),
                _Opt<String>('en', 'English'),
              ],
              onChanged: (String v) {
                setState(() => _locale = v);
                _save('locale', v);
              },
            ),
            const _Divider(),
            _RadioRow<String>(
              label: 'السمة',
              value: _themeMode,
              options: const <_Opt<String>>[
                _Opt<String>('system', 'تلقائي'),
                _Opt<String>('light', 'فاتح'),
                _Opt<String>('dark', 'داكن'),
              ],
              onChanged: (String v) {
                setState(() => _themeMode = v);
                _save('themeMode', v);
              },
            ),
          ]),

          const SizedBox(height: 28),
          _SectionHeader(label: 'الوحدات والدقة'),
          _Card(children: <Widget>[
            _RadioRow<String>(
              label: 'وحدة المسافة',
              value: _units,
              options: const <_Opt<String>>[
                _Opt<String>('metric', 'متري (كم)'),
                _Opt<String>('imperial', 'إمبراطوري (ميل)'),
              ],
              onChanged: (String v) {
                setState(() => _units = v);
                _save('units', v);
              },
            ),
            const _Divider(),
            SwitchListTile.adaptive(
              title: const Text('دقة GPS عالية'),
              subtitle: const Text(
                  'يستهلك المزيد من البطارية. أنصح بإبقائه مفعّلاً للسائقين.'),
              value: _highAccuracyGps,
              activeColor: AppTheme.brand600,
              onChanged: (bool v) {
                setState(() => _highAccuracyGps = v);
                _save('highAccuracyGps', v);
              },
              contentPadding: EdgeInsets.zero,
            ),
          ]),

          const SizedBox(height: 28),
          _SectionHeader(label: 'حول'),
          _Card(children: <Widget>[
            _LinkRow(label: 'الإصدار', value: '1.0.0+1'),
            const _Divider(),
            _LinkRow(label: 'سياسة الخصوصية', onTap: () {}),
            const _Divider(),
            _LinkRow(label: 'الشروط', onTap: () {}),
            const _Divider(),
            _LinkRow(label: 'المصدر المفتوح', onTap: () {}),
          ]),

          const SizedBox(height: 36),
          Center(
            child: Text(
              'صُنع بدمشق · مفتوح المصدر',
              style: theme.textTheme.bodySmall?.copyWith(
                  color: AppTheme.textMuteLight, fontStyle: FontStyle.italic),
            ),
          ),
        ],
      ),
    );
  }
}

// --- Quiet primitives ---

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.label});
  final String label;
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(left: 8, right: 8, bottom: 10, top: 4),
      child: Text(
        label.toUpperCase(),
        style: const TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          letterSpacing: 0.12 * 11,
          color: AppTheme.brand600,
        ),
      ),
    );
  }
}

class _Card extends StatelessWidget {
  const _Card({required this.children});
  final List<Widget> children;
  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.surfaceLight,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppTheme.borderLight),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: children),
    );
  }
}

class _Divider extends StatelessWidget {
  const _Divider();
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14),
        child: Container(height: 1, color: AppTheme.borderLight.withOpacity(0.7)),
      );
}

class _RadioRow<T> extends StatelessWidget {
  const _RadioRow({
    required this.label,
    required this.value,
    required this.options,
    required this.onChanged,
  });
  final String label;
  final T value;
  final List<_Opt<T>> options;
  final ValueChanged<T> onChanged;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(14, 14, 14, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(label, style: const TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: <Widget>[
              for (final _Opt<T> o in options)
                ChoiceChip(
                  selected: o.value == value,
                  label: Text(o.label),
                  onSelected: (bool _) => onChanged(o.value),
                  selectedColor: AppTheme.brand100,
                  side: BorderSide(
                    color: o.value == value
                        ? AppTheme.brand500
                        : AppTheme.borderLight,
                  ),
                  labelStyle: TextStyle(
                    color: o.value == value
                        ? AppTheme.brand700
                        : AppTheme.textSoftLight,
                    fontWeight: FontWeight.w600,
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _Opt<T> {
  const _Opt(this.value, this.label);
  final T value;
  final String label;
}

class _LinkRow extends StatelessWidget {
  const _LinkRow({required this.label, this.value, this.onTap});
  final String label;
  final String? value;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 16),
        child: Row(
          children: <Widget>[
            Expanded(child: Text(label)),
            if (value != null)
              Text(value!, style: const TextStyle(color: AppTheme.textMuteLight))
            else
              const Icon(Icons.chevron_left, color: AppTheme.textMuteLight),
          ],
        ),
      ),
    );
  }
}
