"""Shared provider interfaces and data types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class RetrievedContext:
    """A single piece of evidence passed to the LLM for answering."""

    index: int  # 1-based citation marker shown to the model
    chunk_id: str
    text: str
    document_id: str
    filename: str
    source_type: str
    page_number: int | None = None


@dataclass
class AnswerResult:
    answer: str
    citation_indices: list[int] = field(default_factory=list)
    provider: str = "stub"


@dataclass
class OCRResult:
    pages: list[str]
    confidence: float
    provider: str = "stub"


@runtime_checkable
class EmbeddingProvider(Protocol):
    name: str
    dim: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def answer(
        self, question: str, contexts: list[RetrievedContext]
    ) -> AnswerResult: ...


@runtime_checkable
class OCRProviderProto(Protocol):
    name: str

    def extract_text(self, data: bytes, content_type: str, filename: str) -> OCRResult: ...
