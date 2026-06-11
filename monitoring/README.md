# Monitoring & MQTT dev stack

Opt-in stack for **Phase S2.2** (MQTT broker + consumer) and **Phase S7.2** (Prometheus + Grafana).
It is **additive** — it does not touch `docker-compose.prod.yml` or the live deployment.

```
monitoring/
├── mosquitto/mosquitto.conf              # dev MQTT broker (anonymous; TLS+certs in prod)
├── prometheus/prometheus.yml             # scrapes the API /metrics
└── grafana/
    ├── provisioning/datasources/         # Prometheus datasource (auto)
    ├── provisioning/dashboards/          # dashboard loader (auto)
    └── dashboards/dam-overview.json      # "API Overview" starter dashboard
```

## Run

```bash
docker compose -f docker-compose.scale.yml up -d
```

| Service | URL | Notes |
|---|---|---|
| Grafana | http://localhost:3001 | `admin` / `admin` — change on first login |
| Prometheus | http://localhost:9090 | |
| Mosquitto | `localhost:1883` (TCP), `localhost:9001` (WS) | |
| Redis | `redis://localhost:6379/0` | pub/sub backend for the live bus (S3.4) |

## Enable API metrics

The API only exposes `/metrics` when `METRICS_ENABLED=true` (kept off on Vercel/serverless):

```bash
METRICS_ENABLED=true uvicorn api.index:app --port 8000
```

Prometheus scrapes `host.docker.internal:8000` by default — change the target to `api:8000` in
`prometheus/prometheus.yml` if you attach the API container to the `scale` network.

## Test MQTT ingestion

```bash
pip install aiomqtt
python scripts/mqtt_sim_publish.py --vehicles 10 --interval 5   # terminal 1 (publisher)
python -m api.workers.mqtt_consumer                              # terminal 2 (consumer)
```

The consumer subscribes to `vehicles/+/status` and `vehicles/+/event` and feeds frames into the
same `_ingest` pipeline as the HTTP bridge (`api/routers/mqtt_ingest.py`).

## Live position bus — `/api/stream` without per-client polling (S3.4)

By default `/api/stream` polls Supabase every 2 s **per connected client** and the work is pinned to
the process holding the socket — so it can't scale past one web process without sticky sessions.
Point the API at the bundled Redis and the ingest path publishes each update once; every web process
just relays it. One snapshot query per *connection*, then pure push:

```bash
# Redis comes up with the scale stack; run the API against it:
REDIS_PUBSUB_URL=redis://localhost:6379/0 uvicorn api.index:app --port 8000

# Drive some traffic and watch /api/stream update with no DB poll:
python scripts/mqtt_sim_publish.py --vehicles 10 --interval 2   # publisher
python -m api.workers.mqtt_consumer                              # consumer (publishes to the bus)
curl -N http://localhost:8000/api/stream                         # subscriber
```

With **no** `REDIS_PUBSUB_URL` set the endpoint keeps its legacy poll path unchanged (this is how
Vercel runs). `LIVE_BUS_BACKEND=memory` gives single-process fan-out for a one-box deployment with no
Redis. See `api/core/live_bus.py`.

## Production notes

- Replace mosquitto with **EMQX/HiveMQ** + per-device **X.509 certificates** (see `firmware/SPEC.md`, ADR-005).
- Add **Loki** for logs and **Tempo** for traces to complete the observability stack.
- The Redis Geo p99 and TimescaleDB chunk-size panels are added once **S3.4 / S4** land.
