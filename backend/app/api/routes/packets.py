"""Claim-packet workflow endpoints: run, poll, list, review, and download."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.runner import start_packet_run
from app.db.models import AgentRun, Claim, ClaimPacket
from app.db.session import get_db
from app.schemas import AgentRunOut, ClaimPacketOut, PacketRequest, PacketReviewRequest
from app.storage import get_object_store

router = APIRouter(prefix="/claims/{claim_id}/packet", tags=["packets"])


def _claim_or_404(db: Session, claim_id: uuid.UUID) -> Claim:
    claim = db.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


@router.post("", response_model=AgentRunOut)
def run_packet(
    claim_id: uuid.UUID,
    payload: PacketRequest | None = None,
    db: Session = Depends(get_db),
) -> AgentRun:
    """Kick off the LangGraph claim-packet workflow (sync or enqueued)."""
    _claim_or_404(db, claim_id)
    return start_packet_run(db, claim_id)


@router.get("/runs/{run_id}", response_model=AgentRunOut)
def get_run(
    claim_id: uuid.UUID, run_id: uuid.UUID, db: Session = Depends(get_db)
) -> AgentRun:
    run = db.get(AgentRun, run_id)
    if run is None or run.claim_id != claim_id:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("", response_model=list[ClaimPacketOut])
def list_packets(claim_id: uuid.UUID, db: Session = Depends(get_db)) -> list[ClaimPacket]:
    _claim_or_404(db, claim_id)
    stmt = (
        select(ClaimPacket)
        .where(ClaimPacket.claim_id == claim_id)
        .order_by(ClaimPacket.created_at.desc())
    )
    return list(db.execute(stmt).scalars())


@router.get("/latest", response_model=ClaimPacketOut)
def latest_packet(claim_id: uuid.UUID, db: Session = Depends(get_db)) -> ClaimPacket:
    _claim_or_404(db, claim_id)
    stmt = (
        select(ClaimPacket)
        .where(ClaimPacket.claim_id == claim_id)
        .order_by(ClaimPacket.created_at.desc())
        .limit(1)
    )
    packet = db.execute(stmt).scalars().first()
    if packet is None:
        raise HTTPException(status_code=404, detail="No packet generated yet")
    return packet


@router.post("/{packet_id}/review", response_model=ClaimPacketOut)
def review_packet(
    claim_id: uuid.UUID,
    packet_id: uuid.UUID,
    payload: PacketReviewRequest,
    db: Session = Depends(get_db),
) -> ClaimPacket:
    """Human-review checkpoint: approve and optionally apply edits to the body."""
    packet = db.get(ClaimPacket, packet_id)
    if packet is None or packet.claim_id != claim_id:
        raise HTTPException(status_code=404, detail="Packet not found")
    if payload.markdown is not None:
        packet.markdown = payload.markdown
    if payload.approve:
        packet.status = "approved"
        packet.needs_review = False
    db.commit()
    db.refresh(packet)
    return packet


@router.get("/{packet_id}/pdf")
def download_pdf(
    claim_id: uuid.UUID, packet_id: uuid.UUID, db: Session = Depends(get_db)
) -> Response:
    packet = db.get(ClaimPacket, packet_id)
    if packet is None or packet.claim_id != claim_id:
        raise HTTPException(status_code=404, detail="Packet not found")
    if not packet.storage_path:
        raise HTTPException(status_code=404, detail="No PDF for this packet")
    try:
        data = get_object_store().read(packet.storage_path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=f"PDF unavailable: {exc}")
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="claim_packet.pdf"'},
    )
