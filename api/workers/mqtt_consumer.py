"""MQTT consumer worker — Phase S2.2 of Scale_100k_Roadmap.md.

What it does
------------
Subscribes to the MQTT broker and feeds every accepted telemetry frame into the
*same* ingest pipeline used by the HTTP bridge (``api/routers/mqtt_ingest.py``):

    broker  ──(vehicles/<id>/status)──►  this worker  ──►  _ingest()
                                                              ├─ Redis Geo (live map)
                                                              ├─ EMA fuel smoothing
                                                              └─ persist to vehicle_positions

Because it reuses ``_ingest`` and ``_PartialDecode``, the MQTT path and the
HTTP-bridge path stay byte-for-byte identical — the broker is purely a transport
swap, exactly as the roadmap intends.

Why a separate process
----------------------
The production API runs on serverless (Vercel) where a long-lived MQTT
subscription cannot live. This worker is meant to run as its own container in
the self-hosted / Docker deployment (see ``docker-compose.scale.yml``)::

    python -m api.workers.mqtt_consumer

Wire format
-----------
For development the payload is JSON matching ``telematics.proto`` 1:1 (the same
shape ``_PartialDecode`` accepts). A single object or a JSON array (replay
batch) are both accepted. When the protoc-generated bindings land, swap the
``json.loads`` decode for the generated parser — the rest is unchanged.

Soft-fail
---------
Redis and Supabase both degrade gracefully when unconfigured (the underlying
helpers no-op), so the worker runs in a bare dev environment for local testing
against mosquitto with no cloud services attached.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import aiomqtt

from api.core import geo_cache
from api.core.logging import logger
from api.routers.mqtt_ingest import _PartialDecode, _ingest

# ── Configuration (env-driven) ────────────────────────────────────────────────
BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
BROKER_USERNAME = os.getenv("MQTT_USERNAME") or None
BROKER_PASSWORD = os.getenv("MQTT_PASSWORD") or None
STATUS_TOPIC = os.getenv("MQTT_STATUS_TOPIC", "vehicles/+/status")
EVENT_TOPIC = os.getenv("MQTT_EVENT_TOPIC", "vehicles/+/event")
RECONNECT_SECONDS = int(os.getenv("MQTT_RECONNECT_SECONDS", "5"))
CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "dam-mqtt-consumer")


def _frames(payload: bytes) -> list[dict[str, Any]]:
    """Decode a payload into a list of frame dicts (single object or batch)."""
    data = json.loads(payload.decode("utf-8", "replace"))
    if isinstance(data, list):
        return [f for f in data if isinstance(f, dict)]
    if isinstance(data, dict):
        # A VehicleStatusBatch may wrap frames under "frames".
        if isinstance(data.get("frames"), list):
            return [f for f in data["frames"] if isinstance(f, dict)]
        return [data]
    return []


async def _handle(topic: str, payload: bytes) -> None:
    try:
        frames = _frames(payload)
    except Exception as exc:  # malformed JSON — log and drop, never crash
        logger.warning(
            "mqtt_payload_decode_failed", extra={"topic": topic, "err": str(exc)[:200]}
        )
        return

    is_event = topic.endswith("/event")
    for frame in frames:
        try:
            decoded = _PartialDecode(**frame)
        except Exception as exc:
            logger.warning(
                "mqtt_frame_invalid", extra={"topic": topic, "err": str(exc)[:200]}
            )
            continue

        await _ingest(decoded)

        # On an ignition-off / offline event, pull the vehicle out of the live
        # GEO set so the map stops showing a stale marker. (Production should map
        # telematics.proto EventType; here we use engine_state as the signal.)
        if is_event and decoded.engine_state is False and decoded.operator_id:
            await geo_cache.remove_position(
                operator_id=decoded.operator_id,
                vehicle_id=decoded.vehicle_id,
            )


async def _run_once() -> None:
    async with aiomqtt.Client(
        hostname=BROKER_HOST,
        port=BROKER_PORT,
        username=BROKER_USERNAME,
        password=BROKER_PASSWORD,
        identifier=CLIENT_ID,
    ) as client:
        logger.info(
            "mqtt_consumer_connected",
            extra={
                "host": BROKER_HOST,
                "port": BROKER_PORT,
                "redis": geo_cache.configured(),
            },
        )
        await client.subscribe(STATUS_TOPIC, qos=0)
        await client.subscribe(EVENT_TOPIC, qos=1)
        async for message in client.messages:
            await _handle(str(message.topic), bytes(message.payload))


async def main() -> None:
    logger.info(
        "mqtt_consumer_starting",
        extra={"status_topic": STATUS_TOPIC, "event_topic": EVENT_TOPIC},
    )
    while True:
        try:
            await _run_once()
        except aiomqtt.MqttError as exc:
            logger.warning(
                "mqtt_consumer_reconnect",
                extra={"err": str(exc)[:200], "retry_in_s": RECONNECT_SECONDS},
            )
            await asyncio.sleep(RECONNECT_SECONDS)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("mqtt_consumer_stopped")
