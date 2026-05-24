#!/usr/bin/env bash
# gtfs_export.sh — build a fresh GTFS static feed and upload to Supabase Storage.
#
# Intended as a Vercel cron job or a host-side cron. Idempotent.
#
# Requires env:
#   API_BASE             — origin of the running FastAPI (e.g. https://syrian-transit-system.vercel.app)
#   SUPABASE_URL         — the bucket host
#   SUPABASE_SERVICE_KEY — write access to the `gtfs/` bucket
#
# Output layout uploaded to the bucket:
#   gtfs/static/latest.zip                   # rolling pointer
#   gtfs/static/YYYY-MM-DD.zip               # daily archive
#   gtfs/static/checksums.sha256

set -euo pipefail

: "${API_BASE:?API_BASE is required}"
: "${SUPABASE_URL:?SUPABASE_URL is required}"
: "${SUPABASE_SERVICE_KEY:?SUPABASE_SERVICE_KEY is required}"

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

DATE_STAMP="$(date -u +%Y-%m-%d)"
ARCHIVE="${WORKDIR}/${DATE_STAMP}.zip"

echo "==> Pulling fresh GTFS static from ${API_BASE}/api/gtfs …"
curl --fail --silent --show-error \
     --header 'Accept: application/zip' \
     --output "$ARCHIVE" \
     "${API_BASE}/api/gtfs"

SIZE=$(stat -c %s "$ARCHIVE" 2>/dev/null || stat -f %z "$ARCHIVE")
if (( SIZE < 1024 )); then
  echo "FATAL: downloaded GTFS archive is suspiciously small (${SIZE} bytes)" >&2
  exit 1
fi

CHECKSUM=$(sha256sum "$ARCHIVE" | awk '{print $1}')
echo "==> Archive size: ${SIZE} bytes  sha256=${CHECKSUM}"

# Upload daily snapshot
echo "==> Uploading daily snapshot…"
curl --fail --silent --show-error \
     --request POST \
     --header "Authorization: Bearer ${SUPABASE_SERVICE_KEY}" \
     --header 'Content-Type: application/zip' \
     --header "x-upsert: true" \
     --data-binary "@${ARCHIVE}" \
     "${SUPABASE_URL}/storage/v1/object/gtfs/static/${DATE_STAMP}.zip" \
   > /dev/null

# Update rolling pointer
echo "==> Updating rolling 'latest.zip' pointer…"
curl --fail --silent --show-error \
     --request POST \
     --header "Authorization: Bearer ${SUPABASE_SERVICE_KEY}" \
     --header 'Content-Type: application/zip' \
     --header "x-upsert: true" \
     --data-binary "@${ARCHIVE}" \
     "${SUPABASE_URL}/storage/v1/object/gtfs/static/latest.zip" \
   > /dev/null

# Maintain checksum log so partners can verify integrity
echo "==> Appending checksum log…"
CHECK_LINE="${DATE_STAMP}  ${CHECKSUM}  ${SIZE}"
echo "$CHECK_LINE" > "${WORKDIR}/append.txt"
# Best-effort: download → append → upload.
curl --silent --show-error \
     --header "Authorization: Bearer ${SUPABASE_SERVICE_KEY}" \
     --output "${WORKDIR}/checksums.sha256" \
     "${SUPABASE_URL}/storage/v1/object/gtfs/static/checksums.sha256" || true
cat "${WORKDIR}/append.txt" >> "${WORKDIR}/checksums.sha256"

curl --fail --silent --show-error \
     --request POST \
     --header "Authorization: Bearer ${SUPABASE_SERVICE_KEY}" \
     --header 'Content-Type: text/plain' \
     --header "x-upsert: true" \
     --data-binary "@${WORKDIR}/checksums.sha256" \
     "${SUPABASE_URL}/storage/v1/object/gtfs/static/checksums.sha256" \
   > /dev/null

echo "==> Done. ${DATE_STAMP}.zip + latest.zip + checksums.sha256 uploaded."
