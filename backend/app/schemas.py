"""Pydantic request/response models."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field


# --- Claims ---
class ClaimCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    claimant_name: Optional[str] = None
    incident_type: Optional[str] = None
    incident_date: Optional[date] = None
    location: Optional[str] = None


class ClaimOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    claimant_name: Optional[str] = None
    incident_type: Optional[str] = None
    incident_date: Optional[date] = None
    location: Optional[str] = None
    status: str
    created_at: datetime


# --- Documents ---
class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    claim_id: uuid.UUID
    filename: str
    content_type: Optional[str] = None
    source_type: str
    page_count: Optional[int] = None
    ocr_confidence: Optional[float] = None
    status: str
    created_at: datetime


class UploadResponse(BaseModel):
    document: DocumentOut
    chunks_created: int


# --- QA ---
class QARequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class Citation(BaseModel):
    index: int
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    source_type: str
    page_number: Optional[int] = None
    snippet: str
    score: float


class QAResponse(BaseModel):
    question: str
    answer: str
    provider: str
    citations: list[Citation]
    latency_ms: int


# --- Agentic workflow / claim packets (Month 2) ---
class PacketRequest(BaseModel):
    # Reserved for future options (e.g. include/exclude sections). Kept for forward-compat.
    regenerate: bool = False


class ClaimPacketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    claim_id: uuid.UUID
    agent_run_id: Optional[uuid.UUID] = None
    markdown: str
    confidence: Optional[float] = None
    needs_review: bool
    status: str
    citations: list[Any] = []
    gaps: list[Any] = []
    verification: Optional[dict] = None
    storage_path: Optional[str] = Field(default=None, exclude=True)
    created_at: datetime

    @computed_field
    @property
    def has_pdf(self) -> bool:
        return bool(self.storage_path)


class AgentRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    claim_id: uuid.UUID
    workflow: str
    status: str
    error: Optional[str] = None
    latency_ms: Optional[int] = None
    created_at: datetime
    packet: Optional[ClaimPacketOut] = None


class PacketReviewRequest(BaseModel):
    approve: bool = True
    markdown: Optional[str] = None  # optional human edits to the packet body
