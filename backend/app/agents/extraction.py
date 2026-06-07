"""Structured field extraction per document.

Uses Gemini JSON output when a key is present; otherwise a deterministic regex
fallback (amounts/dates/policy numbers + a text summary) so the extraction agent
always returns *something* schema-valid and never crashes the workflow.
"""

from __future__ import annotations

import json
import logging
import re

from app.config import settings

logger = logging.getLogger("proofpack.agents.extraction")

MAX_CHARS = 12000  # cap document text sent to the model

# What we ask the model to populate, per source_type.
_SCHEMA_HINT = {
    "policy": (
        "policy_number, named_insured, property_address, coverages "
        "(list of {name, limit}), deductible, exclusions (list), filing_deadline"
    ),
    "invoice": "vendor, invoice_date, total_amount, line_items (list of {description, amount})",
    "receipt": "vendor, date, total_amount, items (list of {description, amount})",
    "inspection": "inspector, inspection_date, findings (list), estimated_damage",
    "permit": "permit_number, permit_type, issue_date, jurisdiction",
    "photo": "description, visible_text, observed_damage",
    "voicenote": "summary, key_points (list)",
    "other": "summary, key_facts (list)",
}

_AMOUNT_RE = re.compile(r"\$\s?[\d,]+(?:\.\d{2})?")
_DATE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b")
_POLICY_RE = re.compile(r"\b(?:policy(?:\s*(?:no\.?|number|#))?\s*[:#]?\s*)([A-Z0-9-]{4,})", re.I)


def _regex_fallback(text: str, source_type: str) -> dict:
    amounts = _AMOUNT_RE.findall(text)
    dates = _DATE_RE.findall(text)
    out: dict = {
        "summary": " ".join(text.split())[:280],
        "amounts": amounts[:10],
        "dates": dates[:10],
    }
    m = _POLICY_RE.search(text)
    if m:
        out["policy_number"] = m.group(1)
    return out


def _gemini_extract(text: str, source_type: str) -> dict | None:
    from google import genai
    from google.genai import types

    hint = _SCHEMA_HINT.get(source_type, _SCHEMA_HINT["other"])
    prompt = (
        f"Extract structured fields from this {source_type} document for a disaster "
        f"insurance claim. Return ONLY JSON with these fields where present: {hint}. "
        f"Use null for missing values. Do not invent data.\n\nDOCUMENT:\n{text[:MAX_CHARS]}"
    )
    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        resp = client.models.generate_content(
            model=settings.gemini_llm_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0, response_mime_type="application/json"
            ),
        )
        raw = (resp.text or "").strip()
        if not raw:
            return None
        return json.loads(raw)
    except Exception as exc:  # noqa: BLE001 - fall back to regex
        logger.warning("Gemini extraction failed (%s); using regex fallback", exc)
        return None


def extract_document(text: str, source_type: str) -> tuple[dict, float, str]:
    """Return (fields, confidence, provider)."""
    text = (text or "").strip()
    if not text or text.startswith("[unprocessed") or text.startswith("[image OCR failed"):
        return {"summary": ""}, 0.0, "none"

    if settings.gemini_api_key:
        fields = _gemini_extract(text, source_type)
        if fields is not None:
            return fields, 0.85, "gemini"

    return _regex_fallback(text, source_type), 0.5, "stub"
