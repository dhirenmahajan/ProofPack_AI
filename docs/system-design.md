# ProofPack AI — System Design

## 1. Goals

- Ingest messy, real-world, **multimodal** disaster-claim evidence (PDFs, scanned forms,
  photos, invoices, receipts, inspection reports, voice notes).
- Reason over that evidence with **RAG + agents** and produce a **claim-ready packet**
  where every assertion is **cited** back to a source (document page, image region,
  weather event, or public record).
- Be **measurable** (eval harness) and **observable** (tracing, cost/latency).

## 2. Component overview

| Layer | Tech | Responsibility |
| ----- | ---- | -------------- |
| Frontend | Next.js / TS / Tailwind | Claim intake wizard, upload, evidence + citations viewer, human approval. |
| Gateway | FastAPI | REST API, validation, orchestration entrypoint. |
| Ingestion | Python services (+ Celery later) | OCR / parse / chunk / embed for each uploaded artifact. |
| Storage | Postgres + pgvector + object store | Structured metadata, embeddings, raw blobs. |
| RAG | hybrid retrieval + re-rank | Find the right evidence, return cited answers. |
| Agents (M2) | LangGraph | Bounded-responsibility agents with tool permissions. |
| Eval/Obs (M3) | Ragas + LangSmith/Phoenix + OTel | Quality gates and production telemetry. |

## 3. Provider abstraction (key design decision)

All model inference flows through `app/providers`. Each provider exposes a narrow
interface and resolves an implementation at runtime:

- `LLM_PROVIDER=auto` → use OpenAI if `OPENAI_API_KEY` is set, else the **stub** LLM
  (deterministic extractive answers assembled from retrieved chunks, with citations).
- `EMBEDDINGS_PROVIDER=auto` → OpenAI embeddings, else a **deterministic hashing
  embedder** that still produces meaningful cosine similarity for demos/tests.
- `OCR_PROVIDER=auto` → HF inference OCR for images, else stub. PDF/text extraction is
  always real (pypdf), so the pipeline is genuinely functional with zero keys.

This keeps the system runnable out-of-the-box, testable in CI without secrets, and a
one-line upgrade to hosted inference.

## 4. Data model

- **Claim** — the unit of work (claimant, incident type/date, location, status).
- **Document** — an uploaded artifact (filename, content type, source type, storage path,
  ocr confidence).
- **Chunk** — a retrievable unit (text, page number, bbox, source type, embedding vector,
  token count) linked to a document + claim.
- **QARun** — an audit record of a question, the retrieved chunk ids, and the cited answer.

## 5. RAG flow (Month 1)

1. Upload → persist blob to object store + `Document` row.
2. Parse/OCR → text (per page for PDFs).
3. Chunk by semantic section/page with overlap; capture layout metadata (page, source).
4. Embed each chunk → store vector in pgvector.
5. Query: hybrid score = α·(vector cosine) + (1−α)·(keyword/trigram), top-k.
6. Re-rank (lexical overlap heuristic now; cross-encoder later).
7. Generate answer with **strict citation requirement**; return `[n]` → chunk mapping.

## 6. Future (Months 2–3)

- LangGraph agents: Intake, Evidence Extraction, FEMA/NWS Verification, Policy RAG,
  Gap Analysis, Report Writer, Human Review.
- Eval harness with seeded claim scenarios; CI eval gates.
- OpenTelemetry traces, cost-per-packet, p95/p99, hallucination + override rates.
