"""Orchestrate a claim-packet workflow run and persist its artifacts."""

from __future__ import annotations

import logging
import time
import uuid

from sqlalchemy.orm import Session

from app.agents.graph import run_graph
from app.agents.pdf import render_pdf_and_store
from app.agents.state import ClaimState
from app.config import settings
from app.db.models import AgentRun, Claim, ClaimPacket

logger = logging.getLogger("proofpack.agents.runner")


def _initial_state(claim: Claim) -> ClaimState:
    return {
        "claim_id": str(claim.id),
        "title": claim.title,
        "claimant_name": claim.claimant_name,
        "incident_type": claim.incident_type,
        "incident_date": claim.incident_date.isoformat() if claim.incident_date else None,
        "location": claim.location,
        "notes": [],
    }


def run_claim_packet(db: Session, agent_run_id: uuid.UUID) -> ClaimPacket:
    """Execute the workflow for an existing AgentRun; persist the ClaimPacket."""
    run = db.get(AgentRun, agent_run_id)
    if run is None:
        raise ValueError(f"AgentRun {agent_run_id} not found")
    claim = db.get(Claim, run.claim_id)
    if claim is None:
        raise ValueError(f"Claim {run.claim_id} not found")

    started = time.perf_counter()
    try:
        final = run_graph(db, _initial_state(claim))
        storage_path = render_pdf_and_store(str(claim.id), final.get("report_markdown", ""))

        packet = ClaimPacket(
            claim_id=claim.id,
            agent_run_id=run.id,
            markdown=final.get("report_markdown", ""),
            storage_path=storage_path,
            confidence=final.get("confidence"),
            needs_review=final.get("needs_review", True),
            citations=final.get("citations", []),
            gaps=final.get("gaps", []),
            verification=final.get("verification"),
        )
        db.add(packet)

        run.status = "completed"
        run.state = {
            k: final.get(k)
            for k in ("notes", "confidence", "needs_review", "gaps", "verification")
        }
        run.latency_ms = int((time.perf_counter() - started) * 1000)
        # advance the claim lifecycle
        claim.status = "review" if packet.needs_review else "ready"
        db.commit()
        db.refresh(packet)
        return packet
    except Exception as exc:  # noqa: BLE001
        logger.exception("Claim-packet run %s failed", agent_run_id)
        db.rollback()
        run = db.get(AgentRun, agent_run_id)
        if run is not None:
            run.status = "failed"
            run.error = str(exc)
            db.commit()
        raise


def start_packet_run(db: Session, claim_id: uuid.UUID) -> AgentRun:
    """Create an AgentRun and execute it (inline when sync, enqueued when async)."""
    run = AgentRun(claim_id=claim_id, workflow="claim_packet", status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    if settings.ingest_mode == "async":
        from app.tasks import run_packet_task

        run_packet_task.delay(str(run.id))
    else:
        run_claim_packet(db, run.id)
        db.refresh(run)
    return run
