<!-- generated-by: gsd-doc-writer -->
# Deployment

How to deploy ProofPack AI to production. The backend (FastAPI API + Celery worker) and the
Next.js frontend deploy independently. The reference production stack runs the API and worker
on **Railway** and the frontend on **Vercel**, both connected to GitHub for auto-deploy. A
**Render** blueprint (`render.yaml`) is also provided as an alternative free-tier path.

The application is **free-API first** and degrades to deterministic stubs with zero API keys,
so a deployment is functional even before any provider keys are configured. Adding keys
(e.g. `GEMINI_API_KEY`) upgrades it to hosted inference at runtime.

## Deployment targets

| Target | Config file | What it deploys |
| ------ | ----------- | --------------- |
| Railway (reference) | `backend/railway.json` | `proofpack-api` (web) + `proofpack-worker` (Celery) from `backend/` |
| Render (alternative) | `render.yaml` | `proofpack-backend` (web) + `proofpack-worker` (Celery) from `backend/` |
| Vercel | `frontend/.vercel/project.json` | Next.js frontend from `frontend/` |
| Docker Compose (local/self-host) | `docker-compose.yml` | postgres+pgvector, redis, backend, worker, frontend |

The backend container is built from `backend/Dockerfile` (`python:3.11-slim`, includes
Tesseract for offline OCR). Its `CMD` binds the platform-injected port:

```dockerfile
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

> Do **not** override the start command with a literal `$PORT` string on a PaaS that does not
> expand shell variables in its start-command field (Railway). The Dockerfile `CMD` already
> handles `$PORT`; leave the start command empty so the image default is used.

### Railway (reference production stack)

Railway project **`proofpack-ai`** runs the scalable path with four resources:

- **`proofpack-api`** — the FastAPI web service. Built from `backend/Dockerfile`. Railway
  injects `$PORT`; the Dockerfile `CMD` binds it. Healthcheck path `/health` is set on this
  service in Railway service config (not in `railway.json`, so the worker does not inherit it).
- **`proofpack-worker`** — the Celery worker. Start command:
  `celery -A app.celery_app.celery_app worker --loglevel=info --concurrency=2`. The worker has
  **no HTTP server**, so it must have **no healthcheck**. `backend/railway.json` deliberately
  does not define a shared `/health` healthcheck for this reason.
- **Managed Postgres** (pgvector) — provides `DATABASE_URL`.
- **Managed Redis** — Celery broker + external-API cache.
- **Cloudflare R2** (recommended) — object storage (`STORAGE_BACKEND=s3`, S3-compatible API).
  Setup: `infra/cloudflare/README.md` and `./scripts/cloudflare_r2_setup.sh`. A Railway
  bucket also works if you prefer keeping storage on Railway.

`backend/railway.json` sets the builder and restart policy for both services:

```json
{
  "build": { "builder": "DOCKERFILE" },
  "deploy": { "restartPolicyType": "ON_FAILURE", "restartPolicyMaxRetries": 3 }
}
```

Both app services deploy from the GitHub repo `dhirenmahajan/ProofPack_AI`, branch `main`,
root directory `backend/`. They run with `INGEST_MODE=async` (uploads enqueue a Celery task;
the worker ingests) and `STORAGE_BACKEND=s3` (Cloudflare R2 or Railway bucket).

| Service | URL |
| ------- | --- |
| Frontend | <!-- VERIFY: https://frontend-cyan-iota-66.vercel.app --> |
| API | <!-- VERIFY: https://proofpack-api-production-ed2f.up.railway.app --> |
| Railway dashboard | <!-- VERIFY: https://railway.com/project/9d9107ee-366c-4edf-ac0b-f8cc6c0670ee --> |

### Render (alternative)

`render.yaml` is a Render blueprint that mirrors the Railway layout on free-tier managed
services: Postgres+pgvector via Supabase, Redis via Upstash, object storage via Cloudflare R2,
frontend via Vercel.

- **`proofpack-backend`** (web, `rootDir: backend`) — `buildCommand: pip install -r requirements.txt`,
  `startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT`, `healthCheckPath: /health`,
  with `INGEST_MODE=async`.
- **`proofpack-worker`** (worker, `rootDir: backend`) — same build command,
  `startCommand: celery -A app.celery_app.celery_app worker --loglevel=info --concurrency=2`.

Both pull shared environment from the `proofpack-shared` env var group; secrets marked
`sync: false` are filled in the Render dashboard.

### Frontend (Vercel)

Vercel hosts the `frontend/` directory (Next.js 14, project name `frontend`). It is connected
to GitHub for auto-deploy. The only required environment variable is the API base URL:

```bash
NEXT_PUBLIC_API_BASE_URL=<!-- VERIFY: https://proofpack-api-production-ed2f.up.railway.app -->
```

`frontend/lib/api.ts` reads this variable; all frontend requests target the deployed API.

## Build pipeline

There is **no deploy step in CI** — `.github/workflows/ci.yml` runs only quality gates. Actual
deployment happens via the GitHub-connected platforms (Railway and Vercel) on push to `main`.

CI (`ci.yml`) runs on push to `main` and on pull requests, with two jobs:

1. **`backend-evals`** — spins up `pgvector/pgvector:pg16` and `redis:7-alpine` service
   containers, installs Tesseract + Python deps, starts the backend (`uvicorn app.main:app`),
   then runs `python scripts/smoke_test.py` and the eval gate
   `python -m evals.run_evals --base-url http://localhost:8000` (Recall@5 + faithfulness).
   Runs key-free with stub providers and `INGEST_MODE=sync`.
2. **`frontend-build`** — installs deps, runs `npx tsc --noEmit`, and `npm run build`.

Auto-deploy flow once CI is green:

1. `git push origin main`.
2. **Railway** auto-builds both `proofpack-api` and `proofpack-worker` from `backend/` using
   `backend/Dockerfile`.
3. **Vercel** auto-builds and deploys the `frontend/` project.

> Fallback: the Railway CLI `railway up` performs a local upload without pushing to GitHub.

### Database schema on deploy

On first boot, `app/main.py` `lifespan` bootstraps the schema (`CREATE EXTENSION` for vector +
pg_trgm, `Base.metadata.create_all`, then `apply_indexes()`). For explicit, versioned schema
control, run Alembic instead:

```bash
cd backend && alembic upgrade head
```

The `0001_baseline` migration (`backend/alembic/versions/0001_baseline.py`) materialises the
current metadata plus the HNSW / GIN FTS / trigram indexes.

## Environment setup

Production environment variables are documented in full in
[CONFIGURATION.md](./CONFIGURATION.md). The reference Railway/Render stack sets at minimum:

| Variable | Production value | Notes |
| -------- | ---------------- | ----- |
| `DATABASE_URL_OVERRIDE` | `${{Postgres.DATABASE_URL}}` (Railway) | `config.py` rewrites `postgresql://` → `postgresql+psycopg://` |
| `REDIS_URL` | managed Redis URL | Celery broker + external-API cache |
| `INGEST_MODE` | `async` | worker performs ingestion |
| `STORAGE_BACKEND` | `s3` | Railway bucket / Cloudflare R2 / MinIO / S3 |
| `EMBEDDING_DIM` | `768` | must match stored vectors; changing it invalidates them |
| `GEMINI_API_KEY` | dashboard secret | <!-- VERIFY: set in the Railway/Render dashboard secret manager --> |
| `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | dashboard secrets | <!-- VERIFY: bucket credentials set in the platform secret manager --> |
| `EXTERNAL_USER_AGENT` | descriptive contact UA | required by NWS / Nominatim |

`DATABASE_URL_OVERRIDE` takes precedence over the individual `POSTGRES_*` variables. Railway and
Supabase hand out `postgresql://` DSNs; `backend/app/config.py` `database_url` rewrites the
scheme to `postgresql+psycopg://` automatically so psycopg3 accepts it:

```python
if url.startswith("postgresql://"):
    return url.replace("postgresql://", "postgresql+psycopg://", 1)
```

> The application never crashes on a missing provider key — it falls back to deterministic
> stubs. Secrets are therefore an upgrade, not a hard requirement, for a working deploy.

## Rollback procedure

There is no automated rollback step in the repository. Use the platform mechanism for the
target you deployed to:

1. **Railway** — in the Railway dashboard, open the affected service (`proofpack-api` and/or
   `proofpack-worker`), find the previous successful deployment, and use Railway's redeploy /
   rollback action to restore it. <!-- VERIFY: exact rollback control lives in the Railway dashboard -->
2. **Git-based rollback** — revert the offending commit on `main` and push; both Railway
   services and Vercel auto-rebuild from the reverted state:
   ```bash
   git revert <bad-commit-sha>
   git push origin main
   ```
3. **Vercel (frontend)** — promote a previous deployment from the Vercel dashboard's
   Deployments list. <!-- VERIFY: redeploy/promote action performed in the Vercel dashboard -->
4. **Schema** — Alembic migrations are forward-only here (single `0001_baseline`); avoid
   destructive schema changes without an explicit down-migration. Changing `EMBEDDING_DIM`
   requires recreating the `chunks` table / dropping the vector volume.

## Monitoring

Tracing is **opt-in** and off by default (`TRACING_ENABLED=false`). When enabled with Langfuse
credentials, QA and agent calls are traced; inputs and outputs are **PII-redacted** before they
leave the process (`backend/app/observability.py`).

Relevant dependencies (`backend/requirements.txt`): `langfuse`, `opentelemetry-sdk`,
`opentelemetry-exporter-otlp`. There is no Sentry, Datadog, or New Relic integration.

To enable tracing in production, set:

| Variable | Purpose |
| -------- | ------- |
| `TRACING_ENABLED` | `true` to activate tracing (default `false`) |
| `LANGFUSE_PUBLIC_KEY` | Langfuse project public key <!-- VERIFY: from the Langfuse dashboard --> |
| `LANGFUSE_SECRET_KEY` | Langfuse project secret key <!-- VERIFY: from the Langfuse dashboard --> |
| `LANGFUSE_HOST` | Langfuse host (default `https://cloud.langfuse.com`) |

Tracing degrades to a no-op when Langfuse is unavailable or unconfigured, so leaving it
disabled is safe.

Liveness can be checked at `GET /health` (returns `{"status": "ok", "version": ...}`). The
active provider implementations (hosted vs stub) are reported at `GET /providers`. The Langfuse
trace dashboard URL is deployment-specific. <!-- VERIFY: Langfuse trace dashboard URL -->
