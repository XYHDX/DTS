import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:damascus_transit/core/theme.dart';

void main() {
  testWidgets('theme renders an AppBar with brand color', (WidgetTester tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(
          theme: null,
          home: Scaffold(appBar: PreferredSize(
            preferredSize: Size.fromHeight(56),
            child: Material(color: AppTheme.brand800),
          )),
        ),
      ),
    );
    expect(find.byType(Scaffold), findsOneWidget);
  });

  test('AppTheme exposes brand palette', () {
    expect(AppTheme.brand800, isA<Color>());
    expect(AppTheme.brand500, isA<Color>());
    expect(AppTheme.gold600, isA<Color>());
  });
}
