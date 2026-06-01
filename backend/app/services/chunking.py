"""Text chunking with page-aware, overlapping windows."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_CHUNK_WORDS = 180
DEFAULT_OVERLAP_WORDS = 40


@dataclass
class TextChunk:
    text: str
    page_number: int | None
    chunk_index: int
    token_count: int


def chunk_pages(
    pages: list[str],
    chunk_words: int = DEFAULT_CHUNK_WORDS,
    overlap_words: int = DEFAULT_OVERLAP_WORDS,
) -> list[TextChunk]:
    """Chunk a list of page texts into overlapping windows, preserving page numbers."""
    chunks: list[TextChunk] = []
    index = 0
    step = max(1, chunk_words - overlap_words)

    for page_idx, page_text in enumerate(pages, start=1):
        words = page_text.split()
        if not words:
            continue
        start = 0
        while start < len(words):
            window = words[start : start + chunk_words]
            text = " ".join(window).strip()
            if text:
                chunks.append(
                    TextChunk(
                        text=text,
                        page_number=page_idx if len(pages) > 1 else page_idx,
                        chunk_index=index,
                        token_count=len(window),
                    )
                )
                index += 1
            if start + chunk_words >= len(words):
                break
            start += step

    return chunks
