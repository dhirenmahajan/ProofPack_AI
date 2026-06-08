<!-- generated-by: gsd-doc-writer -->
# Development

This guide covers local setup, the build/run commands, code style, and the project
conventions you must follow when extending ProofPack AI. For a high-level tour of the
system see [ARCHITECTURE.md](./ARCHITECTURE.md); for environment variables see
[CONFIGURATION.md](./CONFIGURATION.md).

## Local setup

ProofPack is a two-part repository:

- `backend/` — FastAPI app + Celery worker (Python 3.11)
- `frontend/` — Next.js 14 App Router client (Node + npm)

### Full stack (recommended)

Docker Compose brings up Postgres+pgvector, Redis, the backend, a Celery worker, and the
frontend together:

```bash
cp .env.example .env
docker compose up --build
# Frontend  http://localhost:3000
# Backend   http://localhost:8000  (OpenAPI docs at /docs)
# Postgres  localhost:5432
# Redis     localhost:6379
```

Compose defaults to `INGEST_MODE=async`, so the worker performs document ingestion. Set
`INGEST_MODE=sync` in `.env` to run ingestion inline in the request instead.

The stack runs with **zero API keys** out of the box — deterministic stubs back every model
call. Add `GEMINI_API_KEY` (or `OPENAI_API_KEY`) to `.env` to switch on hosted providers.

### Backend only

Requires a local Postgres with the `pgvector` extension. Set `POSTGRES_HOST=localhost` in
`.env` first.

```bash
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

If you run with `INGEST_MODE=async`, also start a Celery worker (see
[Celery worker](#celery-worker) below).

### Frontend only

```bash
cd frontend
npm install
npm run dev
```

The frontend reads `NEXT_PUBLIC_API_BASE_URL` (defaults to `http://localhost:8000`) to
locate the API.

## Build commands

### Backend

| Command | Description |
| ------- | ----------- |
| `uvicorn app.main:app --reload` | Run the API in development with hot reload. |
| `celery -A app.celery_app.celery_app worker --loglevel=info` | Run the Celery worker for async ingestion and packet workflows. |
| `alembic upgrade head` | Apply database migrations (production schema lifecycle). |
| `python -m evals.run_evals --base-url http://localhost:8000` | Run the scored eval harness / CI quality gate (needs a running backend). |
| `python backend/scripts/smoke_test.py [base_url]` | End-to-end smoke test (creates a claim, uploads a doc, waits for ingestion, asserts a citation). |

There is no separate backend "build" step — the app runs directly from source. The
container image is built from `backend/Dockerfile` (Python 3.11 slim + Tesseract for offline
OCR).

### Frontend

| Command | Description |
| ------- | ----------- |
| `npm run dev` | Start the Next.js dev server on port 3000. |
| `npm run build` | Production build (`next build`). |
| `npm run start` | Serve the production build (`next start`). |
| `npm run lint` | Run Next.js / ESLint linting (`next lint`). |

## Code style

### Backend (Python)

- **Python 3.11**, with `from __future__ import annotations` at the top of every module.
- **SQLAlchemy 2.0** typed ORM: declare columns with `Mapped[...]` and `mapped_column(...)`.
  Models live in `backend/app/db/models.py` and inherit from the `Base` defined in
  `backend/app/db/session.py`.
- **Pydantic v2** for request/response schemas (`backend/app/schemas.py`). ORM-out schemas
  set `model_config = ConfigDict(from_attributes=True)` so they can be built directly from
  ORM instances.
- **Centralized config**: read all environment values through the `settings` singleton in
  `backend/app/config.py` (`from app.config import settings`). **Never call `os.getenv`
  directly.** `settings` is a `pydantic_settings.BaseSettings` subclass that loads from `.env`
  and the environment.

No backend linter/formatter config (ruff, black, flake8) is committed to the repository, so
follow the existing style in the codebase: `# noqa: BLE001` is used intentionally on the
broad `except Exception` blocks that implement the degrade-never-crash contract (below).

### Frontend (TypeScript)

- **Next.js 14 App Router** with React 18 and TypeScript in `strict` mode (see
  `frontend/tsconfig.json`). The `@/*` path alias maps to the frontend root.
- Linting is via `next lint` (`npm run lint`). No standalone `.eslintrc` is committed; the
  Next.js default config applies.
- **Keep `frontend/lib/types.ts` in sync with `backend/app/schemas.py`.** The TypeScript
  interfaces (`Claim`, `ClaimDocument`, `UploadResponse`, `Citation`, `QAResponse`,
  `ClaimPacket`, `AgentRun`, etc.) mirror the Pydantic schemas. When you change a backend
  schema, update the matching TS interface in the same change.
- **All API calls go through `frontend/lib/api.ts`.** The `api` object centralizes fetch
  calls against `NEXT_PUBLIC_API_BASE_URL`. Do not scatter raw `fetch` calls across
  components — add a method to `api` instead.

## Core conventions

### The degrade-never-crash contract

This is the most important rule in the codebase. Ingestion/OCR, external API calls, and every
agent node **degrade, never crash**: a failure returns a placeholder, an `unverified` result,
or neutral state rather than raising out of a request or worker.

Examples in the code you should match:

- `GeminiLLM.answer` wraps the hosted call in `try/except` and falls back to `StubLLM` on any
  error (`backend/app/providers/llm.py`).
- Agent nodes (`backend/app/agents/nodes.py`) never raise; a node failure records a note and
  yields neutral output so the graph still reaches a packet (flagged for human review).
- The retrieval layer degrades full-text search failures to vector-only.

When you add a model-backed or network feature, preserve this contract.

### Provider abstraction (Protocol + cached factory)

Every model call — LLM, embeddings, OCR — flows through `backend/app/providers/`. Each provider
type defines a `Protocol` in `backend/app/providers/base.py` and is resolved at runtime by a
`@lru_cache`d `get_*()` factory:

- `get_llm()` → `LLMProvider` (`GeminiLLM` → `OpenAILLM` → `StubLLM`)
- `get_embedder()` → `EmbeddingProvider` (Gemini → OpenAI → `StubEmbedder`)
- `get_ocr()` → `OCRProviderProto` (Gemini Vision → HF → Tesseract → `StubOCR`)

When `*_PROVIDER=auto`, the resolution priority is **Gemini key → OpenAI key → stub**.

#### Adding a new provider

1. Define (or reuse) a `Protocol` in `backend/app/providers/base.py` describing the interface
   — give it a `name: str` attribute and the methods callers depend on.
2. Implement a concrete class in the relevant module (`llm.py`, `embeddings.py`, or `ocr.py`).
   Keep heavy third-party SDK imports **lazy** (inside `__init__` or the method body) so the
   app imports without the SDK installed — see how `GeminiLLM.__init__` does
   `from google import genai` inside the constructor.
3. Wire it into the matching `@lru_cache`d `get_*()` factory, respecting the
   key-presence → priority ordering and always falling back to the deterministic stub.
4. Never make an API key mandatory, and degrade to the stub on error — do not crash.

Two gotchas:

- Factories are `@lru_cache`d singletons. Changing provider env vars **after the process
  starts will not re-resolve** them.
- New model calls must route through a cached factory, not instantiate clients directly. The
  `/providers` endpoint reports which implementation is live.

#### Adding a new agent node

The claim-packet workflow is a linear LangGraph state machine. The node order lives in the
`_ORDER` list in `backend/app/agents/graph.py`
(`intake → extraction → verification → policy_rag → gap_analysis → report_writer →
human_review`).

1. Write a function in `backend/app/agents/nodes.py` with the signature
   `def my_node(db: Session, state: ClaimState) -> dict`. It receives the DB session and the
   running `ClaimState`, and returns a partial state update (a `dict`).
2. **The node must never raise.** Catch failures, append a note via the `_note(state, msg)`
   helper, and return neutral output so the graph still reaches a packet.
3. Add `("my_node", nodes.my_node)` to `_ORDER` in `graph.py` at the correct position. The
   graph wires edges between consecutive entries automatically; if LangGraph is unavailable,
   `_run_sequential` runs the same `_ORDER` as a fallback.
4. If your node persists data, add the corresponding model to `backend/app/db/models.py` and
   create a migration (below). See `extraction`/`verification` nodes for the persistence
   pattern (`db.add(...)` + `db.commit()`).

### Document `source_type` vocabulary

`source_type` is a fixed vocabulary enforced in `backend/app/api/routes/documents.py`
(`ALLOWED_SOURCE_TYPES`). Uploading any other value returns HTTP 422. The allowed values are:

`policy`, `invoice`, `receipt`, `photo`, `inspection`, `permit`, `voicenote`, `other`.

When you add a new document category, update `ALLOWED_SOURCE_TYPES`, the agent checklist
(`backend/app/agents/checklist.py`), and the frontend upload UI together.

## Database: Alembic migrations vs. create_all

The project has two schema paths that produce the **same** shape:

- **Dev bootstrap (`create_all`)** — On startup, `lifespan` in `backend/app/main.py` calls
  `_init_db()`, which runs `CREATE EXTENSION` (vector, pg_trgm), `Base.metadata.create_all`,
  then `apply_indexes()` (HNSW on `chunks.embedding`, plus GIN full-text and trigram indexes
  on `chunks.text`). This is idempotent and is what you get in local Docker / `uvicorn`
  development.
- **Production (Alembic)** — Run `alembic upgrade head` from `backend/`. The `0001_baseline`
  migration materializes the current metadata plus the same indexes. The DB URL is injected at
  runtime from `app.config.settings` by `backend/alembic/env.py` (so `alembic.ini` leaves
  `sqlalchemy.url` blank).

When you change a model in `backend/app/db/models.py`:

1. Make the change to the `Mapped[...]` columns / relationships.
2. Generate a migration:
   ```bash
   cd backend
   alembic revision --autogenerate -m "describe your change"
   ```
   Models must be imported before autogenerate runs — `alembic/env.py` already imports
   `app.db.models` to register them on `Base`.
3. Review the generated migration, then apply it with `alembic upgrade head`.

> Note on embeddings: `Chunk.embedding` is bound to `Vector(settings.embedding_dim)` at import
> time, defaulting to **768** (Gemini). Changing `EMBEDDING_DIM` invalidates already-stored
> vectors — you must recreate the `chunks` table (or drop the Postgres volume in dev).

## Celery worker

The Celery app is defined in `backend/app/celery_app.py`. Both the broker and result backend
are Redis (`REDIS_URL`). Tasks live in `backend/app/tasks.py` and bind to the app via
`@celery_app.task`, so importing `app.tasks` anywhere (API or worker) uses the configured
Redis broker rather than Celery's default `amqp://localhost`.

Run a worker locally:

```bash
cd backend
celery -A app.celery_app.celery_app worker --loglevel=info
```

In Docker Compose and production the worker uses `--concurrency=2`.

Current tasks:

- `process_document_task` — async document ingestion (OCR → chunk → embed) for one stored
  document. Used when `INGEST_MODE=async`; retries up to 3 times with exponential backoff.
- `run_packet_task` — runs the LangGraph claim-packet workflow.

The worker has **no HTTP healthcheck** — do not configure a shared `/health` check for it.

## Branch conventions

No branch-naming convention is documented in the repository. The default branch is `main`,
and pushing to `main` triggers the production deploy (see the project README for the
Railway + Vercel topology).

## PR process

No `PULL_REQUEST_TEMPLATE.md` or `CONTRIBUTING.md` is present in the repository, so there is
no formally documented PR process. Based on the project's CI and conventions, a reasonable
checklist before opening a PR:

- Ensure the backend and frontend run locally (`docker compose up`).
- Keep `frontend/lib/types.ts` in sync with any `backend/app/schemas.py` changes.
- If you changed a DB model, include an Alembic migration.
- Run the smoke test and eval harness against a local backend — both run in CI
  (`.github/workflows/ci.yml`) against Postgres + Redis service containers, key-free, so they
  must pass without any API keys.
- Preserve the degrade-never-crash contract and the stub provider path for any new model
  feature.
