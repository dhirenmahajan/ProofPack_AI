# ProofPack AI — Evaluation Methodology

> **Status:** implemented in `backend/evals/`. CI runs a gated subset on every PR
> (`.github/workflows/ci.yml`). Optional Gemini judge when `GEMINI_API_KEY` is set.

## Harness (`backend/evals/`)

HTTP-driven evals against a **live backend** — exercises ingestion → hybrid retrieval →
cited QA → packet schema end to end. Key-free in CI (stub providers, `INGEST_MODE=sync`).

```bash
# Local
docker compose up --build -d
cd backend && python -m evals.run_evals --base-url http://localhost:8000

# Production (after deploy)
python -m evals.run_evals --base-url https://proofpack-api-production-ed2f.up.railway.app
```

Production backend deploys from GitHub (`dhirenmahajan/ProofPack_AI@main`); run evals after
Railway finishes building `proofpack-api`.

Results: `backend/evals/results.md`

## Seeded dataset (`dataset.py`)

Current **SUBSET** (CI gate):

- Synthetic policy PDF + invoice with gold Q/A pairs
- Gold source filenames for retrieval/citation checks

`get_cases(full=True)` is the extension hook for a larger corpus:

- 30 policy PDFs, 50 invoices/receipts, 100 claim questions, 50 damage photos,
  20 voice-note transcripts, 10 disaster scenarios tied to FEMA/NWS records

## Metrics

| Metric | What it proves | Tool | CI gate |
| ------ | -------------- | ---- | ------- |
| Retrieval Recall@5 | Right evidence retrieved | custom | yes (≥ 0.75) |
| Faithfulness | No unsupported facts | heuristic or Gemini judge | yes (≥ 0.5) |
| MRR / nDCG | Best evidence ranks high | custom | report |
| Citation precision | Citations point at gold sources | custom | report |
| Keyword grounding | Gold terms in answer | custom | report |
| Schema validity | Packet endpoints validate | pydantic | report |
| Extraction F1 | Structured field accuracy | custom | planned |
| Tool-call success rate | FEMA/NWS/geocode reliability | custom | planned |
| Human escalation precision | Low-confidence → review | custom | planned |
| Cost per completed packet | Unit economics | tracing | planned |

## CI eval gates

- Postgres + Redis service containers; smoke test + eval subset; frontend `npm run build`.
- Fail the build if Recall@5 or faithfulness regress below thresholds.
- Store/update results in `backend/evals/results.md`.
