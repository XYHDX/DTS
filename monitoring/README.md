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

## Production notes

- Replace mosquitto with **EMQX/HiveMQ** + per-device **X.509 certificates** (see `firmware/SPEC.md`, ADR-005).
- Add **Loki** for logs and **Tempo** for traces to complete the observability stack.
- The Redis Geo p99 and TimescaleDB chunk-size panels are added once **S3.4 / S4** land.
