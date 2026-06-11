# Postgres connection pooling — tuning for 500 vehicles

> Step 83 of the roadmap. Updated 2026-05-24. Covers the Supavisor (Supabase) pooler, the FastAPI httpx client, and the math behind the numbers.

## What we're solving

A serverless deployment opens a fresh connection on every cold-start. At 500 vehicles each posting a position every 5 seconds plus passenger reads, we'd see roughly **2 600 PostgREST requests / minute** at peak. Without pooling, Postgres exhausts `max_connections` (Supabase free-tier limit is **60**) in seconds and rejects with `53300: too_many_connections`.

The Supabase **Supavisor** transaction pooler sits in front of Postgres and gives us up to **10 000 client connections** multiplexed onto the 60 server connections. That's the only way our shape works.

## Connection string

Use the **transaction-mode pooler URL**:

```
postgres://<user>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?pgbouncer=true&connection_limit=1
```

Key points:

- Port **6543** (transaction mode), **not** 5432 (session).
- `pgbouncer=true` tells client libraries not to negotiate prepared statements (transaction-mode poolers don't preserve session state).
- `connection_limit=1` per serverless invocation — Vercel will spin up many independent functions, each holding exactly one connection.

`SUPABASE_URL` (used by httpx → PostgREST) stays at the project's standard `https://<id>.supabase.co` host. The pooler URL is only for direct Postgres clients (psql, pg_dump, backup workflows).

## httpx client settings

`api/core/database.py` creates an `AsyncClient` per request. Tuning:

```python
httpx.AsyncClient(
    timeout=httpx.Timeout(
        connect=2.0,
        read=8.0,
        write=4.0,
        pool=1.0,
    ),
    limits=httpx.Limits(
        max_connections=20,         # per worker process
        max_keepalive_connections=10,
        keepalive_expiry=20.0,
    ),
    transport=httpx.AsyncHTTPTransport(retries=1),
)
```

These values target the gunicorn 4-worker × Vercel 10-instance scaling envelope — a worst-case of ~800 in-flight outbound requests, well under the pooler's 10 000 ceiling.

## Server-side Postgres tuning

In the Supabase dashboard → Database → Configuration:

| Setting | Free-tier ceiling | Recommended |
|---|---|---|
| `max_connections` | 60 | leave |
| `shared_buffers` | dyn | leave (managed) |
| `work_mem` | 4 MB | leave |
| `effective_cache_size` | dyn | leave |
| `statement_timeout` | 0 | **5 s** for the API user, **0** for the service user |
| `idle_in_transaction_session_timeout` | 0 | **10 s** for the API user |

The two timeouts are added because, under load, a wedged transaction will pile up against the 60-connection ceiling and produce the same `too_many_connections` failure even with the pooler.

Apply via SQL editor (run once):

```sql
ALTER ROLE authenticator SET statement_timeout = '5s';
ALTER ROLE authenticator SET idle_in_transaction_session_timeout = '10s';
-- service role keeps unbounded timeouts for backups + migrations
```

## Indexing for the hot paths

The two queries that drive 80% of read load:

```sql
-- Live positions for a route
SELECT *
FROM   vehicle_positions_latest
WHERE  operator_id = $1
AND    route_id    = $2;

-- Nearest stops within 1.5 km
SELECT id, name, geometry,
       ST_Distance(geometry::geography, ST_MakePoint($1, $2)::geography) AS d
FROM   stops
WHERE  operator_id = $3
ORDER  BY geometry <-> ST_MakePoint($1, $2)
LIMIT  10;
```

Required indexes (already in `db/schema.sql`, double-check after restores):

```sql
CREATE INDEX IF NOT EXISTS ix_vpl_op_route
    ON vehicle_positions_latest (operator_id, route_id);

CREATE INDEX IF NOT EXISTS ix_stops_op
    ON stops (operator_id);

CREATE INDEX IF NOT EXISTS ix_stops_geom
    ON stops USING gist (geometry);
```

The GiST index drops nearest-stop latency from ~80 ms (sequential scan) to ~3 ms at the 500-stop scale we're seeing in production.

## Observability

If you start seeing `too_many_connections` again, check in order:

1. **Pooler hit rate** — Supabase dashboard → Database → Pooler. Active client connections vs. the ceiling.
2. **Long-running transactions** — `SELECT pid, query, state, age(now(), xact_start) AS age FROM pg_stat_activity WHERE state <> 'idle' ORDER BY age DESC LIMIT 10;`
3. **httpx pool exhaustion** — Sentry breadcrumb tags `httpx.pool_exhausted=True`.
4. **/api/health/deep** — the deep healthcheck does a trivial read; a 5xx here means the pool is wedged.

## Capacity headroom

At 500 vehicles + 2 000 daily active passengers:

| Metric | Estimated peak | Budget |
|---|---|---|
| Outbound httpx requests / min | 2 600 | 8 000 |
| Pooler client connections | ~200 | 10 000 |
| Server Postgres connections | ~40 | 60 |
| Query p95 latency | 25 ms | 100 ms |

The headroom comfortably covers a 4× growth before the next tuning round is needed. The next bottleneck after that is `max_connections=60`, which requires the **Supabase Pro plan** ($25/month) to lift to 200.
