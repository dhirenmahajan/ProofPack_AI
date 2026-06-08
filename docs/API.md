<!-- generated-by: gsd-doc-writer -->
# API Reference

The ProofPack AI backend is a [FastAPI](https://fastapi.tiangolo.com/) application
(`title: "ProofPack AI"`, `version: 0.1.0`). It exposes a JSON REST API for managing
disaster insurance **claims**, ingesting **documents** into a per-claim RAG index,
asking **cited questions** against that evidence, and running a multi-agent workflow
that produces a reviewable **claim packet** (markdown + PDF).

An interactive, always-current OpenAPI UI is served at **`/docs`**
(`<base_url>/docs`), with the raw schema at `/openapi.json`. This document mirrors
the route handlers and Pydantic models in the source; `/docs` is authoritative if the
two ever diverge.

Base URLs:

| Environment | Base URL |
| ----------- | -------- |
| Local | `http://localhost:8000` |
| Production | `https://proofpack-api-production-ed2f.up.railway.app` <!-- VERIFY: production API base URL --> |

## Authentication

**None.** The API ships with no authentication or authorization layer. There are no
API keys, tokens, sessions, or login routes in the backend. CORS is fully open
(`allow_origins=["*"]`, all methods and headers allowed), so any origin can call the
API directly.

Access is instead scoped by resource: every document, QA, and packet route is nested
under a `claim_id` path parameter, and retrieval is always claim-scoped. There is no
cross-claim isolation enforced by identity — knowing a claim's UUID is sufficient to
read or mutate it.

> If you deploy this publicly, add an authentication layer (reverse-proxy auth,
> gateway, or app middleware) before exposing it to untrusted clients.

## Endpoints overview

| Method | Path | Description | Auth Required |
| ------ | ---- | ----------- | ------------- |
| `GET` | `/` | Service metadata (name + key links) | No |
| `GET` | `/health` | Liveness check with version | No |
| `GET` | `/providers` | Active LLM / embeddings / OCR implementations | No |
| `POST` | `/claims` | Create a claim | No |
| `GET` | `/claims` | List all claims (newest first) | No |
| `GET` | `/claims/{claim_id}` | Get one claim | No |
| `GET` | `/claims/{claim_id}/documents` | List a claim's documents | No |
| `POST` | `/claims/{claim_id}/documents` | Upload + ingest a document (multipart) | No |
| `POST` | `/claims/{claim_id}/qa` | Cited question-answering over the claim | No |
| `POST` | `/claims/{claim_id}/packet` | Start the claim-packet workflow run | No |
| `GET` | `/claims/{claim_id}/packet` | List generated packets (newest first) | No |
| `GET` | `/claims/{claim_id}/packet/latest` | Get the most recent packet | No |
| `GET` | `/claims/{claim_id}/packet/runs/{run_id}` | Poll a workflow run's status | No |
| `POST` | `/claims/{claim_id}/packet/{packet_id}/review` | Approve / edit a packet | No |
| `GET` | `/claims/{claim_id}/packet/{packet_id}/pdf` | Download the packet PDF | No |

All `{claim_id}`, `{run_id}`, and `{packet_id}` path parameters are UUIDs.

## Request / response formats

Unless noted otherwise, request and response bodies are `application/json`. The
document upload endpoint takes `multipart/form-data`, and the PDF download endpoint
returns `application/pdf`. Field names below are taken verbatim from
`backend/app/schemas.py`.

### Service metadata

#### `GET /`

Returns service metadata and key entry points. No parameters.

```json
{
  "name": "ProofPack AI",
  "docs": "/docs",
  "health": "/health",
  "providers": "/providers"
}
```

#### `GET /health`

Liveness probe. Returns `200` with the package version.

```json
{ "status": "ok", "version": "0.1.0" }
```

#### `GET /providers`

Reports which concrete provider implementation is currently live for each model
capability (hosted vs. offline stub). Names are the provider classes' `name`
attribute — e.g. `gemini-2.5-flash`, `gemini-embedding-001`, or `stub` when no API
key is configured. <!-- VERIFY: exact provider name strings depend on configured keys at runtime -->

```json
{
  "llm": "stub",
  "embeddings": "stub",
  "ocr": "stub"
}
```

### Claims

#### `POST /claims`

Create a new claim. Returns `201 Created`.

Request body (`ClaimCreate`):

| Field | Type | Required | Constraints |
| ----- | ---- | -------- | ----------- |
| `title` | string | Yes | 1–255 chars |
| `claimant_name` | string \| null | No | |
| `incident_type` | string \| null | No | |
| `incident_date` | date (`YYYY-MM-DD`) \| null | No | |
| `location` | string \| null | No | |

```json
{
  "title": "Hurricane roof damage — 123 Main St",
  "claimant_name": "Jane Doe",
  "incident_type": "hurricane",
  "incident_date": "2025-09-28",
  "location": "Tampa, FL"
}
```

Response body (`ClaimOut`):

```json
{
  "id": "4d2c...",
  "title": "Hurricane roof damage — 123 Main St",
  "claimant_name": "Jane Doe",
  "incident_type": "hurricane",
  "incident_date": "2025-09-28",
  "location": "Tampa, FL",
  "status": "intake",
  "created_at": "2026-06-07T12:00:00Z"
}
```

`status` is server-assigned and defaults to `intake`. It advances over the claim's
lifecycle (e.g. to `review` or `ready`) when a packet workflow completes.

#### `GET /claims`

List all claims, newest first. Returns `200` with an array of `ClaimOut`. No
parameters.

#### `GET /claims/{claim_id}`

Get a single claim by UUID. Returns `200` with a `ClaimOut`, or `404` if the claim
does not exist.

#### `GET /claims/{claim_id}/documents`

List the documents attached to a claim, newest first. Returns `200` with an array of
`DocumentOut`, or `404` if the claim does not exist.

### Documents

#### `POST /claims/{claim_id}/documents`

Upload a file and ingest it into the claim's RAG index. Uses `multipart/form-data`.

Form fields:

| Field | Type | Required | Default | Notes |
| ----- | ---- | -------- | ------- | ----- |
| `file` | file | Yes | — | The uploaded document; must be non-empty |
| `source_type` | string (form field) | No | `other` | Must be in the allowed vocabulary below |

`source_type` is a fixed vocabulary enforced by the route. Allowed values:

`policy`, `invoice`, `receipt`, `photo`, `inspection`, `permit`, `voicenote`, `other`

Example (cURL):

```bash
curl -X POST "http://localhost:8000/claims/{claim_id}/documents" \
  -F "file=@policy.pdf" \
  -F "source_type=policy"
```

Response body (`UploadResponse`):

```json
{
  "document": {
    "id": "8a1f...",
    "claim_id": "4d2c...",
    "filename": "policy.pdf",
    "content_type": "application/pdf",
    "source_type": "policy",
    "page_count": 12,
    "ocr_confidence": 0.97,
    "status": "ready",
    "created_at": "2026-06-07T12:01:00Z"
  },
  "chunks_created": 34
}
```

`DocumentOut.status` reflects the ingestion lifecycle: `processing` while OCR /
chunking / embedding are in flight, `ready` once chunks are written, or `failed`.
`page_count` and `ocr_confidence` are populated during processing and may be `null`
until then.

**Sync vs. async ingestion (controlled by `INGEST_MODE`):**

- **Sync mode** (`INGEST_MODE=sync`): the file is OCR'd, chunked, and embedded inline
  before the response returns. `chunks_created` is the actual number of chunks
  written, and `document.status` is typically `ready`.
- **Async mode** (`INGEST_MODE=async`, the Compose/production default): the blob and
  `Document` row are persisted immediately, processing is handed to a Celery worker,
  and the response returns right away with **`chunks_created: 0`** and
  `document.status: "processing"`. Poll `GET /claims/{claim_id}/documents` until the
  document's `status` becomes `ready` (or `failed`).

Errors:

| Status | Condition |
| ------ | --------- |
| `404` | Claim not found |
| `422` | `source_type` not in the allowed vocabulary |
| `422` | Uploaded file is empty |

### Question-answering

#### `POST /claims/{claim_id}/qa`

Ask a natural-language question against the claim's ingested evidence. Runs a
claim-scoped hybrid search (pgvector + full-text, fused with Reciprocal Rank Fusion),
calls the active LLM, and returns the answer with inline citation metadata.

Request body (`QARequest`):

| Field | Type | Required | Default | Constraints |
| ----- | ---- | -------- | ------- | ----------- |
| `question` | string | Yes | — | min length 1 |
| `top_k` | integer | No | `5` | 1–20 |

```json
{ "question": "What is my hurricane deductible?", "top_k": 5 }
```

Response body (`QAResponse`):

```json
{
  "question": "What is my hurricane deductible?",
  "answer": "Your hurricane deductible is 2% of the dwelling coverage [1].",
  "provider": "stub",
  "citations": [
    {
      "index": 1,
      "chunk_id": "c0fe...",
      "document_id": "8a1f...",
      "filename": "policy.pdf",
      "source_type": "policy",
      "page_number": 3,
      "snippet": "Hurricane deductible: 2% of Coverage A ...",
      "score": 0.8421
    }
  ],
  "latency_ms": 142
}
```

`QAResponse` fields:

| Field | Type | Notes |
| ----- | ---- | ----- |
| `question` | string | Echoes the input question |
| `answer` | string | LLM answer with inline `[n]` citation markers |
| `provider` | string | Name of the LLM provider that produced the answer |
| `citations` | array of `Citation` | One entry per cited source |
| `latency_ms` | integer | End-to-end latency for the QA call |

Each `Citation`:

| Field | Type | Notes |
| ----- | ---- | ----- |
| `index` | integer | 1-based marker matching the `[n]` in `answer` |
| `chunk_id` | UUID | Source chunk |
| `document_id` | UUID | Source document |
| `filename` | string | Source document filename |
| `source_type` | string | One of the `source_type` vocabulary values |
| `page_number` | integer \| null | Page the snippet came from, when known |
| `snippet` | string | Up to ~280 chars of the source chunk |
| `score` | float | Fused retrieval relevance score (RRF), rounded to 4 dp |

There is no separate top-level `confidence` field on the QA response; relevance is
conveyed per-citation via the `score` field, and the answer carries inline `[n]`
citation markers. (A packet-level `confidence` score is exposed by the workflow
endpoints below.)

Errors: `404` if the claim does not exist; `422` for an empty question or `top_k`
outside the 1–20 range.

### Claim-packet workflow

These endpoints drive the multi-agent LangGraph workflow that verifies the incident
against public data (FEMA/NWS), analyses coverage, detects evidence gaps, and writes a
cited, human-reviewable packet. A run produces an `AgentRun` record; a successful run
yields a `ClaimPacket`.

#### `POST /claims/{claim_id}/packet`

Start a packet workflow run. Returns `200` with an `AgentRunOut`.

Request body (`PacketRequest`, optional — may be omitted or sent as `null`):

| Field | Type | Default | Notes |
| ----- | ---- | ------- | ----- |
| `regenerate` | boolean | `false` | Reserved for future options; currently unused |

Execution mode mirrors `INGEST_MODE`:

- **Sync mode:** the workflow runs inline and the returned `AgentRun` is already
  `completed` (or `failed`), with `packet` populated on success.
- **Async mode:** an `AgentRun` is created with `status: "running"` and the workflow
  is enqueued to a Celery worker. Poll the run endpoint below until it reaches a
  terminal state.

Response body (`AgentRunOut`):

```json
{
  "id": "9bb2...",
  "claim_id": "4d2c...",
  "workflow": "claim_packet",
  "status": "running",
  "error": null,
  "latency_ms": null,
  "created_at": "2026-06-07T12:05:00Z",
  "packet": null
}
```

`AgentRunOut` fields:

| Field | Type | Notes |
| ----- | ---- | ----- |
| `id` | UUID | The run id (use with the poll endpoint) |
| `claim_id` | UUID | Owning claim |
| `workflow` | string | Workflow name; defaults to `claim_packet` |
| `status` | string | `running` \| `completed` \| `failed` |
| `error` | string \| null | Failure message when `status` is `failed` |
| `latency_ms` | integer \| null | Set on completion |
| `created_at` | datetime | |
| `packet` | `ClaimPacketOut` \| null | Populated once the run completes |

#### `GET /claims/{claim_id}/packet/runs/{run_id}`

Poll a workflow run's status. Returns `200` with an `AgentRunOut`. Returns `404` if
the run id is unknown or does not belong to `claim_id`.

#### `GET /claims/{claim_id}/packet`

List all packets generated for the claim, newest first. Returns `200` with an array
of `ClaimPacketOut`, or `404` if the claim does not exist.

#### `GET /claims/{claim_id}/packet/latest`

Get the most recently created packet. Returns `200` with a `ClaimPacketOut`, `404` if
the claim does not exist, or `404` (`"No packet generated yet"`) if no packet exists.

`ClaimPacketOut` fields:

| Field | Type | Notes |
| ----- | ---- | ----- |
| `id` | UUID | Packet id |
| `claim_id` | UUID | Owning claim |
| `agent_run_id` | UUID \| null | The run that produced it |
| `markdown` | string | The packet body (markdown) |
| `confidence` | float \| null | Overall packet confidence score |
| `needs_review` | boolean | `true` until a human approves |
| `status` | string | `draft` \| `approved` |
| `citations` | array | Evidence citations backing the packet |
| `gaps` | array | Detected evidence gaps |
| `verification` | object \| null | FEMA/NWS/geocode verification outcome |
| `has_pdf` | boolean | Computed: `true` when a stored PDF exists |
| `created_at` | datetime | |

The internal `storage_path` is excluded from responses; presence of a PDF is signalled
by the computed `has_pdf` field.

#### `POST /claims/{claim_id}/packet/{packet_id}/review`

Human-review checkpoint. Optionally apply edits to the packet body and/or approve it.
Returns `200` with the updated `ClaimPacketOut`.

Request body (`PacketReviewRequest`):

| Field | Type | Default | Notes |
| ----- | ---- | ------- | ----- |
| `approve` | boolean | `true` | When `true`, sets `status: "approved"` and `needs_review: false` |
| `markdown` | string \| null | `null` | When provided, replaces the packet body |

```json
{ "approve": true, "markdown": "# Edited Claim Packet\n..." }
```

Returns `404` if the packet id is unknown or does not belong to `claim_id`.

#### `GET /claims/{claim_id}/packet/{packet_id}/pdf`

Download the rendered packet PDF. On success returns `200` with body media type
`application/pdf` and header
`Content-Disposition: inline; filename="claim_packet.pdf"`.

Errors:

| Status | Condition |
| ------ | --------- |
| `404` | Packet not found or not owned by `claim_id` |
| `404` | Packet has no stored PDF (`No PDF for this packet`) |
| `404` | PDF could not be read from object storage (`PDF unavailable: ...`) |

## Error codes

Errors use FastAPI's standard JSON error envelope:

```json
{ "detail": "Claim not found" }
```

Validation errors (`422`) follow FastAPI's structured shape:

```json
{
  "detail": [
    { "loc": ["body", "title"], "msg": "...", "type": "..." }
  ]
}
```

Status codes used across the API:

| Status | Meaning | When |
| ------ | ------- | ---- |
| `200 OK` | Success | Reads, QA, packet run/review, PDF download |
| `201 Created` | Resource created | `POST /claims` |
| `404 Not Found` | Resource missing | Unknown claim, document, run, packet, or PDF |
| `422 Unprocessable Entity` | Validation failed | Bad request body, invalid `source_type`, empty file, out-of-range `top_k` |

A key design contract of this backend is that ingestion, OCR, external API calls, and
agent nodes **degrade rather than crash**: failures return placeholders, `unverified`,
or neutral state instead of surfacing 5xx errors out of a request. As a result,
unexpected `500` responses are not part of the normal API surface.

## Rate limits

**None.** No rate-limiting middleware or library is configured in the backend
(no `express-rate-limit`-equivalent such as `slowapi` or a gateway throttle). Requests
are unthrottled at the application layer.

Note that downstream public data providers used by the agent workflow — FEMA, NWS, and
Nominatim — are keyless and may apply their own rate limits; the backend mitigates this
with Redis caching and `tenacity` retry/backoff. Any hosting-platform or
reverse-proxy rate limits applied in front of the API are deployment-specific.
<!-- VERIFY: any platform-level (Railway/Vercel/proxy) rate limits applied in production -->
