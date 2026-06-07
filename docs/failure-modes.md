# ProofPack AI — Failure Modes

A living catalog of how the system can fail and the mitigations in place.

**Context:** local dev uses Docker Compose (sync or async ingest); production uses Railway
(API + Celery worker + Postgres + Redis + S3 bucket) and Vercel (frontend).

| # | Failure mode | Impact | Mitigation |
| - | ------------ | ------ | ---------- |
| 1 | OCR misreads handwritten / low-quality scans | Wrong extracted figures | Surface OCR confidence; route low-confidence to Human Review; allow manual correction. |
| 2 | Retrieval misses the relevant clause/receipt | Unsupported or wrong answer | Hybrid retrieval (vector + keyword), re-rank, top-k tuning, Recall@K eval gate. |
| 3 | LLM hallucinates coverage/figures | User submits a bad claim | Strict citation requirement; faithfulness eval; refuse when no supporting chunk. |
| 4 | Citation points to the wrong source | Erodes trust | Citation accuracy eval; map every `[n]` to a concrete chunk/page/bbox. |
| 5 | External API (FEMA/NWS) down or rate-limited | Verification stalls | Cache responses; retries w/ backoff; degrade gracefully and flag "unverified". |
| 6 | Geocoding ambiguity (Nominatim) | Wrong location context | Cache; confirm address with user; respect usage limits. |
| 7 | Cost spikes on large claims | Unsustainable unit economics | Cost-per-packet tracking; chunk budget caps; cheaper models for extraction. |
| 8 | Schema drift in agent outputs | Downstream breakage | Pydantic schema validation; schema-validity eval. |
| 9 | Provider key missing/invalid | Hard failure | Provider abstraction with deterministic stub fallback; clear logging. |
| 10 | PII leakage in logs/traces | Compliance risk | Redact PII before tracing; scope retention. |
| 11 | Celery worker down (async ingest) | Uploads stuck at `processing` | Monitor worker logs; scale `proofpack-worker`; fall back to `INGEST_MODE=sync` for dev. |
| 12 | Railway `$PORT` misconfiguration | Healthcheck fails, API never binds | Use shell-form start (`sh -c 'uvicorn … --port ${PORT:-8000}'`) in `Dockerfile`; avoid literal `$PORT` in non-shell commands. |
| 13 | `app/storage` excluded from deploy | ImportError at boot | `.gitignore` only ignores `/backend/storage/` (upload dir), not `backend/app/storage/` Python package. |
| 14 | Embedding dim mismatch (768 vs 1536) | Insert/query errors on chunks | Set `EMBEDDING_DIM=768` with Gemini; recreate DB volume if vectors were stored at wrong dim. |
| 15 | Object store unreachable (S3) | Ingest/PDF download fails | Verify `S3_*` creds from Railway bucket; API and worker must share the same bucket config. |
