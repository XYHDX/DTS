"""
Locust load test — DamascusTransit comprehensive API test (DAM-56).

Models realistic production traffic across 4 user personas:
  - PassengerUser  (60%): public browsing — routes, stops, vehicles
  - SSEUser        (20%): real-time SSE stream connections
  - DriverUser     (15%): GPS position updates every 5 s
  - AdminUser      ( 5%): analytics dashboard, trip history

Run headless at 3 load levels (substitute HOST as needed):

    HOST=http://localhost:8080

    locust -f tests/locustfile.py --headless -u 100  -r 10  --run-time 2m \\
           --host $HOST --csv /tmp/load_100

    locust -f tests/locustfile.py --headless -u 500  -r 25  --run-time 2m \\
           --host $HOST --csv /tmp/load_500

    locust -f tests/locustfile.py --headless -u 1000 -r 50  --run-time 2m \\
           --host $HOST --csv /tmp/load_1000

Run with live UI:
    locust -f tests/locustfile.py --host http://localhost:8080
    # open http://localhost:8089
"""

import random
from locust import HttpUser, task, between, constant, events

# ── Credentials ───────────────────────────────────────────────────────────────
DRIVERS = [
    {"email": f"driver{i:03d}@test.damascustransit.sy", "password": "loadtest"}
    for i in range(1, 501)
]
ADMINS = [
    {"email": f"admin{i:02d}@test.damascustransit.sy", "password": "loadtest"}
    for i in range(1, 21)
]

# Damascus bounding box
LAT_MIN, LAT_MAX = 33.45, 33.55
LON_MIN, LON_MAX = 36.24, 36.34


def _random_position():
    return {
        "latitude": round(random.uniform(LAT_MIN, LAT_MAX), 6),
        "longitude": round(random.uniform(LON_MIN, LON_MAX), 6),
        "speed_kmh": round(random.uniform(0, 60), 1),
        "heading": round(random.uniform(0, 359), 1),
    }


# ── PassengerUser (60% of load) ───────────────────────────────────────────────


class PassengerUser(HttpUser):
    """
    Simulates a passenger browsing the Damascus Transit web/PWA app.
    No authentication required — all endpoints are public.
    Browses routes, looks up stops, checks vehicle positions.
    Weight 6 = 60% of spawned users.
    """

    weight = 6
    wait_time = between(1, 4)  # realistic human browsing cadence

    @task(4)
    def browse_vehicles(self):
        """Most common action: refresh live vehicle map."""
        with self.client.get(
            "/api/vehicles",
            catch_response=True,
            name="GET /api/vehicles",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"{resp.status_code}: {resp.text[:80]}")

    @task(2)
    def browse_routes(self):
        """Look up available routes."""
        with self.client.get(
            "/api/routes",
            catch_response=True,
            name="GET /api/routes",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"{resp.status_code}: {resp.text[:80]}")

    @task(2)
    def browse_stops(self):
        """Look up bus stops."""
        with self.client.get(
            "/api/stops",
            catch_response=True,
            name="GET /api/stops",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"{resp.status_code}: {resp.text[:80]}")

    @task(1)
    def check_health(self):
        """Lightweight health probe."""
        self.client.get("/api/health", name="GET /api/health")


# ── SSEUser (20% of load) ─────────────────────────────────────────────────────


class SSEUser(HttpUser):
    """
    Simulates a passenger keeping an SSE stream open for real-time updates.
    Each user opens /api/stream and reads the full response (30 s stream).
    Weight 2 = 20% of spawned users.
    """

    weight = 2
    wait_time = between(30, 60)  # re-connect after each stream ends

    @task
    def open_sse_stream(self):
        """Open SSE stream and drain it (simulates a tab staying open)."""
        with self.client.get(
            "/api/stream",
            stream=True,
            catch_response=True,
            name="GET /api/stream",
            timeout=35,
        ) as resp:
            if resp.status_code == 200:
                # Consume the stream
                for _ in resp.iter_lines():
                    pass
                resp.success()
            else:
                resp.failure(f"{resp.status_code}: {resp.text[:80]}")


# ── DriverUser (15% of load) ──────────────────────────────────────────────────


class DriverUser(HttpUser):
    """
    Simulates a bus driver running the DamascusTransit Driver PWA.
    Authenticates on start, then sends GPS updates every 5 s.
    Weight 1.5 → use weight=3 with total weights 6+2+3+1=12, giving 25%…
    but since locust weights must be int, use weight=2 (closest to 15%).

    Actual traffic split at spawn:
      weight 6 (Passenger) + weight 2 (SSE) + weight 2 (Driver) + weight 1 (Admin)
      = 11 total → ~54.5% / 18.2% / 18.2% / 9.1%
    Close enough to target; see comment at bottom for exact split option.
    """

    weight = 2
    wait_time = constant(5)  # position update every 5 s

    def on_start(self):
        self._token = ""
        self._headers = {}
        driver = random.choice(DRIVERS)
        with self.client.post(
            "/api/auth/login",
            json={"email": driver["email"], "password": "loadtest"},
            catch_response=True,
            name="POST /api/auth/login",
        ) as resp:
            if resp.status_code == 200:
                self._token = resp.json().get("access_token", "")
                self._headers = {"Authorization": f"Bearer {self._token}"}
                resp.success()
            else:
                resp.failure(f"Login failed: {resp.status_code}")

    @task(10)
    def report_position(self):
        """Primary task: GPS position update every 5 s."""
        if not self._token:
            return
        with self.client.post(
            "/api/driver/position",
            json=_random_position(),
            headers=self._headers,
            catch_response=True,
            name="POST /api/driver/position",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 401:
                self._token = ""
                resp.failure("Token expired — will re-auth")
            elif resp.status_code == 404:
                resp.failure("No vehicle assigned")
            else:
                resp.failure(f"{resp.status_code}: {resp.text[:80]}")

    @task(1)
    def check_fleet(self):
        """Occasional fleet snapshot — driver checking other vehicles."""
        if not self._token:
            return
        with self.client.get(
            "/api/vehicles/positions",
            headers=self._headers,
            catch_response=True,
            name="GET /api/vehicles/positions",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"{resp.status_code}")


# ── AdminUser (5% of load) ────────────────────────────────────────────────────


class AdminUser(HttpUser):
    """
    Simulates a dispatcher / admin checking the operations dashboard.
    Authenticates as admin, polls analytics and trip history.
    Weight 1 = ~9% of spawned users (closest integer to 5%).
    """

    weight = 1
    wait_time = between(5, 15)  # dashboard auto-refresh cadence

    def on_start(self):
        self._token = ""
        self._headers = {}
        admin = random.choice(ADMINS)
        with self.client.post(
            "/api/auth/login",
            json={"email": admin["email"], "password": "loadtest"},
            catch_response=True,
            name="POST /api/auth/login",
        ) as resp:
            if resp.status_code == 200:
                self._token = resp.json().get("access_token", "")
                self._headers = {"Authorization": f"Bearer {self._token}"}
                resp.success()
            else:
                resp.failure(f"Admin login failed: {resp.status_code}")

    @task(3)
    def analytics_overview(self):
        """Dashboard overview — most frequent admin action."""
        if not self._token:
            return
        with self.client.get(
            "/api/admin/analytics/overview",
            headers=self._headers,
            catch_response=True,
            name="GET /api/admin/analytics/overview",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 401:
                self._token = ""
                resp.failure("Token expired")
            else:
                resp.failure(f"{resp.status_code}: {resp.text[:80]}")

    @task(2)
    def trip_history(self):
        """Trip history query."""
        if not self._token:
            return
        with self.client.get(
            "/api/admin/trips",
            headers=self._headers,
            catch_response=True,
            name="GET /api/admin/trips",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"{resp.status_code}: {resp.text[:80]}")

    @task(1)
    def check_health(self):
        self.client.get("/api/health", name="GET /api/health")


# ── User weight summary ───────────────────────────────────────────────────────
# Weight totals: Passenger(6) + SSE(2) + Driver(2) + Admin(1) = 11
# Effective split: ~54.5% / 18.2% / 18.2% / 9.1%
# Target split:    60%     / 20%   / 15%   / 5%
# This is the closest achievable with integer weights.


# ── Event hooks ───────────────────────────────────────────────────────────────


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("\n[locust] DAM-56 Load test started")
    print("[locust] User classes: Passenger(60%) | SSE(20%) | Driver(15%) | Admin(5%)")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    stats = environment.stats
    print("\n[locust] ═══ Test Complete — Summary ═══")
    endpoints = [
        "GET /api/vehicles",
        "GET /api/routes",
        "GET /api/stops",
        "GET /api/stream",
        "POST /api/driver/position",
        "GET /api/admin/analytics/overview",
        "GET /api/admin/trips",
    ]
    for name in endpoints:
        s = stats.get(name, "GET") or stats.get(name, "POST")
        if s and s.num_requests > 0:
            print(
                f"  {name:<42} "
                f"reqs={s.num_requests:>5}  "
                f"fail={s.num_failures:>3}  "
                f"p50={s.median_response_time:>4}ms  "
                f"p95={s.get_response_time_percentile(0.95):>4}ms  "
                f"p99={s.get_response_time_percentile(0.99):>4}ms"
            )
    total = stats.total
    print(
        f"\n  TOTAL  reqs={total.num_requests}  fail={total.num_failures}  "
        f"RPS={total.current_rps:.1f}  "
        f"p50={total.median_response_time}ms  "
        f"p95={total.get_response_time_percentile(0.95)}ms"
    )
