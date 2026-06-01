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
        resp = self._client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


@lru_cache
def get_embedder() -> EmbeddingProvider:
    provider = settings.embeddings_provider
    has_key = bool(settings.openai_api_key)

    if provider == "openai" or (provider == "auto" and has_key):
        if not has_key:
            raise RuntimeError("EMBEDDINGS_PROVIDER=openai but OPENAI_API_KEY is unset")
        return OpenAIEmbedder(
            model=settings.embedding_model,
            dim=settings.embedding_dim,
            api_key=settings.openai_api_key,
        )
    return StubEmbedder(dim=settings.embedding_dim)
