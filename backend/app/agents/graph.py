"""Compile + run the claim-packet workflow as a LangGraph state machine.

The node order is linear (intake -> extraction -> verification -> policy_rag ->
gap_analysis -> report_writer -> human_review). If LangGraph is unavailable we
fall back to an equivalent sequential executor so the workflow still runs.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.agents import nodes
from app.agents.state import ClaimState

logger = logging.getLogger("proofpack.agents.graph")

_ORDER = [
    ("intake", nodes.intake),
    ("extraction", nodes.extraction),
    ("verification", nodes.verification),
    ("policy_rag", nodes.policy_rag),
    ("gap_analysis", nodes.gap_analysis),
    ("report_writer", nodes.report_writer),
    ("human_review", nodes.human_review),
]


def _run_sequential(db: Session, state: ClaimState) -> ClaimState:
    for name, fn in _ORDER:
        try:
            state.update(fn(db, state) or {})
        except Exception:  # noqa: BLE001 - keep going; packet will flag review
            logger.exception("Node %s failed", name)
    return state


def run_graph(db: Session, state: ClaimState) -> ClaimState:
    try:
        from langgraph.graph import END, StateGraph
    except Exception:  # noqa: BLE001
        logger.warning("LangGraph unavailable; using sequential executor")
        return _run_sequential(db, dict(state))

    graph = StateGraph(ClaimState)
    prev: str | None = None
    for name, fn in _ORDER:
        # Bind db + capture fn without late-binding issues.
        graph.add_node(name, (lambda f: (lambda s: f(db, s)))(fn))
        if prev is None:
            graph.set_entry_point(name)
        else:
            graph.add_edge(prev, name)
        prev = name
    graph.add_edge(prev, END)

    try:
        compiled = graph.compile()
        return compiled.invoke(dict(state))
    except Exception:  # noqa: BLE001 - never let orchestration crash the run
        logger.exception("LangGraph execution failed; falling back to sequential")
        return _run_sequential(db, dict(state))
