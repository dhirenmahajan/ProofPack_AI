"""Pure scoring functions for the eval harness.

Retrieval/citation metrics work off the returned citation list; faithfulness uses
a token-overlap heuristic by default (offline, deterministic) and can be swapped
for a Gemini-judge implementation when a key is present.
"""

from __future__ import annotations

import math
import re

from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "for", "this",
    "that", "when", "be", "by", "with", "as", "it", "on", "at", "from", "you",
    "your", "was", "were", "has", "have", "had", "will", "shall", "must", "any",
    "which", "such", "not", "may", "can", "been", "into", "they", "their",
}


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def _content_tokens(text: str) -> set[str]:
    """Salient tokens only (length >= 4, non-stopword) for fair grounding checks."""
    return {t for t in _TOKEN_RE.findall((text or "").lower()) if len(t) >= 4 and t not in _STOPWORDS}


def citation_files(citations: list[dict]) -> list[str]:
    return [c.get("filename", "") for c in citations]


def recall_at_k(retrieved_files: list[str], expect_files: list[str]) -> float:
    """1.0 if any gold source file is present among the retrieved citations."""
    if not expect_files:
        return 1.0
    found = any(f in retrieved_files for f in expect_files)
    return 1.0 if found else 0.0


def mrr(retrieved_files: list[str], expect_files: list[str]) -> float:
    for rank, f in enumerate(retrieved_files, start=1):
        if f in expect_files:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved_files: list[str], expect_files: list[str], k: int = 5) -> float:
    gains = [1.0 if f in expect_files else 0.0 for f in retrieved_files[:k]]
    dcg = sum(g / math.log2(i + 2) for i, g in enumerate(gains))
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(expect_files), k)))
    return (dcg / ideal) if ideal else 0.0


def citation_precision(retrieved_files: list[str], expect_files: list[str]) -> float:
    if not retrieved_files:
        return 0.0
    if not expect_files:
        return 1.0
    hits = sum(1 for f in retrieved_files if f in expect_files)
    return hits / len(retrieved_files)


def keyword_grounding(answer: str, expect_keywords: list[str]) -> float:
    if not expect_keywords:
        return 1.0
    a = (answer or "").lower()
    hits = sum(1 for kw in expect_keywords if kw.lower() in a)
    return hits / len(expect_keywords)


def faithfulness(answer: str, citation_snippets: list[str]) -> float:
    """Faithfulness = are the answer's claims grounded in cited evidence?

    Prefers a Gemini judge (with retry/backoff) when a key is present; otherwise a
    fair content-token recall fallback: fraction of the answer's salient tokens that
    appear in the cited evidence. This tolerates paraphrasing (LLM answers rarely
    quote verbatim) while still penalising invented facts / ungrounded claims.
    """
    if settings.gemini_api_key:
        judged = _gemini_faithfulness(answer, citation_snippets)
        if judged is not None:
            return judged

    evidence = set()
    for s in citation_snippets:
        evidence |= _content_tokens(s)
    answer_toks = _content_tokens(answer)
    if not answer_toks:
        return 1.0  # nothing asserted -> nothing to be unfaithful about
    if not evidence:
        return 0.0  # claims with no supporting evidence
    return round(len(answer_toks & evidence) / len(answer_toks), 4)


@retry(stop=stop_after_attempt(4), wait=wait_exponential(min=2, max=30), reraise=True)
def _judge_call(prompt: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.gemini_api_key)
    resp = client.models.generate_content(
        model=settings.gemini_llm_model,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.0),
    )
    return resp.text or ""


def _gemini_faithfulness(answer: str, snippets: list[str]) -> float | None:
    prompt = (
        "You are a strict grader. Given EVIDENCE and an ANSWER, return a single "
        "number 0..1 = fraction of the answer's claims that are directly supported "
        "by the evidence. Output ONLY the number.\n\n"
        f"EVIDENCE:\n{chr(10).join(snippets)}\n\nANSWER:\n{answer}"
    )
    try:
        text = _judge_call(prompt)
        m = re.search(r"[01](?:\.\d+)?", text)
        return max(0.0, min(1.0, float(m.group()))) if m else None
    except Exception:  # noqa: BLE001 - fall back to the content-recall heuristic
        return None
