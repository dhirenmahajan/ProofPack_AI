"""OCR / document text extraction.

PDF and plain-text extraction are always real (pypdf), so the ingestion pipeline is
fully functional without keys. Image/audio understanding uses, in priority order,
Gemini multimodal (free tier) -> Hugging Face inference -> local Tesseract -> a stub
placeholder that still produces a chunkable record. Nothing here ever raises:
ingestion must degrade, never crash.
"""

from __future__ import annotations

import io
from functools import lru_cache

from app.config import settings
from app.providers.base import OCRProviderProto, OCRResult

_IMAGE_PROMPT = (
    "You are processing evidence for a disaster insurance claim. Transcribe ALL legible "
    "text from this image verbatim. If it is a photo of property/damage rather than a "
    "document, instead give a concise factual description of the visible damage and any "
    "readable text (serial numbers, signage, dates). Do not speculate."
)
_AUDIO_PROMPT = (
    "Transcribe this audio note verbatim. It is a claimant describing disaster damage."
)


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


def _is_pdf(content_type: str, filename: str) -> bool:
    return content_type == "application/pdf" or filename.lower().endswith(".pdf")


def _is_text(content_type: str, filename: str) -> bool:
    return content_type.startswith("text/") or filename.lower().endswith((".txt", ".md"))


class StubOCR:
    name = "stub"

    def extract_text(
        self, data: bytes, content_type: str, filename: str
    ) -> OCRResult:
        ct = (content_type or "").lower()
        if _is_pdf(ct, filename):
            return _extract_pdf(data)
        if _is_text(ct, filename):
            return _extract_text(data)
        # Image/audio without a hosted model: emit a placeholder evidence record.
        return OCRResult(
            pages=[f"[unprocessed binary asset: {filename} ({content_type})]"],
            confidence=0.0,
            provider="stub",
        )


class GeminiVisionOCR:
    """Gemini multimodal extraction: images (OCR + damage description) and audio."""

    name = "gemini"

    def __init__(self, model: str, api_key: str) -> None:
        from google import genai

        self.model = model
        self._client = genai.Client(api_key=api_key)

    def _generate(self, data: bytes, mime_type: str, prompt: str) -> OCRResult:
        from google.genai import types

        try:
            resp = self._client.models.generate_content(
                model=self.model,
                contents=[
                    types.Part.from_bytes(data=data, mime_type=mime_type),
                    prompt,
                ],
            )
            text = (resp.text or "").strip()
            if text:
                return OCRResult(pages=[text], confidence=0.85, provider=self.name)
        except Exception:  # noqa: BLE001 - degrade gracefully
            pass
        return OCRResult(
            pages=["[multimodal extraction failed]"], confidence=0.0, provider=self.name
        )

    def extract_text(
        self, data: bytes, content_type: str, filename: str
    ) -> OCRResult:
        ct = (content_type or "").lower()
        if _is_pdf(ct, filename):
            return _extract_pdf(data)
        if _is_text(ct, filename):
            return _extract_text(data)
        if ct.startswith("image/"):
            return self._generate(data, ct or "image/png", _IMAGE_PROMPT)
        if ct.startswith("audio/"):
            return self._generate(data, ct or "audio/mp3", _AUDIO_PROMPT)
        return OCRResult(
            pages=[f"[unsupported asset: {filename} ({content_type})]"],
            confidence=0.0,
            provider=self.name,
        )


class TesseractOCR:
    """Local, offline image OCR via Tesseract. No network, no keys."""

    name = "tesseract"

    def __init__(self, cmd: str = "") -> None:
        if cmd:
            import pytesseract

            pytesseract.pytesseract.tesseract_cmd = cmd

    def extract_text(
        self, data: bytes, content_type: str, filename: str
    ) -> OCRResult:
        ct = (content_type or "").lower()
        if _is_pdf(ct, filename):
            return _extract_pdf(data)
        if _is_text(ct, filename):
            return _extract_text(data)
        if ct.startswith("image/"):
            try:
                import pytesseract
                from PIL import Image

                text = pytesseract.image_to_string(Image.open(io.BytesIO(data))).strip()
                if text:
                    return OCRResult(pages=[text], confidence=0.6, provider=self.name)
            except Exception:  # noqa: BLE001 - degrade gracefully
                pass
            return OCRResult(pages=["[image OCR failed]"], confidence=0.0, provider=self.name)
        return OCRResult(
            pages=[f"[unsupported asset: {filename} ({content_type})]"],
            confidence=0.0,
            provider=self.name,
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
        if _is_pdf(ct, filename):
            return _extract_pdf(data)
        if _is_text(ct, filename):
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
    has_gemini = bool(settings.gemini_api_key)
    has_hf = bool(settings.hf_api_token)

    if provider == "gemini" or (provider == "auto" and has_gemini):
        if not has_gemini:
            raise RuntimeError("OCR_PROVIDER=gemini but GEMINI_API_KEY is unset")
        return GeminiVisionOCR(model=settings.gemini_vision_model, api_key=settings.gemini_api_key)
    if provider == "hf" or (provider == "auto" and has_hf):
        if not has_hf:
            raise RuntimeError("OCR_PROVIDER=hf but HF_API_TOKEN is unset")
        return HFOCR(model=settings.hf_ocr_model, token=settings.hf_api_token)
    if provider == "tesseract":
        return TesseractOCR(cmd=settings.tesseract_cmd)
    return StubOCR()
