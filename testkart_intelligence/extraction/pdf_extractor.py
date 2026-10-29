"""PyMuPDF-based text and metadata extractor for official government PDF notifications."""

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
    """Raised when PDF cannot be read or is corrupted."""
    pass


class PdfDocumentExtractor:
    """Extracts text page-by-page from PDF documents using PyMuPDF."""

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
        """Extract text and metadata from PDF bytes.

        Returns:
            Tuple of (full_text, pages_list, total_page_count)
            where pages_list is [{"page_number": int, "text": str}]
        """
        if not pdf_bytes or len(pdf_bytes) == 0:
            raise PdfExtractionError("Cannot extract from empty PDF bytes")

        try:
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        except Exception as exc:
            raise PdfExtractionError(f"Failed to open PDF: {exc}") from exc

        page_count = len(doc)
        if page_count == 0:
            doc.close()
            raise PdfExtractionError("PDF document has 0 pages")

        pages: List[Dict[str, Any]] = []
        total_text_chars = 0
        has_legacy_font = False
        legacy_font_names: List[str] = []

        LEGACY_FONT_MARKERS = ("kruti", "walkman", "chanakya", "devlys", "shivaji", "dv-tt", "shree", "aps-")

        for page_idx in range(page_count):
            page_num = page_idx + 1
            layout_lines: List[str] = []
            page_rot = 0
            try:
                page = doc[page_idx]
                page_rot = getattr(page, "rotation", 0)
                page_text = page.get_text("text").strip()
                # Check page fonts for legacy non-Unicode font encodings
                fonts = page.get_fonts()
                for f in fonts:
                    fname = (f[3] if len(f) > 3 else "").lower()
                    if any(marker in fname for marker in LEGACY_FONT_MARKERS):
                        has_legacy_font = True
                        if f[3] not in legacy_font_names:
                            legacy_font_names.append(f[3])

                layout_lines = self._reconstruct_layout_lines(page)
                if layout_lines and (page_rot != 0 or len(layout_lines) > 2):
                    page_text = f"{page_text}\n\n[LAYOUT_RECONSTRUCTED_TABLE]\n" + "\n".join(layout_lines)
            except Exception:
                page_text = ""

            pages.append({
                "page_number": page_num,
                "text": page_text,
                "has_legacy_font": has_legacy_font,
                "layout_lines": layout_lines,
                "rotation": page_rot,
            })
            total_text_chars += len(page_text)

        # Extract structured document tables using TableExtractor
        from testkart_intelligence.extraction.table_extractor import TableExtractor
        try:
            doc_tables = TableExtractor.extract_tables_from_doc(doc)
            if pages and doc_tables:
                pages[0]["document_tables"] = doc_tables
        except Exception:
            pass

        doc.close()

        # If document contains virtually no extractable text across all pages, it's likely scanned
        if total_text_chars < 50:
            scanned_pages = self.ocr_engine.extract_text_from_scanned_pdf(pdf_bytes)
            for sp in scanned_pages:
                sp["is_scanned"] = True
            full_text = "\n\n".join(
                f"--- Page {p.get('page_number', i+1)} [OCR Scanned: conf={p.get('ocr_confidence', 0.0):.2f}] ---\n{p['text']}"
                for i, p in enumerate(scanned_pages)
            )
            return full_text, scanned_pages, page_count

        full_text = "\n\n".join(f"--- Page {p['page_number']} ---\n{p['text']}" for p in pages)
        if has_legacy_font:
            full_text = (
                f"[LEGACY_NON_UNICODE_FONT_DETECTED: Detected legacy non-Unicode fonts: {legacy_font_names}. "
                f"Digital text stream contains unreadable ASCII glyphs; requires glyph transcoder or human review.]\n\n"
                f"{full_text}"
            )
        return full_text, pages, page_count
