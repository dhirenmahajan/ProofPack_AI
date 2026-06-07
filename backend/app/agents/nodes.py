"""Workflow nodes. Each is a small agent: state in, partial state update out.

Nodes receive a DB session (bound via closure in graph.py) plus the running
ClaimState. They never raise: a node failure records a note and yields neutral
output so the graph reaches a packet (possibly flagged for human review).
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.checklist import DESCRIPTIONS, required_for
from app.agents.extraction import extract_document
from app.agents.state import ClaimState
from app.db.models import Chunk, Document, ExtractionResult, VerificationResult
from app.services.external import fema_disaster_declarations, geocode, nws_context
from app.services.qa import answer_question

logger = logging.getLogger("proofpack.agents.nodes")

COVERAGE_QUESTIONS = [
    "Does this policy cover the type of damage described, and under what conditions?",
    "What is the deductible that applies to this loss?",
    "What documentation or deadlines are required to file the claim?",
]


def _note(state: ClaimState, msg: str) -> list[str]:
    notes = list(state.get("notes", []))
    notes.append(msg)
    return notes


def intake(db: Session, state: ClaimState) -> dict:
    """Geocode the claim location (free Nominatim) for downstream verification."""
    geo = geocode(state.get("location"))
    note = "Location geocoded." if geo else "Location could not be geocoded."
    return {"geocode": geo, "notes": _note(state, note)}


def extraction(db: Session, state: ClaimState) -> dict:
    """Per-document structured extraction; persists ExtractionResult rows."""
    claim_id = uuid.UUID(state["claim_id"])
    docs = list(
        db.execute(select(Document).where(Document.claim_id == claim_id)).scalars()
    )
    extractions: list[dict] = []
    for doc in docs:
        chunks = list(
            db.execute(
                select(Chunk)
                .where(Chunk.document_id == doc.id)
                .order_by(Chunk.chunk_index)
            ).scalars()
        )
        text = "\n".join(c.text for c in chunks)
        fields, confidence, provider = extract_document(text, doc.source_type)
        db.add(
            ExtractionResult(
                claim_id=claim_id,
                document_id=doc.id,
                source_type=doc.source_type,
                fields=fields,
                confidence=confidence,
                provider=provider,
            )
        )
        extractions.append(
            {
                "document_id": str(doc.id),
                "filename": doc.filename,
                "source_type": doc.source_type,
                "fields": fields,
                "confidence": confidence,
                "provider": provider,
            }
        )
    db.commit()
    return {"extractions": extractions, "notes": _note(state, f"Extracted {len(docs)} document(s).")}


def verification(db: Session, state: ClaimState) -> dict:
    """Cross-check the incident against FEMA (authoritative) + NWS (supplementary)."""
    geo = state.get("geocode")
    state_code = geo.get("state_code") if geo else None
    fema = fema_disaster_declarations(
        state_code, state.get("incident_date"), state.get("incident_type")
    )
    nws = (
        nws_context(geo.get("lat"), geo.get("lon"))
        if geo
        else {"resolved": False, "error": "no coordinates"}
    )
    verified = bool(fema.get("matched"))
    if verified:
        n = len(fema.get("declarations", []))
        summary = f"FEMA confirms {n} matching federal disaster declaration(s) for the area/date."
    else:
        summary = "No matching FEMA declaration found — event context is UNVERIFIED."

    db.add(
        VerificationResult(
            claim_id=uuid.UUID(state["claim_id"]),
            geocode=geo,
            fema=fema,
            nws=nws,
            verified=verified,
            summary=summary,
        )
    )
    db.commit()
    return {
        "verification": {"verified": verified, "summary": summary, "fema": fema, "nws": nws},
        "notes": _note(state, summary),
    }


def policy_rag(db: Session, state: ClaimState) -> dict:
    """Answer standard coverage questions using the claim-scoped cited RAG."""
    claim_id = uuid.UUID(state["claim_id"])
    coverage_qa: list[dict] = []
    citations: list[dict] = []
    for q in COVERAGE_QUESTIONS:
        try:
            resp = answer_question(db, claim_id, q, top_k=5)
            cites = [c.model_dump(mode="json") for c in resp.citations]
            coverage_qa.append(
                {"question": q, "answer": resp.answer, "provider": resp.provider, "citations": cites}
            )
            citations.extend(cites)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Coverage QA failed for %r: %s", q, exc)
            coverage_qa.append({"question": q, "answer": "(unavailable)", "citations": []})
    return {
        "coverage_qa": coverage_qa,
        "citations": citations,
        "notes": _note(state, f"Answered {len(coverage_qa)} coverage question(s)."),
    }


def gap_analysis(db: Session, state: ClaimState) -> dict:
    """Flag required evidence (by source_type) that is missing for this incident."""
    present = {e["source_type"] for e in state.get("extractions", [])}
    required = required_for(state.get("incident_type"))
    gaps = [
        {"source_type": st, "description": DESCRIPTIONS.get(st, st), "status": "missing"}
        for st in required
        if st not in present
    ]
    return {"gaps": gaps, "notes": _note(state, f"{len(gaps)} evidence gap(s) detected.")}


def report_writer(db: Session, state: ClaimState) -> dict:
    """Assemble the packet markdown deterministically; compute confidence + review flag."""
    from app.agents.report import build_markdown, score_confidence

    markdown = build_markdown(state)
    confidence = score_confidence(state)
    verified = bool(state.get("verification", {}).get("verified"))
    gaps = state.get("gaps", [])
    needs_review = (confidence < 0.6) or (not verified) or bool(gaps)
    return {
        "report_markdown": markdown,
        "confidence": confidence,
        "needs_review": needs_review,
        "notes": _note(state, f"Packet drafted (confidence={confidence:.2f})."),
    }


def human_review(db: Session, state: ClaimState) -> dict:
    """Terminal checkpoint: annotate why review is (or isn't) required."""
    if state.get("needs_review"):
        msg = "Flagged for human review (low confidence, unverified, or missing evidence)."
    else:
        msg = "Auto-approvable: verified, complete, and high-confidence."
    return {"notes": _note(state, msg)}
