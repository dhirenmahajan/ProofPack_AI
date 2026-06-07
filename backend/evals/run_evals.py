"""Run the ProofPack eval harness against a running backend.

Usage:
    python -m evals.run_evals [--base-url URL] [--full] [--no-gate]

Exits non-zero (when gating) if Recall@5 or faithfulness fall below threshold —
this is the CI quality gate. Writes a scorecard to evals/results.md.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.request
from pathlib import Path

from app.config import settings
from evals.dataset import EvalCase, get_cases
from evals.metrics import (
    citation_files,
    citation_precision,
    faithfulness,
    keyword_grounding,
    mrr,
    ndcg_at_k,
    recall_at_k,
)

# CI gate thresholds (the plan gates on Recall@5 + faithfulness).
GATE = {"recall_at_5": 0.75, "faithfulness": 0.5}

# Free-tier Gemini has low RPM; pace calls when a key is live (no-op on stubs/CI).
PACE_SECONDS = 4.0 if settings.gemini_api_key else 0.0


def _pace() -> None:
    if PACE_SECONDS:
        time.sleep(PACE_SECONDS)


def _post(base: str, path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def _get(base: str, path: str) -> dict | list:
    with urllib.request.urlopen(base + path) as r:
        return json.loads(r.read())


def _upload(base: str, claim_id: str, filename: str, content: str, source_type: str) -> dict:
    boundary = "----proofpackevalboundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="source_type"\r\n\r\n{source_type}\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: text/plain\r\n\r\n{content}\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    req = urllib.request.Request(
        f"{base}/claims/{claim_id}/documents",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def _wait_ready(base: str, claim_id: str, doc_id: str, timeout: int = 30) -> None:
    for _ in range(timeout):
        docs = _get(base, f"/claims/{claim_id}/documents")
        doc = next((d for d in docs if d["id"] == doc_id), None)
        if doc and doc["status"] == "ready":
            return
        if doc and doc["status"] == "failed":
            raise RuntimeError(f"ingestion failed for {doc_id}")
        time.sleep(1)
    raise RuntimeError(f"timed out waiting for {doc_id}")


def run_case(base: str, case: EvalCase) -> list[dict]:
    claim = _post(base, "/claims", case.claim)
    cid = claim["id"]
    content_by_file = {d.filename: d.content for d in case.documents}
    for doc in case.documents:
        up = _upload(base, cid, doc.filename, doc.content, doc.source_type)
        _wait_ready(base, cid, up["document"]["id"])

    rows: list[dict] = []
    for q in case.questions:
        _pace()
        resp = _post(base, f"/claims/{cid}/qa", {"question": q.question, "top_k": 5})
        files = citation_files(resp["citations"])
        # Judge faithfulness against the FULL cited source documents (the citation
        # snippet is truncated to ~280 chars, which under-represents the evidence).
        cited = {f for f in files if f in content_by_file}
        evidence = [content_by_file[f] for f in cited] or [
            c.get("snippet", "") for c in resp["citations"]
        ]
        rows.append(
            {
                "case": case.name,
                "question": q.question,
                "recall_at_5": recall_at_k(files, q.expect_files),
                "mrr": mrr(files, q.expect_files),
                "ndcg": ndcg_at_k(files, q.expect_files),
                "citation_precision": citation_precision(files, q.expect_files),
                "keyword_grounding": keyword_grounding(resp["answer"], q.expect_keywords),
                "faithfulness": faithfulness(resp["answer"], evidence),
                "provider": resp["provider"],
            }
        )

    # Schema-validity check: the packet endpoints return validated models on 200.
    schema_ok = 1.0
    try:
        run = _post(base, f"/claims/{cid}/packet", {"regenerate": True})
        packet = run.get("packet")
        if packet is None:  # async: poll
            for _ in range(60):
                r = _get(base, f"/claims/{cid}/packet/runs/{run['id']}")
                if r["status"] == "completed":
                    packet = r.get("packet")
                    break
                if r["status"] == "failed":
                    break
                time.sleep(1)
        schema_ok = 1.0 if (packet and "markdown" in packet and "confidence" in packet) else 0.0
    except Exception:  # noqa: BLE001
        schema_ok = 0.0
    for row in rows:
        row["schema_validity"] = schema_ok
    return rows


def aggregate(rows: list[dict]) -> dict:
    keys = [
        "recall_at_5",
        "mrr",
        "ndcg",
        "citation_precision",
        "keyword_grounding",
        "faithfulness",
        "schema_validity",
    ]
    return {k: round(statistics.mean(r[k] for r in rows), 4) for k in keys}


def write_results(rows: list[dict], agg: dict, gated: bool, passed: bool) -> None:
    out = Path(__file__).parent / "results.md"
    lines = ["# ProofPack AI — Eval Results", ""]
    lines.append(f"Provider: `{rows[0]['provider']}` · questions: {len(rows)}")
    lines.append("")
    lines.append("| Metric | Score | Gate |")
    lines.append("| --- | --- | --- |")
    for k, v in agg.items():
        gate = GATE.get(k)
        gate_str = f">= {gate}" if gate else "—"
        lines.append(f"| {k} | {v} | {gate_str} |")
    lines.append("")
    lines.append(f"**Gate: {'PASS' if passed else 'FAIL'}** (enforced: {gated})")
    out.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--no-gate", action="store_true")
    args = parser.parse_args()

    rows: list[dict] = []
    for case in get_cases(full=args.full):
        rows.extend(run_case(args.base_url, case))

    agg = aggregate(rows)
    passed = all(agg[k] >= thr for k, thr in GATE.items())
    write_results(rows, agg, gated=not args.no_gate, passed=passed)

    print("=== ProofPack Eval Scorecard ===")
    for k, v in agg.items():
        print(f"  {k:20s}: {v}")
    print(f"GATE: {'PASS' if passed else 'FAIL'}")

    if not args.no_gate and not passed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
