"""Pluggable model-inference providers.

Every model call (LLM, embeddings, OCR) flows through this package. Each provider
resolves a concrete implementation at runtime based on env config + available keys,
falling back to a deterministic stub so the system runs with zero secrets.
"""

from app.providers.embeddings import get_embedder
from app.providers.llm import get_llm
from app.providers.ocr import get_ocr

__all__ = ["get_embedder", "get_llm", "get_ocr"]
