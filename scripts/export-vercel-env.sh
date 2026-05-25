#!/usr/bin/env bash
# DamascusTransit — Export Vercel Environment Variable Names
# Exports the list of configured env var names (NOT their values) for auditing.
# To export values, use the Vercel dashboard: Settings → Environment Variables → Export.
#
# Usage: VERCEL_TOKEN=xxx ./scripts/export-vercel-env.sh
set -euo pipefail

: "${VERCEL_TOKEN:?VERCEL_TOKEN must be set}"

OUTPUT_FILE="vercel-env-manifest-$(date -u +%Y-%m-%d).json"

echo "Fetching Vercel project deployments and env manifest..."

# List recent deployments (last 10)
vercel ls --token "$VERCEL_TOKEN" --yes 2>/dev/null | head -15 || true

# Export env var names via Vercel API
# (values are not exported — use dashboard for sensitive value recovery)
curl -sf \
  -H "Authorization: Bearer $VERCEL_TOKEN" \
  "https://api.vercel.com/v9/projects/${VERCEL_PROJECT_ID:-damascus-transit}/env?teamId=${VERCEL_ORG_ID:-}" \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
envs = data.get('envs', [])
manifest = [{'key': e['key'], 'target': e.get('target', []), 'type': e.get('type', 'plain')} for e in envs]
print(json.dumps(manifest, indent=2))
" > "$OUTPUT_FILE" 2>/dev/null || {
  echo "WARN: Could not fetch env vars via API. Check VERCEL_TOKEN and VERCEL_PROJECT_ID."
  echo "Manual recovery: Vercel dashboard → Settings → Environment Variables"
}

if [ -f "$OUTPUT_FILE" ]; then
  echo "Env manifest written to: $OUTPUT_FILE"
  echo "Keys found: $(python3 -c "import json; d=json.load(open('$OUTPUT_FILE')); print(len(d))" 2>/dev/null || echo '?')"
fi
