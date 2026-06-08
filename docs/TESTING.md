<!-- generated-by: gsd-doc-writer -->
# Testing

ProofPack AI does **not** use a unit-test framework (there is no `pytest`, `unittest`,
or JS test runner configured). Instead, quality is enforced by two HTTP-driven checks
that run against a **live backend** and exercise the real pipeline end to end —
ingestion → hybrid retrieval → cited QA → multi-agent packet generation:

- **Smoke test** (`backend/scripts/smoke_test.py`) — a fast end-to-end sanity check.
- **Eval harness** (`backend/evals/run_evals.py`) — a scored quality gate on retrieval
  and faithfulness.

Both run **key-free** on deterministic stub providers, which makes them reliable in CI.
A GitHub Actions workflow (`.github/workflows/ci.yml`) runs both against Postgres + Redis
service containers on every push to `main` and every pull request, plus a frontend
type-check and build.

## Test framework and setup

There is no test framework to install. The checks are plain Python scripts that talk to
a running backend over HTTP using the standard library (`urllib`), so they need:

1. The backend Python dependencies installed (`pip install -r backend/requirements.txt`)
   — used to import `app.config` and the eval scoring modules.
2. A **running backend** reachable over HTTP (default `http://localhost:8000`), backed by
   Postgres (with the `pgvector` extension) and — for async ingestion — Redis and a Celery
   worker.

The simplest way to satisfy the runtime dependencies is the full Docker stack:

```bash
cp .env.example .env
docker compose up --build -d
# Backend + docs on :8000/docs · Postgres :5432 · Redis · Celery worker · frontend :3000
```

Both checks tolerate either ingestion mode: they poll each uploaded document until its
status is `ready` before asking a question. In Docker the default is `INGEST_MODE=async`
(the Celery worker performs ingestion); `INGEST_MODE=sync` runs ingestion inline in the
upload request and needs no worker.

## Running tests

All commands assume the backend is already running and reachable.

### Smoke test

Creates a claim, uploads a sample homeowners policy, waits for ingestion to finish
(polling document status up to 30 seconds), then asks a flood-coverage question and
asserts that the answer comes back with at least one citation. On success it prints
`SMOKE_TEST_PASSED`.

```bash
# Against a local backend (default base URL)
python backend/scripts/smoke_test.py

# Against any backend by passing a base URL
python backend/scripts/smoke_test.py http://localhost:8000
python backend/scripts/smoke_test.py https://proofpack-api-production-ed2f.up.railway.app
```

### Eval harness (quality gate)

Runs the seeded evaluation dataset through the live backend, scores retrieval and answer
faithfulness, writes a scorecard to `backend/evals/results.md`, prints it to stdout, and
**exits non-zero if the gated metrics regress below threshold**. Run it as a module from
the `backend/` directory (it imports `app.config` and `evals.*`):

```bash
cd backend

# Gated subset (this is the CI gate) — exits 1 if Recall@5 or faithfulness fail
python -m evals.run_evals --base-url http://localhost:8000

# Report only, no gate (does not fail on threshold)
python -m evals.run_evals --base-url http://localhost:8000 --no-gate

# Full dataset hook (currently returns the same SUBSET; extend dataset.py to grow it)
python -m evals.run_evals --base-url http://localhost:8000 --full --no-gate

# Against production
python -m evals.run_evals --base-url https://proofpack-api-production-ed2f.up.railway.app
```

Notes:

- When a `GEMINI_API_KEY` is present in the backend env, the harness paces QA calls
  (~4s apart) to respect free-tier Gemini rate limits and uses a Gemini judge for
  faithfulness scoring; on stub providers there is no pacing.
- For production runs against `proofpack-api`, run the harness only after a GitHub →
  Railway deploy has finished building.

## Writing new tests

There is no per-function unit-test convention. To extend coverage, add to the
HTTP-driven harness rather than introducing a new framework:

- **Add eval cases** — edit `backend/evals/dataset.py`. Each `EvalCase` carries a
  `claim` dict, a list of `EvalDoc` (filename, `source_type`, content), and a list of
  `EvalQuestion`. Each question declares gold `expect_files` (used for retrieval/citation
  metrics) and gold `expect_keywords` (used for grounding). The seeded `SUBSET` is the
  CI gate set; `get_cases(full=True)` is the hook for a larger corpus.
- **Add or change a metric** — edit `backend/evals/metrics.py`, which holds pure scoring
  functions (`recall_at_k`, `mrr`, `ndcg_at_k`, `citation_precision`, `keyword_grounding`,
  `faithfulness`). The faithfulness function falls back to a deterministic token-overlap
  heuristic when no Gemini key is set, so metrics stay offline and reproducible.
- Keep new cases small and deterministic so they remain runnable in CI on stub providers.

When adding a new backend feature, the recommended check is to extend the eval dataset
with a question whose gold source proves the feature works end to end through the public
HTTP API.

## Coverage requirements

No line/branch coverage threshold is configured (there is no coverage tool in the
project). Quality is instead gated on the eval harness scorecard. The harness exits
non-zero — failing the build — when either gated metric drops below its threshold:

| Metric        | Threshold | Gated | What it measures                                                  |
| ------------- | --------- | ----- | ----------------------------------------------------------------- |
| Recall@5      | >= 0.75   | Yes   | A gold source file appears among the returned citations           |
| Faithfulness  | >= 0.5    | Yes   | Answer claims are supported by cited evidence (heuristic or judge) |
| MRR           | —         | No    | Rank of the first gold source in citations (report only)          |
| nDCG          | —         | No    | Ranking quality of gold sources in citations (report only)        |
| Citation precision | —    | No    | Fraction of citations pointing at gold sources (report only)      |
| Keyword grounding  | —    | No    | Gold keywords present in the answer (report only)                 |
| Schema validity    | —    | No    | Packet endpoints return validated models (report only)            |

Gate thresholds are defined in `backend/evals/run_evals.py`
(`GATE = {"recall_at_5": 0.75, "faithfulness": 0.5}`). Pass `--no-gate` to run the
harness for reporting without failing on threshold.

## CI integration

The `ci` workflow (`.github/workflows/ci.yml`) runs on every push to `main` and on every
pull request. It has two jobs:

**`backend-evals`** (Ubuntu) brings up service containers and runs both checks key-free:

- Service containers: `pgvector/pgvector:pg16` (Postgres on 5432) and `redis:7-alpine`
  (Redis on 6379), each with health checks.
- Environment: stub providers (no API keys), `INGEST_MODE=sync` (so no Celery worker is
  needed), `EMBEDDING_DIM=768`, local storage.
- Steps: install Python 3.11 and Tesseract → `pip install -r requirements.txt` → start
  the backend with `uvicorn app.main:app` and wait for `/health` → run
  `python scripts/smoke_test.py http://localhost:8000` → run
  `python -m evals.run_evals --base-url http://localhost:8000` (the gate) → upload
  `backend/evals/results.md` as a build artifact (always, even on failure).

**`frontend-build`** (Ubuntu) installs the frontend deps, runs `npx tsc --noEmit`, and
runs `npm run build`.

A regression in Recall@5 or faithfulness causes `python -m evals.run_evals` to exit
non-zero, which fails the `backend-evals` job and the overall build.

## Next steps

- See [GETTING-STARTED.md](GETTING-STARTED.md) for prerequisites and first-run setup.
- See [DEVELOPMENT.md](DEVELOPMENT.md) for local development and build commands.
- See [ARCHITECTURE.md](ARCHITECTURE.md) for how the ingestion → retrieval → QA →
  packet pipeline that these checks exercise fits together.
