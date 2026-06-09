#!/usr/bin/env bash
# Push Cloudflare R2 credentials from .cloudflare-r2.env to Railway API + worker.
#
# Prerequisites:
#   - railway CLI logged in and linked to proofpack-ai
#   - .cloudflare-r2.env filled (from cloudflare_r2_setup.sh + dashboard token)
#
# Usage:
#   ./scripts/railway_apply_r2.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ROOT}/.cloudflare-r2.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: Missing $ENV_FILE"
  echo "Run ./scripts/cloudflare_r2_setup.sh first, then add S3_ACCESS_KEY_ID / S3_SECRET_ACCESS_KEY"
  exit 1
fi

# shellcheck disable=SC1090
set -a
source "$ENV_FILE"
set +a

for var in S3_ENDPOINT_URL S3_BUCKET S3_ACCESS_KEY_ID S3_SECRET_ACCESS_KEY; do
  if [[ -z "${!var:-}" ]]; then
    echo "ERROR: $var is empty in $ENV_FILE"
    exit 1
  fi
done

S3_REGION="${S3_REGION:-auto}"

if ! command -v railway >/dev/null 2>&1; then
  echo "ERROR: railway CLI not found"
  exit 1
fi

echo "==> Railway account"
railway whoami

API_ID=$(railway service list --json | python3 -c "
import sys, json
svcs = json.load(sys.stdin)
print(next(s['id'] for s in svcs if s['name'] == 'proofpack-api'))
")
WORKER_ID=$(railway service list --json | python3 -c "
import sys, json
svcs = json.load(sys.stdin)
print(next(s['id'] for s in svcs if s['name'] == 'proofpack-worker'))
")

apply_vars() {
  local service_id="$1"
  local label="$2"
  echo "==> Set R2 vars on $label"
  railway variable set \
    "STORAGE_BACKEND=s3" \
    "S3_ENDPOINT_URL=${S3_ENDPOINT_URL}" \
    "S3_BUCKET=${S3_BUCKET}" \
    "S3_REGION=${S3_REGION}" \
    "S3_ACCESS_KEY_ID=${S3_ACCESS_KEY_ID}" \
    "S3_SECRET_ACCESS_KEY=${S3_SECRET_ACCESS_KEY}" \
    --service "$service_id"
}

apply_vars "$API_ID" "proofpack-api"
apply_vars "$WORKER_ID" "proofpack-worker"

echo ""
echo "==> Done. Railway will redeploy API + worker with Cloudflare R2."
echo "    Verify after deploy:"
echo "      curl https://proofpack-api-production-ed2f.up.railway.app/health"
echo "      python backend/scripts/smoke_test.py https://proofpack-api-production-ed2f.up.railway.app"
