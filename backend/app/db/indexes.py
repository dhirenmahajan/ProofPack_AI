"""Performance indexes applied after the schema exists.

Kept separate from model definitions because they are expression/operator-class
indexes (HNSW ANN + full-text GIN) that SQLAlchemy's ``create_all`` does not emit.
Applied idempotently at startup (dev) and from the Alembic baseline (prod).
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.engine import Connection

logger = logging.getLogger("proofpack.indexes")

# Each is idempotent (IF NOT EXISTS). HNSW gives sub-linear cosine ANN; the GIN
# index backs the to_tsvector('english', text) full-text query in retrieval.
INDEX_STATEMENTS: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw "
    "ON chunks USING hnsw (embedding vector_cosine_ops)",
    "CREATE INDEX IF NOT EXISTS ix_chunks_text_fts "
    "ON chunks USING gin (to_tsvector('english', text))",
    "CREATE INDEX IF NOT EXISTS ix_chunks_text_trgm "
    "ON chunks USING gin (text gin_trgm_ops)",
)


def apply_indexes(conn: Connection) -> None:
    for stmt in INDEX_STATEMENTS:
        try:
            conn.execute(text(stmt))
        except Exception as exc:  # noqa: BLE001 - never block startup on an index
            logger.warning("Index DDL skipped (%s): %s", stmt.split()[5], exc)
