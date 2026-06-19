import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:go_router/go_router.dart';
import 'package:latlong2/latlong.dart';

import '../../core/api_client.dart';
import '../../core/theme.dart';
import '../map/vehicle_stream.dart';
import '../routes/route_repository.dart';

// TODO(i18n): strings are still hardcoded; externalize to AppLocalizations.of(context)

class PassengerHome extends ConsumerStatefulWidget {
  const PassengerHome({super.key});
  @override
  ConsumerState<PassengerHome> createState() => _PassengerHomeState();
}

class _PassengerHomeState extends ConsumerState<PassengerHome> {
  LatLng _center = const LatLng(33.513, 36.291);
  final TextEditingController _searchCtl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _locate();
  }

  @override
  void dispose() {
    _searchCtl.dispose();
    super.dispose();
  }

  void _openNearby() => context.push('/nearby');

  Future<void> _locate() async {
    try {
      final LocationPermission perm = await Geolocator.requestPermission();
      if (perm == LocationPermission.denied ||
          perm == LocationPermission.deniedForever) {
        return;
      }
      final Position p = await Geolocator.getCurrentPosition(
          locationSettings: const LocationSettings(accuracy: LocationAccuracy.medium));
      if (mounted) setState(() => _center = LatLng(p.latitude, p.longitude));
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final AsyncValue<List<TransitRoute>> routes = ref.watch(routesProvider);
    final AsyncValue<List<VehiclePosition>> vehicles = ref.watch(vehicleStreamProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('نقل دمشق')),
      bottomNavigationBar: const _BottomNav(),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: <Widget>[
          // Hero search bar
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                begin: Alignment.topRight,
                end: Alignment.bottomLeft,
                colors: <Color>[AppTheme.brand800, AppTheme.brand600],
              ),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                const Text('أهلاً بك',
                    style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.w700)),
                const SizedBox(height: 8),
                const Text('ابحث عن خطك أو شاهد أقرب الحافلات.',
                    style: TextStyle(color: Colors.white70)),
                const SizedBox(height: 14),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.16),
                    borderRadius: BorderRadius.circular(40),
                  ),
                  child: TextField(
                    controller: _searchCtl,
                    textInputAction: TextInputAction.search,
                    onSubmitted: (_) => _openNearby(),
                    style: const TextStyle(color: Colors.white),
                    decoration: InputDecoration(
                      border: InputBorder.none,
                      hintText: 'مزة، باب توما، خط ١٢ …',
                      hintStyle: const TextStyle(color: Colors.white60),
                      prefixIcon: IconButton(
                        icon: const Icon(Icons.search, color: Colors.white),
                        onPressed: _openNearby,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
          Text('الخريطة المباشرة',
              style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          SizedBox(
            height: 260,
            child: ClipRRect(
              borderRadius: BorderRadius.circular(16),
              child: FlutterMap(
                options: MapOptions(
                  initialCenter: _center,
                  initialZoom: 13,
                  interactionOptions: const InteractionOptions(
                    flags: InteractiveFlag.all & ~InteractiveFlag.rotate,
                  ),
                ),
                children: <Widget>[
                  TileLayer(
                    urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                    userAgentPackageName: 'sy.gov.damascus.transit',
                  ),
                  vehicles.when(
                    data: (List<VehiclePosition> list) => MarkerLayer(
                      markers: <Marker>[
                        for (final VehiclePosition v in list)
                          Marker(
                            point: LatLng(v.lat, v.lon),
                            width: 16,
                            height: 16,
                            child: const _BusDot(),
                          ),
                      ],
                    ),
                    error: (_, __) => const SizedBox.shrink(),
                    loading: () => const SizedBox.shrink(),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 20),
          Text('الخطوط الشائعة',
              style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          routes.when(
            data: (List<TransitRoute> list) => Column(
              children: <Widget>[
                for (final TransitRoute r in list.take(8))
                  _RouteTile(route: r, onTap: () => context.push('/routes/${r.id}')),
              ],
            ),
            loading: () => const Padding(
                padding: EdgeInsets.all(24),
                child: Center(child: CircularProgressIndicator())),
            error: (Object e, _) => Text('تعذّر تحميل الخطوط: $e'),
          ),
        ],
      ),
    );
  }
}

class _BusDot extends StatelessWidget {
  const _BusDot();
  @override
  Widget build(BuildContext context) => Container(
        decoration: const BoxDecoration(
          color: AppTheme.brand500,
          shape: BoxShape.circle,
          border: Border.fromBorderSide(BorderSide(color: Colors.white, width: 2)),
          boxShadow: <BoxShadow>[
            BoxShadow(color: Color(0x33000000), blurRadius: 4, offset: Offset(0, 1)),
          ],
        ),
      );
}

class _RouteTile extends StatelessWidget {
  const _RouteTile({required this.route, required this.onTap});
  final TransitRoute route;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
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
                child: Text(route.code,
                    style: const TextStyle(
                        color: AppTheme.brand700, fontWeight: FontWeight.w700)),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(route.nameAr ?? route.name,
                        style: const TextStyle(fontWeight: FontWeight.w700)),
                    const SizedBox(height: 2),
                    Text('${route.from ?? ''} ↔ ${route.to ?? ''}',
                        style: const TextStyle(color: Colors.black54, fontSize: 13)),
                  ],
                ),
              ),
              const Icon(Icons.chevron_left, color: Colors.black38),
            ],
          ),
        ),
      ),
    );
  }
}

class _BottomNav extends ConsumerWidget {
  const _BottomNav();
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return NavigationBar(
      destinations: const <NavigationDestination>[
        NavigationDestination(icon: Icon(Icons.home_outlined), selectedIcon: Icon(Icons.home), label: 'الرئيسية'),
        NavigationDestination(icon: Icon(Icons.near_me_outlined), selectedIcon: Icon(Icons.near_me), label: 'قريب'),
        NavigationDestination(icon: Icon(Icons.alt_route_outlined), selectedIcon: Icon(Icons.alt_route), label: 'الخطوط'),
        NavigationDestination(icon: Icon(Icons.person_outline), selectedIcon: Icon(Icons.person), label: 'حسابي'),
      ],
      selectedIndex: 0,
      onDestinationSelected: (int idx) {
        switch (idx) {
          case 1:
            GoRouter.of(context).go('/nearby');
            break;
          case 2:
            GoRouter.of(context).go('/routes');
            break;
          case 3:
            GoRouter.of(context).go('/login');
            break;
          default:
        }
      },
    );
  }
}
