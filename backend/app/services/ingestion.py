"""Ingestion pipeline: upload -> OCR/parse -> chunk -> embed -> pgvector."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.db.models import Chunk, Document
from app.providers import get_embedder, get_ocr
from app.services.chunking import chunk_pages
from app.storage import get_object_store


def ingest_document(
    db: Session,
    claim_id: uuid.UUID,
    filename: str,
    content_type: str | None,
    source_type: str,
    data: bytes,
) -> tuple[Document, int]:
    """Run the full ingestion pipeline for a single uploaded artifact."""
    store = get_object_store()
    ocr = get_ocr()
    embedder = get_embedder()

    storage_path = store.save(str(claim_id), filename, data)

    ocr_result = ocr.extract_text(data, content_type or "", filename)

    document = Document(
        claim_id=claim_id,
        filename=filename,
        content_type=content_type,
        source_type=source_type,
        storage_path=storage_path,
        page_count=len(ocr_result.pages),
        ocr_confidence=ocr_result.confidence,
        status="processing",
    )
    db.add(document)
    db.flush()  # assign document.id

    text_chunks = chunk_pages(ocr_result.pages)

    if text_chunks:
        embeddings = embedder.embed_documents([c.text for c in text_chunks])
        for tc, emb in zip(text_chunks, embeddings):
            db.add(
                Chunk(
                    document_id=document.id,
                    claim_id=claim_id,
                    chunk_index=tc.chunk_index,
                    page_number=tc.page_number,
                    source_type=source_type,
                    text=tc.text,
                    token_count=tc.token_count,
                    embedding=emb,
                )
            )

    document.status = "ready"
    db.commit()
    db.refresh(document)
    return document, len(text_chunks)
