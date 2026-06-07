"""Local and S3-compatible object stores for claim document blobs."""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Protocol

from app.config import settings

logger = logging.getLogger("proofpack.storage")


class ObjectStore(Protocol):
    def save(self, claim_id: str, filename: str, data: bytes) -> str: ...

    def read(self, storage_path: str) -> bytes: ...


def _safe_filename(filename: str) -> str:
    base = os.path.basename(filename).replace("\x00", "")
    return base or "upload.bin"


class LocalObjectStore:
    """Persist blobs under ``settings.storage_local_dir``."""

    def __init__(self) -> None:
        self._root = Path(settings.storage_local_dir)
        self._root.mkdir(parents=True, exist_ok=True)

    def save(self, claim_id: str, filename: str, data: bytes) -> str:
        claim_dir = self._root / claim_id
        claim_dir.mkdir(parents=True, exist_ok=True)
        safe = _safe_filename(filename)
        path = claim_dir / f"{uuid.uuid4().hex}_{safe}"
        path.write_bytes(data)
        # Relative to storage root so ``read`` can resolve after restarts.
        rel = path.relative_to(self._root).as_posix()
        logger.debug("Stored %s bytes at %s", len(data), rel)
        return rel

    def read(self, storage_path: str) -> bytes:
        path = self._root / storage_path
        return path.read_bytes()


class S3ObjectStore:
    """S3-compatible store (Railway buckets, R2, MinIO)."""

    def __init__(self) -> None:
        import boto3

        if not settings.s3_bucket:
            raise ValueError("S3_BUCKET is required when STORAGE_BACKEND=s3")
        self._bucket = settings.s3_bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url or None,
            region_name=settings.s3_region or None,
            aws_access_key_id=settings.s3_access_key_id or None,
            aws_secret_access_key=settings.s3_secret_access_key or None,
        )

    def save(self, claim_id: str, filename: str, data: bytes) -> str:
        safe = _safe_filename(filename)
        key = f"{claim_id}/{uuid.uuid4().hex}_{safe}"
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data)
        logger.debug("Stored %s bytes at s3://%s/%s", len(data), self._bucket, key)
        return key

    def read(self, storage_path: str) -> bytes:
        resp = self._client.get_object(Bucket=self._bucket, Key=storage_path)
        return resp["Body"].read()
