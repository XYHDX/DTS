import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:sentry_flutter/sentry_flutter.dart';

import 'core/router.dart';
import 'core/theme.dart';

// Wire Sentry at build time:  --dart-define=SENTRY_DSN=https://…@sentry.io/…
const String _kSentryDsn = String.fromEnvironment('SENTRY_DSN');
const String _kRelease   = String.fromEnvironment('APP_RELEASE',
    defaultValue: 'damascus-transit@dev');
const String _kEnv       = String.fromEnvironment('APP_ENV',
    defaultValue: 'development');

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await SystemChrome.setPreferredOrientations(<DeviceOrientation>[
    DeviceOrientation.portraitUp,
  ]);
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Color(0xFF002623),
      statusBarIconBrightness: Brightness.light,
      systemNavigationBarColor: Color(0xFF002623),
      systemNavigationBarIconBrightness: Brightness.light,
    ),
  );

  // Step 38 — Sentry. Soft-init: if no DSN is provided, skip entirely.
  if (_kSentryDsn.isNotEmpty) {
    await SentryFlutter.init((SentryFlutterOptions o) {
      o.dsn = _kSentryDsn;
      o.release = _kRelease;
      o.environment = _kEnv;
      o.tracesSampleRate = kDebugMode ? 0.0 : 0.1;
      o.sendDefaultPii = false;
      o.beforeSend = (SentryEvent event, Hint hint) {
        // Drop noisy DioException 401s — they're handled by the interceptor.
        if (event.throwable?.toString().contains('DioException') == true &&
            event.throwable.toString().contains('401')) {
          return null;
        }
        return event;
      };
    },
        appRunner: () =>
            runApp(const ProviderScope(child: DamascusTransitApp())));
  } else {
    runApp(const ProviderScope(child: DamascusTransitApp()));
  }
}

class DamascusTransitApp extends ConsumerWidget {
  const DamascusTransitApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);
    return MaterialApp.router(
      title: 'نقل دمشق',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      themeMode: ThemeMode.system,
      routerConfig: router,
      supportedLocales: const <Locale>[Locale('ar'), Locale('en')],
      // Follow the device locale when supported; otherwise fall back to Arabic
      // so Arabic stays the effective default for unsupported locales.
      localeResolutionCallback:
          (Locale? deviceLocale, Iterable<Locale> supported) {
        if (deviceLocale != null) {
          for (final Locale l in supported) {
            if (l.languageCode == deviceLocale.languageCode) return l;
          }
        }
        return const Locale('ar');
      },
      localizationsDelegates: const <LocalizationsDelegate<dynamic>>[
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      builder: (BuildContext context, Widget? child) => Directionality(
        textDirection: TextDirection.rtl,
        child: child ?? const SizedBox.shrink(),
      ),
    );
  }
}
