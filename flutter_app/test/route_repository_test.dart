import 'package:flutter_test/flutter_test.dart';

import 'package:damascus_transit/features/routes/route_repository.dart';

void main() {
  group('TransitRoute.fromJson', () {
    test('parses canonical shape', () {
      final TransitRoute r = TransitRoute.fromJson(<String, dynamic>{
        'id': 12,
        'code': 'M2',
        'name': 'Mezzeh — Bab Touma',
        'name_ar': 'المزة — باب توما',
        'from': 'Mezzeh',
        'to': 'Bab Touma',
        'stops_count': 18,
      });
      expect(r.id, '12');
      expect(r.code, 'M2');
      expect(r.nameAr, 'المزة — باب توما');
      expect(r.stopsCount, 18);
    });

    test('falls back when code/short_name missing', () {
      final TransitRoute r = TransitRoute.fromJson(<String, dynamic>{
        'id': 'abcdef',
        'name': 'X',
      });
      expect(r.code, 'abcdef');
      expect(r.stopsCount, isNull);
    });

    test('parses stops_count from a string field', () {
      final TransitRoute r = TransitRoute.fromJson(<String, dynamic>{
        'id': 1,
        'code': 'R1',
        'name': 'X',
        'stops_count': '7',
      });
      expect(r.stopsCount, 7);
    });
  });

  group('Stop.fromJson', () {
    test('handles latitude/longitude alias', () {
      final Stop s = Stop.fromJson(<String, dynamic>{
        'id': 99,
        'name': 'Umayyad Square',
        'name_ar': 'الأمويين',
        'latitude': 33.512,
        'longitude': 36.292,
      });
      expect(s.id, '99');
      expect(s.lat, closeTo(33.512, 1e-6));
      expect(s.lon, closeTo(36.292, 1e-6));
      expect(s.nameAr, 'الأمويين');
    });
  });
}
