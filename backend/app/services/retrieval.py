"""Hybrid retrieval: pgvector cosine similarity + keyword overlap re-rank."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk
from app.providers import get_embedder

VECTOR_WEIGHT = 0.7
KEYWORD_WEIGHT = 0.3
CANDIDATE_MULTIPLIER = 6


@dataclass
class ScoredChunk:
    chunk: Chunk
    score: float
    vector_score: float
    keyword_score: float


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def hybrid_search(
    db: Session,
    claim_id: uuid.UUID,
    question: str,
    top_k: int = 5,
) -> list[ScoredChunk]:
    """Return the top_k chunks for a claim using vector + keyword hybrid scoring."""
    embedder = get_embedder()
    q_emb = embedder.embed_query(question)
    q_tokens = _tokens(question)

    candidate_k = max(top_k * CANDIDATE_MULTIPLIER, top_k)

    stmt = (
        select(Chunk, Chunk.embedding.cosine_distance(q_emb).label("dist"))
        .where(Chunk.claim_id == claim_id, Chunk.embedding.is_not(None))
        .order_by("dist")
        .limit(candidate_k)
    )
    rows = db.execute(stmt).all()

    scored: list[ScoredChunk] = []
    for chunk, dist in rows:
        vector_score = 1.0 - float(dist)  # cosine distance -> similarity
        chunk_tokens = _tokens(chunk.text)
        keyword_score = (
            len(q_tokens & chunk_tokens) / len(q_tokens) if q_tokens else 0.0
        )
        combined = VECTOR_WEIGHT * vector_score + KEYWORD_WEIGHT * keyword_score
        scored.append(
            ScoredChunk(
                chunk=chunk,
                score=combined,
                vector_score=vector_score,
                keyword_score=keyword_score,
            )
        )

    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[:top_k]
