# ADR-004 — Ingestion stack for 100k vehicles: MQTT + Kafka + TimescaleDB

- **Status:** Accepted
- **Date:** 2026-05-24
- **Deciders:** 3dtitans, Claude (advisory), guided by `docs/transit_architecture_guide.md`
- **Supersedes:** the implicit "HTTP webhook → PostgREST → Postgres" pattern that ships today.

## Context

The current ingestion path is:

```
GPS device → Traccar → HTTPS POST /api/traccar/position → FastAPI → Supabase (Postgres + PostGIS)
```

At our pilot scale (24 vehicles, ~5 s pings) this is fine — roughly 5 writes/sec, JSON over TLS, single Postgres connection per request through the Supavisor pooler.

The architecture guide we adopted on 24 May 2026 targets **100,000 vehicles**. That changes every assumption:

| | 500 vehicles today | 100,000 vehicles target |
|---|---|---|
| Writes per second | ~5 | **~10,000** (200×) |
| Monthly egress @ 10 s ping × 180-byte JSON | ~25 GB | ~4.6 TB |
| Concurrent device sockets | tens | tens of thousands |
| Tail latency on `/api/stops/nearest` if PostGIS is in the hot path | acceptable | unacceptable |
| Cost of HTTPS handshakes alone | invisible | dominant |

The HTTPS-webhook pattern crashes through three of those walls before we reach 5,000 vehicles. We need a substrate that:

1. Sustains tens of thousands of long-lived device connections without rebuilding TLS every 10 seconds.
2. Decouples ingest from analytics so a slow query never blocks a write.
3. Keeps writes ordered per device (so trip stitching works).
4. Stores telemetry in a database that doesn't slow down as the table grows to billions of rows.

## Decision

Adopt the **MQTT + Kafka + TimescaleDB** stack as documented in §2–3 of the architecture guide.

**Ingest tier — MQTT broker (EMQX OSS).** Devices speak MQTT over TLS to a horizontally-scaled EMQX cluster. Keep-alive is 60–120 s, well below cellular NAT timeouts but high enough that idle bandwidth is negligible. QoS 0 for periodic pings, QoS 1 for critical events (ignition, geofence, panic).

**Wire format — Protocol Buffers.** Defined in `schemas/telematics.proto`. The 80% bandwidth saving from §2 is real-money saving at this scale and reduces packet fragmentation on flaky cellular.

**Streaming tier — Apache Kafka (or Redpanda).** Single buffer between MQTT and storage. Topic `vehicles.positions` partitioned by `vehicle_id` so all telemetry for a single bus stays in order. Retention 7 days, room to replay any incident.

**Hot path — Redis Geo.** Every accepted position writes to `GEO:vehicles:<operator>` for sub-millisecond nearest-vehicle lookups. Replaces PostGIS for the live-map query path.

**Cold path — TimescaleDB.** `vehicle_positions` becomes a hypertable with 7-day chunks. Continuous aggregates do the 1-minute and 5-minute rollups so analytics never scans raw data. Native compression after 7 days delivers ~10× shrink.

**Legacy path — kept indefinitely.** `/api/traccar/position` HTTPS webhook stays. Some operators will keep that pattern for low-vehicle-count partner integrations; the MQTT path doesn't replace it, it adds capacity above it.

## Consequences

### Positive

- Linear scale to 100k vehicles using the EMQX OSS edition (free) and Redpanda Community (free).
- Bandwidth bill drops by ~80% vs JSON-over-HTTPS once devices switch to Protobuf.
- TimescaleDB native compression keeps the hot OLTP working set small.
- Per-device ordering preserved by partition key.
- Hot reads (nearest, live-map) move off the database entirely.

### Negative

- Two new persistent services (MQTT broker + Kafka) increase operational surface area. We accept this at the 5,000-vehicle threshold, not before.
- Protobuf is harder to inspect by eye than JSON. We add a `/api/debug/decode` (admin-only, rate-limited) helper to render any Protobuf payload back to JSON for support.
- Migration window — devices must dual-encode (HTTPS + MQTT) during cutover. The bridge endpoint in `api/routers/mqtt_ingest.py` accepts Protobuf-over-HTTP so the format can land before the broker does.
- We lose Supabase's auto-generated PostgREST endpoints for the telemetry table once it becomes a hypertable. Routes that need raw telemetry must query through our own FastAPI handlers.

## Triggers — when do we actually deploy this?

The current pilot scale doesn't warrant the operational complexity. We deploy each layer at a defined trigger:

| Layer | Trigger to deploy |
|---|---|
| Protobuf-over-HTTP bridge (`/api/v1/telemetry/protobuf`) | **immediately** — it's a small endpoint, no new infrastructure |
| TimescaleDB hypertable | **at 1,000 vehicles** sustained or 100M-row position table |
| EMQX broker cluster | **at 5,000 sustained device connections** |
| Kafka / Redpanda buffer | **when ingest p95 latency exceeds 50 ms** at any rate, or when the consumer needs to fan out to a second downstream sink |
| Redis Geo cache | **immediately** — already a near-free win for live-map queries |

These thresholds are far above today's 24-vehicle pilot, but we lay the foundation now so the migration is a switch, not a rewrite.

## Alternatives considered

- **CoAP over UDP** (LWM2M). Considered. Rejected because firmware support for MQTT is mature on the SIM900A and successors; CoAP would need bespoke parsing.
- **gRPC streaming.** Rejected — gRPC requires HTTP/2, which is fragile on flaky cellular and uncommon on legacy modems.
- **Direct device → Kafka via REST proxy.** Considered. Rejected because we still need to terminate millions of TLS connections somewhere; that's exactly what MQTT brokers are good at.
- **ClickHouse over TimescaleDB.** Reserved for §S4 if rollups become CPU-bound at 100k scale. TimescaleDB wins on operational familiarity (we already use Postgres) and on the SQL-join story with our business metadata tables.

## Follow-up

- ADR-005 will cover the broker high-availability topology (single-zone vs multi-zone EMQX cluster).
- ADR-006 will cover the firmware OTA-update strategy once the reference firmware in `firmware/sim900a-reference/` is real code.
