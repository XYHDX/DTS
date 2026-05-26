#!/usr/bin/env python3
"""
Damascus Transit GPS Simulator

Continuously simulates vehicle positions by calling the admin simulate endpoint.
Designed for demos, development, and validating the real-time tracking pipeline.

Usage:
    # One-shot: generate positions once
    python scripts/simulate_gps.py --base-url https://syrian-transit-system.vercel.app --once

    # Continuous: update every 10 seconds
    python scripts/simulate_gps.py --base-url https://syrian-transit-system.vercel.app --interval 10

    # With explicit credentials
    python scripts/simulate_gps.py --base-url https://syrian-transit-system.vercel.app \
        --email admin@damascustransit.sy --password YOUR_PASSWORD

Environment variables:
    TRANSIT_API_URL     Base URL of the transit API
    TRANSIT_ADMIN_EMAIL Admin email for authentication
    TRANSIT_ADMIN_PASS  Admin password for authentication
"""

import argparse
import os
import sys
import time

import httpx


def login(client: httpx.Client, base_url: str, email: str, password: str) -> str:
    """Authenticate and return JWT token."""
    resp = client.post(
        f"{base_url}/api/auth/login",
        json={"email": email, "password": password},
    )
    if resp.status_code != 200:
        print(f"Login failed ({resp.status_code}): {resp.text}", file=sys.stderr)
        sys.exit(1)
    token = resp.json()["access_token"]
    print(f"Authenticated as {email}")
    return token


def simulate(client: httpx.Client, base_url: str, token: str) -> dict:
    """Call the simulate endpoint and return the response."""
    resp = client.post(
        f"{base_url}/api/admin/simulate",
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code != 200:
        print(f"Simulate failed ({resp.status_code}): {resp.text}", file=sys.stderr)
        return {"status": "error", "updated": 0, "_status_code": resp.status_code}
    return resp.json()


def main():
    parser = argparse.ArgumentParser(description="Damascus Transit GPS Simulator")
    parser.add_argument(
        "--base-url",
        default=os.getenv(
            "TRANSIT_API_URL", "https://syrian-transit-system.vercel.app"
        ),
        help="Transit API base URL",
    )
    parser.add_argument(
        "--email",
        default=os.getenv("TRANSIT_ADMIN_EMAIL", "admin@damascustransit.sy"),
        help="Admin email",
    )
    parser.add_argument(
        "--password", default=os.getenv("TRANSIT_ADMIN_PASS"), help="Admin password"
    )
    parser.add_argument(
        "--interval", type=int, default=10, help="Seconds between updates"
    )
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if not args.password:
        print(
            "Password required. Set TRANSIT_ADMIN_PASS or use --password.",
            file=sys.stderr,
        )
        sys.exit(1)

    with httpx.Client(timeout=30.0) as client:
        token = login(client, args.base_url, args.email, args.password)

        if args.once:
            result = simulate(client, args.base_url, token)
            print(f"Updated {result.get('updated', 0)} vehicles")
            for v in result.get("vehicles", []):
                print(
                    f"  {v['vehicle_id']}: ({v['lat']}, {v['lon']}) {v['speed_kmh']} km/h"
                )
            return

        print(f"Simulating every {args.interval}s — Ctrl+C to stop")
        try:
            while True:
                result = simulate(client, args.base_url, token)
                if result.get("_status_code") == 401:
                    print("Token expired — re-authenticating…")
                    token = login(client, args.base_url, args.email, args.password)
                    result = simulate(client, args.base_url, token)
                ts = result.get("timestamp", "?")
                count = result.get("updated", 0)
                print(f"[{ts}] Updated {count} vehicles")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
