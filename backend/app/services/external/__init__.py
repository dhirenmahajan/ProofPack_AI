"""Clients for free public APIs used by the verification agent.

All clients are keyless, send a descriptive User-Agent (required by NWS and
Nominatim usage policies), cache responses in Redis, retry with backoff, and
return ``None``/empty on failure so verification degrades to 'unverified' rather
than crashing the workflow.
"""

from app.services.external.fema import fema_disaster_declarations
from app.services.external.geocode import geocode
from app.services.external.nws import nws_context

__all__ = ["geocode", "fema_disaster_declarations", "nws_context"]
