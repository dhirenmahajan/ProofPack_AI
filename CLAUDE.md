# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

ProofPack AI assembles evidence-backed disaster insurance claim packets. Users create a
**claim**, upload **documents** (photos, invoices, policies, inspection reports, voice
notes), and the backend ingests them into a per-claim RAG index that answers questions
with inline citations and confidence scores. Only **Month 1** of the roadmap is built:
upload → OCR/parse → chunk → embed → pgvector → cited QA. Month 2 (LangGraph agents,
FEMA/NWS verification, packet generation) and Month 3 (eval harness, observability) are
planned, not implemented.

## Commands

Everything runs with **zero API keys** (see provider abstraction below).

```bash
# Full stack (postgres+pgvector, redis, backend, frontend)
cp .env.example .env
docker compose up --build
# Frontend :3000 · Backend+docs :8000/docs · Postgres :5432

# Backend only (needs a local Postgres+pgvector; set POSTGRES_HOST=localhost in .env)
cd backend && python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend only
cd frontend && npm install && npm run dev      # npm run build · npm run lint

# End-to-end smoke test (requires a running backend; exits "SMOKE_TEST_PASSED")
python backend/scripts/smoke_test.py [base_url]
```

There is **no unit-test framework** (no pytest, no jest). `scripts/smoke_test.py` is the
only automated check — it creates a claim, uploads a sample policy, asks a question, and
asserts a citation comes back. Use it to verify backend changes end-to-end.

## Architecture

### Provider abstraction is the center of gravity

Every model call — LLM, embeddings, OCR — flows through `backend/app/providers/`. Each
`get_*()` factory (`get_llm`, `get_embedder`, `get_ocr`) resolves a concrete
implementation **at runtime** from env config + key presence, falling back to a
deterministic, key-free **stub**:

- `LLM_PROVIDER=auto` → `OpenAILLM` if `OPENAI_API_KEY` set, else `StubLLM` (extractive,
  citation-preserving — picks evidence sentences overlapping the question).
- `EMBEDDINGS_PROVIDER=auto` → `OpenAIEmbedder` or `StubEmbedder` (deterministic hashed
  bag-of-words, L2-normalized — real cosine similarity, no network).
- `OCR_PROVIDER=auto` → `HFOCR` (HuggingFace inference) or `StubOCR`. **PDF and plaintext
  extraction are always real (pypdf)** regardless of provider; only image/audio OCR needs
  `HF_API_TOKEN`.

Consequences when working here:
- The stubs make dev/tests deterministic and offline. Preserve the stub path when adding
  any model-backed feature — don't make a key mandatory.
- Factories are `@lru_cache`d singletons. Changing provider env vars **after the process
  starts won't re-resolve** them. `/providers` reports which implementation is live.
- New model calls must define a `Protocol` in `providers/base.py` and route through a
  cached factory, not instantiate clients directly.

### Request flow

```
POST /claims                          → create claim
POST /claims/{id}/documents           → ingest_document(): store → OCR → chunk → embed → pgvector
POST /claims/{id}/qa                  → answer_question(): hybrid_search → LLM.answer → log QARun
```

- **Ingestion** (`services/ingestion.py`): saves bytes via the object store, extracts text,
  writes a `Document`, chunks pages, embeds chunks, writes `Chunk` rows with vectors. Runs
  **synchronously inside the request** (no Celery yet, though Redis is wired in compose).
- **Chunking** (`services/chunking.py`): page-aware overlapping word windows (180 words,
  40 overlap), preserving page numbers for citations.
- **Retrieval** (`services/retrieval.py`): always **claim-scoped**. Hybrid score =
  `0.7 * vector_cosine + 0.3 * keyword_overlap`. Pulls `6 × top_k` candidates by pgvector
  cosine distance, then re-ranks by the combined score.
- **QA** (`services/qa.py`): builds 1-based `RetrievedContext` list, calls the LLM, maps
  the `[n]` citation markers in the answer back to chunk metadata (filename, page,
  snippet, score). If the LLM emits no markers, it cites all contexts. Every answer is
  persisted as a `QARun` (question, answer, retrieved chunk ids, citations, provider,
  latency) — this is the LLMOps groundwork for Month 3.

### Data model (`backend/app/db/models.py`)

`Claim` 1—N `Document` 1—N `Chunk`; `QARun` logs each QA call. Chunks carry both
`document_id` and `claim_id` (denormalized so retrieval filters by claim without a join).
The `Chunk.embedding` column is `Vector(settings.embedding_dim)` — **the vector dimension
is bound at import time from `EMBEDDING_DIM` (default 1536)**. Stub and OpenAI both use
1536; changing `EMBEDDING_DIM` invalidates already-stored vectors.

### Schema lifecycle — no migrations

The DB schema is created at app startup in `main.py`'s `lifespan` → `_init_db()`:
`CREATE EXTENSION IF NOT EXISTS vector` then `Base.metadata.create_all`. There is **no
Alembic**. Models must be imported before `create_all` runs — `main.py` does
`from app.db import models  # noqa: F401` for exactly this reason. New models go in
`models.py`; schema changes to existing tables won't auto-migrate (drop the volume or
alter by hand in dev).

### Frontend

Next.js 14 App Router, single client page (`frontend/app/page.tsx`) — claim sidebar +
upload panel + QA panel. All backend calls go through the typed client in
`frontend/lib/api.ts` (base URL from `NEXT_PUBLIC_API_BASE_URL`); response shapes mirror
the backend Pydantic schemas in `frontend/lib/types.ts`. Keep those two in sync with
`backend/app/schemas.py` when changing the API.

## Conventions

- Backend: Python 3.11, `from __future__ import annotations` everywhere, SQLAlchemy 2.0
  typed `Mapped[...]` models, Pydantic v2 (`model_config = ConfigDict(from_attributes=True)`
  for ORM-out schemas). Config is centralized in `app/config.py` (`settings` singleton);
  read env through it, never `os.getenv` directly.
- `source_type` is a fixed vocabulary enforced in `routes/documents.py`
  (`policy|invoice|receipt|photo|inspection|permit|voicenote|other`).
- Ingestion/OCR is built to **degrade, never crash**: failed image OCR returns a
  placeholder evidence record rather than raising. Maintain that contract.
- `FEMA_API_BASE` / `NWS_API_BASE` / `NOMINATIM_API_BASE` exist in config but are unused —
  they're for the Month 2 verification agent.
