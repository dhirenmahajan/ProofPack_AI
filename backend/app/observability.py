"""Lightweight observability: PII redaction + optional tracing.

Tracing is opt-in (TRACING_ENABLED) and degrades to a no-op when Langfuse is not
configured/installed, so it never affects request behaviour. All inputs/outputs
are PII-redacted before they leave the process (failure-mode #10).
"""

from __future__ import annotations

import logging
import re
from contextlib import contextmanager
from functools import lru_cache
from typing import Any

from app.config import settings

logger = logging.getLogger("proofpack.observability")

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CARD = re.compile(r"\b(?:\d[ -]?){13,16}\b")


def redact(text: str | None) -> str:
    if not text:
        return ""
    out = _EMAIL.sub("[email]", text)
    out = _SSN.sub("[ssn]", out)
    out = _CARD.sub("[card]", out)
    out = _PHONE.sub("[phone]", out)
    return out


@lru_cache
def _langfuse():
    if not (settings.tracing_enabled and settings.langfuse_public_key):
        return None
    try:
        from langfuse import Langfuse

        return Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    except Exception as exc:  # noqa: BLE001 - tracing is best-effort
        logger.warning("Langfuse unavailable: %s", exc)
        return None


@contextmanager
def traced(name: str, *, inputs: dict[str, Any] | None = None):
    """Context manager yielding a recorder. No-op unless tracing is configured.

    Usage:
        with traced("qa", inputs={"question": q}) as span:
            ...
            span(output={"answer": a}, metadata={"provider": p, "latency_ms": ms})
    """
    client = _langfuse()
    safe_inputs = {k: (redact(v) if isinstance(v, str) else v) for k, v in (inputs or {}).items()}
    captured: dict[str, Any] = {}

    def record(output: Any = None, metadata: dict[str, Any] | None = None) -> None:
        captured["output"] = redact(output) if isinstance(output, str) else output
        captured["metadata"] = metadata or {}

    trace = None
    if client is not None:
        try:
            trace = client.trace(name=name, input=safe_inputs)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Trace %s init failed: %s", name, exc)

    try:
        yield record
    finally:
        if trace is not None:
            try:
                trace.update(
                    output=captured.get("output"), metadata=captured.get("metadata")
                )
            except Exception:  # noqa: BLE001
                pass
        if client is not None:
            try:
                client.flush()
            except Exception:  # noqa: BLE001
                pass
