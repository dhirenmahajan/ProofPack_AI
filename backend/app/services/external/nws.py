"""NWS api.weather.gov context. Keyless; requires a descriptive User-Agent.

NWS is strongest for current/forecast data; historical event confirmation is
limited, so this is treated as *supplementary* context (it resolves the location
to a forecast office and surfaces any active alerts). The authoritative
event-occurred signal comes from FEMA.
"""

from __future__ import annotations

import hashlib
import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.cache import cache_get, cache_set
from app.config import settings


logger = logging.getLogger("proofpack.external.nws")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8), reraise=True)
def _get(url: str, params: dict | None = None) -> dict:
    resp = httpx.get(
        url,
        params=params or {},
        headers={
            "User-Agent": settings.external_user_agent,
            "Accept": "application/geo+json",
        },
        timeout=20.0,
    )
    resp.raise_for_status()
    return resp.json()


def nws_context(lat: float | None, lon: float | None) -> dict:
    """Return {office, forecast_zone, active_alerts: int, alerts: [...]} or error."""
    out: dict = {"resolved": False}
    if lat is None or lon is None:
        out["error"] = "no coordinates"
        return out

    key = f"nws:{round(lat, 3)}:{round(lon, 3)}"
    cached = cache_get(key)
    if cached is not None:
        return cached

    try:
        points = _get(f"{settings.nws_api_base}/points/{lat},{lon}")
        props = points.get("properties", {}) or {}
        out["resolved"] = True
        out["office"] = props.get("cwa") or props.get("gridId")
        out["forecast_zone"] = props.get("forecastZone")
        alerts = _get(
            f"{settings.nws_api_base}/alerts",
            params={"point": f"{lat},{lon}", "status": "actual"},
        )
        features = alerts.get("features", []) or []
        out["active_alerts"] = len(features)
        out["alerts"] = [
            {
                "event": f.get("properties", {}).get("event"),
                "severity": f.get("properties", {}).get("severity"),
                "onset": f.get("properties", {}).get("onset"),
            }
            for f in features[:5]
        ]
    except Exception as exc:  # noqa: BLE001 - supplementary; degrade silently
        logger.warning("NWS context failed: %s", exc)
        out["error"] = str(exc)

    cache_set(key, out, ttl=settings.external_cache_ttl_seconds)
    return out
