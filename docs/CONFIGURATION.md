<!-- generated-by: gsd-doc-writer -->
# Configuration

ProofPack AI is configured entirely through environment variables. All settings are
centralized in the `Settings` singleton (`backend/app/config.py`), loaded via
`pydantic-settings` from a `.env` file (and the process environment). Code reads
configuration through the `settings` object — never `os.getenv` directly.

A canonical, fully-commented template lives in [`.env.example`](../.env.example). Copy it
to `.env` and fill in values as needed:

```bash
cp .env.example .env
```

The system is designed to run with **zero secrets** — every optional key falls back to a
deterministic stub provider. Adding keys automatically upgrades the relevant subsystem to
hosted inference (see [Provider resolution](#provider-resolution)).

## Environment variables

Defaults below are the in-code defaults from `backend/app/config.py`. The `.env.example`
template overrides some of them for the docker-compose topology (noted inline).

### Core

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `APP_ENV` | Optional | `development` | Application environment label. |
| `LOG_LEVEL` | Optional | `INFO` | Logging level. |

### Database (Postgres + pgvector)

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `POSTGRES_USER` | Optional | `proofpack` | Postgres user. |
| `POSTGRES_PASSWORD` | Optional | `proofpack` | Postgres password. |
| `POSTGRES_DB` | Optional | `proofpack` | Postgres database name. |
| `POSTGRES_HOST` | Optional | `localhost` | Postgres host. `.env.example` sets `postgres` (the docker-compose service name); use `localhost` for backend-only local dev. |
| `POSTGRES_PORT` | Optional | `5432` | Postgres port. |
| `DATABASE_URL_OVERRIDE` | Optional | `""` (empty) | Full DSN that takes precedence over the `POSTGRES_*` parts above. Use for managed Postgres (e.g. Supabase pooled connection). A `postgresql://` prefix is automatically rewritten to `postgresql+psycopg://` by `Settings.database_url`. |

The effective connection string is computed by the `Settings.database_url` property: it
uses `DATABASE_URL_OVERRIDE` when set, otherwise assembles `postgresql+psycopg://user:pass@host:port/db`
from the discrete `POSTGRES_*` values.

### Redis (Celery broker + external-API cache)

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `REDIS_URL` | Optional | `redis://localhost:6379/0` | Redis URL. Used as the Celery broker and result backend (`backend/app/celery_app.py`) and for the external-API response cache (`backend/app/cache.py`). `.env.example` sets `redis://redis:6379/0` for docker-compose. |

### Object storage

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `STORAGE_BACKEND` | Optional | `local` | Storage backend. One of `local` or `s3`. Selects `LocalObjectStore` vs `S3ObjectStore` in `backend/app/storage/object_store.py`. |
| `STORAGE_LOCAL_DIR` | Optional | `./storage` | Root directory for local blob storage (used when `STORAGE_BACKEND=local`). `.env.example` and docker-compose set `/data/storage`. |
| `S3_ENDPOINT_URL` | Conditional | `""` (empty) | S3-compatible endpoint URL (Cloudflare R2 / MinIO / Railway bucket). Used only when `STORAGE_BACKEND=s3`. |
| `S3_REGION` | Optional | `auto` | S3 region. |
| `S3_BUCKET` | Conditional | `proofpack` | Bucket name. **Required when `STORAGE_BACKEND=s3`** — `S3ObjectStore.__init__` raises `ValueError` if empty. |
| `S3_ACCESS_KEY_ID` | Conditional | `""` (empty) | S3 access key. Used only when `STORAGE_BACKEND=s3`. |
| `S3_SECRET_ACCESS_KEY` | Conditional | `""` (empty) | S3 secret key. Used only when `STORAGE_BACKEND=s3`. |

### Ingestion mode

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `INGEST_MODE` | Optional | `sync` | One of `sync` or `async`. `sync` runs OCR → chunk → embed inside the upload request (simple/local). `async` enqueues a Celery task so the worker performs ingestion (scalable/prod); the upload response returns `chunks_created=0` and the frontend polls document status. docker-compose defaults this to `async`. |

### LLM provider

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `LLM_PROVIDER` | Optional | `auto` | One of `auto`, `gemini`, `openai`, `stub`. Selects the LLM implementation in `backend/app/providers/llm.py`. |
| `LLM_MODEL` | Optional | `gpt-4o-mini` | OpenAI model name. Used **only** when the OpenAI provider is active. |
| `GEMINI_LLM_MODEL` | Optional | `gemini-2.5-flash` | Gemini chat model used by `GeminiLLM`. |

### Embeddings provider

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `EMBEDDINGS_PROVIDER` | Optional | `auto` | One of `auto`, `gemini`, `openai`, `stub`. Selects the embedder in `backend/app/providers/embeddings.py`. |
| `EMBEDDING_MODEL` | Optional | `text-embedding-3-small` | OpenAI embedding model name (used only when the OpenAI embedder is active). |
| `GEMINI_EMBEDDING_MODEL` | Optional | `gemini-embedding-001` | Gemini embedding model used by `GeminiEmbedder`. |
| `EMBEDDING_DIM` | Optional | `768` | Embedding output dimensionality, shared by every embedder. **This value is bound to the `Chunk.embedding` pgvector column at import time** — changing it invalidates already-stored vectors (recreate the `chunks` table / drop the DB volume). |

### OCR / vision provider

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `OCR_PROVIDER` | Optional | `auto` | One of `auto`, `gemini`, `hf`, `tesseract`, `stub`. Selects the OCR implementation in `backend/app/providers/ocr.py`. PDF and plain-text extraction are always real (pypdf) regardless of this setting; this only governs image/audio understanding. |
| `GEMINI_VISION_MODEL` | Optional | `gemini-2.5-flash` | Gemini multimodal model for image OCR / damage description and audio transcription. |
| `HF_API_TOKEN` | Optional | `""` (empty) | Hugging Face inference token. Presence enables the `hf` OCR path under `auto`. |
| `HF_OCR_MODEL` | Optional | `microsoft/trocr-base-printed` | Hugging Face OCR model. |
| `TESSERACT_CMD` | Optional | `""` (empty) | Explicit path to the `tesseract` binary (used only when `OCR_PROVIDER=tesseract`). |

### AI provider keys

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `GEMINI_API_KEY` | Optional | `""` (empty) | Google Gemini key (free tier). Primary hosted provider. Presence enables Gemini across LLM, embeddings, and OCR under `auto`. |
| `OPENAI_API_KEY` | Optional | `""` (empty) | OpenAI key. Secondary hosted provider for LLM and embeddings under `auto`. |

When no key is set, all three subsystems run their deterministic stubs — the application
starts and serves requests with **no secrets at all**.

### External public APIs (keyless)

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `FEMA_API_BASE` | Optional | `https://www.fema.gov/api/open` | FEMA OpenFEMA API base URL. |
| `NWS_API_BASE` | Optional | `https://api.weather.gov` | National Weather Service API base URL. |
| `NOMINATIM_API_BASE` | Optional | `https://nominatim.openstreetmap.org` | Nominatim geocoding API base URL. |
| `EXTERNAL_USER_AGENT` | Optional | `ProofPackAI/1.0 (contact: ops@proofpack.example)` | Descriptive `User-Agent` with contact info. **NWS and Nominatim require a real contact `User-Agent`** — set this to a genuine address for production use. |
| `EXTERNAL_CACHE_TTL_SECONDS` | Optional | `86400` | Default TTL (seconds) for cached external-API responses in Redis (`backend/app/cache.py`). |

These APIs require no authentication but are rate-sensitive — responses are Redis-cached
and requests retry with backoff.

### Observability (optional)

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `TRACING_ENABLED` | Optional | `false` | Master switch for Langfuse tracing. Tracing only activates when this is `true` **and** `LANGFUSE_PUBLIC_KEY` is set (`backend/app/observability.py`). All traced inputs/outputs are PII-redacted. |
| `LANGFUSE_PUBLIC_KEY` | Optional | `""` (empty) | Langfuse public key. |
| `LANGFUSE_SECRET_KEY` | Optional | `""` (empty) | Langfuse secret key. |
| `LANGFUSE_HOST` | Optional | `https://cloud.langfuse.com` | Langfuse host. |

### Frontend

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `NEXT_PUBLIC_API_BASE_URL` | Optional | `http://localhost:8000` | Base URL the Next.js frontend uses to reach the backend API. docker-compose sets `http://localhost:8000`. <!-- VERIFY: production Vercel value NEXT_PUBLIC_API_BASE_URL=https://proofpack-api-production-ed2f.up.railway.app --> |

## Config file format

ProofPack AI does not use a JSON/YAML/TOML application config file — all runtime settings
come from environment variables (the `.env` file and process environment). The repository
does include deployment-platform config files, which set environment variables rather than
application behavior directly:

- `docker-compose.yml` — local full-stack topology; injects per-service env (`POSTGRES_HOST`,
  `REDIS_URL`, `STORAGE_LOCAL_DIR`, `INGEST_MODE`) and reads the rest from `.env`.
- `backend/railway.json` — Railway build/deploy config (Dockerfile builder, restart policy).
  It deliberately contains no application env vars and no shared healthcheck (the worker has
  no HTTP endpoint).
- `render.yaml` — Render blueprint defining the `proofpack-backend` web service and
  `proofpack-worker`, plus a `proofpack-shared` env-var group (see
  [Per-environment overrides](#per-environment-overrides)).

A minimal `.env` for keyless local development:

```bash
APP_ENV=development
POSTGRES_HOST=localhost
REDIS_URL=redis://localhost:6379/0
STORAGE_BACKEND=local
STORAGE_LOCAL_DIR=./storage
INGEST_MODE=sync
EMBEDDING_DIM=768
```

## Required vs optional settings

Almost every variable has a usable default, so the application boots with an empty `.env`.
There is no global startup validator that aborts on missing values; instead, requirements
are enforced contextually:

- **Database connectivity** is required at runtime. Either point the discrete `POSTGRES_*`
  variables at a reachable Postgres+pgvector instance, or set `DATABASE_URL_OVERRIDE` to a
  full DSN. There is no in-memory fallback.
- **`S3_BUCKET` is required when `STORAGE_BACKEND=s3`.** `S3ObjectStore.__init__` raises
  `ValueError("S3_BUCKET is required when STORAGE_BACKEND=s3")` if it is empty. The S3
  credential variables (`S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`) are
  also effectively required for a working S3 backend, though boto3 may resolve them from the
  ambient AWS environment.
- **Pinned providers require their key.** When a `*_PROVIDER` is set to an explicit hosted
  value, the matching factory raises at resolution time if the key is missing:
  - `LLM_PROVIDER=gemini` without `GEMINI_API_KEY` → `RuntimeError("LLM_PROVIDER=gemini but GEMINI_API_KEY is unset")`
  - `LLM_PROVIDER=openai` without `OPENAI_API_KEY` → `RuntimeError("LLM_PROVIDER=openai but OPENAI_API_KEY is unset")`
  - `EMBEDDINGS_PROVIDER=gemini` / `=openai` without the matching key → analogous `RuntimeError`
  - `OCR_PROVIDER=gemini` without `GEMINI_API_KEY`, or `OCR_PROVIDER=hf` without `HF_API_TOKEN` → analogous `RuntimeError`

  Under the default `*_PROVIDER=auto`, a missing key never raises — it just falls through to
  the next provider (and ultimately the stub).

Everything else is optional and falls back to its default.

## Provider resolution

Each provider factory in `backend/app/providers/` resolves a concrete implementation **at
runtime** based on `*_PROVIDER` plus key presence. When the provider is `auto`, the priority
is **Gemini key → OpenAI key → stub**:

| Subsystem | Factory | `auto` priority |
| --------- | ------- | --------------- |
| LLM | `get_llm` (`llm.py`) | `GeminiLLM` (`gemini-2.5-flash`) → `OpenAILLM` → `StubLLM` (extractive, citation-preserving) |
| Embeddings | `get_embedder` (`embeddings.py`) | `GeminiEmbedder` (`gemini-embedding-001`, 768-dim) → `OpenAIEmbedder` (output dim pinned to `EMBEDDING_DIM`) → `StubEmbedder` (deterministic hashed bag-of-words) |
| OCR / vision | `get_ocr` (`ocr.py`) | `GeminiVisionOCR` → `HFOCR` (needs `HF_API_TOKEN`) → `TesseractOCR` (only when `OCR_PROVIDER=tesseract`) → `StubOCR` |

Important behaviors:

- Factories are `@lru_cache`d singletons. **Changing provider env vars after the process
  starts will not re-resolve them** — restart the process to pick up new keys.
- Hosted LLM/embedding/OCR calls degrade to the stub on error rather than crashing.
- PDF and plain-text extraction are always real (pypdf), independent of `OCR_PROVIDER`.

To see which implementation is live, query the `GET /providers` endpoint, which returns the
active `llm`, `embeddings`, and `ocr` provider names (`backend/app/api/routes/health.py`):

```bash
curl http://localhost:8000/providers
# {"llm":"stub","embeddings":"stub","ocr":"stub"}
```

## Per-environment overrides

Configuration differs by where the app runs. The same variables apply; only their values
and source change.

**Local — docker-compose** (`docker-compose.yml`): reads `.env` via `env_file`, then
overrides per service so the containers find each other:

| Variable | Value (compose) |
| -------- | --------------- |
| `POSTGRES_HOST` | `postgres` |
| `REDIS_URL` | `redis://redis:6379/0` |
| `STORAGE_LOCAL_DIR` | `/data/storage` |
| `INGEST_MODE` | `async` (overridable via `${INGEST_MODE:-async}`) |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` (frontend service) |

**Local — backend only**: set `POSTGRES_HOST=localhost` (and run a local Postgres+pgvector
and Redis). `INGEST_MODE=sync` lets you run without a Celery worker.

**Production — Railway** (primary deploy path): the `proofpack-api` and `proofpack-worker`
services run with `STORAGE_BACKEND=s3`, `INGEST_MODE=async`, managed Postgres, and Redis.
`DATABASE_URL_OVERRIDE=${{Postgres.DATABASE_URL}}` is wired to the managed Postgres
(the `postgresql://` DSN is rewritten to `postgresql+psycopg://` by `config.py`).
<!-- VERIFY: Railway service env values (full secret set for proofpack-api / proofpack-worker) are configured in the Railway dashboard and not present in the repository -->

**Production — Render** (`render.yaml`, alternate blueprint): defines a `proofpack-shared`
env-var group consumed by both the web service and the worker. Secrets marked `sync: false`
must be filled in the Render dashboard:

| Variable | Source in `render.yaml` |
| -------- | ----------------------- |
| `DATABASE_URL_OVERRIDE` | dashboard secret (Supabase pooled DSN) |
| `REDIS_URL` | dashboard secret (Upstash) |
| `GEMINI_API_KEY` | dashboard secret |
| `EMBEDDING_DIM` | `768` (fixed) |
| `STORAGE_BACKEND` | `s3` (fixed) |
| `S3_ENDPOINT_URL` | dashboard secret (Cloudflare R2) |
| `S3_BUCKET` | `proofpack` (fixed) |
| `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | dashboard secrets |
| `S3_REGION` | `auto` (fixed) |
| `EXTERNAL_USER_AGENT` | dashboard secret (real contact) |
| `TRACING_ENABLED` | `false` (fixed) |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | dashboard secrets |

The web service sets `INGEST_MODE=async`; the worker inherits the shared group.

There are no `.env.development` / `.env.production` / `.env.test` files in the repository —
per-environment values come from the platform configs above and the single `.env` template.
