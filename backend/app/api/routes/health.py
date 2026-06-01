"""Health and provider-status endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.providers import get_embedder, get_llm, get_ocr

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@router.get("/providers")
def providers() -> dict:
    """Report which provider implementation is active (hosted vs stub)."""
    return {
        "llm": get_llm().name,
        "embeddings": get_embedder().name,
        "ocr": get_ocr().name,
    }
