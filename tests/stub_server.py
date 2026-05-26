"""
Load-test stub server for DamascusTransit API.

Mirrors the production API surface with in-memory stores and realistic
simulated latencies for all endpoints tested in DAM-56 load test.

Run with:
    uvicorn tests.stub_server:app --host 0.0.0.0 --port 8080 --workers 4

Or from the project root:
    python -m uvicorn tests.stub_server:app --host 0.0.0.0 --port 8080 --workers 4
"""

import asyncio
import random
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import jwt
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

# ── Config ─────────────────────────────────────────────────────────────────
STUB_JWT_SECRET = "stub-load-test-secret-32-characters-long"
JWT_ALGORITHM = "HS256"
security = HTTPBearer(auto_error=False)

# Simulated per-request latencies (seconds) to approximate Supabase REST
DB_WRITE_LATENCY_MEAN = 0.035  # 35 ms mean
DB_WRITE_LATENCY_STD = 0.015  # ±15 ms std
DB_READ_LATENCY_MEAN = 0.025
DB_READ_LATENCY_STD = 0.010
HEAVY_READ_MEAN = 0.060  # Analytics/aggregation queries
HEAVY_READ_STD = 0.020

# Simulate Vercel cold start: first request after inactivity gets a spike
COLD_START_THRESHOLD_S = 30
COLD_START_LATENCY_S = 1.2

# ── In-memory state ─────────────────────────────────────────────────────────
_vehicles: Dict[str, dict] = {}
_last_request_time: float = time.time()
_cold_start_count: int = 0

# Pre-generate 500 test driver accounts
_test_drivers: List[dict] = [
    {
        "user_id": str(uuid.uuid4()),
        "email": f"driver{i:03d}@test.damascustransit.sy",
        "vehicle_id": f"VEH-{i:03d}",
        "role": "driver",
    }
    for i in range(1, 501)
]

# Pre-generate 20 admin accounts
_test_admins: List[dict] = [
    {
        "user_id": str(uuid.uuid4()),
        "email": f"admin{i:02d}@test.damascustransit.sy",
        "role": "admin",
    }
    for i in range(1, 21)
]

_all_users = {u["email"]: u for u in _test_drivers + _test_admins}

# Static route data (Damascus routes)
_ROUTES = [
    {
        "id": f"R{i:02d}",
        "name": f"Route {i}",
        "name_ar": f"خط {i}",
        "route_type": random.choice(["bus", "microbus"]),
        "color": f"#{random.randint(0, 0xFFFFFF):06x}",
        "distance_km": round(random.uniform(5, 25), 1),
        "fare_syp": random.choice([500, 1000, 1500]),
    }
    for i in range(1, 9)
]

# Static stop data (42 Damascus stops)
_STOPS = [
    {
        "id": f"S{i:03d}",
        "name": f"Stop {i}",
        "name_ar": f"موقف {i}",
        "latitude": round(random.uniform(33.45, 33.55), 6),
        "longitude": round(random.uniform(36.24, 36.34), 6),
        "has_shelter": random.choice([True, False]),
    }
    for i in range(1, 43)
]

# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(title="DamascusTransit Load-Test Stub", version="2.0.0-stub")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ──────────────────────────────────────────────────────────────────
def _sim_latency(mean: float, std: float) -> float:
    return max(0.005, random.gauss(mean, std))


def _make_token(user: dict) -> str:
    expire = datetime.utcnow() + timedelta(hours=24)
    payload = {
        "user_id": user["user_id"],
        "email": user["email"],
        "role": user["role"],
        "exp": expire,
    }
    if "vehicle_id" in user:
        payload["vehicle_id"] = user["vehicle_id"]
    return jwt.encode(payload, STUB_JWT_SECRET, algorithm=JWT_ALGORITHM)


def _verify_token(token: str) -> dict:
    try:
        return jwt.decode(token, STUB_JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def _get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return _verify_token(credentials.credentials)


async def _get_driver(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    user = await _get_current_user(credentials)
    if user.get("role") != "driver":
        raise HTTPException(status_code=403, detail="Driver role required")
    return user


async def _get_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    user = await _get_current_user(credentials)
    if user.get("role") not in ("admin", "dispatcher"):
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


async def _maybe_cold_start():
    global _last_request_time, _cold_start_count
    now = time.time()
    idle = now - _last_request_time
    _last_request_time = now
    if idle > COLD_START_THRESHOLD_S:
        _cold_start_count += 1
        await asyncio.sleep(COLD_START_LATENCY_S)


# ── Models ───────────────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    email: str
    password: str


class PositionUpdate(BaseModel):
    latitude: float
    longitude: float
    speed_kmh: float = 0.0
    heading: float = 0.0


# ── Public Routes ─────────────────────────────────────────────────────────────


@app.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "mode": "stub",
        "vehicles_tracked": len(_vehicles),
        "cold_starts": _cold_start_count,
        "database": True,
    }


@app.post("/api/auth/login")
async def login(body: LoginRequest):
    await _maybe_cold_start()
    user = _all_users.get(body.email)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    await asyncio.sleep(_sim_latency(DB_READ_LATENCY_MEAN, DB_READ_LATENCY_STD))
    return {"access_token": _make_token(user), "token_type": "bearer"}


@app.get("/api/routes")
async def get_routes():
    await asyncio.sleep(_sim_latency(DB_READ_LATENCY_MEAN, DB_READ_LATENCY_STD))
    return _ROUTES


@app.get("/api/stops")
async def get_stops():
    await asyncio.sleep(_sim_latency(DB_READ_LATENCY_MEAN, DB_READ_LATENCY_STD))
    return _STOPS


@app.get("/api/vehicles")
async def get_vehicles():
    await asyncio.sleep(_sim_latency(DB_READ_LATENCY_MEAN, DB_READ_LATENCY_STD))
    return [
        {
            "id": vid,
            "vehicle_id": vid,
            "status": "active",
            "latitude": pos.get("latitude"),
            "longitude": pos.get("longitude"),
            "speed_kmh": pos.get("speed_kmh"),
            "heading": pos.get("heading"),
            "updated_at": pos.get("updated_at"),
        }
        for vid, pos in list(_vehicles.items())
    ]


@app.get("/api/vehicles/positions")
async def get_positions():
    await asyncio.sleep(_sim_latency(DB_READ_LATENCY_MEAN, DB_READ_LATENCY_STD))
    return [{"vehicle_id": vid, **pos} for vid, pos in _vehicles.items()]


@app.get("/api/stats")
async def get_stats():
    await asyncio.sleep(_sim_latency(DB_READ_LATENCY_MEAN, DB_READ_LATENCY_STD))
    return {
        "active_vehicles": len(_vehicles),
        "total_vehicles": 500,
        "active_routes": len(_ROUTES),
        "total_stops": len(_STOPS),
    }


@app.get("/api/stream")
async def stream():
    """SSE stream: sends vehicle positions rapidly for unit tests.

    Note: sleep is kept very short (50ms) so tests using TestClient.stream()
    complete well within the pytest-timeout window. The real production endpoint
    uses longer intervals; this stub is only for fast CI verification.
    """

    async def event_generator():
        import json

        for _ in range(5):  # 5 events, fast cadence for test clients
            data = [
                {"vehicle_id": vid, **pos} for vid, pos in list(_vehicles.items())[:50]
            ]
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(0.05)

    return StreamingResponse(event_generator(), media_type="text/event-stream")



# ── Driver API ────────────────────────────────────────────────────────────────


@app.post("/api/driver/position")
async def report_position(
    position: PositionUpdate,
    current: dict = Depends(_get_driver),
):
    await _maybe_cold_start()
    await asyncio.sleep(_sim_latency(DB_WRITE_LATENCY_MEAN, DB_WRITE_LATENCY_STD))
    _vehicles[current["vehicle_id"]] = {
        "latitude": position.latitude,
        "longitude": position.longitude,
        "speed_kmh": position.speed_kmh,
        "heading": position.heading,
        "updated_at": datetime.utcnow().isoformat(),
    }
    return {"status": "success", "timestamp": datetime.utcnow().isoformat()}


# ── Admin API ─────────────────────────────────────────────────────────────────


@app.get("/api/admin/analytics/overview")
async def admin_analytics_overview(current: dict = Depends(_get_admin)):
    # Heavier query simulation (aggregation across multiple tables)
    await asyncio.sleep(_sim_latency(HEAVY_READ_MEAN, HEAVY_READ_STD))
    return {
        "total_trips_today": random.randint(120, 180),
        "active_vehicles": len(_vehicles),
        "avg_speed_kmh": round(random.uniform(20, 40), 1),
        "on_time_pct": round(random.uniform(75, 95), 1),
        "alerts_unresolved": random.randint(0, 5),
        "passengers_today": random.randint(5000, 12000),
    }


@app.get("/api/admin/trips")
async def admin_trips(current: dict = Depends(_get_admin)):
    # Simulate paginated trip query
    await asyncio.sleep(_sim_latency(HEAVY_READ_MEAN, HEAVY_READ_STD))
    return [
        {
            "id": str(uuid.uuid4()),
            "vehicle_id": f"VEH-{random.randint(1, 500):03d}",
            "route_id": f"R{random.randint(1, 8):02d}",
            "status": random.choice(["completed", "in_progress", "cancelled"]),
            "passenger_count": random.randint(5, 45),
            "distance_km": round(random.uniform(3, 25), 1),
            "on_time_pct": round(random.uniform(60, 100), 1),
        }
        for _ in range(20)
    ]
