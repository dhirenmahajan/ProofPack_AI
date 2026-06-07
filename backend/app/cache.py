"""Tiny Redis-backed JSON cache for external public-API responses.

Degrades to a no-op when Redis is unreachable so a cache outage never breaks a
request. Used by the FEMA / NWS / Nominatim clients to respect rate limits and to
keep verification fast and cheap.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

from app.config import settings

logger = logging.getLogger("proofpack.cache")


@lru_cache
def _client():
    try:
        import redis

        return redis.Redis.from_url(settings.redis_url, decode_responses=True)
    except Exception as exc:  # noqa: BLE001 - cache is best-effort
        logger.warning("Redis cache unavailable: %s", exc)
        return None


def cache_get(key: str) -> Any | None:
    client = _client()
    if client is None:
        return None
    try:
        raw = client.get(key)
        return json.loads(raw) if raw else None
    except Exception:  # noqa: BLE001
        return None


def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    client = _client()
    if client is None:
        return
    try:
        client.set(
            key,
            json.dumps(value),
            ex=ttl if ttl is not None else settings.external_cache_ttl_seconds,
        )
    except Exception:  # noqa: BLE001
        pass
