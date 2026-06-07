"""Nominatim (OpenStreetMap) geocoding. Keyless; ≤1 req/s; cache aggressively."""

from __future__ import annotations

import hashlib
import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.cache import cache_get, cache_set
from app.config import settings

logger = logging.getLogger("proofpack.external.geocode")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8), reraise=True)
def _request(location: str) -> list[dict]:
    resp = httpx.get(
        f"{settings.nominatim_api_base}/search",
        params={"q": location, "format": "jsonv2", "addressdetails": 1, "limit": 1},
        headers={"User-Agent": settings.external_user_agent},
        timeout=20.0,
    )
    resp.raise_for_status()
    return resp.json()


def geocode(location: str | None) -> dict | None:
    """Return {lat, lon, display_name, state, state_code, country_code} or None."""
    if not location or not location.strip():
        return None
    key = "geo:" + hashlib.md5(location.strip().lower().encode()).hexdigest()
    cached = cache_get(key)
    if cached is not None:
        return cached or None

    try:
        results = _request(location.strip())
    except Exception as exc:  # noqa: BLE001 - degrade to unverified
        logger.warning("Geocode failed for %r: %s", location, exc)
        return None

    if not results:
        cache_set(key, {}, ttl=settings.external_cache_ttl_seconds)
        return None

    top = results[0]
    address = top.get("address", {}) or {}
    out = {
        "lat": float(top["lat"]),
        "lon": float(top["lon"]),
        "display_name": top.get("display_name"),
        "state": address.get("state"),
        "state_code": (address.get("ISO3166-2-lvl4") or "").split("-")[-1] or None,
        "country_code": (address.get("country_code") or "").upper() or None,
    }
    cache_set(key, out, ttl=settings.external_cache_ttl_seconds)
    return out
