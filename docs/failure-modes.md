# ProofPack AI — Failure Modes

A living catalog of how the system can fail and the mitigations in place / planned.

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
