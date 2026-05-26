#!/usr/bin/env bash
# setup-ssl.sh — Generate SSL certificates for the Ministry self-hosted deployment.
# Run once before starting the production stack.
#
# Usage:
#   bash scripts/setup-ssl.sh                    # self-signed (dev/staging)
#   bash scripts/setup-ssl.sh --domain mot.gov.sy  # Let's Encrypt (production)
set -euo pipefail

SSL_DIR="$(dirname "$0")/../nginx/ssl"
mkdir -p "$SSL_DIR"

DOMAIN="${1:-}"
if [[ "$DOMAIN" == "--domain" ]]; then
  DOMAIN="${2:-}"
fi

if [[ -n "$DOMAIN" ]]; then
  # ── Let's Encrypt via certbot ──────────────────────────────────────────────
  echo "Requesting Let's Encrypt certificate for $DOMAIN ..."
  command -v certbot >/dev/null 2>&1 || { echo "certbot not found. Install it first: apt install certbot"; exit 1; }
  certbot certonly --standalone -d "$DOMAIN" --agree-tos --non-interactive \
    --email admin@"$DOMAIN"
  ln -sf /etc/letsencrypt/live/"$DOMAIN"/fullchain.pem "$SSL_DIR/cert.pem"
  ln -sf /etc/letsencrypt/live/"$DOMAIN"/privkey.pem  "$SSL_DIR/key.pem"
  echo "Certificate linked to $SSL_DIR/"
else
  # ── Self-signed fallback ───────────────────────────────────────────────────
  echo "No domain provided — generating self-signed certificate (not for production use)."
  openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$SSL_DIR/key.pem" \
    -out    "$SSL_DIR/cert.pem" \
    -subj "/C=SY/ST=Damascus/L=Damascus/O=Ministry of Transport/CN=transit.local"
  echo "Self-signed certificate written to $SSL_DIR/"
fi

chmod 600 "$SSL_DIR/key.pem"
echo "SSL setup complete."
