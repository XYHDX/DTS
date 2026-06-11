"""Live position bus — Phase S3.4 of Scale_100k_Roadmap.md.

Why this exists
---------------
The legacy ``/api/stream`` SSE endpoint generated its payload *inside the web
process*: every connected client ran its own 2-second Supabase poll for the
whole life of the connection. That has two fatal properties at scale:

  * **O(clients) database load** — 10,000 passengers watching the live map means
    10,000 independent pollers hammering Postgres every two seconds.
  * **Sticky sessions** — the position-generation work is pinned to whichever
    process holds the socket, so you cannot put more than one web process behind
    a load balancer without sticky routing.

S3.4 moves the *generation* off the web process. Telemetry is published **once**,
on the ingest path, to a pub/sub channel; every web process simply subscribes and
relays whatever arrives. Any process can serve any client, the database is touched
once per *update* (not once per client), and horizontal scale needs no sticky
sessions::

    driver / MQTT ingest ──publish()──► channel ──subscribe()──► /api/stream ──► client
                                        (fan-out)

Backends
--------
* ``redis``  — native Redis pub/sub over a TCP connection (redis-py asyncio),
               selected when ``REDIS_PUBSUB_URL`` is set. This is the only backend
               that fans out across *processes and hosts*, so it is the one that
               actually delivers horizontal scale. (The Upstash REST client used
               for the geo cache and rate limiter cannot hold a long-lived
               ``SUBSCRIBE``, which is why pub/sub takes its own TCP URL.)
* ``memory`` — in-process asyncio fan-out, selected with ``LIVE_BUS_BACKEND=memory``.
               Handy for a single-process self-hosted box and for tests; it does
               **not** cross process boundaries.
* disabled   — the default. :func:`configured` returns ``False`` and ``/api/stream``
               keeps its legacy Supabase-poll path, so the production Vercel
               deployment is byte-for-byte unchanged until a Redis URL is provided.

Soft-fail
---------
Every call swallows backend errors. A Redis blip must never take down telemetry
ingestion or an open SSE stream: :func:`publish` returns ``False`` and
:func:`subscribe` ends cleanly, and the caller carries on.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import AsyncIterator, Optional

from api.core.logging import logger

# Channel layout. Every update is published to its operator's channel *and* to a
# single firehose channel, so the admin "all operators" view can subscribe to one
# well-known channel instead of needing pattern subscriptions.
_CHANNEL_PREFIX = "dam:positions:"
_FIREHOSE = _CHANNEL_PREFIX + "_all"

# Bounded per-subscriber buffer. If a client is slower than the publish rate we
# drop the oldest frames rather than let the queue grow without bound or stall
# the publisher — a live map only ever cares about the freshest position.
_QUEUE_MAXSIZE = int(os.getenv("LIVE_BUS_QUEUE_MAXSIZE", "256"))


def _channel(operator_id: Optional[str]) -> str:
    safe = (operator_id or "default").replace(":", "_")
    return _CHANNEL_PREFIX + safe


# ───────────────────────── backends ──────────────────────────────────────────


class _MemoryBackend:
    """Single-process asyncio fan-out. Does not cross process boundaries."""

    name = "memory"

    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = {}

    async def publish(self, channel: str, message: str) -> bool:
        queues = self._subs.get(channel)
        if not queues:
            return True  # no subscribers on this process — nothing to do
        for q in list(queues):
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                # Drop the oldest frame to make room for the freshest one.
                try:
                    q.get_nowait()
                    q.put_nowait(message)
                except Exception:
                    pass
        return True

    async def subscribe(self, channel: str) -> AsyncIterator[str]:
        q: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        self._subs.setdefault(channel, set()).add(q)
        try:
            while True:
                yield await q.get()
        finally:
            subs = self._subs.get(channel)
            if subs is not None:
                subs.discard(q)
                if not subs:
                    self._subs.pop(channel, None)


class _RedisBackend:
    """Native Redis pub/sub over TCP — fans out across processes and hosts."""

    name = "redis"

    def __init__(self, url: str) -> None:
        self._url = url
        self._client = None  # lazily created shared publisher connection

    def _publisher(self):
        if self._client is None:
            from redis.asyncio import Redis  # lazy import; optional dependency

            self._client = Redis.from_url(self._url, decode_responses=True)
        return self._client

    async def publish(self, channel: str, message: str) -> bool:
        try:
            await self._publisher().publish(channel, message)
            return True
        except Exception as exc:  # never let a Redis blip break ingestion
            logger.warning("live_bus_publish_failed", extra={"err": str(exc)[:200]})
            return False

    async def subscribe(self, channel: str) -> AsyncIterator[str]:
        from redis.asyncio import Redis  # lazy import

        # A dedicated connection per subscriber — pub/sub holds the socket open.
        client = Redis.from_url(self._url, decode_responses=True)
        pubsub = client.pubsub()
        try:
            await pubsub.subscribe(channel)
            async for msg in pubsub.listen():
                if not msg or msg.get("type") != "message":
                    continue  # skip the subscribe-confirmation control frame
                data = msg.get("data")
                if isinstance(data, (bytes, bytearray)):
                    data = data.decode("utf-8", "replace")
                if data is not None:
                    yield data
        finally:
            for closer in (
                lambda: pubsub.unsubscribe(channel),
                pubsub.aclose,
                client.aclose,
            ):
                try:
                    await closer()
                except Exception:
                    pass


# ───────────────────────── backend selection ─────────────────────────────────

_backend: Optional[object] = None
_selected = False


def _select_backend():
    """Pick a backend from the environment, once, and cache it.

    ``REDIS_PUBSUB_URL`` wins (the real horizontal-scale path). Otherwise
    ``LIVE_BUS_BACKEND=memory`` enables single-process fan-out. The default is
    *disabled* so the serverless deployment keeps its legacy poll path.
    """
    global _backend, _selected
    if _selected:
        return _backend
    _selected = True

    url = os.getenv("REDIS_PUBSUB_URL", "").strip()
    if url:
        _backend = _RedisBackend(url)
        logger.info("live_bus_backend", extra={"backend": "redis"})
    elif os.getenv("LIVE_BUS_BACKEND", "").strip().lower() == "memory":
        _backend = _MemoryBackend()
        logger.info("live_bus_backend", extra={"backend": "memory"})
    else:
        _backend = None  # disabled — /api/stream falls back to polling
    return _backend


# ───────────────────────── public API ────────────────────────────────────────


def configured() -> bool:
    """True when a real fan-out backend is active (so ``/api/stream`` can push)."""
    return _select_backend() is not None


def backend_name() -> str:
    b = _select_backend()
    return getattr(b, "name", "disabled")


async def publish(*, operator_id: Optional[str], payload: dict) -> bool:
    """Fan a position update out to the operator channel and the firehose.

    Best-effort: returns ``True`` on success, ``False`` on any failure or when no
    backend is configured. Never raises — ingestion must not depend on the bus.
    """
    backend = _select_backend()
    if backend is None:
        return False
    try:
        message = json.dumps(payload, default=str)
    except (TypeError, ValueError):
        return False
    ok_op = await backend.publish(_channel(operator_id), message)
    ok_all = await backend.publish(_FIREHOSE, message)
    return bool(ok_op and ok_all)


async def subscribe(*, operator_id: Optional[str]) -> AsyncIterator[dict]:
    """Yield position dicts as they are published for ``operator_id``.

    ``operator_id=None`` subscribes to the firehose (every operator) for the
    admin / super-admin "all vehicles" view. Yields nothing and ends cleanly when
    no backend is configured. Each malformed frame is skipped, not fatal.
    """
    backend = _select_backend()
    if backend is None:
        return
    channel = _FIREHOSE if operator_id is None else _channel(operator_id)
    async for raw in backend.subscribe(channel):
        try:
            yield json.loads(raw)
        except (TypeError, ValueError):
            continue


# ───────────────────────── test helpers ──────────────────────────────────────


def _reset_for_test() -> None:
    """Forget the cached backend so the next call re-reads the environment."""
    global _backend, _selected
    _backend = None
    _selected = False


def _use_memory_backend() -> None:
    """Force the in-memory backend (used by the test-suite, no Redis required)."""
    global _backend, _selected
    _backend = _MemoryBackend()
    _selected = True
