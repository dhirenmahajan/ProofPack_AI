#!/usr/bin/env bash
# Delete proofpack-ai from dhiren@nextsignal.io (run AFTER new account is verified).
set -euo pipefail

export RAILWAY_CALLER="skill:use-railway"
OLD_PROJECT_ID="98e16273-4514-4ffc-946f-4f4417dba8f2"

echo "==> Railway account"
WHOAMI=$(railway whoami --json)
echo "$WHOAMI"

EMAIL=$(echo "$WHOAMI" | python3 -c "import sys,json; print(json.load(sys.stdin)['email'])")
if [[ "$EMAIL" != "dhiren@nextsignal.io" ]]; then
  echo "ERROR: Not logged in as dhiren@nextsignal.io."
  echo "Run: railway logout && railway login   (authorize the OLD account)"
  exit 1
fi

echo "==> Deleting project proofpack-ai ($OLD_PROJECT_ID)"
railway project delete --project "$OLD_PROJECT_ID" --yes --json

echo "Done. Log out with: railway logout"
