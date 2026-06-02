"""MQTT simulator — publish fake Damascus telemetry for testing Phase S2.2.

Publishes N moving vehicles to ``vehicles/<id>/status`` at the adaptive
heartbeat rate so you can watch the MQTT consumer ingest them locally.

Usage::

    pip install aiomqtt
    python scripts/mqtt_sim_publish.py --vehicles 10 --interval 5

Then run the consumer in another terminal::

    python -m api.workers.mqtt_consumer
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import time

import aiomqtt

# Roughly central Damascus.
BASE_LAT, BASE_LON = 33.5138, 36.2765
OPERATOR_ID = "00000000-0000-0000-0000-000000000001"  # default 'damascus' operator


def _frame(vehicle_id: str, lat: float, lon: float) -> dict:
    return {
        "vehicle_id": vehicle_id,
        "operator_id": OPERATOR_ID,
        "timestamp": int(time.time() * 1000),
        "latitude": round(lat, 6),
        "longitude": round(lon, 6),
        "speed_kph": round(random.uniform(0, 45), 1),
        "heading": round(random.uniform(0, 359), 1),
        "engine_state": True,
        "fuel_level": round(random.uniform(20, 95), 1),
        "trigger_event": 0,
        "satellite_count": random.randint(5, 12),
        "hdop": round(random.uniform(0.6, 2.5), 1),
        "firmware_version": 10000,
        "battery_mv": random.randint(3600, 4200),
    }


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--vehicles", type=int, default=10)
    ap.add_argument("--interval", type=float, default=5.0, help="seconds between pings")
    args = ap.parse_args()

    # Each vehicle does a small random walk from the base point.
    pos = {
        f"DAM-{i:03d}": [BASE_LAT + random.uniform(-0.05, 0.05), BASE_LON + random.uniform(-0.05, 0.05)]
        for i in range(1, args.vehicles + 1)
    }

    async with aiomqtt.Client(hostname=args.host, port=args.port, identifier="dam-sim-publisher") as client:
        print(f"Publishing {args.vehicles} vehicles every {args.interval}s to {args.host}:{args.port} ...")
        while True:
            for vid, p in pos.items():
                p[0] += random.uniform(-0.002, 0.002)
                p[1] += random.uniform(-0.002, 0.002)
                payload = json.dumps(_frame(vid, p[0], p[1]))
                await client.publish(f"vehicles/{vid}/status", payload=payload, qos=0)
            print(f"  ...published {len(pos)} frames")
            await asyncio.sleep(args.interval)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nstopped")
