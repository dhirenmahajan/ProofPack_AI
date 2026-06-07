# ProofPack AI — System Design

> **Status:** Months 1–3 are implemented. Production runs on Railway (API + worker +
> Postgres + Redis + S3 bucket) with the frontend on Vercel. See `writeup.md` for live URLs.

## 1. Goals

- Ingest messy, real-world, **multimodal** disaster-claim evidence (PDFs, scanned forms,
  photos, invoices, receipts, inspection reports, voice notes).
- Reason over that evidence with **RAG + agents** and produce a **claim-ready packet**
  where every assertion is **cited** back to a source (document page, image region,
  weather event, or public record).
- Be **measurable** (eval harness + CI gate) and **observable** (opt-in PII-redacted tracing).

## 2. Component overview

| Layer | Tech | Responsibility |
| ----- | ---- | -------------- |
| Frontend | Next.js / TS / Tailwind | Claim dashboard, upload (async poll), cited QA, packet panel. **Prod:** Vercel. |
| Gateway | FastAPI | REST API, validation, orchestration entrypoint. **Prod:** Railway `proofpack-api`. |
| Ingestion | Python + **Celery** | OCR / parse / chunk / embed per artifact. Sync or async (`INGEST_MODE`). |
| Storage | Postgres + pgvector + **S3/local object store** | Metadata, embeddings, raw blobs. |
| RAG | DB-side hybrid retrieval (HNSW + FTS + RRF) | Claim-scoped cited answers. |
| Agents | **LangGraph** workflow | Intake → extraction → FEMA/NWS verify → policy RAG → gaps → report → review. |
| Eval/Obs | HTTP eval harness + Langfuse (opt-in) | Quality gates in CI; PII-redacted traces. |

## 3. Provider abstraction (key design decision)

All model inference flows through `app/providers`. Each factory is `@lru_cache`d and
resolves at runtime with `*_PROVIDER=auto` priority **Gemini → OpenAI → stub**:

- **LLM** — `GeminiLLM` (`gemini-2.5-flash`) → OpenAI → `StubLLM` (extractive, cites).
- **Embeddings** — `GeminiEmbedder` (`gemini-embedding-001`, 768-dim) → OpenAI →
  `StubEmbedder` (deterministic hashed BoW).
- **OCR** — `GeminiVisionOCR` → HF → Tesseract → `StubOCR`. PDF/text via **pypdf** always.

Hosted providers fall back to stubs on error. `GET /providers` reports live implementations.
**Prod** runs with Gemini when `GEMINI_API_KEY` is set on Railway.

## 4. Data model

- **Claim** — unit of work (claimant, incident type/date, location, status).
- **Document** — uploaded artifact (filename, source type, storage path, OCR confidence, status).
- **Chunk** — retrievable unit (text, page, source type, `Vector(768)` embedding); denormalised `claim_id`.
- **QARun** — audit of each QA call (question, answer, citations, provider, latency).
- **AgentRun / ExtractionResult / VerificationResult / ClaimPacket** — agent workflow outputs.

## 5. RAG flow (Month 1 — built)

1. Upload → persist blob (`app/storage`) + `Document` row (`processing`).
2. OCR/parse → per-page text.
3. Chunk (180-word windows, 40 overlap) with page metadata.
4. Embed → store in pgvector with HNSW index.
5. Query: pgvector cosine ANN + Postgres FTS, fused with **Reciprocal Rank Fusion** (0.7/0.3).
6. LLM answer with `[n]` citations → `QARun` persisted.

Async path: API enqueues `process_document_task`; worker completes ingestion.

## 6. Agent workflow (Month 2 — built)

Linear LangGraph state machine (`app/agents/`): intake (Nominatim) → extraction (Gemini/regex) →
verification (OpenFEMA + NWS) → policy RAG → gap analysis → report writer (deterministic) →
human review. Packet markdown + PDF (reportlab) stored in object storage. Contract: `AGENTS.md`.

## 7. Eval + observability (Month 3 — built)

- `backend/evals/` — HTTP-driven harness; gates Recall@5 + faithfulness in CI.
- `app/observability.py` — opt-in Langfuse tracing with PII redaction.

## 8. Production topology

```
Vercel frontend → Railway API → Postgres / Redis / S3 bucket
                      ↓ enqueue
                Railway Celery worker
```

Live URLs: see `README.md` § Production deployment.
