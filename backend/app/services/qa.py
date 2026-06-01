"""Cited question-answering over a claim's evidence."""

from __future__ import annotations

import time
import uuid

from sqlalchemy.orm import Session

from app.db.models import QARun
from app.providers import get_llm
from app.providers.base import RetrievedContext
from app.schemas import Citation, QAResponse
from app.services.retrieval import hybrid_search

SNIPPET_LEN = 280


def answer_question(
    db: Session,
    claim_id: uuid.UUID,
    question: str,
    top_k: int = 5,
) -> QAResponse:
    started = time.perf_counter()
    llm = get_llm()

    scored = hybrid_search(db, claim_id, question, top_k=top_k)

    contexts: list[RetrievedContext] = []
    citation_meta: dict[int, dict] = {}
    for i, s in enumerate(scored, start=1):
        chunk = s.chunk
        contexts.append(
            RetrievedContext(
                index=i,
                chunk_id=str(chunk.id),
                text=chunk.text,
                document_id=str(chunk.document_id),
                filename=chunk.document.filename,
                source_type=chunk.source_type,
                page_number=chunk.page_number,
            )
        )
        citation_meta[i] = {
            "chunk_id": chunk.id,
            "document_id": chunk.document_id,
            "filename": chunk.document.filename,
            "source_type": chunk.source_type,
            "page_number": chunk.page_number,
            "snippet": chunk.text[:SNIPPET_LEN],
            "score": round(s.score, 4),
        }

    result = llm.answer(question, contexts)

    cited_indices = result.citation_indices or [c.index for c in contexts]
    citations: list[Citation] = []
    for idx in cited_indices:
        meta = citation_meta.get(idx)
        if meta:
            citations.append(Citation(index=idx, **meta))

    latency_ms = int((time.perf_counter() - started) * 1000)

    db.add(
        QARun(
            claim_id=claim_id,
            question=question,
            answer=result.answer,
            retrieved_chunk_ids=[str(c.chunk_id) for c in contexts],
            citations=[c.model_dump(mode="json") for c in citations],
            llm_provider=result.provider,
            latency_ms=latency_ms,
        )
    )
    db.commit()

    return QAResponse(
        question=question,
        answer=result.answer,
        provider=result.provider,
        citations=citations,
        latency_ms=latency_ms,
    )
