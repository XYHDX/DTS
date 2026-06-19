import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../features/auth/auth_controller.dart';
import '../features/auth/login_screen.dart';
import '../features/driver/driver_home.dart';
import '../features/passenger/nearest_stops_screen.dart';
import '../features/passenger/passenger_home.dart';
import '../features/passenger/route_detail_screen.dart';
import '../features/routes/routes_list_screen.dart';
import '../shared/widgets/role_gate.dart';

final routerProvider = Provider<GoRouter>((Ref ref) {
  final AuthController auth = ref.read(authControllerProvider.notifier);
  return GoRouter(
    initialLocation: '/',
    redirect: (BuildContext _, GoRouterState state) {
      final bool loggedIn = auth.isAuthenticated;
      final bool atLogin = state.matchedLocation == '/login';
      if (!loggedIn && state.matchedLocation.startsWith('/driver')) {
        return '/login?next=${Uri.encodeComponent(state.matchedLocation)}';
      }
      if (loggedIn && atLogin) return '/';
      return null;
    },
    routes: <RouteBase>[
      GoRoute(
        path: '/',
        builder: (_, __) => const PassengerHome(),
      ),
      GoRoute(
        path: '/nearby',
        builder: (_, __) => const NearestStopsScreen(),
      ),
      GoRoute(
        path: '/routes',
        builder: (_, __) => const RoutesListScreen(),
      ),
      GoRoute(
        path: '/routes/:id',
        builder: (_, GoRouterState s) =>
            RouteDetailScreen(routeId: s.pathParameters['id']!),
      ),
      GoRoute(
        path: '/login',
        builder: (_, GoRouterState s) =>
            LoginScreen(next: s.uri.queryParameters['next']),
      ),
      GoRoute(
        path: '/driver',
        builder: (_, __) => const RoleGate(
          allow: <String>['driver', 'admin', 'super_admin'],
          child: DriverHome(),
        ),
      ),
    ],
  );
});
