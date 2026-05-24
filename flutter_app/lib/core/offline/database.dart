import 'dart:io';

import 'package:drift/drift.dart';
import 'package:drift/native.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

part 'database.g.dart';

/// ---------------------------------------------------------------------------
/// Routes table — mirror of the canonical record from /api/routes
/// ---------------------------------------------------------------------------
@DataClassName('CachedRoute')
class CachedRoutes extends Table {
  TextColumn  get id          => text()();
  TextColumn  get code        => text()();
  TextColumn  get name        => text()();
  TextColumn  get nameAr      => text().nullable()();
  TextColumn  get fromName    => text().nullable()();
  TextColumn  get toName      => text().nullable()();
  IntColumn   get stopsCount  => integer().nullable()();
  DateTimeColumn get updatedAt => dateTime()();

  @override
  Set<Column<Object>> get primaryKey => <Column<Object>>{id};
}

/// ---------------------------------------------------------------------------
/// Stops table — denormalised per route for fast lookup
/// ---------------------------------------------------------------------------
@DataClassName('CachedStop')
class CachedStops extends Table {
  TextColumn  get id      => text()();
  TextColumn  get routeId => text().references(CachedRoutes, #id)();
  IntColumn   get seq     => integer()();
  TextColumn  get name    => text()();
  TextColumn  get nameAr  => text().nullable()();
  RealColumn  get lat     => real()();
  RealColumn  get lon     => real()();
  DateTimeColumn get updatedAt => dateTime()();

  @override
  Set<Column<Object>> get primaryKey => <Column<Object>>{id};
}

/// ---------------------------------------------------------------------------
/// LastKnownPositions — single row per vehicle. Used when SSE is silent.
/// ---------------------------------------------------------------------------
@DataClassName('CachedPosition')
class CachedPositions extends Table {
  TextColumn  get vehicleId => text()();
  TextColumn  get routeId   => text().nullable()();
  RealColumn  get lat       => real()();
  RealColumn  get lon       => real()();
  RealColumn  get speed     => real().nullable()();
  RealColumn  get heading   => real().nullable()();
  IntColumn   get occupancy => integer().nullable()();
  DateTimeColumn get ts     => dateTime()();

  @override
  Set<Column<Object>> get primaryKey => <Column<Object>>{vehicleId};
}

@DriftDatabase(tables: <Type>[CachedRoutes, CachedStops, CachedPositions])
class AppDatabase extends _$AppDatabase {
  AppDatabase() : super(_openConnection());

  @override
  int get schemaVersion => 1;

  Future<void> upsertRoutes(Iterable<CachedRoute> rows) =>
      batch((Batch b) => b.insertAllOnConflictUpdate(cachedRoutes, rows.toList()));

  Future<void> upsertStops(Iterable<CachedStop> rows) =>
      batch((Batch b) => b.insertAllOnConflictUpdate(cachedStops, rows.toList()));

  Future<void> upsertPosition(CachedPosition p) =>
      into(cachedPositions).insertOnConflictUpdate(p);

  Future<List<CachedRoute>> allRoutes() => select(cachedRoutes).get();

  Future<List<CachedStop>> stopsForRoute(String routeId) =>
      (select(cachedStops)
            ..where(($CachedStopsTable t) => t.routeId.equals(routeId))
            ..orderBy(<OrderClauseGenerator<$CachedStopsTable>>[
              ($CachedStopsTable t) => OrderingTerm(expression: t.seq)
            ]))
          .get();

  Future<List<CachedPosition>> lastKnownPositions() => select(cachedPositions).get();
}

LazyDatabase _openConnection() {
  return LazyDatabase(() async {
    final Directory dir = await getApplicationDocumentsDirectory();
    final File f = File(p.join(dir.path, 'damascus_transit.sqlite'));
    return NativeDatabase.createInBackground(f);
  });
}

final databaseProvider = Provider<AppDatabase>((Ref ref) {
  final AppDatabase db = AppDatabase();
  ref.onDispose(db.close);
  return db;
});
