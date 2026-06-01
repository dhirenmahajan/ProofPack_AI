"""OCR / document text extraction.

PDF and plain-text extraction are always real (pypdf), so the ingestion pipeline is
fully functional without keys. Image OCR uses Hugging Face inference when a token is
present, otherwise a stub placeholder that still produces a chunkable record.
"""

from __future__ import annotations

import io
from functools import lru_cache

from app.config import settings
from app.providers.base import OCRProviderProto, OCRResult


def _extract_pdf(data: bytes) -> OCRResult:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    non_empty = [p for p in pages if p]
    # Heuristic confidence: born-digital PDFs extract cleanly; scanned ones don't.
    confidence = 0.95 if non_empty else 0.0
    return OCRResult(pages=pages, confidence=confidence, provider="pypdf")


def _extract_text(data: bytes) -> OCRResult:
    text = data.decode("utf-8", errors="replace").strip()
    return OCRResult(pages=[text], confidence=1.0, provider="plaintext")


class StubOCR:
    name = "stub"

    def extract_text(
        self, data: bytes, content_type: str, filename: str
    ) -> OCRResult:
        ct = (content_type or "").lower()
        if ct == "application/pdf" or filename.lower().endswith(".pdf"):
            return _extract_pdf(data)
        if ct.startswith("text/") or filename.lower().endswith((".txt", ".md")):
            return _extract_text(data)
        # Image/audio without a hosted model: emit a placeholder evidence record.
        return OCRResult(
            pages=[f"[unprocessed binary asset: {filename} ({content_type})]"],
            confidence=0.0,
            provider="stub",
        )


class HFOCR:
    name = "hf"

    def __init__(self, model: str, token: str) -> None:
        self.model = model
        self._token = token

    def extract_text(
        self, data: bytes, content_type: str, filename: str
    ) -> OCRResult:
        ct = (content_type or "").lower()
        if ct == "application/pdf" or filename.lower().endswith(".pdf"):
            return _extract_pdf(data)
        if ct.startswith("text/") or filename.lower().endswith((".txt", ".md")):
            return _extract_text(data)
        if ct.startswith("image/"):
            return self._ocr_image(data)
        return OCRResult(
            pages=[f"[unsupported asset: {filename} ({content_type})]"],
            confidence=0.0,
            provider=self.name,
        )

    def _ocr_image(self, data: bytes) -> OCRResult:
        import httpx

        url = f"https://api-inference.huggingface.co/models/{self.model}"
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            resp = httpx.post(url, headers=headers, content=data, timeout=60.0)
            resp.raise_for_status()
            payload = resp.json()
            if isinstance(payload, list) and payload and "generated_text" in payload[0]:
                return OCRResult(
                    pages=[payload[0]["generated_text"].strip()],
                    confidence=0.8,
                    provider=self.name,
                )
        except Exception:  # noqa: BLE001 - degrade gracefully, never crash ingestion
            pass
        return OCRResult(pages=["[image OCR failed]"], confidence=0.0, provider=self.name)


@lru_cache
def get_ocr() -> OCRProviderProto:
    provider = settings.ocr_provider
    has_token = bool(settings.hf_api_token)

    if provider == "hf" or (provider == "auto" and has_token):
        if not has_token:
            raise RuntimeError("OCR_PROVIDER=hf but HF_API_TOKEN is unset")
        return HFOCR(model=settings.hf_ocr_model, token=settings.hf_api_token)
    return StubOCR()
