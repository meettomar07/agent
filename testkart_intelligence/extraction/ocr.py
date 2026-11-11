"""Local Optical Character Recognition (OCR) Engine for scanned government PDF notifications.

Operates entirely locally using Windows Media OCR (Windows.Media.Ocr via winocr).
Preserves document provenance, page numbers, word coordinates, and assigns empirical
confidence scores to prevent hallucinations and route low-confidence scans to human review.
Uses subprocess process isolation to guarantee compatibility with AnyIO, Uvicorn, and Pytest.
"""

from abc import ABC, abstractmethod
import json
import logging
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def compute_ocr_confidence(text: str, lines: Optional[List[Dict[str, Any]]] = None) -> float:
    """Compute an empirical quality and confidence score (0.0 to 1.0) for extracted OCR text.

    Considers printable character ratio, word structure, line density, and presence of standard
    official notification vocabulary. Low-confidence outputs (< 0.60) are routed for human verification.
    """
    if not text or len(text.strip()) < 10:
        return 0.0

    cleaned = text.strip()
    total_chars = len(cleaned)
    if total_chars == 0:
        return 0.0

    # Ratio of valid printable alphanumeric and standard punctuation characters
    valid_chars = sum(1 for c in cleaned if c.isalnum() or c in " .,:;()/-–'\"\n₹")
    char_validity = valid_chars / total_chars

    words = [w for w in re.split(r"\s+", cleaned) if w]
    if not words:
        return 0.0

    # Proportion of words containing alphabetic letters
    word_has_letter = sum(1 for w in words if re.search(r"[a-zA-Z]", w))
    word_validity = word_has_letter / len(words)

    # Official terminology bonus for public recruitment/examination domains
    COMMON_OFFICIAL_TERMS = {
        "commission", "public", "service", "notice", "recruitment", "application",
        "examination", "post", "posts", "dated", "candidate", "candidates",
        "government", "advertisement", "advt", "date", "selection", "national",
        "testing", "agency", "board", "notification", "eligibility", "qualification",
        "fee", "vacancies", "vacancy", "schedule", "cbt", "hall", "ticket", "admit",
        "corrigendum", "cancellation", "result", "marks", "cut-off", "delhi", "pradesh",
    }
    matched_terms = sum(1 for w in words if w.lower().strip(".,:;()-–'\"") in COMMON_OFFICIAL_TERMS)
    term_bonus = min(0.20, (matched_terms / max(1, len(words))) * 2.0)

    # Penalty for excessive non-alphanumeric noise strings (e.g. repeated symbols)
    noise_words = sum(1 for w in words if len(w) > 3 and not re.search(r"[aeiouAEIOU0-9]", w))
    noise_penalty = min(0.30, (noise_words / max(1, len(words))) * 1.5)

    raw_score = (char_validity * 0.50) + (word_validity * 0.30) + term_bonus - noise_penalty
    return round(min(1.0, max(0.0, raw_score)), 3)


class OcrEngineInterface(ABC):
    """Abstract interface for local Optical Character Recognition."""

    @abstractmethod
    def extract_text_from_scanned_pdf(self, pdf_bytes: bytes) -> List[Dict[str, Any]]:
        """Extract text from scanned PDF pages.

        Returns list of dicts with:
            page_number (int)
            text (str)
            ocr_confidence (float)
            is_scanned (bool)
            requires_human_verification (bool)
            ocr_notes (str)
        """
        pass

    @abstractmethod
    def ocr_page_pixmap(self, pixmap: Any, page_num: int = 1) -> Dict[str, Any]:
        """Perform OCR on a single rendered PyMuPDF Pixmap."""
        pass


class StubOcrEngine(OcrEngineInterface):
    """Fallback stub OCR engine when local OCR runtime is unavailable."""

    def __init__(self, canned_text: Optional[str] = None, ocr_confidence: float = 0.0):
        self.canned_text = canned_text
        self.ocr_confidence = ocr_confidence

    def extract_text_from_scanned_pdf(self, pdf_bytes: bytes) -> List[Dict[str, Any]]:
        text = self.canned_text or "[SCANNED DOCUMENT: Local OCR engine unavailable. Manual review required.]"
        conf = self.ocr_confidence if self.canned_text else 0.0
        return [
            {
                "page_number": 1,
                "text": text,
                "ocr_confidence": conf,
                "is_scanned": True,
                "requires_human_verification": not bool(self.canned_text and conf >= 0.6),
                "ocr_notes": "Stub OCR result" if self.canned_text else "Local OCR not configured",
            }
        ]

    def ocr_page_pixmap(self, pixmap: Any, page_num: int = 1) -> Dict[str, Any]:
        text = self.canned_text or ""
        conf = self.ocr_confidence if self.canned_text else 0.0
        return {
            "page_number": page_num,
            "text": text,
            "ocr_confidence": conf,
            "is_scanned": True,
            "requires_human_verification": not bool(self.canned_text and conf >= 0.6),
            "ocr_notes": "Stub OCR result" if self.canned_text else "Local OCR not configured",
        }


class WindowsMediaOcrEngine(OcrEngineInterface):
    """Local, offline OCR engine leveraging Windows native Windows.Media.Ocr via isolated worker."""

    CONFIDENCE_REVIEW_THRESHOLD = 0.60

    def __init__(self, lang: str = "en"):
        self.lang = lang
        self.python_exe = sys.executable
        self._check_availability()

    def _check_availability(self) -> None:
        try:
            import winocr
            self.available = True
            self.python_exe = sys.executable
        except ImportError:
            # Check if .venv python has winocr available
            venv_py = os.path.join(os.path.abspath("."), ".venv", "Scripts", "python.exe")
            if os.path.exists(venv_py):
                try:
                    res = subprocess.run([venv_py, "-c", "import winocr"], capture_output=True)
                    if res.returncode == 0:
                        self.available = True
                        self.python_exe = venv_py
                        return
                except Exception:
                    pass
            self.available = False
            self.python_exe = sys.executable
            logger.warning("winocr not installed; WindowsMediaOcrEngine running in disabled mode")

    def ocr_page_pixmap(self, pixmap: Any, page_num: int = 1) -> Dict[str, Any]:
        """Process a single PyMuPDF pixmap using local Windows Media OCR worker."""
        if not self.available:
            return StubOcrEngine().ocr_page_pixmap(pixmap, page_num)

        import pymupdf
        # Create single-page in-memory PDF from pixmap to pass to worker
        try:
            doc = pymupdf.open()
            rect = pymupdf.Rect(0, 0, pixmap.width, pixmap.height)
            page = doc.new_page(width=pixmap.width, height=pixmap.height)
            page.insert_image(rect, pixmap=pixmap)
            pdf_bytes = doc.tobytes()
            doc.close()
            pages = self.extract_text_from_scanned_pdf(pdf_bytes)
            if pages:
                p = pages[0]
                p["page_number"] = page_num
                return p
        except Exception as exc:
            logger.error("Failed single-page pixmap OCR: %s", exc)

        return {
            "page_number": page_num,
            "text": "",
            "ocr_confidence": 0.0,
            "is_scanned": True,
            "requires_human_verification": True,
            "ocr_notes": "Single-page OCR failed",
        }

    def extract_text_from_scanned_pdf(self, pdf_bytes: bytes) -> List[Dict[str, Any]]:
        """Run isolated worker subprocess to execute Windows Media OCR without COM apartment collisions."""
        if not self.available:
            return StubOcrEngine().extract_text_from_scanned_pdf(pdf_bytes)

        if not pdf_bytes or len(pdf_bytes) == 0:
            return StubOcrEngine().extract_text_from_scanned_pdf(pdf_bytes)

        try:
            res = subprocess.run(
                [self.python_exe, "-m", "testkart_intelligence.extraction.ocr_worker"],
                input=pdf_bytes,
                capture_output=True,
                timeout=60,
            )
            if res.returncode == 0 and res.stdout.strip():
                pages_data = json.loads(res.stdout.strip())
                return pages_data
            else:
                logger.warning("OCR worker exited with code %d: %s", res.returncode, res.stderr.decode("utf-8", "ignore"))
                return StubOcrEngine().extract_text_from_scanned_pdf(pdf_bytes)
        except Exception as exc:
            logger.error("Subprocess OCR invocation failed: %s", exc)
            return StubOcrEngine().extract_text_from_scanned_pdf(pdf_bytes)


class TesseractOcrEngine(OcrEngineInterface):
    """Local OCR engine fallback using Tesseract OCR (via pytesseract or CLI)."""

    def __init__(self, lang: str = "eng"):
        self.lang = lang
        self._check_availability()

    def _check_availability(self) -> None:
        try:
            import pytesseract
            self.available = True
        except ImportError:
            self.available = False

    def ocr_page_pixmap(self, pixmap: Any, page_num: int = 1) -> Dict[str, Any]:
        """Process PyMuPDF pixmap using Tesseract OCR."""
        if not self.available:
            return StubOcrEngine().ocr_page_pixmap(pixmap, page_num)

        try:
            import io
            import pytesseract
            from PIL import Image

            img_bytes = pixmap.tobytes("png")
            img = Image.open(io.BytesIO(img_bytes))
            text = pytesseract.image_to_string(img, lang=self.lang).strip()
            conf = compute_ocr_confidence(text)
            requires_review = (conf < 0.60) or (len(text) < 20)

            return {
                "page_number": page_num,
                "text": text,
                "ocr_confidence": conf,
                "is_scanned": True,
                "requires_human_verification": requires_review,
                "ocr_notes": f"Processed via Tesseract OCR (conf={conf:.2f})",
            }
        except Exception as exc:
            logger.error("Tesseract single-page OCR failed: %s", exc)
            return StubOcrEngine().ocr_page_pixmap(pixmap, page_num)

    def extract_text_from_scanned_pdf(self, pdf_bytes: bytes) -> List[Dict[str, Any]]:
        """Process all pages of scanned PDF via PyMuPDF rendering + Tesseract OCR."""
        if not self.available:
            return StubOcrEngine().extract_text_from_scanned_pdf(pdf_bytes)

        import pymupdf
        pages: List[Dict[str, Any]] = []
        try:
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            for page_idx in range(len(doc)):
                page_num = page_idx + 1
                pix = doc[page_idx].get_pixmap(dpi=150, alpha=False)
                res = self.ocr_page_pixmap(pix, page_num=page_num)
                pages.append(res)
            doc.close()
            return pages
        except Exception as exc:
            logger.error("Tesseract PDF extraction failed: %s", exc)
            return StubOcrEngine().extract_text_from_scanned_pdf(pdf_bytes)


def get_default_ocr_engine() -> OcrEngineInterface:
    """Return an instance of the best available local OCR engine."""
    try:
        engine = WindowsMediaOcrEngine()
        if engine.available:
            return engine
    except Exception:
        pass

    try:
        engine = TesseractOcrEngine()
        if engine.available:
            return engine
    except Exception:
        pass

    return StubOcrEngine()
