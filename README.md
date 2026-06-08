<!-- generated-by: gsd-doc-writer -->
# ProofPack AI — Multimodal Disaster Claim Intelligence Platform

ProofPack AI assembles evidence-backed disaster insurance claim packets for small
businesses, property owners, and local governments recovering from floods, hurricanes,
hail, fires, and storms. Users create a claim, upload photos, invoices, receipts, policy
PDFs, inspection reports, permits, and voice notes; the system ingests them into a
per-claim RAG index that answers questions with inline citations and confidence scores,
then runs a multi-agent workflow that verifies the event against public data (FEMA/NWS),
analyses coverage, detects evidence gaps, and generates a cited, human-reviewable claim
packet in markdown and PDF.

It runs with **zero API keys** out of the box (deterministic stub providers) and is
**free-API first**: add a free `GEMINI_API_KEY` and the provider layer transparently
upgrades to hosted Gemini for LLM, embeddings, and multimodal OCR. FEMA, NWS, and
Nominatim verification is always keyless.

---

## Architecture

```text
User Uploads
   ↓
Next.js Claim Dashboard
   ↓
FastAPI Gateway
   ↓
Ingestion (OCR / parse / chunk / embed)
   ↓
PostgreSQL + Object Storage + pgvector
   ↓
RAG (hybrid retrieval + RRF fusion + cited answers)
   ↓
LangGraph Agent Workflow
   ├── Intake · Evidence Extraction · FEMA/NWS Verification
   ├── Policy RAG · Gap Analysis · Report Writer · Human Review
   ↓
Claim Packet + Evidence Index + Citations
   ↓
Evaluation + Observability
```

See [`docs/system-design.md`](docs/system-design.md) for the full design and
[`AGENTS.md`](AGENTS.md) for the agent workflow contract.

---

## Installation

ProofPack AI is a two-runtime project: a Python 3.11 FastAPI backend and a Next.js
frontend. The recommended path runs the full stack with Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

This starts Postgres (with pgvector), Redis, the FastAPI backend, a Celery worker, and
the frontend. No API keys are required.

To run the runtimes individually without Docker:

```bash
# Backend (needs a local Postgres + pgvector; set POSTGRES_HOST=localhost in .env)
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend
npm install
```

---

## Quick start

1. Copy the environment template: `cp .env.example .env`
2. Bring up the stack: `docker compose up --build`
3. Open the dashboard at http://localhost:3000
4. Open the API docs at http://localhost:8000/docs

Default service ports:

- Frontend: http://localhost:3000
- Backend API + interactive docs: http://localhost:8000/docs
- Postgres: localhost:5432 (pgvector enabled)
- Redis: localhost:6379

Docker Compose defaults to `INGEST_MODE=async`, so the Celery worker handles document
ingestion and the frontend polls document status until it is `ready`.

### Run the backend without Docker

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
# Async ingestion also needs a worker:
celery -A app.celery_app.celery_app worker --loglevel=info
```

### Run the frontend without Docker

```bash
cd frontend
npm run dev      # also: npm run build · npm run start · npm run lint
```

---

## Usage examples

ProofPack AI is driven by a REST API (mounted by `backend/app/main.py`). The frontend
dashboard at http://localhost:3000 wraps the same endpoints. Below are the core calls
against a local backend.

**Create a claim:**

```bash
curl -X POST http://localhost:8000/claims \
  -H "Content-Type: application/json" \
  -d '{"title": "Hurricane roof damage", "description": "Storm of 2024-10"}'
```

**Upload a document** (`source_type` is one of
`policy|invoice|receipt|photo|inspection|permit|voicenote|other`):

```bash
curl -X POST http://localhost:8000/claims/{claim_id}/documents \
  -F "file=@policy.pdf" \
  -F "source_type=policy"
```

**Ask a question and get cited answers:**

```bash
curl -X POST http://localhost:8000/claims/{claim_id}/qa \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the wind damage deductible?"}'
```

**Generate a claim packet** (kicks off the LangGraph workflow; poll the returned run):

```bash
curl -X POST http://localhost:8000/claims/{claim_id}/packet
curl http://localhost:8000/claims/{claim_id}/packet/runs/{run_id}
```

**End-to-end smoke test** — creates a claim, uploads a policy, waits for ingestion, and
asserts a citation (prints `SMOKE_TEST_PASSED` on success):

```bash
python backend/scripts/smoke_test.py [base_url]
```

**Eval harness / CI quality gate** — gates on Recall@5 and faithfulness against a running
backend:

```bash
cd backend && python -m evals.run_evals --base-url http://localhost:8000
```

See [`writeup.md`](writeup.md) for the full end-to-end walkthrough.

---

## Repository layout

```text
ProofPack_AI/
├── backend/                FastAPI service (RAG pipeline, agents, providers)
│   ├── app/
│   │   ├── api/routes/     REST endpoints (claims, documents, qa, packets, health)
│   │   ├── agents/         LangGraph workflow (intake → … → report → review)
│   │   ├── db/             SQLAlchemy models + session + indexes (pgvector)
│   │   ├── providers/      LLM / embeddings / OCR abstraction (Gemini + stub)
│   │   ├── services/       ingestion, chunking, retrieval, qa, external (FEMA/NWS/geo)
│   │   ├── storage/        local FS or S3-compatible object store
│   │   ├── celery_app.py   Celery app · tasks.py async tasks · observability.py tracing
│   │   └── schemas.py      Pydantic request/response models
│   ├── alembic/            migrations (baseline = current metadata + indexes)
│   ├── evals/              HTTP eval harness + CI gate
│   └── scripts/            smoke_test.py end-to-end check
├── frontend/               Next.js + TypeScript + Tailwind dashboard
├── infra/postgres/         pgvector init SQL
├── docs/                   system design, eval methodology, failure modes
├── .github/workflows/      CI: smoke test + eval gate + frontend build
├── docker-compose.yml      postgres (pgvector) + redis + backend + worker + frontend
├── render.yaml             Render blueprint (backend web + Celery worker)
├── writeup.md              end-to-end how-it-works + deploy guide
├── AGENTS.md               LangGraph agent workflow contract
└── .env.example            copy to .env
```

---

## Tech stack

- **Frontend:** Next.js 14, TypeScript, Tailwind CSS
- **Backend:** FastAPI, SQLAlchemy 2.0, Pydantic v2, Celery (async ingestion), Alembic
- **Data:** PostgreSQL + pgvector (HNSW + full-text search), Redis, S3-compatible object
  storage (local filesystem by default)
- **AI:** Google Gemini (LLM / embeddings / multimodal OCR) behind a provider abstraction,
  with OpenAI optional and a deterministic key-free stub fallback
- **Agents:** LangGraph workflow + keyless FEMA / NWS / Nominatim verification + PDF packets
- **Eval / Obs:** HTTP eval harness + GitHub Actions CI gate + Langfuse tracing (opt-in)

---

## Production deployment

The live stack runs on Railway (backend + worker + Postgres + Redis + object storage) and
Vercel (frontend). Both backend services deploy from GitHub — pushing to `main` on
[`dhirenmahajan/ProofPack_AI`](https://github.com/dhirenmahajan/ProofPack_AI) triggers
Railway builds for `proofpack-api` and `proofpack-worker`.

| Service | URL / host | Role |
| ------- | ---------- | ---- |
| Frontend | https://frontend-cyan-iota-66.vercel.app | Next.js dashboard <!-- VERIFY: production frontend URL --> |
| API | https://proofpack-api-production-ed2f.up.railway.app | FastAPI gateway + docs at `/docs` <!-- VERIFY: production API URL --> |
| Worker | Railway `proofpack-worker` | Celery async ingestion + packet runs |
| Postgres | Railway `Postgres` | pgvector + FTS |
| Redis | Railway `Redis` | Celery broker + external-API cache |
| Object storage | Railway bucket | S3-compatible blobs shared by API + worker |

Verify a deployed API:

```bash
curl https://proofpack-api-production-ed2f.up.railway.app/health
python backend/scripts/smoke_test.py https://proofpack-api-production-ed2f.up.railway.app
```

Redeploy:

```bash
# Primary — push to GitHub (Railway auto-deploys both services)
git push origin main

# Frontend (Vercel)
cd frontend && vercel deploy --prod -y
```

See [`writeup.md`](writeup.md) for the full environment matrix and setup steps.

---

## Status

| Phase | Deliverable | Status |
| ----- | ----------- | ------ |
| RAG core | Upload → OCR/parse → chunk → embed → pgvector → cited QA | Built |
| Agents | LangGraph multi-agent workflow + FEMA/NWS verification + claim packet (PDF) generation | Built |
| Eval + obs | Eval harness (Recall@K, faithfulness, schema validity) + CI gate + PII-redacted tracing | Built |

---

## License

No license file is present in this repository. This project is not currently published
under an open-source license.
