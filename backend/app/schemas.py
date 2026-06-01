"""Pydantic request/response models."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


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
