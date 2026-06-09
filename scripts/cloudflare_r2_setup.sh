#!/usr/bin/env bash
# Provision Cloudflare R2 for ProofPack AI and write a local credentials file.
#
# Prerequisites:
#   - wrangler installed (`npm i -g wrangler` or use `npx wrangler`)
#   - `wrangler login` (OAuth) OR CLOUDFLARE_API_TOKEN with R2 permissions
#   - CLOUDFLARE_ACCOUNT_ID (dashboard → Overview → Account ID)
#
# Usage:
#   export CLOUDFLARE_ACCOUNT_ID=your_account_id
#   ./scripts/cloudflare_r2_setup.sh
#   # Create R2 API token in dashboard, fill .cloudflare-r2.env, then:
#   ./scripts/railway_apply_r2.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BUCKET_NAME="${R2_BUCKET_NAME:-proofpack}"
ENV_FILE="${ROOT}/.cloudflare-r2.env"
EXAMPLE="${ROOT}/.cloudflare-r2.env.example"

if ! command -v wrangler >/dev/null 2>&1; then
  echo "ERROR: wrangler not found. Install: npm i -g wrangler"
  exit 1
fi

# Resolve account ID: env > infra/cloudflare/wrangler.toml > wrangler whoami
ACCOUNT_ID="${CLOUDFLARE_ACCOUNT_ID:-}"
if [[ -z "$ACCOUNT_ID" && -f "$ROOT/infra/cloudflare/wrangler.toml" ]]; then
  ACCOUNT_ID="$(grep -E '^account_id\s*=' "$ROOT/infra/cloudflare/wrangler.toml" | sed -E 's/.*"([^"]+)".*/\1/' || true)"
  if [[ "$ACCOUNT_ID" == "" ]]; then
    ACCOUNT_ID=""
  fi
fi

if [[ -z "$ACCOUNT_ID" ]]; then
  echo "ERROR: Set CLOUDFLARE_ACCOUNT_ID (Cloudflare dashboard → Overview → Account ID)"
  echo "  export CLOUDFLARE_ACCOUNT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  exit 1
fi

export CLOUDFLARE_ACCOUNT_ID="$ACCOUNT_ID"

echo "==> Cloudflare account: $CLOUDFLARE_ACCOUNT_ID"
echo "==> Ensure R2 is enabled (dashboard → R2 → subscribe if prompted)"

echo "==> Create R2 bucket '$BUCKET_NAME' (skip if exists)"
if wrangler r2 bucket info "$BUCKET_NAME" >/dev/null 2>&1; then
  echo "Bucket '$BUCKET_NAME' already exists"
else
  wrangler r2 bucket create "$BUCKET_NAME"
  echo "Created bucket '$BUCKET_NAME'"
fi

ENDPOINT="https://${CLOUDFLARE_ACCOUNT_ID}.r2.cloudflarestorage.com"

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$EXAMPLE" "$ENV_FILE"
fi

# Patch non-secret fields; leave keys for user to paste from dashboard.
python3 <<PY
from pathlib import Path
import re

path = Path("$ENV_FILE")
text = path.read_text()
replacements = {
    "CLOUDFLARE_ACCOUNT_ID": "$CLOUDFLARE_ACCOUNT_ID",
    "S3_BUCKET": "$BUCKET_NAME",
    "S3_REGION": "auto",
    "S3_ENDPOINT_URL": "$ENDPOINT",
}
for key, val in replacements.items():
    if re.search(rf"^{key}=", text, re.M):
        text = re.sub(rf"^{key}=.*$", f"{key}={val}", text, flags=re.M)
    else:
        text += f"\n{key}={val}"
path.write_text(text)
print(f"Wrote {path}")
PY

echo ""
echo "==> Next: create an R2 S3 API token"
echo "    https://dash.cloudflare.com/?to=/:account/r2/overview"
echo "    → Manage (API Tokens) → Create → Object Read & Write → bucket '$BUCKET_NAME'"
echo ""
echo "    Copy Access Key ID + Secret Access Key into:"
echo "      $ENV_FILE"
echo ""
echo "    Then apply to Railway (API + worker):"
echo "      ./scripts/railway_apply_r2.sh"
echo ""
echo "    Local smoke test (optional):"
echo "      cd backend && python scripts/test_r2.py"
