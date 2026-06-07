"""Hybrid retrieval: pgvector ANN + Postgres full-text, fused with weighted RRF.

Both candidate lists are produced **in the database** (so this scales past an
in-Python scan): an HNSW cosine search over ``chunks.embedding`` and a full-text
``ts_rank`` search over ``chunks.text``. The two ranked lists are merged with
weighted Reciprocal Rank Fusion (RRF), which is robust to the two scores living on
different scales. Retrieval is always claim-scoped.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import func, literal, select
from sqlalchemy.orm import Session

from app.db.models import Chunk
from app.providers import get_embedder

VECTOR_WEIGHT = 0.7
KEYWORD_WEIGHT = 0.3
CANDIDATE_MULTIPLIER = 6
RRF_K = 60  # standard RRF dampening constant

logger = logging.getLogger("proofpack.retrieval")


@dataclass
class ScoredChunk:
    chunk: Chunk
    score: float
    vector_score: float
    keyword_score: float


def _vector_candidates(
    db: Session, claim_id: uuid.UUID, q_emb: list[float], limit: int
) -> list[tuple[Chunk, float]]:
    stmt = (
        select(Chunk, Chunk.embedding.cosine_distance(q_emb).label("dist"))
        .where(Chunk.claim_id == claim_id, Chunk.embedding.is_not(None))
        .order_by("dist")
        .limit(limit)
    )
    return [(chunk, 1.0 - float(dist)) for chunk, dist in db.execute(stmt).all()]


def _keyword_candidates(
    db: Session, claim_id: uuid.UUID, question: str, limit: int
) -> list[tuple[Chunk, float]]:
    tsv = func.to_tsvector(literal("english"), Chunk.text)
    tsq = func.plainto_tsquery(literal("english"), question)
    rank = func.ts_rank(tsv, tsq).label("rank")
    stmt = (
        select(Chunk, rank)
        .where(Chunk.claim_id == claim_id, tsv.op("@@")(tsq))
        .order_by(rank.desc())
        .limit(limit)
    )
    try:
        return [(chunk, float(r)) for chunk, r in db.execute(stmt).all()]
    except Exception:  # noqa: BLE001 - FTS is best-effort; vector still carries retrieval
        logger.warning("Keyword (FTS) retrieval failed; falling back to vector-only")
        db.rollback()
        return []


def hybrid_search(
    db: Session,
    claim_id: uuid.UUID,
    question: str,
    top_k: int = 5,
) -> list[ScoredChunk]:
    """Return the top_k chunks for a claim using vector + keyword hybrid scoring."""
    embedder = get_embedder()
    q_emb = embedder.embed_query(question)

    candidate_k = max(top_k * CANDIDATE_MULTIPLIER, top_k)

    vec = _vector_candidates(db, claim_id, q_emb, candidate_k)
    kw = _keyword_candidates(db, claim_id, question, candidate_k)

    merged: dict[uuid.UUID, ScoredChunk] = {}

    def _ensure(chunk: Chunk) -> ScoredChunk:
        sc = merged.get(chunk.id)
        if sc is None:
            sc = ScoredChunk(chunk=chunk, score=0.0, vector_score=0.0, keyword_score=0.0)
            merged[chunk.id] = sc
        return sc

    for rank, (chunk, vscore) in enumerate(vec):
        sc = _ensure(chunk)
        sc.vector_score = vscore
        sc.score += VECTOR_WEIGHT * (1.0 / (RRF_K + rank))

    for rank, (chunk, kscore) in enumerate(kw):
        sc = _ensure(chunk)
        sc.keyword_score = kscore
        sc.score += KEYWORD_WEIGHT * (1.0 / (RRF_K + rank))

    results = sorted(merged.values(), key=lambda s: s.score, reverse=True)
    return results[:top_k]
