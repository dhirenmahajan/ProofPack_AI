"""Deterministic claim-packet assembly + confidence scoring.

The markdown is built deterministically from workflow state so structure and
citations are reliable regardless of provider. (A model may polish prose later;
the backbone never depends on it.)
"""

from __future__ import annotations

from typing import Any

from app.agents.checklist import required_for
from app.agents.state import ClaimState


def _fmt_fields(fields: dict[str, Any]) -> str:
    lines = []
    for k, v in fields.items():
        if v in (None, "", [], {}):
            continue
        if isinstance(v, list):
            v = ", ".join(str(x) for x in v[:8])
        lines.append(f"  - **{k}**: {v}")
    return "\n".join(lines) if lines else "  - _(no fields extracted)_"


def build_markdown(state: ClaimState) -> str:
    parts: list[str] = []
    parts.append(f"# Disaster Insurance Claim Packet — {state.get('title', 'Claim')}")

    parts.append("\n## 1. Claim Summary\n")
    parts.append(f"- **Claimant**: {state.get('claimant_name') or '—'}")
    parts.append(f"- **Incident type**: {state.get('incident_type') or '—'}")
    parts.append(f"- **Incident date**: {state.get('incident_date') or '—'}")
    parts.append(f"- **Location**: {state.get('location') or '—'}")
    geo = state.get("geocode")
    if geo:
        parts.append(f"- **Geocoded**: {geo.get('display_name')} ({geo.get('lat')}, {geo.get('lon')})")

    verification = state.get("verification", {})
    parts.append("\n## 2. Event Verification\n")
    badge = "VERIFIED" if verification.get("verified") else "UNVERIFIED"
    parts.append(f"**Status: {badge}.** {verification.get('summary', '')}")
    fema = verification.get("fema", {})
    for d in (fema.get("declarations") or [])[:5]:
        parts.append(
            f"- FEMA {d.get('femaDeclarationString', '?')}: {d.get('declarationTitle', '')} "
            f"({d.get('incidentType')}, {d.get('state')}, began {d.get('incidentBeginDate', '')[:10]})"
        )
    nws = verification.get("nws", {})
    if nws.get("resolved"):
        parts.append(f"- NWS office: {nws.get('office')} · active alerts: {nws.get('active_alerts', 0)}")

    parts.append("\n## 3. Extracted Evidence\n")
    extractions = state.get("extractions", [])
    if not extractions:
        parts.append("_No documents ingested._")
    for e in extractions:
        parts.append(f"### {e['filename']} ({e['source_type']}, confidence {e.get('confidence', 0):.2f})")
        parts.append(_fmt_fields(e.get("fields", {})))

    parts.append("\n## 4. Coverage Analysis\n")
    for qa in state.get("coverage_qa", []):
        parts.append(f"**Q: {qa['question']}**")
        parts.append(qa.get("answer", ""))
        cites = qa.get("citations", [])
        if cites:
            cite_str = "; ".join(
                f"[{c['index']}] {c['filename']}"
                + (f" p.{c['page_number']}" if c.get("page_number") is not None else "")
                for c in cites
            )
            parts.append(f"_Sources: {cite_str}_")
        parts.append("")

    parts.append("## 5. Documentation Gaps\n")
    required = required_for(state.get("incident_type"))
    gaps = {g["source_type"]: g for g in state.get("gaps", [])}
    for st in required:
        if st in gaps:
            parts.append(f"- [ ] MISSING — {gaps[st]['description']}")
        else:
            parts.append(f"- [x] Present — {st}")

    parts.append("\n## 6. Confidence & Review\n")
    parts.append(f"- **Overall confidence**: {state.get('confidence', 0):.2f}")
    parts.append(
        f"- **Human review**: {'REQUIRED' if state.get('needs_review', True) else 'not required'}"
    )

    return "\n".join(parts)


def score_confidence(state: ClaimState) -> float:
    extractions = state.get("extractions", [])
    if extractions:
        extract_conf = sum(e.get("confidence", 0.0) for e in extractions) / len(extractions)
    else:
        extract_conf = 0.0

    verified = 1.0 if state.get("verification", {}).get("verified") else 0.3

    coverage = state.get("coverage_qa", [])
    answered = [c for c in coverage if c.get("citations")]
    coverage_conf = (len(answered) / len(coverage)) if coverage else 0.0

    required = required_for(state.get("incident_type"))
    gaps = state.get("gaps", [])
    gap_conf = 1.0 - (len(gaps) / len(required)) if required else 1.0

    score = 0.35 * extract_conf + 0.25 * verified + 0.25 * coverage_conf + 0.15 * gap_conf
    return round(max(0.0, min(1.0, score)), 3)
