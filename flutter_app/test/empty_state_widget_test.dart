import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:damascus_transit/shared/widgets/empty_state.dart';
import 'package:damascus_transit/shared/widgets/eta_card.dart';

void main() {
  group('EmptyState', () {
    Future<void> _pump(WidgetTester t, EmptyState es) async {
      await t.pumpWidget(MaterialApp(home: Scaffold(body: es)));
    }

    testWidgets('renders title + body', (WidgetTester t) async {
      await _pump(t, const EmptyState(
        title: 'لا تنبيهات',
        body: 'كل شيء على ما يرام.',
      ));
      expect(find.text('لا تنبيهات'), findsOneWidget);
      expect(find.text('كل شيء على ما يرام.'), findsOneWidget);
      expect(find.byType(TextButton), findsNothing);
    });

    testWidgets('shows action button when both label + callback are set',
        (WidgetTester t) async {
      bool tapped = false;
      await _pump(t, EmptyState(
        title: 'فارغ',
        body: 'مع ذلك ابدأ بشيء.',
        actionLabel: 'ابدأ',
        onAction: () => tapped = true,
      ));
      expect(find.text('ابدأ'), findsOneWidget);
      await t.tap(find.text('ابدأ'));
      expect(tapped, isTrue);
    });

    testWidgets('hides action when only one of label/callback is set',
        (WidgetTester t) async {
      await _pump(t, EmptyState(
        title: 'فارغ',
        body: 'لا فعل ممكن',
        actionLabel: 'ابدأ',          // no callback
      ));
      expect(find.byType(TextButton), findsNothing);
    });
  });

  group('EtaCard', () {
    testWidgets('renders stop name and minute count', (WidgetTester t) async {
      await t.pumpWidget(const MaterialApp(home: Scaffold(body: EtaCard(
        stopName: 'ساحة الأمويين',
        etaMinutes: 4,
        routeCode: 'R-12',
      ))));
      expect(find.text('ساحة الأمويين'), findsOneWidget);
      expect(find.text('4'), findsOneWidget);
      expect(find.text('R-12'), findsOneWidget);
    });

    testWidgets('says "الآن" for zero minutes', (WidgetTester t) async {
      await t.pumpWidget(const MaterialApp(home: Scaffold(body: EtaCard(
        stopName: 'X',
        etaMinutes: 0,
      ))));
      expect(find.text('الآن'), findsOneWidget);
      expect(find.text('يصل الآن'), findsOneWidget);
    });

    testWidgets('chevron only appears when onTap is provided',
        (WidgetTester t) async {
      // No onTap
      await t.pumpWidget(const MaterialApp(home: Scaffold(body: EtaCard(
        stopName: 'X', etaMinutes: 3,
      ))));
      expect(find.byIcon(Icons.chevron_left), findsNothing);

      // With onTap
      await t.pumpWidget(MaterialApp(home: Scaffold(body: EtaCard(
        stopName: 'X', etaMinutes: 3, onTap: () {},
      ))));
      expect(find.byIcon(Icons.chevron_left), findsOneWidget);
    });
  });
}
