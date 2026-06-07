"""Shared state object threaded through the LangGraph workflow."""

from __future__ import annotations

from typing import Any, TypedDict


class ClaimState(TypedDict, total=False):
    # Inputs (from the Claim row)
    claim_id: str
    title: str
    claimant_name: str | None
    incident_type: str | None
    incident_date: str | None
    location: str | None

    # Produced by nodes
    geocode: dict[str, Any] | None
    extractions: list[dict[str, Any]]
    verification: dict[str, Any]
    coverage_qa: list[dict[str, Any]]
    gaps: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    report_markdown: str
    confidence: float
    needs_review: bool
    notes: list[str]
