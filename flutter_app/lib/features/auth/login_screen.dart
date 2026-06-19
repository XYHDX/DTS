import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'auth_controller.dart';

// TODO(i18n): strings are still hardcoded; externalize to AppLocalizations.of(context)

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key, this.next});
  final String? next;

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final TextEditingController _emailCtl = TextEditingController();
  final TextEditingController _pwCtl = TextEditingController();
  final GlobalKey<FormState> _form = GlobalKey<FormState>();
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _emailCtl.dispose();
    _pwCtl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_form.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    final LoginResult result = await ref
        .read(authControllerProvider.notifier)
        .login(_emailCtl.text.trim(), _pwCtl.text);
    setState(() => _busy = false);
    if (!mounted) return;
    switch (result) {
      case LoginResult.success:
        context.go(widget.next ?? '/');
      case LoginResult.invalidCredentials:
        setState(() => _error = 'بيانات الدخول غير صحيحة');
      case LoginResult.serverUnreachable:
        setState(() => _error = 'تعذّر الوصول إلى الخادم، حاول مجددًا');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('دخول')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Form(
                  key: _form,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      Text('دخول السائق', style: Theme.of(context).textTheme.titleLarge),
                      const SizedBox(height: 6),
                      Text('استخدم بريدك وكلمة المرور.',
                          style: Theme.of(context).textTheme.bodyMedium),
                      const SizedBox(height: 20),
                      TextFormField(
                        controller: _emailCtl,
                        keyboardType: TextInputType.emailAddress,
                        autofillHints: const <String>[AutofillHints.email],
                        decoration: const InputDecoration(labelText: 'البريد'),
                        validator: (String? v) =>
                            (v == null || !v.contains('@')) ? 'بريد غير صالح' : null,
                      ),
                      const SizedBox(height: 14),
                      TextFormField(
                        controller: _pwCtl,
                        obscureText: true,
                        autofillHints: const <String>[AutofillHints.password],
                        decoration: const InputDecoration(labelText: 'كلمة المرور'),
                        validator: (String? v) =>
                            (v == null || v.length < 4) ? 'مطلوب' : null,
                      ),
                      if (_error != null) ...<Widget>[
                        const SizedBox(height: 12),
                        Text(_error!,
                            style: const TextStyle(color: Color(0xFFB53A30))),
                      ],
                      const SizedBox(height: 20),
                      FilledButton(
                        onPressed: _busy ? null : _submit,
                        child: _busy
                            ? const SizedBox(
                                height: 18,
                                width: 18,
                                child: CircularProgressIndicator(
                                    strokeWidth: 2, color: Colors.white))
                            : const Text('دخول'),
                      ),
                      // TODO(biometric): wire to secure credential store
                      // Biometric sign-in is hidden until a real credential
                      // store exists. The previous button injected placeholder
                      // credentials, so it always failed — see auth_controller.
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
