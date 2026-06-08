<!-- generated-by: gsd-doc-writer -->
# Getting Started

This guide takes you from a fresh clone to a running ProofPack AI stack and your first
cited claim packet. ProofPack AI runs with **zero API keys** out of the box — the provider
layer falls back to deterministic offline stubs, so no Gemini or OpenAI key is required to
follow this guide.

The recommended path is Docker Compose, which brings up the entire stack (Postgres with
pgvector, Redis, FastAPI backend, Celery worker, and the Next.js frontend) with one command.
Local non-Docker paths for the backend and frontend are also documented below.

---

## Prerequisites

For the recommended Docker Compose path:

- **Docker** with the Compose plugin (`docker compose`, v2 syntax)
- **Git**

That is all you need for the full stack — Compose builds the Python and Node images for you.

For running the runtimes individually without Docker:

- **Python `3.11`** — the backend image is built `FROM python:3.11-slim` and the codebase
  targets 3.11
- **Node.js `20`** — the frontend image is built `FROM node:20-alpine`; Next.js 14 requires
  Node 18 or newer
- **PostgreSQL with the `pgvector` extension** — required for the backend; the project uses
  the `pgvector/pgvector:pg16` image in Compose
- **Redis** — required only for async ingestion (Celery broker) and the external-API cache
- **Tesseract** (optional) — for offline OCR; the Docker image installs it automatically

No API keys are required for any path. Adding a free `GEMINI_API_KEY` to `.env` later
transparently upgrades the LLM, embeddings, and OCR providers — see
[`CONFIGURATION.md`](CONFIGURATION.md).

---

## Installation steps

### Recommended: full stack with Docker Compose

```bash
# 1. Clone the repository
git clone https://github.com/dhirenmahajan/ProofPack_AI.git

# 2. Enter the project directory
cd ProofPack_AI

# 3. Create your environment file from the template
cp .env.example .env

# 4. Build and start the full stack
docker compose up --build
```

This starts five services: `postgres` (pgvector), `redis`, `backend` (FastAPI), `worker`
(Celery), and `frontend` (Next.js). Compose sets `INGEST_MODE=async` by default, so the
Celery worker handles document ingestion and the frontend polls each document's status
until it is `ready`.

Default service ports:

- Frontend dashboard: `http://localhost:3000`
- Backend API + interactive docs: `http://localhost:8000/docs`
- Postgres: `localhost:5432` (pgvector enabled)
- Redis: `localhost:6379`

### Backend only (without Docker)

The backend needs a local Postgres with pgvector. Set `POSTGRES_HOST=localhost` in your
`.env` first (the template defaults it to `postgres` for the Compose network).

```bash
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The schema bootstraps automatically on startup (`CREATE EXTENSION vector`,
`create_all`, and the pgvector/FTS indexes). For async ingestion you also need a Celery
worker running against a local Redis:

```bash
celery -A app.celery_app.celery_app worker --loglevel=info
```

To run ingestion inline inside the upload request instead (no worker needed), set
`INGEST_MODE=sync` in `.env`.

### Frontend only (without Docker)

```bash
cd frontend
npm install
npm run dev
```

The frontend reads `NEXT_PUBLIC_API_BASE_URL` (defaults to `http://localhost:8000`) to
reach the backend. Additional scripts: `npm run build`, `npm run start`, `npm run lint`.

---

## First run

With the stack up (`docker compose up --build`), confirm everything is healthy and walk
the full claim flow: **create claim → upload → poll until ready → ask a question → generate
a packet**.

### 1. Verify the backend is up

```bash
curl http://localhost:8000/health
# {"status": "ok", "version": "..."}

# See which provider implementation is live (stub vs hosted Gemini/OpenAI)
curl http://localhost:8000/providers
# {"llm": "stub", "embeddings": "stub", "ocr": "stub"}
```

Then open the dashboard at `http://localhost:3000` and the interactive API docs at
`http://localhost:8000/docs`.

### 2. Create a claim

Only `title` is required; `claimant_name`, `incident_type`, `incident_date`, and `location`
are optional.

```bash
curl -X POST http://localhost:8000/claims \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Cedar Falls flood — Delgado",
    "claimant_name": "Maria Delgado",
    "incident_type": "flood",
    "incident_date": "2024-06-12",
    "location": "482 Riverside Drive, Cedar Falls, IA"
  }'
```

The response includes the new claim `id` — use it in the steps below as `{claim_id}`.

### 3. Upload a document

`source_type` must be one of
`policy | invoice | receipt | photo | inspection | permit | voicenote | other`.

```bash
curl -X POST http://localhost:8000/claims/{claim_id}/documents \
  -F "file=@policy.pdf" \
  -F "source_type=policy"
```

In async mode (the Compose default) the response returns `chunks_created: 0` and a document
with status `processing`; the worker ingests it in the background.

### 4. Poll until the document is ready

Ingestion (OCR → chunk → embed) runs asynchronously, so wait for the document status to
become `ready` before asking questions.

```bash
curl http://localhost:8000/claims/{claim_id}/documents
# Each document has a "status" field: processing → ready (or failed)
```

The frontend dashboard polls this automatically while any document is `processing`.

### 5. Ask a question and get cited answers

```bash
curl -X POST http://localhost:8000/claims/{claim_id}/qa \
  -H "Content-Type: application/json" \
  -d '{"question": "Does this policy cover flood damage and what is the deductible?"}'
```

The response includes an `answer` with inline `[n]` markers and a `citations` array mapping
each marker back to the source document, page, and snippet.

### 6. Generate a claim packet

This kicks off the LangGraph multi-agent workflow (intake → extraction → FEMA/NWS
verification → policy RAG → gap analysis → report writer → human review). It returns an
agent run you then poll for completion.

```bash
# Start the workflow
curl -X POST http://localhost:8000/claims/{claim_id}/packet
# Returns a run with an "id" and "status"

# Poll the run until it completes
curl http://localhost:8000/claims/{claim_id}/packet/runs/{run_id}

# Once finished, fetch the latest packet and download its PDF
curl http://localhost:8000/claims/{claim_id}/packet/latest
curl -o claim_packet.pdf http://localhost:8000/claims/{claim_id}/packet/{packet_id}/pdf
```

A human-review checkpoint is available to approve or edit the packet body before download:

```bash
curl -X POST http://localhost:8000/claims/{claim_id}/packet/{packet_id}/review \
  -H "Content-Type: application/json" \
  -d '{"approve": true}'
```

### Fastest verification: the smoke test

Instead of running the steps manually, the bundled smoke test creates a claim, uploads a
sample policy, waits for ingestion, and asserts that the QA answer is backed by at least one
citation. It prints `SMOKE_TEST_PASSED` on success.

```bash
python backend/scripts/smoke_test.py
# or against a different host:
python backend/scripts/smoke_test.py http://localhost:8000
```

---

## Common setup issues

- **`POSTGRES_HOST` mismatch (local backend).** `.env.example` defaults
  `POSTGRES_HOST=postgres`, which is the Docker Compose service name. When running the
  backend directly on your machine, set `POSTGRES_HOST=localhost` or the connection will
  fail to resolve.

- **QA returns no citations / document stuck on `processing`.** In async mode the Celery
  worker performs ingestion. If the worker is not running (local non-Docker setup) the
  document never reaches `ready`. Either start the worker
  (`celery -A app.celery_app.celery_app worker --loglevel=info`) or set `INGEST_MODE=sync`
  in `.env` to ingest inline during the upload request.

- **Port already in use (`3000`, `8000`, `5432`, or `6379`).** Another process is bound to
  the port. Stop the conflicting service or remap the port in `docker-compose.yml`.

- **Forgot to copy the env file.** The backend and worker read configuration from `.env`.
  Run `cp .env.example .env` before `docker compose up`. Everything works key-free; you do
  not need to fill in any provider keys.

- **Wrong runtime version (local non-Docker).** The backend targets Python `3.11` and the
  frontend targets Node.js `20`. Mismatched versions can cause install or build failures —
  the Docker Compose path avoids this entirely.

---

## Next steps

- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — system overview, request/workflow flow, and
  the provider abstraction.
- [`docs/CONFIGURATION.md`](CONFIGURATION.md) — every environment variable, required vs
  optional settings, and how to add a Gemini key.
- [`README.md`](../README.md) — project overview, usage examples, and production
  deployment.
