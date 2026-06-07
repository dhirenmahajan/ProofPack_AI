"""Render a claim packet to PDF (reportlab) and store it via the object store.

Reportlab is pure-Python (no system libs), so this works in the slim container
and on free-tier hosts. Degrades to ``None`` (markdown-only packet) on any error.
"""

from __future__ import annotations

import io
import logging
import re

from app.agents.state import ClaimState
from app.storage import get_object_store

logger = logging.getLogger("proofpack.agents.pdf")


def _markdown_to_flowables(markdown: str):
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, Spacer

    styles = getSampleStyleSheet()
    flow = []
    for raw in markdown.splitlines():
        line = raw.rstrip()
        if not line:
            flow.append(Spacer(1, 6))
            continue
        # Convert **bold** -> <b>bold</b> and escape stray ampersands.
        text = line.replace("&", "&amp;")
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        if line.startswith("# "):
            flow.append(Paragraph(text[2:], styles["Title"]))
        elif line.startswith("## "):
            flow.append(Paragraph(text[3:], styles["Heading2"]))
        elif line.startswith("### "):
            flow.append(Paragraph(text[4:], styles["Heading3"]))
        elif line.lstrip().startswith(("- ", "* ", "  - ")):
            flow.append(Paragraph("&bull; " + text.lstrip("-* "), styles["Normal"]))
        else:
            flow.append(Paragraph(text, styles["Normal"]))
    return flow


def render_pdf(markdown: str) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, title="ProofPack Claim Packet")
    doc.build(_markdown_to_flowables(markdown))
    return buf.getvalue()


def render_pdf_and_store(claim_id: str, markdown: str) -> str | None:
    try:
        data = render_pdf(markdown)
        store = get_object_store()
        return store.save(str(claim_id), "claim_packet.pdf", data)
    except Exception as exc:  # noqa: BLE001 - markdown packet still available
        logger.warning("PDF render/store failed: %s", exc)
        return None
