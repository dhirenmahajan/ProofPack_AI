"""LLM providers: OpenAI (hosted) + deterministic extractive stub fallback."""

from __future__ import annotations

import re
from functools import lru_cache

from app.config import settings
from app.providers.base import AnswerResult, LLMProvider, RetrievedContext

SYSTEM_PROMPT = (
    "You are ProofPack AI, an assistant that answers questions about disaster "
    "insurance claim documents. Answer ONLY using the provided evidence. Cite every "
    "claim with bracketed markers like [1], [2] that refer to the evidence numbers. "
    "If the evidence does not contain the answer, say you cannot find it in the "
    "provided documents. Never invent facts, figures, or coverage."
)


def _format_contexts(contexts: list[RetrievedContext]) -> str:
    blocks = []
    for c in contexts:
        loc = f" p.{c.page_number}" if c.page_number is not None else ""
        blocks.append(f"[{c.index}] ({c.filename}{loc}, {c.source_type})\n{c.text}")
    return "\n\n".join(blocks)


class StubLLM:
    """Extractive, citation-preserving fallback answer.

    Selects the evidence sentences that best overlap the question and stitches them
    into a grounded answer with citations. Deterministic and key-free.
    """

    name = "stub"

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", text.lower()))

    def answer(
        self, question: str, contexts: list[RetrievedContext]
    ) -> AnswerResult:
        if not contexts:
            return AnswerResult(
                answer="I could not find supporting evidence in the provided documents.",
                citation_indices=[],
                provider=self.name,
            )
        q_tokens = self._tokens(question)
        scored: list[tuple[float, RetrievedContext, str]] = []
        for c in contexts:
            best_sentence = c.text.strip()
            sentences = re.split(r"(?<=[.!?])\s+", c.text.strip())
            best_score = -1.0
            for s in sentences:
                if not s.strip():
                    continue
                overlap = len(q_tokens & self._tokens(s))
                if overlap > best_score:
                    best_score = overlap
                    best_sentence = s.strip()
            scored.append((best_score, c, best_sentence))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[: min(3, len(scored))]
        used: list[int] = []
        parts: list[str] = []
        for _, c, sentence in top:
            used.append(c.index)
            parts.append(f"{sentence} [{c.index}]")
        answer = (
            "Based on the provided evidence: " + " ".join(parts)
            if parts
            else "I could not find supporting evidence in the provided documents."
        )
        return AnswerResult(answer=answer, citation_indices=used, provider=self.name)


class OpenAILLM:
    name = "openai"

    def __init__(self, model: str, api_key: str) -> None:
        from openai import OpenAI

        self.model = model
        self._client = OpenAI(api_key=api_key)

    def answer(
        self, question: str, contexts: list[RetrievedContext]
    ) -> AnswerResult:
        user_prompt = (
            f"Question: {question}\n\n"
            f"Evidence:\n{_format_contexts(contexts)}\n\n"
            "Answer with inline citations like [1]."
        )
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
        )
        text = resp.choices[0].message.content or ""
        used = sorted({int(n) for n in re.findall(r"\[(\d+)\]", text)})
        return AnswerResult(answer=text, citation_indices=used, provider=self.name)


@lru_cache
def get_llm() -> LLMProvider:
    provider = settings.llm_provider
    has_key = bool(settings.openai_api_key)

    if provider == "openai" or (provider == "auto" and has_key):
        if not has_key:
            raise RuntimeError("LLM_PROVIDER=openai but OPENAI_API_KEY is unset")
        return OpenAILLM(model=settings.llm_model, api_key=settings.openai_api_key)
    return StubLLM()
