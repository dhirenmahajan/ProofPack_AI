# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

ProofPack AI assembles evidence-backed disaster insurance claim packets. Users create a
**claim**, upload **documents** (photos, invoices, policies, inspection reports, voice
notes), and the backend ingests them into a per-claim RAG index that answers questions
with inline citations and confidence scores, then runs a **multi-agent workflow** that
verifies the event against public data (FEMA/NWS), analyses coverage, detects evidence
gaps, and generates a cited, human-reviewable **claim packet** (markdown + PDF).

All three roadmap phases are now implemented:
- **Month 1 — RAG core:** upload → OCR/parse → chunk → embed → pgvector → cited QA.
- **Month 2 — agents:** LangGraph workflow (intake → extraction → FEMA/NWS verification →
  policy RAG → gap analysis → report writer → human review) + packet generation.
- **Month 3 — eval + obs:** HTTP-driven eval harness with a CI gate, plus PII-redacted
  tracing.

Everything still runs with **zero API keys** (deterministic stubs), and is **free-API
first**: Google Gemini is the primary hosted provider; FEMA/NWS/Nominatim are keyless.

## Commands

```bash
# Full stack (postgres+pgvector, redis, backend, Celery worker, frontend)
cp .env.example .env
docker compose up --build
# Frontend :3000 · Backend+docs :8000/docs · Postgres :5432
# Compose defaults to INGEST_MODE=async (worker does ingestion); set sync to run inline.

# Backend only (needs a local Postgres+pgvector; set POSTGRES_HOST=localhost in .env)
cd backend && python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
# async ingestion also needs a worker:
celery -A app.celery_app.celery_app worker --loglevel=info

# Frontend only
cd frontend && npm install && npm run dev   # npm run build · npm run lint

# Schema (prod): create_all bootstraps on startup; explicit migrations via Alembic
cd backend && alembic upgrade head

# End-to-end smoke test (waits for async ingestion; exits "SMOKE_TEST_PASSED")
python backend/scripts/smoke_test.py [base_url]

# Eval harness / CI gate (needs a running backend; gates on Recall@5 + faithfulness)
cd backend && python -m evals.run_evals --base-url http://localhost:8000
```

Automated checks: `scripts/smoke_test.py` (creates a claim, uploads a policy, waits for
ingestion, asserts a citation) and `evals/run_evals.py` (scored quality gate). Both run in
CI (`.github/workflows/ci.yml`) against postgres+redis service containers, key-free.

## Production (Railway + Vercel)

| Service | URL |
| ------- | --- |
| Frontend | https://frontend-cyan-iota-66.vercel.app |
| API | https://proofpack-api-production.up.railway.app |

Railway project `proofpack-ai` runs the **scalable path**: `proofpack-api` + `proofpack-worker`
(Celery) + managed Postgres + Redis + an S3-compatible **Railway bucket** (`STORAGE_BACKEND=s3`,
`INGEST_MODE=async`). Vercel hosts `frontend/` with
`NEXT_PUBLIC_API_BASE_URL=https://proofpack-api-production.up.railway.app`.

Deploy notes:
- API start command must use shell form for `$PORT` (see `backend/Dockerfile`); literal
  `$PORT` in a non-shell start command fails on Railway.
- Worker has **no HTTP healthcheck** — only the API should healthcheck `/health`.
- `backend/app/storage/` is a Python package; `.gitignore` must **not** exclude it (only
  `/backend/storage/` local upload dir).
- `DATABASE_URL_OVERRIDE` from Railway is auto-normalized to `postgresql+psycopg://` in
  `config.py`.

## Architecture

### Provider abstraction is the center of gravity

Every model call — LLM, embeddings, OCR — flows through `backend/app/providers/`. Each
`get_*()` factory resolves a concrete implementation **at runtime** from env config + key
presence. When `*_PROVIDER=auto` the priority is **Gemini key → OpenAI key → stub**:

- **LLM** (`get_llm`): `GeminiLLM` (`gemini-2.5-flash`) → `OpenAILLM` → `StubLLM`
  (extractive, citation-preserving). Hosted providers fall back to the stub on any error.
- **Embeddings** (`get_embedder`): `GeminiEmbedder` (`gemini-embedding-001` at **768-dim**) →
  `OpenAIEmbedder` (output dim pinned to 768) → `StubEmbedder` (deterministic hashed
  bag-of-words). All share `EMBEDDING_DIM`.
- **OCR / multimodal** (`get_ocr`): `GeminiVisionOCR` (images → OCR + damage description,
  audio → transcription) → `HFOCR` → `TesseractOCR` (offline) → `StubOCR`. **PDF + plaintext
  extraction are always real (pypdf)** regardless of provider.

Consequences when working here:
- The stubs make dev/tests deterministic and offline. **Preserve the stub path** when
  adding any model-backed feature — never make a key mandatory, and degrade, never crash.
- Factories are `@lru_cache`d singletons. Changing provider env vars **after the process
  starts won't re-resolve** them. `/providers` reports which implementation is live.
- New model calls must define a `Protocol` in `providers/base.py` and route through a
  cached factory, not instantiate clients directly. Google SDK imports are lazy (inside the
  provider classes) so the app imports without `google-genai` installed.

### Request + workflow flow

```
POST /claims                        → create claim
POST /claims/{id}/documents         → store blob + Document; ingest sync OR enqueue Celery
POST /claims/{id}/qa                 → hybrid_search → LLM.answer → log QARun (traced)
POST /claims/{id}/packet             → AgentRun → LangGraph workflow → ClaimPacket (+PDF)
GET  /claims/{id}/packet/runs/{rid}  → poll workflow status
POST /claims/{id}/packet/{pid}/review→ human approve / edit
GET  /claims/{id}/packet/{pid}/pdf   → download packet PDF
```

- **Ingestion** (`services/ingestion.py`) is split into `store_document` (fast: blob +
  `Document` row, status `processing`) and `process_document` (OCR → chunk → embed → write
  `Chunk` rows, status `ready`/`failed`). `ingest_document` chains both for sync. In async
  mode (`INGEST_MODE=async`) the upload route enqueues `app.tasks.process_document_task`
  and returns `chunks_created=0`; the frontend polls document status.
- **Chunking** (`services/chunking.py`): page-aware overlapping word windows (180/40),
  preserving page numbers for citations.
- **Retrieval** (`services/retrieval.py`): always **claim-scoped**, computed **in the DB** —
  a pgvector HNSW cosine search and a Postgres full-text (`to_tsvector`/`ts_rank`) search,
  fused with weighted **Reciprocal Rank Fusion** (`0.7` vector / `0.3` keyword, `RRF_K=60`).
  FTS failures degrade to vector-only.
- **QA** (`services/qa.py`): builds 1-based `RetrievedContext`, calls the LLM, maps `[n]`
  markers back to chunk metadata, persists a `QARun`, and wraps the call in a PII-redacted
  trace span.
- **Agents** (`app/agents/`): a LangGraph state machine (`graph.py`) of bounded nodes
  (`nodes.py`); see `AGENTS.md`. Runs sync or via `app.tasks.run_packet_task`. Each node has
  a deterministic key-free path so the workflow runs offline.

### Data model (`backend/app/db/models.py`)

`Claim` 1—N `Document` 1—N `Chunk`; `QARun` logs each QA call. Month-2 tables: `AgentRun`
(one workflow execution), `ExtractionResult` (per-document structured fields),
`VerificationResult` (FEMA/NWS/geocode outcome), `ClaimPacket` (markdown + PDF path +
confidence + citations + gaps + status). `Chunk.embedding` is `Vector(settings.embedding_dim)`
bound at import — `EMBEDDING_DIM` defaults to **768** (Gemini); changing it invalidates
stored vectors (recreate `chunks`/drop the volume).

### Schema lifecycle + indexes

Dev bootstrap is unchanged: `main.py` `lifespan` → `_init_db()` runs `CREATE EXTENSION`
(vector, pg_trgm), `Base.metadata.create_all`, then `apply_indexes()` (HNSW on
`chunks.embedding`, GIN FTS + trigram on `chunks.text`; see `db/indexes.py`). Production uses
**Alembic** (`alembic upgrade head`); the `0001_baseline` migration materialises current
metadata + the same indexes. Models must be imported before `create_all`/autogenerate runs.

### Object storage

`storage/object_store.py` resolves `LocalObjectStore` or `S3ObjectStore` (boto3; works with
Cloudflare R2 / MinIO / S3) from `STORAGE_BACKEND`. `storage_path` is a filesystem path
(local) or object key (S3); the worker and PDF download read it back.

### Frontend

Next.js 14 App Router, single client page (`frontend/app/page.tsx`): claim sidebar +
upload panel (polls while documents are `processing`) + QA panel + **packet panel**
(generate/poll/approve/download). All calls go through `frontend/lib/api.ts`; shapes mirror
`backend/app/schemas.py` in `frontend/lib/types.ts` — keep those in sync.

## Conventions

- Backend: Python 3.11, `from __future__ import annotations`, SQLAlchemy 2.0 typed
  `Mapped[...]`, Pydantic v2 (`ConfigDict(from_attributes=True)` for ORM-out schemas).
  Config is centralized in `app/config.py` (`settings` singleton); read env through it,
  never `os.getenv`.
- `source_type` is a fixed vocabulary enforced in `routes/documents.py`
  (`policy|invoice|receipt|photo|inspection|permit|voicenote|other`).
- Ingestion/OCR, external API calls, and every agent node **degrade, never crash**: failures
  return placeholders / `unverified` / neutral state rather than raising out of a request or
  worker. Maintain that contract.
- External public APIs (`services/external/`: FEMA, NWS, Nominatim) are keyless but require a
  descriptive `EXTERNAL_USER_AGENT`, are Redis-cached (`app/cache.py`), and retry with
  `tenacity` backoff.
- Tracing (`app/observability.py`) is opt-in (`TRACING_ENABLED` + Langfuse keys) and always
  PII-redacts inputs/outputs.
