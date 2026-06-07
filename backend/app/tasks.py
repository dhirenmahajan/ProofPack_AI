"""Celery tasks. Currently: asynchronous document ingestion."""

from __future__ import annotations

import uuid

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.ingestion import process_document


@celery_app.task(name="app.tasks.process_document_task", bind=True, max_retries=3)
def process_document_task(self, document_id: str) -> int:
    """Worker entrypoint: OCR -> chunk -> embed for one stored document."""
    db = SessionLocal()
    try:
        return process_document(db, uuid.UUID(document_id))
    except Exception as exc:  # noqa: BLE001 - retry with backoff, status already 'failed'
        raise self.retry(exc=exc, countdown=min(60, 2 ** self.request.retries))
    finally:
        db.close()


@celery_app.task(name="app.tasks.run_packet_task", bind=True, max_retries=1)
def run_packet_task(self, agent_run_id: str) -> str:
    """Worker entrypoint: run the LangGraph claim-packet workflow."""
    from app.agents.runner import run_claim_packet

    db = SessionLocal()
    try:
        packet = run_claim_packet(db, uuid.UUID(agent_run_id))
        return str(packet.id)
    finally:
        db.close()
