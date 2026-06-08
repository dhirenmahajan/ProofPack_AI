# AGENTS.md

The ProofPack AI agent layer (Month 2). A **LangGraph** state machine that turns a
claim's ingested evidence into a cited, human-reviewable claim packet. Each node is a
small agent with one job, explicit inputs/outputs, and a deterministic key-free fallback.

> This document is the contract for the agent workflow. For the overall system see
> `CLAUDE.md`; for the end-to-end narrative + setup see `writeup.md`.

**Production:** packet runs execute on the Railway Celery worker (`proofpack-worker`) when
`INGEST_MODE=async`. Generated PDFs land in the Railway S3 bucket via `app/storage/` and are
served at `GET /claims/{id}/packet/{packet_id}/pdf`.

| Surface | URL |
| ------- | --- |
| Frontend | https://frontend-cyan-iota-66.vercel.app |
| API | https://proofpack-api-production-ed2f.up.railway.app |

Backend deploys from GitHub `dhirenmahajan/ProofPack_AI@main` (Railway auto-deploy on push).

## Where it lives

```
backend/app/agents/
├── state.py        ClaimState — the TypedDict threaded through the graph
├── graph.py        builds + runs the StateGraph (sequential fallback if LangGraph absent)
├── nodes.py        the seven node functions (state in → partial state out)
├── extraction.py   per-document structured extraction (Gemini JSON / regex fallback)
├── checklist.py    per-incident required-evidence checklist (gap analysis)
├── report.py       deterministic packet markdown + confidence scoring
├── pdf.py          markdown → PDF (reportlab) → object store
└── runner.py       create AgentRun → run graph → persist ClaimPacket (sync or Celery)
backend/app/services/external/   FEMA · NWS · Nominatim clients (keyless, cached, backoff)
```

## The workflow

```
intake → extraction → verification → policy_rag → gap_analysis → report_writer → human_review
```

Execution is linear. `graph.py` compiles this with LangGraph (`StateGraph(ClaimState)`),
binding a DB session into each node via closure; if LangGraph is unavailable it runs the
identical sequence directly. A node never raises — failures append a note and yield neutral
output, so the graph always reaches a packet (likely flagged for review).

## Nodes (responsibility · inputs · outputs · tools)

| Node | Responsibility | Reads from state | Writes to state | Tools / providers |
| ---- | -------------- | ---------------- | --------------- | ----------------- |
| `intake` | Resolve the incident location to coordinates + state | `location` | `geocode` | Nominatim (geocode) |
| `extraction` | Pull structured fields from each document; persist `ExtractionResult` | `claim_id` | `extractions` | Gemini JSON → regex fallback; DB |
| `verification` | Confirm the event occurred where/when claimed; persist `VerificationResult` | `geocode`, `incident_*` | `verification` | OpenFEMA (authoritative), NWS (supplementary) |
| `policy_rag` | Answer standard coverage questions with citations | `claim_id` | `coverage_qa`, `citations` | `services/qa.answer_question` (hybrid RAG + LLM) |
| `gap_analysis` | Flag missing required evidence for the incident type | `extractions`, `incident_type` | `gaps` | `checklist.required_for` |
| `report_writer` | Assemble packet markdown; compute confidence + review flag | all of the above | `report_markdown`, `confidence`, `needs_review` | `report.build_markdown` (deterministic) |
| `human_review` | Terminal checkpoint: annotate why review is/ isn't needed | `needs_review` | `notes` | — |

`needs_review` is set true when confidence `< 0.6`, the event is unverified, **or** any
evidence gap exists. Confidence is a weighted blend (`report.score_confidence`): extraction
confidence `0.35`, verification `0.25`, coverage-answered ratio `0.25`, gap completeness `0.15`.

## Tool permissions

Nodes only touch what their row above lists. In particular:
- Only `extraction`, `verification`, and `policy_rag` perform model/external calls.
- Only `intake`/`verification` reach the public internet (FEMA/NWS/Nominatim), always via
  `services/external/` (keyless, Redis-cached, `tenacity` backoff, `EXTERNAL_USER_AGENT`).
- `report_writer` is deterministic — it does not call a model, so packet structure and
  citations are reproducible regardless of provider.

## Structured outputs (schemas)

- Extraction returns a per-`source_type` field dict (see `extraction._SCHEMA_HINT`) +
  confidence + provider; persisted to `ExtractionResult.fields` (JSONB).
- Verification returns `{verified, summary, fema, nws}`; persisted to `VerificationResult`.
- The packet is persisted as `ClaimPacket` and surfaced through `schemas.ClaimPacketOut`
  (markdown, confidence, needs_review, status, citations, gaps, verification, `has_pdf`).
- A 200 from the packet endpoints proves schema validity (Pydantic-validated) — this is the
  `schema_validity` metric in the eval harness.

## Running it

- API: `POST /claims/{id}/packet` → `start_packet_run`. Sync (`INGEST_MODE=sync`) runs inline
  and returns the run **with** its packet; async enqueues `app.tasks.run_packet_task` and the
  client polls `GET /claims/{id}/packet/runs/{run_id}`.
- Human review: `POST /claims/{id}/packet/{packet_id}/review` (`approve`, optional edited
  `markdown`). The claim advances to `review` or `ready` accordingly.

## Adding a new agent/node

1. Write `def my_node(db: Session, state: ClaimState) -> dict:` in `nodes.py`. Return only the
   keys you produce. Catch your own errors and append a `notes` entry; never raise.
2. Add the field(s) you emit to `ClaimState` in `state.py`.
3. Insert `("my_node", nodes.my_node)` at the right position in `_ORDER` in `graph.py`.
4. If you call a model, go through a provider factory or guard on `settings.gemini_api_key`
   with a deterministic fallback. If you call the internet, add a cached client under
   `services/external/`.
5. If you persist data, add a model in `db/models.py` (+ a `ClaimPacketOut`-style schema) and
   a relationship on `Claim`; `create_all`/the Alembic baseline will pick it up.
6. Surface anything user-facing through `schemas.py` and keep `frontend/lib/types.ts` in sync.
