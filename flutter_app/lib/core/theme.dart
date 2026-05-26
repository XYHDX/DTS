import 'package:flutter/material.dart';

/// Claude-inspired theme.
/// Mirrors the tokens in `public/lib/design-system.css` so the web and mobile
/// shells share an identity: warm cream surface, coral primary, calm density.
class AppTheme {
  AppTheme._();

  // Brand — warm, Claude-style
  static const Color brand900 = Color(0xFF2A1810);
  static const Color brand800 = Color(0xFF3D2516);
  static const Color brand700 = Color(0xFF6B3D24);
  static const Color brand600 = Color(0xFFC96442); // primary action coral
  static const Color brand500 = Color(0xFFD97757); // hover coral
  static const Color brand400 = Color(0xFFE8967A);
  static const Color brand100 = Color(0xFFFBE7DB);

  // Sage accent
  static const Color gold600 = Color(0xFF6B8E78);
  static const Color gold500 = Color(0xFF8FAA9A);

  // Status
  static const Color success = Color(0xFF4A8060);
  static const Color warning = Color(0xFFB85D24);
  static const Color danger  = Color(0xFFB53A30);

  // Surface
  static const Color surfaceLight  = Color(0xFFFAF7F2);
  static const Color surfaceDark   = Color(0xFF232020);
  static const Color bgLight       = Color(0xFFF5F1EA);
  static const Color bgDark        = Color(0xFF1A1614);
  static const Color borderLight   = Color(0xFFE5DFD3);
  static const Color borderDark    = Color(0xFF3A3633);
  static const Color textLight     = Color(0xFF181818);
  static const Color textDark      = Color(0xFFF2EBE2);
  static const Color textSoftLight = Color(0xFF4A4644);
  static const Color textMuteLight = Color(0xFF7C7570);

  /// Display serif stack — works without bundling any custom font.
  static const String fontSerif = 'Charter';
  static const String fontSans  = 'IBMPlexSansArabic';

  static ThemeData get light => _build(Brightness.light);
  static ThemeData get dark  => _build(Brightness.dark);

  static ThemeData _build(Brightness brightness) {
    final bool isDark = brightness == Brightness.dark;
    final Color bg     = isDark ? bgDark : bgLight;
    final Color surf   = isDark ? surfaceDark : surfaceLight;
    final Color border = isDark ? borderDark : borderLight;
    final Color text   = isDark ? textDark : textLight;
    final Color soft   = isDark ? const Color(0xFFC5BDB2) : textSoftLight;
    final Color mute   = isDark ? const Color(0xFF8E867D) : textMuteLight;

    final ColorScheme scheme = ColorScheme(
      brightness: brightness,
      primary: brand600,
      onPrimary: const Color(0xFFFFF8F3),
      secondary: gold600,
      onSecondary: const Color(0xFFFFF8F3),
      tertiary: brand400,
      onTertiary: const Color(0xFF1A1614),
      error: danger,
      onError: Colors.white,
      surface: surf,
      onSurface: text,
      surfaceContainerHighest: isDark ? const Color(0xFF2E2A28) : const Color(0xFFEFEBE3),
      onSurfaceVariant: soft,
      outline: border,
      outlineVariant: border,
      shadow: Colors.black.withOpacity(0.06),
      scrim: Colors.black.withOpacity(0.32),
      inverseSurface: text,
      onInverseSurface: surf,
      inversePrimary: brand400,
    );

    // Type — serif for Latin display, sans for body + all Arabic.
    final TextTheme txt = TextTheme(
      displayLarge:   _serif(56, 1.05, weight: FontWeight.w500, color: text),
      displayMedium:  _serif(44, 1.08, weight: FontWeight.w500, color: text),
      displaySmall:   _serif(36, 1.10, weight: FontWeight.w500, color: text),
      headlineLarge:  _serif(32, 1.15, weight: FontWeight.w500, color: text),
      headlineMedium: _serif(26, 1.18, weight: FontWeight.w500, color: text),
      headlineSmall:  _serif(22, 1.20, weight: FontWeight.w500, color: text),
      titleLarge:     _sans (20, 1.30, weight: FontWeight.w600, color: text),
      titleMedium:    _sans (17, 1.30, weight: FontWeight.w600, color: text),
      titleSmall:     _sans (15, 1.30, weight: FontWeight.w600, color: text),
      bodyLarge:      _sans (17, 1.55, weight: FontWeight.w400, color: text),
      bodyMedium:     _sans (15, 1.55, weight: FontWeight.w400, color: text),
      bodySmall:      _sans (13, 1.50, weight: FontWeight.w400, color: soft),
      labelLarge:     _sans (14, 1.20, weight: FontWeight.w500, color: text),
      labelMedium:    _sans (12, 1.20, weight: FontWeight.w500, color: mute),
      labelSmall:     _sans (11, 1.20, weight: FontWeight.w500, color: mute),
    );

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: scheme,
      scaffoldBackgroundColor: bg,
      canvasColor: bg,
      dividerColor: border,
      textTheme: txt,
      appBarTheme: AppBarTheme(
        elevation: 0,
        scrolledUnderElevation: 0,
        backgroundColor: surf,
        foregroundColor: text,
        centerTitle: true,
        surfaceTintColor: Colors.transparent,
        titleTextStyle: txt.titleMedium,
        shape: Border(bottom: BorderSide(color: border, width: 1)),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: brand600,
          foregroundColor: const Color(0xFFFFF8F3),
          disabledBackgroundColor: brand600.withOpacity(0.4),
          minimumSize: const Size.fromHeight(48),
          shape: const StadiumBorder(),
          padding: const EdgeInsets.symmetric(horizontal: 24),
          textStyle: txt.labelLarge,
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: text,
          side: BorderSide(color: border),
          minimumSize: const Size.fromHeight(48),
          shape: const StadiumBorder(),
          padding: const EdgeInsets.symmetric(horizontal: 24),
          textStyle: txt.labelLarge,
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: brand600,
          textStyle: txt.labelLarge,
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surf,
        hintStyle: txt.bodyMedium?.copyWith(color: mute),
        labelStyle: txt.labelMedium,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: brand500, width: 1.6),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: danger),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      ),
      cardTheme: CardTheme(
        elevation: 0,
        margin: EdgeInsets.zero,
        color: surf,
        shadowColor: Colors.transparent,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(18),
          side: BorderSide(color: border),
        ),
      ),
      listTileTheme: ListTileThemeData(
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        iconColor: soft,
        textColor: text,
        titleTextStyle: txt.titleSmall,
        subtitleTextStyle: txt.bodySmall,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: scheme.surfaceContainerHighest,
        labelStyle: txt.labelMedium,
        side: BorderSide(color: border),
        shape: const StadiumBorder(),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      ),
      navigationBarTheme: NavigationBarThemeData(
        height: 64,
        backgroundColor: surf,
        surfaceTintColor: Colors.transparent,
        indicatorColor: brand100,
        labelTextStyle: WidgetStatePropertyAll<TextStyle>(
          txt.labelSmall ?? const TextStyle(),
        ),
        iconTheme: WidgetStateProperty.resolveWith<IconThemeData>((Set<WidgetState> s) {
          return IconThemeData(
            color: s.contains(WidgetState.selected) ? brand600 : mute,
            size: 22,
          );
        }),
      ),
      dialogTheme: DialogTheme(
        backgroundColor: surf,
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        titleTextStyle: txt.titleLarge,
        contentTextStyle: txt.bodyMedium,
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: const Color(0xFF1A1614),
        contentTextStyle: txt.bodyMedium?.copyWith(color: const Color(0xFFF2EBE2)),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    );
  }

  static TextStyle _serif(double size, double height, {required FontWeight weight, required Color color}) =>
      TextStyle(
        fontFamily: fontSerif,
        fontFamilyFallback: const <String>[
          'Source Serif 4', 'Iowan Old Style', 'Apple Garamond', 'Georgia', 'serif',
        ],
        fontSize: size,
        height: height,
        fontWeight: weight,
        color: color,
        letterSpacing: -0.5,
      );

  static TextStyle _sans(double size, double height, {required FontWeight weight, required Color color}) =>
      TextStyle(
        fontFamily: fontSans,
        fontFamilyFallback: const <String>[
          'Söhne', 'Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto',
        ],
        fontSize: size,
        height: height,
        fontWeight: weight,
        color: color,
      );
}
