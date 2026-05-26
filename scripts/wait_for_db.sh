#!/usr/bin/env bash
# wait_for_db.sh — block until Supabase / Postgres is reachable.
#
# Usage:
#   ./scripts/wait_for_db.sh                           # uses $SUPABASE_DB_URL
#   ./scripts/wait_for_db.sh postgres://user:pass@h:5432/db
#   TIMEOUT=60 ./scripts/wait_for_db.sh
#
# Designed for docker-compose entrypoints where the API container has to
# wait for Postgres before gunicorn starts. Exits 0 on success, 1 on timeout.

set -euo pipefail

URL="${1:-${SUPABASE_DB_URL:-}}"
TIMEOUT="${TIMEOUT:-30}"
INTERVAL="${INTERVAL:-1}"

if [[ -z "$URL" ]]; then
  echo "wait_for_db: SUPABASE_DB_URL not set and no arg supplied" >&2
  exit 2
fi

# Strip scheme + extract host/port for a TCP probe before doing the real query.
# This is more portable than relying on psql being available in every image.
HOST=$(echo "$URL" | sed -E 's|^[a-z]+://([^:@/]+@)?([^:/]+).*|\2|')
PORT=$(echo "$URL" | sed -nE 's|^[a-z]+://([^:@/]+@)?[^:/]+:([0-9]+).*|\2|p')
PORT="${PORT:-5432}"

echo "wait_for_db: waiting for ${HOST}:${PORT} (timeout=${TIMEOUT}s)…"
deadline=$(( $(date +%s) + TIMEOUT ))

while true; do
  if (echo > "/dev/tcp/${HOST}/${PORT}") 2>/dev/null; then
    echo "wait_for_db: tcp open on ${HOST}:${PORT}"
    break
  fi
  if (( $(date +%s) >= deadline )); then
    echo "wait_for_db: timeout after ${TIMEOUT}s — ${HOST}:${PORT} unreachable" >&2
    exit 1
  fi
  sleep "$INTERVAL"
done

# Optional second-phase check: actually execute a query when psql is present.
if command -v psql >/dev/null 2>&1; then
  echo "wait_for_db: tcp open — attempting trivial query…"
  if ! psql "$URL" -tAc 'SELECT 1' >/dev/null 2>&1; then
    echo "wait_for_db: tcp open but psql trivial query failed" >&2
    exit 1
  fi
  echo "wait_for_db: query OK — ready."
else
  echo "wait_for_db: psql not present, skipping query phase."
fi

exit 0
