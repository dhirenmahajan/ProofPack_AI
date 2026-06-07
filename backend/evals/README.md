# ProofPack AI — Evaluation Harness (Month 3)

HTTP-driven evals that run against a **live backend**, so they exercise the real
ingestion → hybrid retrieval → cited QA → packet pipeline end to end. Runs with
**zero API keys** (deterministic stub providers), which makes it a reliable CI gate.

## Run locally

```bash
# 1. start the stack (or just backend + postgres + redis)
docker compose up --build -d

# 2. run the harness
cd backend
python -m evals.run_evals --base-url http://localhost:8000        # gated subset
python -m evals.run_evals --full --no-gate                        # full, report only
```

## Run against production

```bash
cd backend
python -m evals.run_evals --base-url https://proofpack-api-production.up.railway.app
```

Use a `GEMINI_API_KEY` in the Railway API env for Gemini judge faithfulness scoring.
Async ingest (`INGEST_MODE=async`) may require a short wait between upload and QA in manual runs.

Results are written to [`results.md`](results.md).

## What it measures

| Metric | Source | Gated |
| ------ | ------ | ----- |
| Recall@5 | gold source file present in returned citations | yes (>= 0.75) |
| Faithfulness | answer claims supported by cited evidence (heuristic; Gemini judge if `GEMINI_API_KEY` set) | yes (>= 0.5) |
| MRR / nDCG | rank of the gold source in citations | report |
| Citation precision | fraction of citations pointing at gold sources | report |
| Keyword grounding | gold keywords present in the answer | report |
| Schema validity | packet endpoints return validated models | report |

## Dataset

`dataset.py` holds the seeded `SUBSET` (synthetic policy + invoice with gold Q/A).
`get_cases(full=True)` is the hook for a larger corpus (the 30 policies / 50 invoices /
100 questions described in `docs/eval-methodology.md`).

## Gemini judge (optional)

Set `GEMINI_API_KEY` to score faithfulness with a Gemini judge LLM instead of the
token-overlap heuristic. The metric interface is Ragas-compatible (faithfulness /
answer relevance), so a Ragas backend can be dropped in later.
