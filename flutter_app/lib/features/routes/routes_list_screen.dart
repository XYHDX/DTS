import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme.dart';
import 'route_repository.dart';

class RoutesListScreen extends ConsumerWidget {
  const RoutesListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<List<TransitRoute>> routes = ref.watch(routesProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('الخطوط')),
      body: routes.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (Object e, _) => Center(child: Text('خطأ: $e')),
        data: (List<TransitRoute> list) => RefreshIndicator(
          onRefresh: () async => ref.invalidate(routesProvider),
          child: ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: list.length,
            separatorBuilder: (_, __) => const SizedBox(height: 10),
            itemBuilder: (BuildContext _, int i) {
              final TransitRoute r = list[i];
              return Card(
                child: InkWell(
                  borderRadius: BorderRadius.circular(16),
                  onTap: () => context.push('/routes/${r.id}'),
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Row(
                      children: <Widget>[
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                          decoration: BoxDecoration(
                            color: AppTheme.brand100,
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Text(r.code,
                              style: const TextStyle(
                                  color: AppTheme.brand700,
                                  fontWeight: FontWeight.w700)),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: <Widget>[
                              Text(r.nameAr ?? r.name,
                                  style: const TextStyle(fontWeight: FontWeight.w700)),
                              const SizedBox(height: 2),
                              Text('${r.from ?? ''} ↔ ${r.to ?? ''}',
                                  style: const TextStyle(color: Colors.black54, fontSize: 13)),
                            ],
                          ),
                        ),
                        if (r.stopsCount != null) Text('${r.stopsCount} محطة',
                            style: const TextStyle(color: Colors.black54)),
                      ],
                    ),
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}
