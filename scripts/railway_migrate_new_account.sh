#!/usr/bin/env bash
# Recreate proofpack-ai on the CURRENT Railway account (run AFTER `railway login` on the new account).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export RAILWAY_CALLER="skill:use-railway"

echo "==> Railway account"
railway whoami --json

EMAIL=$(railway whoami --json | python3 -c "import sys,json; print(json.load(sys.stdin)['email'])")
if [[ "$EMAIL" == "dhiren@nextsignal.io" ]]; then
  echo "ERROR: Still logged in as dhiren@nextsignal.io. Log out and log into the NEW account first:"
  echo "  railway logout && railway login"
  exit 1
fi

echo "==> Create project proofpack-ai"
if railway status --json >/dev/null 2>&1; then
  echo "Already linked to a project; skipping init"
else
  railway init --name proofpack-ai
fi

PROJECT_ID=$(railway status --json | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
ENV_ID=$(railway status --json | python3 -c "import sys,json; print(json.load(sys.stdin)['environments']['edges'][0]['node']['id'])")
echo "Project: $PROJECT_ID  Environment: $ENV_ID"

echo "==> Provision databases (skip if already present)"
EXISTING=$(railway service list --json | python3 -c "
import sys,json
svcs=[s['name'].lower() for s in json.load(sys.stdin)]
print('postgres' if any('postgres' in n for n in svcs) else '')
print('redis' if any('redis' in n for n in svcs) else '')
")
HAS_PG=$(echo "$EXISTING" | sed -n '1p')
HAS_REDIS=$(echo "$EXISTING" | sed -n '2p')
if [[ -z "$HAS_PG" ]]; then railway add --database postgres --json; else echo "Postgres exists"; fi
if [[ -z "$HAS_REDIS" ]]; then railway add --database redis --json; else echo "Redis exists"; fi

echo "==> Create app services"
for svc in proofpack-api proofpack-worker; do
  if railway service list --json | python3 -c "import sys,json; import sys; names=[s['name'] for s in json.load(sys.stdin)]; sys.exit(0 if '$svc' in names else 1)"; then
    echo "$svc exists"
  else
    railway add --service "$svc" --json
  fi
done

echo "==> Create bucket"
if railway bucket list --json | python3 -c "import sys,json; sys.exit(0 if json.load(sys.stdin) else 1)" 2>/dev/null; then
  echo "Bucket exists"
else
  railway bucket create proofpack --region sjc --json
fi

API_ID=$(railway service list --json | python3 -c "import sys,json; print(next(s['id'] for s in json.load(sys.stdin) if s['name']=='proofpack-api'))")
WORKER_ID=$(railway service list --json | python3 -c "import sys,json; print(next(s['id'] for s in json.load(sys.stdin) if s['name']=='proofpack-worker'))")
PG_NAME=$(railway service list --json | python3 -c "
import sys,json
for s in json.load(sys.stdin):
  if 'postgres' in s['name'].lower():
    print(s['name']); break
")
REDIS_NAME=$(railway service list --json | python3 -c "
import sys,json
for s in json.load(sys.stdin):
  if s['name'].lower()=='redis':
    print(s['name']); break
")

GEMINI_KEY=""
if [[ -f "$ROOT/.railway-migrate/gemini.key" ]]; then
  GEMINI_KEY=$(cat "$ROOT/.railway-migrate/gemini.key")
elif [[ -f "$ROOT/.env" ]]; then
  GEMINI_KEY=$(grep -E '^GEMINI_API_KEY=' "$ROOT/.env" | cut -d= -f2- || true)
fi
if [[ -z "$GEMINI_KEY" ]]; then
  echo "WARN: No GEMINI_API_KEY found locally; set it on Railway after deploy"
fi

BUCKET_JSON=$(railway bucket credentials --bucket proofpack --json)
export GEMINI_KEY BUCKET_JSON API_ID WORKER_ID PG_NAME REDIS_NAME
python3 <<'PY'
import json, os, subprocess

gemini = os.environ.get("GEMINI_KEY", "")
bucket = json.loads(os.environ.get("BUCKET_JSON", "{}"))
pg = os.environ.get("PG_NAME", "Postgres")
redis = os.environ.get("REDIS_NAME", "Redis")

common_vars = {
    "GEMINI_API_KEY": {"value": gemini},
    "GEMINI_LLM_MODEL": {"value": "gemini-2.5-flash"},
    "GEMINI_EMBEDDING_MODEL": {"value": "gemini-embedding-001"},
    "GEMINI_VISION_MODEL": {"value": "gemini-2.5-flash"},
    "EMBEDDING_DIM": {"value": "768"},
    "LLM_PROVIDER": {"value": "auto"},
    "EMBEDDINGS_PROVIDER": {"value": "auto"},
    "OCR_PROVIDER": {"value": "auto"},
    "INGEST_MODE": {"value": "async"},
    "STORAGE_BACKEND": {"value": "s3"},
    "S3_BUCKET": {"value": bucket.get("bucketName", "")},
    "S3_REGION": {"value": bucket.get("region", "auto")},
    "S3_ENDPOINT_URL": {"value": bucket.get("endpoint", "")},
    "S3_ACCESS_KEY_ID": {"value": bucket.get("accessKeyId", "")},
    "S3_SECRET_ACCESS_KEY": {"value": bucket.get("secretAccessKey", "")},
    "DATABASE_URL_OVERRIDE": {"value": "${{" + pg + ".DATABASE_URL}}"},
    "REDIS_URL": {"value": "${{" + redis + ".REDIS_URL}}"},
    "APP_ENV": {"value": "production"},
    "EXTERNAL_USER_AGENT": {"value": "ProofPackAI/1.0 (contact: dhiren@nextsignal.io)"},
}

patch = {
    "services": {
        os.environ["API_ID"]: {
            "source": {"rootDirectory": "backend"},
            "build": {"builder": "DOCKERFILE"},
            "deploy": {
                "startCommand": "",
                "healthcheckPath": "/health",
                "healthcheckTimeout": 120,
            },
            "variables": common_vars,
        },
        os.environ["WORKER_ID"]: {
            "source": {"rootDirectory": "backend"},
            "build": {"builder": "DOCKERFILE"},
            "deploy": {
                "startCommand": "celery -A app.celery_app.celery_app worker --loglevel=info --concurrency=2",
                "healthcheckPath": None,
            },
            "variables": common_vars,
        },
    }
}

subprocess.run(
    ["railway", "environment", "edit", "--json", "--message", "Migrate proofpack-ai"],
    input=json.dumps(patch), text=True, check=True,
    env={**os.environ, "RAILWAY_CALLER": "skill:use-railway"},
)
print("Config applied")
PY

echo "==> Deploy API + worker"
railway up --service proofpack-api --detach -m "Migrate: API deploy"
railway up --service proofpack-worker --detach -m "Migrate: worker deploy"

echo "==> Generate public domain"
DOMAIN_JSON=$(railway domain --service proofpack-api --json)
echo "$DOMAIN_JSON"

API_URL=$(echo "$DOMAIN_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['domain'])")
echo ""
echo "============================================"
echo "Migration deploy started."
echo "API URL: $API_URL"
echo "After deployments succeed, run:"
echo "  python backend/scripts/smoke_test.py $API_URL"
echo "Update Vercel:"
echo "  cd frontend && printf '%s' '$API_URL' | npx vercel env add NEXT_PUBLIC_API_BASE_URL production --stdin -y"
echo "  cd frontend && npx vercel deploy --prod -y"
echo "============================================"
