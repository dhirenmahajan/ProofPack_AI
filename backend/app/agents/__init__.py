"""Month 2 — LangGraph claim-packet agent workflow.

A bounded-responsibility state machine. Each node is a small agent with a single
job and explicit inputs/outputs (see AGENTS.md). Every node degrades to a
deterministic, key-free path so the workflow runs offline on stub providers.
"""

from app.agents.runner import run_claim_packet

__all__ = ["run_claim_packet"]
