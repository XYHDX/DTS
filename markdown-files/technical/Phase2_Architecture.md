# Phase 2 Architecture Decision Record — 5,000 Vehicles

**Date:** 2026-03-30
**Author:** CTO Agent
**Status:** Proposed
**Context:** Scale Damascus Transit System from 500 to 5,000 vehicles

---

## Current State (Phase 1)

| Component | Technology | Limit |
|-----------|-----------|-------|
| Compute | Vercel Serverless (Python) | ~50 req/s, cold starts |
| Database | Supabase PostgreSQL + PostGIS | 500 vehicles (with Supavisor) |
| Cache | Upstash Redis | Basic key-value, rate limiting |
| Real-time | SSE via serverless functions | 25s Vercel timeout |
| Message Queue | None | N/A |

**Proven ceiling:** 500 concurrent vehicles at 10s update interval = 50 position writes/s, 100 Supabase calls/s.

**Phase 2 target:** 5,000 vehicles = 500 writes/s, sustained. Peak (morning rush): ~750 writes/s.

---

## Decision 1: Message Queue — NATS JetStream

### Options Evaluated

| Criteria | NATS JetStream | Apache Kafka |
|----------|---------------|--------------|
| Latency (p99) | <1ms | 5-15ms |
| Memory footprint | ~50 MB | ~1 GB+ (JVM) |
| Ops complexity | Single binary, zero config | ZooKeeper/KRaft, topic management |
| Throughput | 10M+ msg/s | 1M+ msg/s |
| Clustering | Built-in RAFT | Requires partition planning |
| Syria deployment | Runs on 1 vCPU ARM | Needs 4+ vCPU x86 |
| Cost (3 nodes) | ~$15/mo (small VMs) | ~$90/mo (medium VMs) |

### Decision: NATS JetStream

**Why:** For a transit system processing 500-750 msg/s, both are massively over-provisioned. NATS wins on:
- **Operational simplicity** — single Go binary, no JVM tuning, no ZooKeeper
- **Resource efficiency** — critical for on-premises K3s with limited hardware
- **Sub-millisecond latency** — matters for real-time vehicle tracking
- **Built-in key-value store** — can replace some Redis use cases

Kafka's strengths (massive throughput, ecosystem, exactly-once semantics) are not needed at this scale. If we ever reach 50,000+ vehicles, Kafka becomes the better choice.

### Architecture

```
Drivers/Traccar → NATS Subject: transit.positions.{vehicle_id}
                → Consumer Group: position-writer (→ TimescaleDB)
                → Consumer Group: cache-updater (→ Redis)
                → Consumer Group: alerter (→ geofence/speed checks)
                → Consumer Group: sse-broadcaster (→ SSE/WebSocket clients)
```

**Subjects:**
- `transit.positions.>` — GPS position updates (wildcard consumers)
- `transit.events.>` — Traccar events, driver trip actions
- `transit.alerts.>` — System-generated alerts (speed, geofence)
- `transit.commands.>` — Dispatcher-to-driver commands

**JetStream config:**
- Stream: `POSITIONS`, retention: 24h, max bytes: 5 GB
- Stream: `EVENTS`, retention: 7d, max bytes: 10 GB

---

## Decision 2: Time-Series Storage — TimescaleDB Hypertables

### Problem

`vehicle_positions` table grows at 500 rows/s × 86,400s/day = ~43M rows/day. Standard PostgreSQL:
- B-tree indexes degrade after ~100M rows
- `VACUUM` becomes expensive
- Partitioning requires manual management

### Decision: TimescaleDB on existing PostgreSQL

TimescaleDB is a PostgreSQL extension (not a separate database). It converts `vehicle_positions` into a hypertable partitioned by time.

**Why not a separate time-series DB (InfluxDB, QuestDB)?**
- TimescaleDB runs inside our existing PostgreSQL — no new infrastructure
- Full SQL compatibility — existing queries work unchanged
- PostGIS + TimescaleDB coexist on the same instance
- Continuous aggregates replace manual rollup jobs

### Schema Migration

```sql
-- Convert existing table to hypertable (one-time migration)
SELECT create_hypertable('vehicle_positions', 'recorded_at',
    chunk_time_interval => INTERVAL '1 hour',
    migrate_data => true
);

-- Continuous aggregate: 1-minute position summaries
CREATE MATERIALIZED VIEW vehicle_positions_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', recorded_at) AS bucket,
    vehicle_id,
    AVG(speed_kmh) AS avg_speed,
    MAX(speed_kmh) AS max_speed,
    last(location, recorded_at) AS last_location,
    last(heading, recorded_at) AS last_heading,
    COUNT(*) AS sample_count
FROM vehicle_positions
GROUP BY bucket, vehicle_id;

-- Retention policy: raw data for 30 days, aggregates forever
SELECT add_retention_policy('vehicle_positions', INTERVAL '30 days');
```

### Expected Impact

| Metric | PostgreSQL | TimescaleDB |
|--------|-----------|-------------|
| Insert throughput | ~800 rows/s | ~15,000 rows/s |
| Query last 1h (per vehicle) | 120ms | 8ms |
| Query last 24h aggregate | 3.2s | 45ms |
| Storage (30 days) | ~180 GB | ~60 GB (compression) |
| Index maintenance | Manual REINDEX | Automatic per-chunk |

---

## Decision 3: Redis Architecture — Tiered Caching

### Current State

Upstash Redis is used for basic caching and rate limiting. Phase 2 expands this to a proper caching tier.

### Decision: Keep Upstash for edge caching, add self-hosted Redis for hot path

| Layer | Technology | Purpose | TTL |
|-------|-----------|---------|-----|
| L1 (hot) | Self-hosted Redis 7 (K3s) | Latest positions, active trips | 30s |
| L2 (warm) | Upstash Redis (serverless) | Route/stop data, session cache | 5min |
| L3 (cold) | TimescaleDB | Historical positions | Permanent |

### Key Patterns

**Latest positions (L1):**
```
HSET vehicle:positions:{vehicle_id} lat 33.5138 lon 36.2765 speed 42 heading 180 ts 1711785600
```
- Written by NATS `cache-updater` consumer on every position update
- Read by SSE/WebSocket broadcaster and `GET /api/vehicles/positions`
- Single Redis HGETALL replaces a Supabase query

**Active trip state (L1):**
```
HSET trip:active:{vehicle_id} trip_id abc123 route_id R-001 started_at 1711780000 pax 12
```

**Geofence cache (L1):**
```
GEOADD geofences:zone 36.2765 33.5138 "damascus-center"
```
- Redis GEO commands for O(1) point-in-polygon checks against geofence zones
- Refreshed from PostgreSQL every 60s

### Sizing

5,000 vehicles × ~500 bytes per position hash = ~2.5 MB. Total Redis memory with all keys: <50 MB. A single 256 MB Redis instance is sufficient.

---

## Decision 4: Compute — K3s On-Premises Cluster

### Why On-Premises

1. **Latency** — Damascus ↔ nearest cloud (Frankfurt) = 80ms RTT. On-premises = <1ms.
2. **Cost** — 5,000 vehicles generating 500 req/s would cost ~$300/mo on Vercel Pro. On-premises hardware amortizes to ~$50/mo after 12 months.
3. **Sovereignty** — Syrian transit data stays in-country. No cross-border data transfer concerns.
4. **Reliability** — No dependency on international internet links for core operations.

### Why K3s (not full K8s)

- K3s is a CNCF-certified Kubernetes distribution in a single ~70 MB binary
- Designed for edge/IoT — runs on ARM and low-resource hardware
- Built-in Traefik ingress, CoreDNS, local-path storage
- Same kubectl/Helm ecosystem as full K8s

### Cluster Design

```
┌─────────────────────────────────────────────────┐
│                 K3s Cluster                      │
│                                                  │
│  Node 1 (Control + Worker)    Node 2 (Worker)   │
│  ┌──────────────┐            ┌──────────────┐   │
│  │ API Server   │            │ Transit API  │   │
│  │ Transit API  │            │ NATS Node 2  │   │
│  │ NATS Node 1  │            │ Redis        │   │
│  │ TimescaleDB  │            │ (replica)    │   │
│  │ (primary)    │            └──────────────┘   │
│  └──────────────┘                                │
│                                                  │
│  Node 3 (Worker)                                 │
│  ┌──────────────┐                                │
│  │ Transit API  │  ← Traefik load balances      │
│  │ NATS Node 3  │     across all API replicas    │
│  │ TimescaleDB  │                                │
│  │ (replica)    │                                │
│  └──────────────┘                                │
└─────────────────────────────────────────────────┘
         ↑                    ↑
    Traccar/GPS          Passenger/Admin
    devices              web clients
```

### Hardware Requirements (Minimum)

| Node | CPU | RAM | Storage | Est. Cost |
|------|-----|-----|---------|-----------|
| Node 1 (control) | 4 vCPU | 8 GB | 256 GB NVMe | $400 |
| Node 2 (worker) | 4 vCPU | 8 GB | 128 GB NVMe | $350 |
| Node 3 (worker) | 4 vCPU | 8 GB | 128 GB NVMe | $350 |
| **Total** | **12 vCPU** | **24 GB** | **512 GB** | **~$1,100** |

Can run on 3x Intel NUC, 3x Raspberry Pi 5 (8GB), or 3x refurbished mini PCs.

### Hybrid Mode (Transition Period)

During the transition from Vercel to K3s:

```
Internet traffic → Vercel (static frontend, API proxy)
                      ↓ (reverse proxy)
                   K3s Cluster (API, NATS, DB)
                      ↑
                   Traccar devices (direct)
```

- Vercel serves frontend assets and proxies API calls to the K3s cluster via Vercel Edge Functions
- Traccar devices connect directly to K3s (no Vercel hop)
- Fallback: if K3s is down, Vercel serves cached data from Upstash Redis

---

## Migration Plan

### Phase 2a (Weeks 1-4): Database Layer

1. Install TimescaleDB extension on Supabase (or migrate to self-hosted PostgreSQL with TimescaleDB)
2. Convert `vehicle_positions` to hypertable
3. Set up continuous aggregates and retention policies
4. Benchmark: confirm 500+ writes/s sustained

### Phase 2b (Weeks 5-8): Message Queue + Cache

1. Deploy NATS JetStream (3-node cluster on K3s)
2. Refactor `POST /api/driver/position` to publish to NATS instead of direct DB write
3. Build consumer workers: position-writer, cache-updater, alerter
4. Deploy self-hosted Redis on K3s for L1 cache
5. Benchmark: confirm end-to-end latency <50ms for position updates

### Phase 2c (Weeks 9-12): Compute Migration

1. Set up K3s cluster (3 nodes)
2. Containerize Transit API (already has Dockerfile)
3. Deploy 3 API replicas behind Traefik
4. Set up hybrid mode with Vercel frontend proxy
5. Load test: 5,000 simulated vehicles, confirm <100ms p95
6. Cut over DNS when stable

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Hardware failure (single node) | Medium | High | 3-node cluster, TimescaleDB replication, NATS RAFT |
| Power outage | Medium | Critical | UPS (30 min), graceful shutdown scripts |
| Internet link failure | Low | Medium | Core operations work offline; sync when restored |
| TimescaleDB migration data loss | Low | Critical | pg_dump backup before migration; test on staging first |
| NATS message loss | Low | Medium | JetStream persistence + acknowledgments |

---

## Cost Comparison

| | Phase 1 (Vercel + Supabase) | Phase 2 (K3s On-Prem) |
|-|----------------------------|----------------------|
| Compute | $20/mo (Vercel Pro) | $0 (owned hardware) |
| Database | $25/mo (Supabase Pro) | $0 (self-hosted) |
| Cache | $10/mo (Upstash) | $0 (self-hosted) + $10 (Upstash edge) |
| Hardware amortization | N/A | ~$90/mo (12-month) |
| Bandwidth | $0 (included) | ~$20/mo (ISP) |
| **Total** | **~$55/mo** | **~$120/mo** (drops to ~$30/mo after year 1) |

Phase 2 costs more initially but amortizes to less than Phase 1 while supporting 10x the capacity.

---

## Decision Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Message Queue | NATS JetStream | Low resource, sub-ms latency, simple ops |
| Time-Series | TimescaleDB (PG extension) | No new infra, full SQL, compression |
| Cache | Self-hosted Redis (L1) + Upstash (L2) | Hot path local, edge caching remote |
| Compute | K3s on-premises (3 nodes) | Latency, cost, sovereignty |

---

*This ADR should be reviewed by the CEO and board before implementation begins. Hardware procurement and ISP arrangements should start in parallel with Phase 2a database work.*
