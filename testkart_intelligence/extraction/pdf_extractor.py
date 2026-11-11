"""PyMuPDF-based text and metadata extractor for official government PDF notifications.

Includes PDF signature verification, encryption detection, page-level scanned detection,
layout reconstruction for rotated pages and multi-column tables, and OCR fallback.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
import pymupdf

from testkart_intelligence.extraction.ocr import (
    OcrEngineInterface,
    StubOcrEngine,
    WindowsMediaOcrEngine,
    get_default_ocr_engine,
)


class PdfExtractionError(Exception):
    """Raised when PDF cannot be read, is corrupted, or is encrypted."""

    def __init__(self, message: str, code: Optional[str] = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        elif ":" in message:
            self.code = message.split(":", 1)[0].strip()
        else:
            self.code = "EXTRACTION_ERROR"


class PdfDocumentExtractor:
    """Extracts text page-by-page from PDF documents using PyMuPDF and OCR."""

    MAX_PDF_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB safety limit

    def __init__(self, ocr_engine: Optional[OcrEngineInterface] = None):
        self.ocr_engine = ocr_engine or get_default_ocr_engine()

    @staticmethod
    def _reconstruct_layout_lines(page: Any) -> List[str]:
        """Cluster and sort visual text blocks into horizontal rows accounting for page rotation.
        
        Handles rotated pages (e.g. 270 or 90 degrees) and multi-column tabular layouts where
        PyMuPDF's default text stream reads entire columns top-to-bottom sequentially.
        """
        try:
            blocks = [b for b in page.get_text("blocks") if b[6] == 0]
            if not blocks:
                return []
            rot = getattr(page, "rotation", 0)

            def v_coords(b):
                xm = (b[0] + b[2]) / 2.0
                ym = (b[1] + b[3]) / 2.0
                if rot == 0:
                    return ym, xm
                elif rot == 270:
                    return -xm, ym
                elif rot == 90:
                    return xm, -ym
                elif rot == 180:
                    return -ym, -xm
                return ym, xm

            sorted_blocks = sorted(blocks, key=lambda b: v_coords(b)[0])
            rows: List[List[Any]] = []
            for b in sorted_blocks:
                vr, vc = v_coords(b)
                if not rows or abs(vr - v_coords(rows[-1][0])[0]) > 10.0:
                    rows.append([b])
                else:
                    rows[-1].append(b)

            out_lines: List[str] = []
            for r_blocks in rows:
                r_blocks.sort(key=lambda b: v_coords(b)[1])
                line_text = " : ".join(b[4].strip().replace("\n", " ") for b in r_blocks if b[4].strip())
                if line_text:
                    out_lines.append(line_text)
            return out_lines
        except Exception:
            return []

    def extract(self, pdf_bytes: bytes) -> Tuple[str, List[Dict[str, Any]], int]:
        """Extract text and metadata from PDF bytes with signature, encryption, and page-level OCR checks.

        Returns:
            Tuple of (full_text, pages_list, total_page_count)
            where pages_list is:
            [{"page_number": int, "text": str, "is_scanned": bool, "ocr_confidence": float, ...}]
        """
        # 1. Validate payload presence and size
        if not pdf_bytes or len(pdf_bytes) == 0:
            raise PdfExtractionError("EMPTY_PDF: Cannot extract from empty PDF bytes")

        if len(pdf_bytes) > self.MAX_PDF_SIZE_BYTES:
            raise PdfExtractionError(
                f"PAYLOAD_TOO_LARGE: PDF size ({len(pdf_bytes)} bytes) exceeds limit of {self.MAX_PDF_SIZE_BYTES} bytes"
            )

        # 2. Validate PDF signature (%PDF-)
        # Most valid PDFs start with %PDF- within the first 1024 bytes (allowing for minor BOM/whitespace prefixes)
        header_sample = pdf_bytes[:1024]
        if b"%PDF-" not in header_sample:
            raise PdfExtractionError("INVALID_PDF_SIGNATURE: File does not contain valid %PDF- magic header")

        # 3. Open PDF via PyMuPDF
        try:
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        except Exception as exc:
            raise PdfExtractionError(f"CORRUPT_PDF: Failed to open PDF stream: {exc}") from exc

        # 4. Check for encryption / password protection
        if doc.is_encrypted or getattr(doc, "needs_pass", False):
            doc.close()
            raise PdfExtractionError("ENCRYPTED_PDF: Document is password-protected or encrypted; cannot extract text")

        page_count = len(doc)
        if page_count == 0:
            doc.close()
            raise PdfExtractionError("EMPTY_PDF: PDF document has 0 pages")

        pages: List[Dict[str, Any]] = []
        total_text_chars = 0
        has_legacy_font = False
        legacy_font_names: List[str] = []

        LEGACY_FONT_MARKERS = ("kruti", "walkman", "chanakya", "devlys", "shivaji", "dv-tt", "shree", "aps-")

        # 5. Page-by-page extraction with page-level scanned detection
        for page_idx in range(page_count):
            page_num = page_idx + 1
            layout_lines: List[str] = []
            page_rot = 0
            page_is_scanned = False
            page_ocr_conf = 1.0

            try:
                page = doc[page_idx]
                page_rot = getattr(page, "rotation", 0)
                page_text = page.get_text("text").strip()

                # Check page fonts for legacy non-Unicode font encodings
                try:
                    fonts = page.get_fonts()
                    for f in fonts:
                        fname = (f[3] if len(f) > 3 else "").lower()
                        if any(marker in fname for marker in LEGACY_FONT_MARKERS):
                            has_legacy_font = True
                            if f[3] not in legacy_font_names:
                                legacy_font_names.append(f[3])
                except Exception:
                    pass

                # Reconstruct multi-column or rotated table layout rows
                layout_lines = self._reconstruct_layout_lines(page)
                if layout_lines and (page_rot != 0 or len(layout_lines) > 2):
                    page_text = f"{page_text}\n\n[LAYOUT_RECONSTRUCTED_TABLE]\n" + "\n".join(layout_lines)

                # Page-level scanned detection:
                # If page contains < 50 chars of text, it may be an image-only or scanned page
                if len(page_text.strip()) < 50:
                    page_is_scanned = True
                    try:
                        # Render pixmap for page-level OCR
                        pix = page.get_pixmap(dpi=150, alpha=False)
                        ocr_res = self.ocr_engine.ocr_page_pixmap(pix, page_num=page_num)
                        ocr_text = ocr_res.get("text", "").strip()
                        page_ocr_conf = ocr_res.get("ocr_confidence", 0.0)

                        if ocr_text:
                            page_text = f"--- Page {page_num} [OCR Scanned: conf={page_ocr_conf:.2f}] ---\n{ocr_text}"
                    except Exception:
                        pass

            except Exception:
                page_text = ""
                page_is_scanned = True
                page_ocr_conf = 0.0

            pages.append({
                "page_number": page_num,
                "text": page_text,
                "tables": [],
                "is_scanned": page_is_scanned,
                "ocr_confidence": page_ocr_conf,
                "has_legacy_font": has_legacy_font,
                "layout_lines": layout_lines,
                "rotation": page_rot,
            })
            total_text_chars += len(page_text)

        # 6. Extract structured document tables using TableExtractor
        from testkart_intelligence.extraction.table_extractor import TableExtractor
        try:
            doc_tables = TableExtractor.extract_tables_from_doc(doc)
            if pages and doc_tables:
                pages[0]["document_tables"] = doc_tables
        except Exception:
            pass

        doc.close()

        # 7. Document-level fallback: If document contains virtually no extractable text across all pages
        all_pages_scanned = all(p.get("is_scanned") for p in pages)
        if total_text_chars < 50 or all_pages_scanned:
            try:
                scanned_pages = self.ocr_engine.extract_text_from_scanned_pdf(pdf_bytes)
                if scanned_pages and any(len(p.get("text", "").strip()) > 0 for p in scanned_pages):
                    for sp in scanned_pages:
                        sp["is_scanned"] = True
                    full_text = "\n\n".join(
                        f"--- Page {p.get('page_number', i+1)} [OCR Scanned: conf={p.get('ocr_confidence', 0.0):.2f}] ---\n{p['text']}"
                        for i, p in enumerate(scanned_pages)
                    )
                    return full_text, scanned_pages, page_count
            except Exception:
                pass

        full_text = "\n\n".join(f"--- Page {p['page_number']} ---\n{p['text']}" for p in pages)
        if has_legacy_font:
            full_text = (
                f"[LEGACY_NON_UNICODE_FONT_DETECTED: Detected legacy non-Unicode fonts: {legacy_font_names}. "
                f"Digital text stream contains unreadable ASCII glyphs; requires glyph transcoder or human review.]\n\n"
                f"{full_text}"
            )

        return full_text, pages, page_count
