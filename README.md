# ProofPack AI — Multimodal Disaster Claim Intelligence Platform

ProofPack AI helps small businesses, property owners, and local governments assemble
evidence-backed disaster recovery / insurance claim packets after floods, hurricanes,
hail, fires, and storms. Users upload damaged-property photos, invoices, receipts,
insurance PDFs, inspection reports, permits, and voice notes. The system extracts
evidence, verifies event context against public data (FEMA / NWS), detects missing
documentation, and generates a claim-ready packet with **citations, confidence scores,
and human-review checkpoints**.

> This is not "chat with a PDF." It is a production-grade multimodal AI system that
> combines vision, document intelligence, RAG, agents, evaluation, and LLMOps.

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
RAG (hybrid retrieval + re-rank + cited answers)
   ↓  (Month 2)
LangGraph Agent Workflow
   ├── Intake · Evidence Extraction · FEMA/NWS Verification
   ├── Policy RAG · Gap Analysis · Report Writer · Human Review
   ↓
Claim Packet + Evidence Index + Citations
   ↓  (Month 3)
Evaluation + Observability + Feedback Loop
```

See [`docs/system-design.md`](docs/system-design.md) for the full design.

---

## Repository layout

```text
proofpack-ai/
├── backend/                FastAPI service (RAG pipeline, agents, providers)
│   ├── app/
│   │   ├── api/routes/     REST endpoints (claims, documents, qa, packets, health)
│   │   ├── agents/         LangGraph workflow (intake→…→report→review)
│   │   ├── db/             SQLAlchemy models + session + indexes (pgvector)
│   │   ├── providers/      LLM / embeddings / OCR abstraction (Gemini + stub)
│   │   ├── services/       ingestion, chunking, retrieval, qa, external (FEMA/NWS/geo)
│   │   ├── storage/        local FS or S3-compatible object store (Railway/R2/MinIO)
│   │   ├── celery_app.py   Celery app · tasks.py async tasks · observability.py tracing
│   │   └── schemas.py      Pydantic request/response models
│   ├── alembic/            migrations (baseline = current metadata + indexes)
│   └── evals/              HTTP eval harness + CI gate
├── frontend/               Next.js + TypeScript + Tailwind dashboard
├── infra/postgres/         pgvector init SQL
├── docs/                   system design, eval methodology, failure modes
├── .github/workflows/      CI: smoke test + eval gate + frontend build
├── render.yaml             Render blueprint (backend web + Celery worker)
├── backend/railway.json    Railway healthcheck config for the API service
├── docker-compose.yml      postgres (pgvector) + redis + backend + worker + frontend
├── writeup.md              end-to-end how-it-works + deploy guide
├── AGENTS.md               LangGraph agent workflow contract
└── .env.example            copy to .env
```

---

## Quick start (Docker — recommended)

```bash
cp .env.example .env
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API + docs: http://localhost:8000/docs
- Postgres: localhost:5432 (pgvector enabled)

**No API keys required.** With keys absent, ProofPack runs on deterministic *stub*
providers (still does real PDF text extraction, chunking, hybrid retrieval, and
extractive cited answers). It is **free-API first**: add a free `GEMINI_API_KEY` (from
[Google AI Studio](https://aistudio.google.com/app/apikey)) and the provider layer
transparently upgrades to hosted Gemini for LLM, embeddings, and multimodal OCR. FEMA/NWS/
Nominatim verification is keyless. See [`writeup.md`](writeup.md) for the full walkthrough.

Compose runs postgres+pgvector, redis, the API, a **Celery worker**, and the frontend
(default `INGEST_MODE=async`).

---

## Local dev (without Docker)

Backend:

```bash
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# point at a local Postgres+pgvector, then:
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

---

## Production deployment

The scalable stack is live on free-tier cloud hosting:

| Service | URL / host | Role |
| ------- | ---------- | ---- |
| **Frontend** | https://frontend-cyan-iota-66.vercel.app | Next.js dashboard (`NEXT_PUBLIC_API_BASE_URL` → API) |
| **API** | https://proofpack-api-production.up.railway.app | FastAPI gateway + docs at `/docs` |
| **Worker** | Railway `proofpack-worker` | Celery async ingestion + packet runs |
| **Postgres** | Railway `Postgres-k_pO` | pgvector + FTS (extensions auto-created on boot) |
| **Redis** | Railway `Redis` | Celery broker + external-API cache |
| **Object storage** | Railway bucket `proofpack` | S3-compatible blobs shared by API + worker |

Verify production:

```bash
curl https://proofpack-api-production.up.railway.app/health
python backend/scripts/smoke_test.py https://proofpack-api-production.up.railway.app
```

Redeploy after changes:

```bash
railway up --service proofpack-api --detach -m "message"
railway up --service proofpack-worker --detach -m "message"
cd frontend && vercel deploy --prod -y
```

See [`writeup.md`](writeup.md) §11 for the full env matrix and setup steps.

---

## Roadmap

| Phase | Deliverable | Status |
| ----- | ----------- | ------ |
| **Month 1** | Upload → OCR/parse → chunk → embed → pgvector → cited QA. | **Built** |
| **Month 2** | LangGraph multi-agent workflow + FEMA/NWS verification + claim packet (PDF) generation. | **Built** |
| **Month 3** | Eval harness (Recall@K, faithfulness, schema validity) + CI gate + PII-redacted tracing. | **Built** |

---

## Tech stack

- **Frontend:** Next.js, TypeScript, Tailwind CSS
- **Backend:** FastAPI, SQLAlchemy, Pydantic v2, Celery (async ingestion), Alembic
- **Data:** PostgreSQL + pgvector (HNSW + FTS), Redis, S3-compatible object storage (local FS default)
- **AI:** Google Gemini (LLM / embeddings / multimodal OCR) behind a provider abstraction,
  with OpenAI optional and a deterministic key-free stub fallback
- **Agents:** LangGraph workflow + keyless FEMA / NWS / Nominatim verification + PDF packets
- **Eval/Obs:** HTTP eval harness + GitHub Actions CI gate + Langfuse tracing (opt-in)
