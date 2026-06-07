"""OpenFEMA Disaster Declarations Summaries. Keyless OData-style API.

Docs: https://www.fema.gov/about/openfema/api
Endpoint: {FEMA_API_BASE}/v2/DisasterDeclarationsSummaries
We filter by US state + a date window around the incident date (and optionally
incident type) to find a matching federal disaster declaration — the strong signal
that an event actually occurred where/when the claim says it did.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.cache import cache_get, cache_set
from app.config import settings

logger = logging.getLogger("proofpack.external.fema")

# Claim incident_type vocabulary -> FEMA incidentType values (best-effort).
_INCIDENT_MAP = {
    "flood": "Flood",
    "hurricane": "Hurricane",
    "hail": "Severe Storm",
    "fire": "Fire",
    "storm": "Severe Storm",
}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8), reraise=True)
def _request(params: dict) -> dict:
    resp = httpx.get(
        f"{settings.fema_api_base}/v2/DisasterDeclarationsSummaries",
        params=params,
        headers={"User-Agent": settings.external_user_agent},
        timeout=25.0,
    )
    resp.raise_for_status()
    return resp.json()


def _window(incident_date: str | None, days: int = 30) -> tuple[str, str] | None:
    if not incident_date:
        return None
    try:
        d = dt.date.fromisoformat(incident_date[:10])
    except ValueError:
        return None
    lo = (d - dt.timedelta(days=days)).isoformat()
    hi = (d + dt.timedelta(days=days)).isoformat()
    return lo, hi


def fema_disaster_declarations(
    state_code: str | None,
    incident_date: str | None,
    incident_type: str | None,
) -> dict:
    """Return {matched: bool, declarations: [...], query: {...}}."""
    result: dict = {"matched": False, "declarations": [], "query": {}}
    if not state_code:
        result["error"] = "no state resolved from location"
        return result

    filters = [f"state eq '{state_code.upper()}'"]
    window = _window(incident_date)
    if window:
        lo, hi = window
        # incident overlaps the window
        filters.append(f"incidentBeginDate le '{hi}T23:59:59.000Z'")
        filters.append(f"incidentEndDate ge '{lo}T00:00:00.000Z'")
    fema_type = _INCIDENT_MAP.get((incident_type or "").lower())
    if fema_type:
        filters.append(f"incidentType eq '{fema_type}'")

    params = {
        "$filter": " and ".join(filters),
        "$select": (
            "femaDeclarationString,declarationTitle,incidentType,state,"
            "declarationDate,incidentBeginDate,incidentEndDate,designatedArea,fyDeclared"
        ),
        "$orderby": "incidentBeginDate desc",
        "$top": 10,
    }
    result["query"] = params

    key = "fema:" + hashlib.md5(str(params).encode()).hexdigest()
    cached = cache_get(key)
    if cached is not None:
        return cached

    try:
        payload = _request(params)
        decls = payload.get("DisasterDeclarationsSummaries", []) or []
        result["declarations"] = decls
        result["matched"] = bool(decls)
    except Exception as exc:  # noqa: BLE001 - degrade to unverified
        logger.warning("FEMA query failed: %s", exc)
        result["error"] = str(exc)

    cache_set(key, result, ttl=settings.external_cache_ttl_seconds)
    return result
