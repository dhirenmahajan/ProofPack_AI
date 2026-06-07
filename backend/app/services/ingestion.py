"""Ingestion pipeline: upload -> OCR/parse -> chunk -> embed -> pgvector.

Split into two steps so it runs either synchronously (inside the request) or
asynchronously (a Celery worker picks up ``process_document``):

  1. ``store_document`` — persist the blob + create the ``Document`` row fast.
  2. ``process_document`` — OCR -> chunk -> embed -> write ``Chunk`` rows.

``ingest_document`` chains both for the simple/sync path.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.db.models import Chunk, Document
from app.providers import get_embedder, get_ocr
from app.services.chunking import chunk_pages
from app.storage import get_object_store

logger = logging.getLogger("proofpack.ingestion")


def store_document(
    db: Session,
    claim_id: uuid.UUID,
    filename: str,
    content_type: str | None,
    source_type: str,
    data: bytes,
) -> Document:
    """Persist the raw blob and create the Document row (status='processing')."""
    store = get_object_store()
    storage_path = store.save(str(claim_id), filename, data)

    document = Document(
        claim_id=claim_id,
        filename=filename,
        content_type=content_type,
        source_type=source_type,
        storage_path=storage_path,
        status="processing",
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def process_document(db: Session, document_id: uuid.UUID) -> int:
    """OCR -> chunk -> embed -> write chunks for an already-stored Document.

    Idempotent-ish: clears any existing chunks before re-processing. Degrades by
    marking the document 'failed' rather than raising out of a worker.
    """
    document = db.get(Document, document_id)
    if document is None:
        raise ValueError(f"Document {document_id} not found")

    store = get_object_store()
    ocr = get_ocr()
    embedder = get_embedder()

    try:
        data = store.read(document.storage_path)
        ocr_result = ocr.extract_text(data, document.content_type or "", document.filename)

        document.page_count = len(ocr_result.pages)
        document.ocr_confidence = ocr_result.confidence

        # Replace existing chunks if reprocessing.
        for existing in list(document.chunks):
            db.delete(existing)

        text_chunks = chunk_pages(ocr_result.pages)
        if text_chunks:
            embeddings = embedder.embed_documents([c.text for c in text_chunks])
            for tc, emb in zip(text_chunks, embeddings):
                db.add(
                    Chunk(
                        document_id=document.id,
                        claim_id=document.claim_id,
                        chunk_index=tc.chunk_index,
                        page_number=tc.page_number,
                        source_type=document.source_type,
                        text=tc.text,
                        token_count=tc.token_count,
                        embedding=emb,
                    )
                )

        document.status = "ready"
        db.commit()
        return len(text_chunks)
    except Exception as exc:  # noqa: BLE001 - record failure, don't crash the worker
        logger.exception("Ingestion failed for document %s", document_id)
        db.rollback()
        document = db.get(Document, document_id)
        if document is not None:
            document.status = "failed"
            db.commit()
        raise


def ingest_document(
    db: Session,
    claim_id: uuid.UUID,
    filename: str,
    content_type: str | None,
    source_type: str,
    data: bytes,
) -> tuple[Document, int]:
    """Synchronous convenience: store + process in one call."""
    document = store_document(db, claim_id, filename, content_type, source_type, data)
    chunks_created = process_document(db, document.id)
    db.refresh(document)
    return document, chunks_created
