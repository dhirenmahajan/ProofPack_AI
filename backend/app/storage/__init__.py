"""Object storage abstraction (local filesystem or S3-compatible)."""

from __future__ import annotations

from functools import lru_cache

from app.config import settings
from app.storage.object_store import LocalObjectStore, ObjectStore, S3ObjectStore


@lru_cache
def get_object_store() -> ObjectStore:
    if settings.storage_backend == "s3":
        return S3ObjectStore()
    return LocalObjectStore()
