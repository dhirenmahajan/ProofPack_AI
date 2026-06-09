#!/usr/bin/env bash
# Full end-to-end verification: local API, eval harness, R2, production.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

LOCAL_URL="${LOCAL_URL:-http://localhost:8000}"
PROD_URL="${PROD_URL:-https://proofpack-api-production-ed2f.up.railway.app}"
FAIL=0

pass() { echo "✓ $1"; }
fail() { echo "✗ $1"; FAIL=1; }

echo "=== ProofPack E2E workflow ==="
echo "worktree: $(pwd)"
echo "branch:   $(git branch --show-current)"
echo ""

echo "--- 1/5 Health + providers (local) ---"
if curl -sf "$LOCAL_URL/health" >/dev/null; then
  pass "local /health"
  curl -s "$LOCAL_URL/providers" | python3 -c "import sys,json; d=json.load(sys.stdin); print('  providers:', d)"
else
  fail "local API not reachable at $LOCAL_URL (run: docker compose up --build -d)"
fi

echo ""
echo "--- 2/5 Smoke test (local) ---"
if (cd backend && python scripts/smoke_test.py "$LOCAL_URL"); then
  pass "local smoke_test"
else
  fail "local smoke_test"
fi

echo ""
echo "--- 3/5 Eval harness (local, gated subset) ---"
if (cd backend && python -m evals.run_evals --base-url "$LOCAL_URL"); then
  pass "local evals gate"
else
  fail "local evals gate"
fi

echo ""
echo "--- 4/5 R2 object store ---"
if [[ -f "$ROOT/.cloudflare-r2.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.cloudflare-r2.env"
  set +a
  export STORAGE_BACKEND=s3
  if (cd backend && python scripts/test_r2.py 2>/dev/null); then
    pass "R2 round-trip"
  else
    fail "R2 round-trip (check .cloudflare-r2.env or boto3)"
  fi
else
  echo "  (skip — no .cloudflare-r2.env)"
fi

echo ""
echo "--- 5/5 Smoke test (production) ---"
if (cd backend && python scripts/smoke_test.py "$PROD_URL"); then
  pass "production smoke_test"
else
  fail "production smoke_test"
fi

echo ""
if [[ "$FAIL" -eq 0 ]]; then
  echo "E2E_WORKFLOW_PASSED"
  exit 0
fi
echo "E2E_WORKFLOW_FAILED"
exit 1
