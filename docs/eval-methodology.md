# ProofPack AI — Evaluation Methodology

> Status: planned for Month 3. This document defines the harness so the system is
> built eval-first.

## Seeded dataset (`/evals`)

- 30 policy PDFs (or synthetic policy documents)
- 50 invoices / receipts
- 100 claim questions with gold answers + gold source spans
- 50 damage photos (labeled)
- 20 voice-note transcripts
- 10 disaster scenarios tied to FEMA/NWS records

## Metrics

| Metric | What it proves | Tool |
| ------ | -------------- | ---- |
| Retrieval Recall@5 | The right evidence is retrieved. | custom |
| MRR / nDCG | Best evidence ranks near the top. | custom |
| Citation accuracy | Claims are backed by the correct sources. | custom |
| Faithfulness | No invented/unsupported facts. | Ragas |
| Answer relevance | The answer addresses the question. | Ragas |
| Extraction F1 | Invoice/policy fields, dates, addresses extracted correctly. | custom |
| Tool-call success rate | Agents reliably call FEMA/NWS/geocoding. | custom |
| Schema validity | Agent outputs conform to JSON schemas. | pydantic |
| Human escalation precision | Low-confidence cases routed to review. | custom |
| Cost per completed packet | Production awareness. | tracing |

## CI eval gates

- Run a fast subset on every PR; fail the build if Recall@5 or faithfulness regress
  beyond a threshold versus the last green run.
- Store results in `/evals/results.md`.
