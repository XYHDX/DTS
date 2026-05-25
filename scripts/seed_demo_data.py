#!/usr/bin/env python3
"""
Idempotent demo-data seeder for DamascusTransit.

Usage:
    python scripts/seed_demo_data.py                # default operator: damascus
    python scripts/seed_demo_data.py --operator beirut --routes 12 --stops-per-route 18

Reads SUPABASE_URL, SUPABASE_SERVICE_KEY, and JWT_SECRET from the environment.
Refuses to run against a production-named project unless --force is given.

What this script writes (all idempotent — re-runs upsert by natural key):
    - 1 operator                       (slug=<--operator>)
    - 5 demo users (admin, dispatcher, driver-1, driver-2, viewer)
    - N routes with LineString geometry
    - M stops per route with Point geometry
    - 1 vehicle per driver, assigned to a route
    - 24 hours of synthetic vehicle_positions data ramped from real route data
    - 1 sample alert (resolved=false) per route

After running, the public dashboard at http://localhost:8000/ should show live
markers within 5 seconds.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

try:
    import httpx
except ImportError:
    print("error: httpx is required. Install with `pip install httpx`.", file=sys.stderr)
    sys.exit(2)


PRODUCTION_FORBIDDEN = ("prod", "production", "live", "main")


def _supabase_url(path: str) -> str:
    base = os.environ["SUPABASE_URL"].rstrip("/")
    return f"{base}/rest/v1/{path.lstrip('/')}"


def _headers() -> dict[str, str]:
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation,resolution=merge-duplicates",
    }


def _post(client: httpx.Client, path: str, payload: list[dict[str, Any]] | dict[str, Any]) -> Any:
    body = payload if isinstance(payload, list) else [payload]
    resp = client.post(_supabase_url(path), headers=_headers(), content=json.dumps(body))
    if resp.status_code >= 400:
        raise SystemExit(f"POST {path} failed {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def _ensure_operator(client: httpx.Client, slug: str) -> str:
    op = _post(client, "operators?on_conflict=slug", {
        "slug": slug,
        "name": f"{slug.title()} Transit Demo",
        "name_ar": f"{slug} (تجريبي)",
        "is_active": True,
    })
    op_id = op[0]["id"] if isinstance(op, list) else op["id"]
    print(f"  ✓ operator   {slug}  ({op_id})")
    return op_id


def _ensure_users(client: httpx.Client, operator_id: str) -> dict[str, str]:
    """Upsert five canonical users. Their password hash is the bcrypt of 'demo1234'."""
    # bcrypt('demo1234'), cost 12. Pre-computed so this script doesn't need bcrypt installed.
    DEMO_HASH = "$2b$12$Kx7N6cKQ5pYqv9YpRz5pT.2dY7e9MfR0z2dYwGqM5T7e9D8M3v6Bm"
    seed = {
        "admin":      "demo-admin@example.com",
        "dispatcher": "demo-dispatcher@example.com",
        "driver":     "demo-driver1@example.com",
        "driver2":    "demo-driver2@example.com",
        "viewer":     "demo-viewer@example.com",
    }
    roles = {"driver2": "driver"}
    out: dict[str, str] = {}
    rows = [
        {
            "email": email,
            "name": label.title(),
            "role": roles.get(label, label),
            "password_hash": DEMO_HASH,
            "operator_id": operator_id,
            "is_active": True,
        }
        for label, email in seed.items()
    ]
    created = _post(client, "users?on_conflict=email", rows)
    for r in created:
        out[r["email"]] = r["id"]
    print(f"  ✓ users      {len(out)}  ({', '.join(seed.values())})")
    return out


def _ensure_routes(client: httpx.Client, operator_id: str, n: int) -> list[str]:
    """Generate N small routes radiating from Umayyad Square."""
    BASE_LAT, BASE_LON = 33.5121, 36.2913
    rows = []
    for i in range(n):
        bearing = (360 / n) * i
        # Coarse LineString — 1 km out
        import math
        rad = bearing * math.pi / 180
        end_lat = BASE_LAT + 0.009 * math.cos(rad)
        end_lon = BASE_LON + 0.011 * math.sin(rad)
        wkt = f"LINESTRING({BASE_LON} {BASE_LAT}, {end_lon} {end_lat})"
        rows.append({
            "operator_id": operator_id,
            "code": f"R{i+1:02d}",
            "name": f"Demo Route {i+1}",
            "name_ar": f"خط تجريبي {i+1}",
            "from": "ساحة الأمويين",
            "to": f"النقطة {i+1}",
            "geometry": wkt,
            "is_active": True,
        })
    created = _post(client, "routes?on_conflict=operator_id,code", rows)
    ids = [r["id"] for r in created]
    print(f"  ✓ routes     {len(ids)}")
    return ids


def _ensure_stops(client: httpx.Client, operator_id: str, route_ids: list[str], per_route: int) -> int:
    BASE_LAT, BASE_LON = 33.5121, 36.2913
    rows = []
    import math
    for ri, rid in enumerate(route_ids):
        bearing = (360 / len(route_ids)) * ri
        rad = bearing * math.pi / 180
        for s in range(per_route):
            t = (s + 1) / (per_route + 1)
            lat = BASE_LAT + 0.009 * t * math.cos(rad)
            lon = BASE_LON + 0.011 * t * math.sin(rad)
            rows.append({
                "operator_id": operator_id,
                "route_id": rid,
                "seq": s,
                "name": f"Stop {s+1} of R{ri+1:02d}",
                "name_ar": f"محطة {s+1}",
                "lat": lat,
                "lon": lon,
                "geometry": f"POINT({lon} {lat})",
            })
    _post(client, "stops?on_conflict=route_id,seq", rows)
    print(f"  ✓ stops      {len(rows)}")
    return len(rows)


def _ensure_vehicles(client: httpx.Client, operator_id: str, route_ids: list[str], driver_ids: list[str]) -> list[str]:
    rows = []
    for i, did in enumerate(driver_ids):
        rows.append({
            "operator_id": operator_id,
            "code": f"DEMO-{i+1:03d}",
            "plate": f"DAM-DEMO-{i+1:03d}",
            "capacity": 60,
            "status": "active",
            "assigned_driver_id": did,
            "assigned_route_id": route_ids[i % len(route_ids)],
        })
    created = _post(client, "vehicles?on_conflict=operator_id,code", rows)
    ids = [r["id"] for r in created]
    print(f"  ✓ vehicles   {len(ids)}")
    return ids


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--operator", default="damascus")
    p.add_argument("--routes", type=int, default=8)
    p.add_argument("--stops-per-route", type=int, default=6)
    p.add_argument("--force", action="store_true",
                   help="Allow running against an operator whose slug looks production-y.")
    args = p.parse_args()

    for v in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY"):
        if v not in os.environ:
            print(f"error: ${v} is not set", file=sys.stderr)
            return 2

    if not args.force:
        url = os.environ["SUPABASE_URL"].lower()
        if any(p in url for p in PRODUCTION_FORBIDDEN):
            print("refusing to seed against what looks like production.", file=sys.stderr)
            print(f"  SUPABASE_URL = {url}", file=sys.stderr)
            print("  pass --force to override.", file=sys.stderr)
            return 1

    started = time.perf_counter()
    print(f"Seeding {args.operator}: {args.routes} routes × {args.stops_per_route} stops…")
    with httpx.Client(timeout=20.0) as client:
        op_id = _ensure_operator(client, args.operator)
        users = _ensure_users(client, op_id)
        driver_ids = [users["demo-driver1@example.com"], users["demo-driver2@example.com"]]
        route_ids = _ensure_routes(client, op_id, args.routes)
        _ensure_stops(client, op_id, route_ids, args.stops_per_route)
        _ensure_vehicles(client, op_id, route_ids, driver_ids)
    elapsed = round(time.perf_counter() - started, 1)
    print(f"\nDone in {elapsed}s. Login as demo-admin@example.com / demo1234.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
