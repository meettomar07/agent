"""Unit tests for Stage 3: PDF/HTML extraction, structured facts, and verification."""

import pytest
from pathlib import Path
import pymupdf

from testkart_intelligence.database.connection import init_db, get_db
from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor, PdfExtractionError, StubOcrEngine
from testkart_intelligence.extraction.html_extractor import HtmlDocumentExtractor
from testkart_intelligence.extraction.fact_extractor import FactExtractor
from testkart_intelligence.extraction.verifier import VerificationAgent


def create_sample_pdf_bytes(pages_text: list[str]) -> bytes:
    """Helper to generate an in-memory PDF using PyMuPDF."""
    doc = pymupdf.open()
    for text in pages_text:
        page = doc.new_page()
        page.insert_text((50, 72), text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture
def test_db(tmp_path: Path):
    db_file = tmp_path / "test_stage3.db"
    init_db(db_file)
    with get_db(db_file) as conn:
        conn.execute(
            """
            INSERT INTO official_sources (
                id, code, name, category, state, official_domain, listing_url,
                retrieval_method, verification_status, enabled, consecutive_failures,
                created_at, updated_at
            ) VALUES ('src_upsc', 'UPSC', 'Union Public Service Commission', 'Central', 'Central',
                      'upsc.gov.in', 'https://upsc.gov.in/notices', 'html_scrape', 'VERIFIED', 1, 0,
                      '2026-10-24T00:00:00Z', '2026-10-24T00:00:00Z')
            """
        )
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, status, first_discovered_at, last_updated_at
            ) VALUES ('not_test_geo', 'src_upsc', 'Union Public Service Commission', '02/2026-GEOL',
                      'Combined Geo-Scientist Examination 2026', 'https://upsc.gov.in/geo-2026.pdf',
                      'Central', 'Central', 'DISCOVERED', '2026-10-24T00:00:00Z', '2026-10-24T00:00:00Z')
            """
        )
    return db_file


def test_pdf_extractor_multi_page():
    """Verify PyMuPDF extracts page numbers and text correctly."""
    p1 = "UNION PUBLIC SERVICE COMMISSION\nNotice No. 02/2026-GEOL\nTotal Vacancies: 85"
    p2 = "Start Date: 15-11-2026\nLast Date: 15-12-2026\nAge limit: 21 to 32 years"
    pdf_bytes = create_sample_pdf_bytes([p1, p2])

    extractor = PdfDocumentExtractor()
    full_text, pages, count = extractor.extract(pdf_bytes)

    assert count == 2
    assert len(pages) == 2
    assert pages[0]["page_number"] == 1
    assert "Notice No. 02/2026-GEOL" in pages[0]["text"]
    assert pages[1]["page_number"] == 2
    assert "15-12-2026" in pages[1]["text"]


def test_pdf_extractor_empty_or_corrupt_error():
    """Verify empty or corrupt PDF raises PdfExtractionError."""
    extractor = PdfDocumentExtractor()
    with pytest.raises(PdfExtractionError):
        extractor.extract(b"")

    with pytest.raises(PdfExtractionError):
        extractor.extract(b"Not a real pdf document file content")


def test_pdf_extractor_scanned_ocr_fallback():
    """Verify that a PDF with no text triggers the OCR engine interface."""
    # Blank PDF page
    doc = pymupdf.open()
    doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()

    extractor = PdfDocumentExtractor(ocr_engine=StubOcrEngine())
    full_text, pages, count = extractor.extract(pdf_bytes)

    assert count == 1
    assert "SCANNED DOCUMENT" in full_text


def test_fact_extraction_and_verification_pipeline(test_db: Path):
    """Test full fact extraction, evidence linking, and contradiction handling."""
    notice_text = (
        "UNION PUBLIC SERVICE COMMISSION\n"
        "Advt. No. 02/2026-GEOL\n"
        "Combined Geo-Scientist Examination 2026\n"
        "Total Vacancies: 85\n"
        "Opening Date: 15/11/2026\n"
        "Closing Date: 15/12/2026\n"
        "Date of Examination: 18/02/2027\n"
        "Age limit: 21 to 32 years\n"
        "Application Fee: Rs. 200 for General/OBC candidates, Nil for SC/ST\n"
        "Educational Qualification: Master's Degree in Geological Science\n"
        "Pay Scale: Level 10 of Pay Matrix\n"
    )
    pdf_bytes = create_sample_pdf_bytes([notice_text])

    verifier = VerificationAgent(db_path=test_db)
    v_id, facts = verifier.process_and_verify_document(
        notice_id="not_test_geo",
        doc_bytes=pdf_bytes,
        doc_url="https://upsc.gov.in/geo-2026.pdf",
        content_type="application/pdf",
    )

    assert v_id.startswith("ver_")
    fact_map = {f.key: f for f in facts}

    assert fact_map["recruiting_authority"].value == "Union Public Service Commission"
    assert fact_map["notice_number"].value == "02/2026-GEOL"
    assert fact_map["total_vacancies"].value == "85"
    assert fact_map["application_start_date"].value == "15/11/2026"
    assert fact_map["application_end_date"].value == "15/12/2026"
    assert fact_map["exam_date"].value == "18/02/2027"

    # All these facts must be VERIFIED
    assert fact_map["total_vacancies"].status == "VERIFIED"
    assert fact_map["application_end_date"].status == "VERIFIED"
    assert fact_map["total_vacancies"].page_number == 1
    assert fact_map["total_vacancies"].evidence_text is not None

    # Verify database persistence
    with get_db(test_db) as conn:
        ver_row = conn.execute("SELECT * FROM notice_versions WHERE id = ?", (v_id,)).fetchone()
        assert ver_row is not None
        assert ver_row["version_number"] == 1
        assert ver_row["document_type"] == "PDF"

        fact_rows = conn.execute("SELECT * FROM extracted_facts WHERE notice_version_id = ?", (v_id,)).fetchall()
        assert len(fact_rows) >= 6


def test_contradiction_detection(test_db: Path):
    """Verify that contradictory dates (closing before opening) are flagged."""
    contradictory_text = (
        "Notice No. 99/2026\n"
        "Total Vacancies: 50\n"
        "Opening Date: 20/12/2026\n"
        "Closing Date: 10/11/2026\n"  # Invalid! Closing before opening
    )
    pdf_bytes = create_sample_pdf_bytes([contradictory_text])

    verifier = VerificationAgent(db_path=test_db)
    v_id, facts = verifier.process_and_verify_document(
        notice_id="not_test_geo",
        doc_bytes=pdf_bytes,
        doc_url="https://upsc.gov.in/geo-2026.pdf",
        content_type="application/pdf",
    )

    fact_map = {f.key: f for f in facts}
    assert fact_map["application_end_date"].status == "CONTRADICTORY"
    assert "before start date" in fact_map["application_end_date"].notes
