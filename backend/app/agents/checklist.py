"""Per-incident required-evidence checklist used by the gap-analysis node."""

from __future__ import annotations

# Minimum evidence (by source_type) expected for a credible packet, per incident.
REQUIRED_EVIDENCE: dict[str, list[str]] = {
    "flood": ["policy", "photo", "invoice", "inspection"],
    "hurricane": ["policy", "photo", "invoice", "inspection"],
    "hail": ["policy", "photo", "inspection"],
    "fire": ["policy", "photo", "invoice", "inspection", "permit"],
    "storm": ["policy", "photo", "invoice"],
    "other": ["policy", "photo"],
}

DESCRIPTIONS: dict[str, str] = {
    "policy": "Insurance policy / declarations page establishing coverage",
    "photo": "Photographs documenting the damage",
    "invoice": "Contractor invoice(s) for repair/replacement costs",
    "receipt": "Receipts for expenses incurred",
    "inspection": "Independent inspection or adjuster report",
    "permit": "Building permit(s) for repairs",
    "voicenote": "Claimant statement / voice note",
}


def required_for(incident_type: str | None) -> list[str]:
    return REQUIRED_EVIDENCE.get((incident_type or "other").lower(), REQUIRED_EVIDENCE["other"])
