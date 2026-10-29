"""Isolated worker process for running local Windows Media OCR on PDF documents.

Decouples WinRT COM runtime from host process event loops (such as AnyIO, Uvicorn, or Pytest)
to guarantee process isolation, prevent thread apartment conflicts, and eliminate access violations.
"""

import asyncio
import json
import os
import sys
import tempfile
from typing import Any, Dict, List

import pymupdf
import winocr

from testkart_intelligence.extraction.ocr import compute_ocr_confidence


def process_pdf_bytes_ocr(pdf_bytes: bytes, lang: str = "en") -> List[Dict[str, Any]]:
    """Render all PDF pages and perform Windows Media OCR on each page."""
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    pages: List[Dict[str, Any]] = []
    page_count = len(doc)

    for page_idx in range(page_count):
        page_num = page_idx + 1
        page = doc[page_idx]
        pix = page.get_pixmap(dpi=150, alpha=True)

        async def _run():
            op = winocr.recognize_bytes(pix.samples, pix.width, pix.height, lang)
            res = await winocr.to_coroutine(op)
            return winocr.picklify(res)

        try:
            res = asyncio.run(_run())
            text = res.get("text", "").strip()
            lines = res.get("lines", [])
            conf = compute_ocr_confidence(text, lines)
            requires_review = (conf < 0.60) or (len(text) < 20)
            notes = (
                f"OCR confidence {conf:.2f} meets threshold"
                if not requires_review
                else f"Low OCR confidence ({conf:.2f}) or sparse text; flagged for human verification"
            )
            pages.append({
                "page_number": page_num,
                "text": text,
                "ocr_confidence": conf,
                "is_scanned": True,
                "requires_human_verification": requires_review,
                "ocr_notes": notes,
                "lines_count": len(lines),
            })
        except Exception as exc:
            pages.append({
                "page_number": page_num,
                "text": "",
                "ocr_confidence": 0.0,
                "is_scanned": True,
                "requires_human_verification": True,
                "ocr_notes": f"OCR exception on page {page_num}: {exc}",
                "lines_count": 0,
            })

    doc.close()
    return pages


def main() -> None:
    if len(sys.argv) > 1:
        path = sys.argv[1]
        with open(path, "rb") as f:
            pdf_bytes = f.read()
    else:
        pdf_bytes = sys.stdin.buffer.read()

    pages = process_pdf_bytes_ocr(pdf_bytes)
    sys.stdout.write(json.dumps(pages))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
