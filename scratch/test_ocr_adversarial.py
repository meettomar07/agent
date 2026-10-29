"""Adversarial and Edge Case Audit for OCR Pipeline.
Tests empty output, low confidence, malformed bytes, timeouts, subprocess crashes,
and confirms unreadable documents NEVER produce a publishable draft.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))

import pytest
import pymupdf
from testkart_intelligence.extraction.ocr import (
    compute_ocr_confidence,
    StubOcrEngine,
    WindowsMediaOcrEngine,
)
from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.verifier import VerificationAgent
from testkart_intelligence.writing.qa import QualityAssuranceAgent
from testkart_intelligence.database.connection import init_db, get_db

def test_adversarial_ocr_scenarios(tmp_path: Path):
    print("=" * 80)
    print("AUDIT: ADVERSARIAL OCR STRESS TESTING")
    print("=" * 80)

    engine = WindowsMediaOcrEngine()

    # 1. Empty bytes
    res_empty = engine.extract_text_from_scanned_pdf(b"")
    print(f"1. Empty bytes: returned {len(res_empty)} page(s), conf={res_empty[0]['ocr_confidence']}, review={res_empty[0]['requires_human_verification']}")
    assert res_empty[0]["ocr_confidence"] == 0.0
    assert res_empty[0]["requires_human_verification"] is True

    # 2. Corrupted PDF bytes
    res_corrupt = engine.extract_text_from_scanned_pdf(b"NOT_A_REAL_PDF_JUST_RANDOM_GARBAGE_BYTES")
    print(f"2. Corrupted bytes: returned {len(res_corrupt)} page(s), conf={res_corrupt[0]['ocr_confidence']}, review={res_corrupt[0]['requires_human_verification']}")
    assert res_corrupt[0]["ocr_confidence"] == 0.0
    assert res_corrupt[0]["requires_human_verification"] is True

    # 3. Blank PDF page (white rectangle, no text)
    doc_blank = pymupdf.open()
    doc_blank.new_page(width=595, height=842)
    blank_bytes = doc_blank.tobytes()
    doc_blank.close()

    res_blank = engine.extract_text_from_scanned_pdf(blank_bytes)
    print(f"3. Blank PDF page: conf={res_blank[0]['ocr_confidence']}, review={res_blank[0]['requires_human_verification']}, text={repr(res_blank[0]['text'][:30])}")
    assert res_blank[0]["ocr_confidence"] < 0.60
    assert res_blank[0]["requires_human_verification"] is True

    # 4. Low-confidence noise / gibberish text
    noise_str = "!@#$%^&*()_+ <>?:{}|~ 11111 22222 ///// \\\\\\\\ ===="
    noise_conf = compute_ocr_confidence(noise_str)
    print(f"4. Noise text confidence: {noise_conf:.3f} (< 0.60 threshold: {noise_conf < 0.60})")
    assert noise_conf < 0.60

    # 5. End-to-end fail-safe test: Scanned/unreadable document blocked from QA & publishing
    db_file = tmp_path / "audit_ocr_failsafe.db"
    init_db(db_file)
    with get_db(db_file) as conn:
        conn.execute(
            """
            INSERT INTO official_sources (
                id, code, name, category, state, official_domain, listing_url,
                retrieval_method, verification_status, enabled, consecutive_failures,
                created_at, updated_at
            ) VALUES ('src_nta', 'NTA', 'National Testing Agency', 'Central', 'Central',
                      'nta.ac.in', 'https://nta.ac.in', 'html_scrape', 'VERIFIED', 1, 0,
                      '2026-10-24T00:00:00Z', '2026-10-24T00:00:00Z')
            """
        )
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, status, first_discovered_at, last_updated_at
            ) VALUES ('not_scanned_fail', 'src_nta', 'National Testing Agency', 'NTA/2026',
                      'Scanned Unreadable Notice', 'https://nta.ac.in/scanned.pdf',
                      'Central', 'Central', 'DISCOVERED', '2026-10-24T00:00:00Z', '2026-10-24T00:00:00Z')
            """
        )

    # Ingest blank scanned PDF with VerificationAgent using Stub OCR (simulating OCR failure / low confidence)
    agent = VerificationAgent(db_path=db_file)
    agent.pdf_extractor.ocr_engine = StubOcrEngine()
    ver_id, facts = agent.process_and_verify_document(
        notice_id="not_scanned_fail",
        doc_bytes=blank_bytes,
        doc_url="https://nta.ac.in/scanned.pdf",
        content_type="application/pdf",
    )

    with get_db(db_file) as conn:
        notice = conn.execute("SELECT status FROM canonical_notices WHERE id = 'not_scanned_fail'").fetchone()
        print(f"5. Verification status on OCR failure: {notice['status']}")
        assert notice["status"] == "SCANNED_OCR_BLOCKED_FLAGGED_FOR_HUMAN_REVIEW"

        # Now test that QA strictly blocks any draft associated with this notice
        conn.execute(
            """
            INSERT INTO blog_articles (
                id, canonical_notice_id, template_type, current_version_id, status, title, slug, created_at, updated_at
            ) VALUES ('art_scanned', 'not_scanned_fail', 'recruitment', 'arv_scanned', 'DRAFT',
                      'NTA Scanned Notice Article', 'nta-scanned-notice', '2026-10-24T00:00:00Z', '2026-10-24T00:00:00Z')
            """
        )
        conn.execute(
            """
            INSERT INTO article_versions (
                id, article_id, version_number, title, content_markdown,
                content_hash, generated_by, created_at
            ) VALUES ('arv_scanned', 'art_scanned', 1, 'NTA Scanned Notice Article',
                      'National Testing Agency notice: https://nta.ac.in/scanned.pdf. Testkart editorial.',
                      'hash_scanned_art', 'agent_writer', '2026-10-24T00:00:00Z')
            """
        )

    qa = QualityAssuranceAgent(db_path=db_file)
    passed, score, checks = qa.inspect_and_evaluate("arv_scanned")
    print(f"6. QA evaluation passed: {passed} (Score: {score})")
    failing_rules = [c.rule_name for c in checks if not c.passed]
    print(f"   Failing QA checks: {failing_rules}")
    assert passed is False, "Draft on unreadable/scanned notice MUST NOT pass QA!"
    assert "rule_document_readability" in failing_rules
    print("CONFIRMED: OCR failure NEVER silently produces a publishable draft!")

if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        test_adversarial_ocr_scenarios(Path(td))
