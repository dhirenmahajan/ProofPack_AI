"""Embedding providers: OpenAI (hosted) + deterministic stub fallback."""

from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache

from app.config import settings
from app.providers.base import EmbeddingProvider

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class StubEmbedder:
    """Deterministic hashing bag-of-words embedder.

    Produces L2-normalized vectors where shared vocabulary yields meaningful cosine
    similarity. No network, no keys — good enough for local dev, tests, and demos.
    """

    name = "stub"

    def __init__(self, dim: int) -> None:
        self.dim = dim

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in _tokenize(text):
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            idx = h % self.dim
            sign = 1.0 if (h >> 8) % 2 == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class GeminiEmbedder:
    """Google Gemini embeddings (free tier). gemini-embedding-001 at output dim 768.

    Falls back to the deterministic stub on any API error so ingestion/retrieval
    never hard-fail.
    """

    name = "gemini"

    def __init__(self, model: str, dim: int, api_key: str) -> None:
        from google import genai

        self.model = model
        self.dim = dim
        self._client = genai.Client(api_key=api_key)
        self._stub = StubEmbedder(dim=dim)

    def _embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        if not texts:
            return []
        from google.genai import types

        try:
            resp = self._client.models.embed_content(
                model=self.model,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type=task_type, output_dimensionality=self.dim
                ),
            )
            return [list(e.values) for e in resp.embeddings]
        except Exception:  # noqa: BLE001 - degrade to deterministic stub
            return [self._stub.embed_query(t) for t in texts]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, task_type="RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], task_type="RETRIEVAL_QUERY")[0]


class OpenAIEmbedder:
    name = "openai"

    def __init__(self, model: str, dim: int, api_key: str) -> None:
        from openai import OpenAI

        self.model = model
        self.dim = dim
        self._client = OpenAI(api_key=api_key)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # text-embedding-3-* support an explicit output dimension so we can match
        # the column's bound EMBEDDING_DIM (default 768).
        resp = self._client.embeddings.create(
            model=self.model, input=texts, dimensions=self.dim
        )
        return [d.embedding for d in resp.data]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


@lru_cache
def get_embedder() -> EmbeddingProvider:
    provider = settings.embeddings_provider
    has_gemini = bool(settings.gemini_api_key)
    has_openai = bool(settings.openai_api_key)
    dim = settings.embedding_dim

    if provider == "gemini" or (provider == "auto" and has_gemini):
        if not has_gemini:
            raise RuntimeError("EMBEDDINGS_PROVIDER=gemini but GEMINI_API_KEY is unset")
        return GeminiEmbedder(
            model=settings.gemini_embedding_model, dim=dim, api_key=settings.gemini_api_key
        )
    if provider == "openai" or (provider == "auto" and has_openai):
        if not has_openai:
            raise RuntimeError("EMBEDDINGS_PROVIDER=openai but OPENAI_API_KEY is unset")
        return OpenAIEmbedder(
            model=settings.embedding_model, dim=dim, api_key=settings.openai_api_key
        )
    return StubEmbedder(dim=dim)
