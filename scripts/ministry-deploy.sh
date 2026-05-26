#!/usr/bin/env bash
# ministry-deploy.sh — Start / stop / update the Ministry self-hosted stack.
# Must be run from the TransitSystem project root.
set -euo pipefail

COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

require_env() {
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: $ENV_FILE not found. Copy .env.ministry.example to .env and fill in the values."
    exit 1
  fi
}

cmd="${1:-help}"

case "$cmd" in
  start)
    require_env
    log "Starting DamascusTransit production stack..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build
    log "Stack started. API health: http://localhost/api/health"
    ;;

  stop)
    log "Stopping stack..."
    docker compose -f "$COMPOSE_FILE" down
    ;;

  restart)
    require_env
    log "Restarting stack..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" restart
    ;;

  update)
    require_env
    log "Pulling latest images and rebuilding API..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" pull redis nginx
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build --remove-orphans
    log "Update complete."
    ;;

  logs)
    docker compose -f "$COMPOSE_FILE" logs -f --tail=100
    ;;

  status)
    docker compose -f "$COMPOSE_FILE" ps
    ;;

  health)
    curl -sf http://localhost/api/health | python3 -m json.tool
    ;;

  *)
    echo "Usage: $0 {start|stop|restart|update|logs|status|health}"
    echo
    echo "  start    — build and start the full stack"
    echo "  stop     — stop and remove containers"
    echo "  restart  — restart running containers"
    echo "  update   — pull new images and rebuild (zero-downtime rolling update)"
    echo "  logs     — follow all container logs"
    echo "  status   — show container health and port bindings"
    echo "  health   — call the API health endpoint"
    ;;
esac
