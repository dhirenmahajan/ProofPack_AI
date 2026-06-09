#!/usr/bin/env python3
"""Quick R2 / S3 connectivity check using app settings."""

from __future__ import annotations

import sys
import uuid

# Allow running from repo root or backend/
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from app.config import settings
from app.storage.object_store import S3ObjectStore


def main() -> int:
    if settings.storage_backend != "s3":
        print("Set STORAGE_BACKEND=s3 and S3_* env vars (see .cloudflare-r2.env)")
        return 1

    store = S3ObjectStore()
    claim_id = f"r2-test-{uuid.uuid4().hex[:8]}"
    payload = b"proofpack-r2-ok"
    key = store.save(claim_id, "probe.txt", payload)
    got = store.read(key)
    if got != payload:
        print(f"FAIL: round-trip mismatch for key {key}")
        return 1
    print(f"OK: wrote and read s3://{settings.s3_bucket}/{key}")
    print(f"endpoint={settings.s3_endpoint_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
