"""SQLAlchemy ORM models for ProofPack AI."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.db.session import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    title: Mapped[str] = mapped_column(String(255))
    claimant_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    incident_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    incident_date: Mapped[date | None] = mapped_column(nullable=True)
    location: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="intake")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    documents: Mapped[list["Document"]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    claim_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # e.g. policy | invoice | receipt | photo | inspection | permit | voicenote | other
    source_type: Mapped[str] = mapped_column(String(32), default="other")
    storage_path: Mapped[str] = mapped_column(String(1024))
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="uploaded")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    claim: Mapped["Claim"] = relationship(back_populates="documents")
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    claim_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), default="other")
    text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dim), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    document: Mapped["Document"] = relationship(back_populates="chunks")
    claim: Mapped["Claim"] = relationship(back_populates="chunks")


class QARun(Base):
    __tablename__ = "qa_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    claim_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), index=True
    )
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    retrieved_chunk_ids: Mapped[list] = mapped_column(JSONB, default=list)
    citations: Mapped[list] = mapped_column(JSONB, default=list)
    llm_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
