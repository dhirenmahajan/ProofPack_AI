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
├── backend/                FastAPI service (RAG pipeline, ingestion, providers)
│   └── app/
│       ├── api/routes/     REST endpoints (claims, documents, qa, health)
│       ├── db/             SQLAlchemy models + session (pgvector)
│       ├── providers/      LLM / embeddings / OCR abstraction (hosted + stub)
│       ├── services/       ingestion, chunking, retrieval, qa
│       └── schemas/        Pydantic request/response models
├── frontend/               Next.js + TypeScript + Tailwind dashboard
├── infra/postgres/         pgvector init SQL
├── docs/                   system design, eval methodology, failure modes
├── docker-compose.yml      postgres (pgvector) + redis + backend + frontend
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
extractive cited answers). Add `OPENAI_API_KEY` / `HF_API_TOKEN` to `.env` and the
provider layer transparently upgrades to hosted inference.

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

## Roadmap

| Phase | Deliverable |
| ----- | ----------- |
| **Month 1 (this scaffold)** | Upload → OCR/parse → chunk → embed → pgvector → cited QA. |
| Month 2 | LangGraph multi-agent workflow + FEMA/NWS verification + claim packet generation. |
| Month 3 | Eval harness (Recall@K, faithfulness, extraction F1) + tracing + cost/latency dashboards. |

---

## Tech stack

- **Frontend:** Next.js, TypeScript, Tailwind CSS
- **Backend:** FastAPI, SQLAlchemy, Pydantic v2
- **Data:** PostgreSQL + pgvector, Redis, S3-compatible object storage (local FS default)
- **AI:** hosted LLM (OpenAI) + HF inference for OCR/vision, behind a provider abstraction
- **Planned:** LangGraph (agents), Ragas / LangSmith / Phoenix (evals + observability)
