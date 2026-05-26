#!/usr/bin/env bash
# =============================================================================
# Damascus Transit System — Supabase Migration to Frankfurt (eu-central-1)
# =============================================================================
# Context: Current project (usxcuocnvfeltcdcnqoy) runs in us-east-1,
# adding 80-120ms latency for Damascus/Middle-East users.
# This script migrates to a new Frankfurt project.
#
# Prerequisites:
#   1. Create a new Supabase project in Frankfurt (eu-central-1) via dashboard
#   2. Set the four NEW_* variables below from the new project's Settings > API
#   3. Run this script: bash db/migrate_to_frankfurt.sh
#
# What this script does:
#   1. Enables PostGIS on the new Frankfurt project
#   2. Applies db/schema.sql (15 tables + functions + RLS)
#   3. Applies db/seed.sql (8 routes, 42 stops, 24 vehicles, users, etc.)
#   4. Updates Vercel environment variables to point to Frankfurt
#   5. Triggers a Vercel redeployment
# =============================================================================

set -euo pipefail

# ── FILL THESE IN after creating the new Frankfurt project ────────────────────
NEW_SUPABASE_URL=""          # e.g. https://abcdefghijklmnop.supabase.co
NEW_SUPABASE_ANON_KEY=""     # Settings > API > anon public
NEW_SUPABASE_SERVICE_KEY=""  # Settings > API > service_role (secret!)
NEW_SUPABASE_JWT_SECRET=""   # Settings > API > JWT Secret
# ─────────────────────────────────────────────────────────────────────────────

VERCEL_TOKEN="${VERCEL_TOKEN:?VERCEL_TOKEN env var required}"
VERCEL_PROJECT_ID="prj_YhiCddRpAglbm40Nhpe8IOxATZbT"
PSQL="$(brew --prefix 2>/dev/null)/opt/libpq/bin/psql"

# Validate inputs
if [[ -z "$NEW_SUPABASE_URL" || -z "$NEW_SUPABASE_SERVICE_KEY" ]]; then
  echo "ERROR: Set NEW_SUPABASE_URL, NEW_SUPABASE_ANON_KEY, NEW_SUPABASE_SERVICE_KEY, and NEW_SUPABASE_JWT_SECRET at the top of this script."
  exit 1
fi

NEW_PROJECT_REF=$(echo "$NEW_SUPABASE_URL" | sed 's|https://||' | cut -d'.' -f1)
echo "→ Target Frankfurt project ref: $NEW_PROJECT_REF"

# ── Step 1: Enable PostGIS ────────────────────────────────────────────────────
echo "Step 1: Enabling PostGIS on Frankfurt project..."
curl -s -X POST "${NEW_SUPABASE_URL}/rest/v1/rpc/query" \
  -H "Authorization: Bearer $NEW_SUPABASE_SERVICE_KEY" \
  -H "apikey: $NEW_SUPABASE_SERVICE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "CREATE EXTENSION IF NOT EXISTS postgis; CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"}' \
  2>/dev/null || true

# Alternative: use SQL Editor API
echo "  (If PostGIS isn't enabled, run in SQL Editor: CREATE EXTENSION IF NOT EXISTS postgis;)"

# ── Step 2 & 3: Apply schema and seed via REST ────────────────────────────────
echo ""
echo "Step 2: Applying schema.sql via Supabase SQL API..."
SCHEMA_SQL=$(cat "$(dirname "$0")/schema.sql")
curl -s -X POST "${NEW_SUPABASE_URL}/rest/v1/rpc/exec_sql" \
  -H "Authorization: Bearer $NEW_SUPABASE_SERVICE_KEY" \
  -H "apikey: $NEW_SUPABASE_SERVICE_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"sql\": $(echo "$SCHEMA_SQL" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')}" \
  2>/dev/null || echo "  → Apply schema.sql manually in Supabase SQL Editor"

echo ""
echo "Step 3: Applying seed.sql via Supabase SQL API..."
SEED_SQL=$(cat "$(dirname "$0")/seed.sql")
curl -s -X POST "${NEW_SUPABASE_URL}/rest/v1/rpc/exec_sql" \
  -H "Authorization: Bearer $NEW_SUPABASE_SERVICE_KEY" \
  -H "apikey: $NEW_SUPABASE_SERVICE_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"sql\": $(echo "$SEED_SQL" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')}" \
  2>/dev/null || echo "  → Apply seed.sql manually in Supabase SQL Editor"

# Enable realtime
echo ""
echo "Enabling Realtime on vehicle_positions_latest and alerts..."
curl -s -X POST "${NEW_SUPABASE_URL}/rest/v1/rpc/exec_sql" \
  -H "Authorization: Bearer $NEW_SUPABASE_SERVICE_KEY" \
  -H "apikey: $NEW_SUPABASE_SERVICE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"sql": "ALTER PUBLICATION supabase_realtime ADD TABLE vehicle_positions_latest; ALTER PUBLICATION supabase_realtime ADD TABLE alerts;"}' \
  2>/dev/null || true

# ── Step 4: Update Vercel environment variables ───────────────────────────────
echo ""
echo "Step 4: Updating Vercel environment variables..."

update_vercel_env() {
  local KEY="$1"
  local VALUE="$2"
  local ENV_ID
  # Find existing env var ID
  ENV_ID=$(curl -s "https://api.vercel.com/v9/projects/${VERCEL_PROJECT_ID}/env" \
    -H "Authorization: Bearer $VERCEL_TOKEN" | \
    python3 -c "import sys,json; data=json.load(sys.stdin); envs=[e for e in data.get('envs',[]) if e['key']=='${KEY}']; print(envs[0]['id'] if envs else '')" 2>/dev/null)

  if [[ -n "$ENV_ID" ]]; then
    # Update existing
    curl -s -X PATCH "https://api.vercel.com/v9/projects/${VERCEL_PROJECT_ID}/env/${ENV_ID}" \
      -H "Authorization: Bearer $VERCEL_TOKEN" \
      -H "Content-Type: application/json" \
      -d "{\"value\": \"${VALUE}\", \"type\": \"encrypted\", \"target\": [\"production\", \"preview\", \"development\"]}" \
      -o /dev/null -w "  Updated $KEY: HTTP %{http_code}\n"
  else
    # Create new
    curl -s -X POST "https://api.vercel.com/v9/projects/${VERCEL_PROJECT_ID}/env" \
      -H "Authorization: Bearer $VERCEL_TOKEN" \
      -H "Content-Type: application/json" \
      -d "{\"key\": \"${KEY}\", \"value\": \"${VALUE}\", \"type\": \"encrypted\", \"target\": [\"production\", \"preview\", \"development\"]}" \
      -o /dev/null -w "  Created $KEY: HTTP %{http_code}\n"
  fi
}

# Use Frankfurt pooler URL for SUPABASE_URL (for 500+ vehicle scale)
FRANKFURT_POOLER_URL="https://aws-0-eu-central-1.pooler.supabase.com"
update_vercel_env "SUPABASE_URL" "$FRANKFURT_POOLER_URL"
update_vercel_env "SUPABASE_KEY" "$NEW_SUPABASE_ANON_KEY"
update_vercel_env "SUPABASE_ANON_KEY" "$NEW_SUPABASE_ANON_KEY"
update_vercel_env "SUPABASE_SERVICE_KEY" "$NEW_SUPABASE_SERVICE_KEY"
update_vercel_env "SUPABASE_SERVICE_ROLE_KEY" "$NEW_SUPABASE_SERVICE_KEY"
update_vercel_env "JWT_SECRET" "$NEW_SUPABASE_JWT_SECRET"
update_vercel_env "SUPABASE_JWT_SECRET" "$NEW_SUPABASE_JWT_SECRET"

echo ""
echo "Step 4 complete: Vercel env vars updated."

# ── Step 5: Trigger Vercel redeployment ───────────────────────────────────────
echo ""
echo "Step 5: Triggering Vercel redeployment..."
LATEST_DEPLOY=$(curl -s "https://api.vercel.com/v6/deployments?projectId=${VERCEL_PROJECT_ID}&limit=1" \
  -H "Authorization: Bearer $VERCEL_TOKEN" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); deps=d.get('deployments',[]); print(deps[0]['uid'] if deps else '')" 2>/dev/null)

if [[ -n "$LATEST_DEPLOY" ]]; then
  curl -s -X POST "https://api.vercel.com/v13/deployments" \
    -H "Authorization: Bearer $VERCEL_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"syrian-transit-system\", \"source\": \"api\", \"deploymentId\": \"${LATEST_DEPLOY}\"}" \
    -o /dev/null -w "  Triggered redeploy: HTTP %{http_code}\n" || true
fi

echo ""
echo "============================================================"
echo "Migration complete!"
echo ""
echo "MANUAL STEPS STILL REQUIRED in Supabase Dashboard:"
echo "  1. Enable PostGIS: SQL Editor → CREATE EXTENSION IF NOT EXISTS postgis;"
echo "  2. Apply schema.sql via SQL Editor (if API call above failed)"
echo "  3. Apply seed.sql via SQL Editor (if API call above failed)"
echo "  4. Enable Connection Pooling (Supavisor) in Settings → Database"
echo "  5. Enable Realtime: Settings → Replication → supabase_realtime"
echo ""
echo "VERIFY deployment:"
echo "  curl https://syrian-transit-system.vercel.app/api/health"
echo "  curl https://syrian-transit-system.vercel.app/api/routes | python3 -m json.tool | head -20"
echo ""
echo "OLD project (us-east-1) ref: usxcuocnvfeltcdcnqoy"
echo "NEW project (eu-central-1) ref: $NEW_PROJECT_REF"
echo "============================================================"
