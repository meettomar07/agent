"""Automated regression and acceptance tests for OCR integration and the Evidence & Validation Reliability Gate."""

import json
from pathlib import Path
import pytest
import pymupdf

from testkart_intelligence.config import settings
from testkart_intelligence.database.connection import init_db, get_db
from testkart_intelligence.extraction.ocr import (
    compute_ocr_confidence,
    StubOcrEngine,
    WindowsMediaOcrEngine,
    get_default_ocr_engine,
)
from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.fact_extractor import ExtractedFactItem
from testkart_intelligence.extraction.verifier import VerificationAgent
from testkart_intelligence.writing.qa import QualityAssuranceAgent


@pytest.fixture
def test_db(tmp_path: Path):
    db_file = tmp_path / "test_ocr_gate.db"
    init_db(db_file)
    with get_db(db_file) as conn:
        conn.execute(
            """
            INSERT INTO official_sources (
                id, code, name, category, state, official_domain, listing_url,
                retrieval_method, verification_status, enabled, consecutive_failures,
                created_at, updated_at
            ) VALUES ('src_tnpsc', 'TNPSC', 'Tamil Nadu Public Service Commission', 'State', 'Tamil Nadu',
                      'tnpsc.gov.in', 'https://tnpsc.gov.in/notices', 'html_scrape', 'VERIFIED', 1, 0,
                      '2026-10-24T00:00:00Z', '2026-10-24T00:00:00Z')
            """
        )
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, status, first_discovered_at, last_updated_at
            ) VALUES ('not_gate_01', 'src_tnpsc', 'Tamil Nadu Public Service Commission', '08/2026',
                      'Assistant Engineer Recruitment 2026', 'https://tnpsc.gov.in/notices/ae2026.pdf',
                      'State', 'Tamil Nadu', 'DISCOVERED', '2026-10-24T00:00:00Z', '2026-10-24T00:00:00Z')
            """
        )
    return db_file


# =========================================================================
# 1. OCR Confidence Scoring Tests
# =========================================================================

def test_compute_ocr_confidence_empty_and_short():
    """Verify empty or very short strings yield 0.0 confidence."""
    assert compute_ocr_confidence("") == 0.0
    assert compute_ocr_confidence("   ") == 0.0
    assert compute_ocr_confidence("abc") == 0.0


def test_compute_ocr_confidence_official_text():
    """Verify structured official text receives high confidence score (>= 0.60)."""
    text = (
        "TAMIL NADU PUBLIC SERVICE COMMISSION\n"
        "Notification No. 05/2026 Dated: 12.03.2026\n"
        "Applications are invited through online mode for direct recruitment to the posts of "
        "Assistant Agricultural Officer and Assistant Horticultural Officer in the Tamil Nadu "
        "Agricultural Extension Subordinate Service. Total Vacancies: 185. Application fee is Rs. 150. "
        "Last date for submission of online application is 15.04.2026."
    )
    score = compute_ocr_confidence(text)
    assert score >= 0.70, f"Expected high score, got {score}"


def test_compute_ocr_confidence_gibberish_and_noise():
    """Verify symbol noise and unreadable character sequences receive low confidence (< 0.60)."""
    noise_text = "%%%% $$$$ #### @@@@ ^^^^ ~~~~~ 1111111 2222222 ||||| \\\\\\\\ >>> <<< ====="
    score = compute_ocr_confidence(noise_text)
    assert score < 0.60, f"Expected low score for noise, got {score}"


# =========================================================================
# 2. OCR Engine Mechanics & Graceful Fallback
# =========================================================================

def test_stub_ocr_engine_behavior():
    """Verify StubOcrEngine returns structured review-flagged placeholder."""
    stub = StubOcrEngine()
    res = stub.extract_text_from_scanned_pdf(b"%PDF-sample-bytes")
    assert len(res) == 1
    assert res[0]["ocr_confidence"] == 0.0
    assert res[0]["requires_human_verification"] is True
    assert "[SCANNED DOCUMENT" in res[0]["text"]

    single = stub.ocr_page_pixmap(None, page_num=2)
    assert single["page_number"] == 2
    assert single["ocr_confidence"] == 0.0
    assert single["requires_human_verification"] is True


def test_windows_media_ocr_engine_empty_bytes_fallback():
    """Verify WindowsMediaOcrEngine handles empty bytes cleanly without crashing."""
    engine = WindowsMediaOcrEngine()
    res = engine.extract_text_from_scanned_pdf(b"")
    assert len(res) >= 1
    assert res[0]["ocr_confidence"] == 0.0


def test_pdf_extractor_scanned_density_detection():
    """Verify that a page with zero text is flagged as is_scanned=True."""
    # Create empty PDF page with PyMuPDF (no text inserted)
    doc = pymupdf.open()
    doc.new_page(width=595, height=842)
    pdf_bytes = doc.tobytes()
    doc.close()

    extractor = PdfDocumentExtractor()
    full_text, pages, count = extractor.extract(pdf_bytes)
    assert count == 1
    assert pages[0]["is_scanned"] is True
    assert pages[0]["ocr_confidence"] >= 0.0


# =========================================================================
# 3. Evidence & Validation Gate Unit Tests
# =========================================================================

def test_validation_gate_1_verbatim_evidence_check():
    """Gate 1: If supporting evidence snippet is missing from raw text, fact is UNVERIFIED."""
    agent = VerificationAgent()
    facts = [
        ExtractedFactItem(
            key="application_end_date",
            value="30-10-2026",
            evidence_text="Non-existent phrase nowhere in document",
            page_number=1,
            confidence=0.9,
            status="VERIFIED",
        )
    ]
    checked = agent._verify_and_cross_check_facts(facts, full_text="Only generic text here.")
    assert checked[0].status == "UNVERIFIED"
    assert "Supporting quote not found verbatim" in checked[0].notes


def test_validation_gate_2a_deadline_ordering_contradiction():
    """Gate 2a: End date before start date must be flagged CONTRADICTORY."""
    agent = VerificationAgent()
    doc_text = "Start: 25-10-2026. Closing: 10-10-2026."
    facts = [
        ExtractedFactItem(
            key="application_start_date",
            value="25-10-2026",
            evidence_text="Start: 25-10-2026",
            page_number=1,
            confidence=0.95,
            status="VERIFIED",
        ),
        ExtractedFactItem(
            key="application_end_date",
            value="10-10-2026",
            evidence_text="Closing: 10-10-2026",
            page_number=1,
            confidence=0.95,
            status="VERIFIED",
        ),
    ]
    checked = agent._verify_and_cross_check_facts(facts, full_text=doc_text)
    end_f = [f for f in checked if f.key == "application_end_date"][0]
    assert end_f.status == "CONTRADICTORY"
    assert "before start date" in end_f.notes


def test_validation_gate_2b_age_cutoff_vs_application_deadline():
    """Gate 2b: Age reckoning cut-off date mistaken for application deadline is flagged CONTRADICTORY."""
    agent = VerificationAgent()
    doc_text = "The age limit will be reckoned as on 01.08.2026 for all posts."
    facts = [
        ExtractedFactItem(
            key="application_end_date",
            value="01-08-2026",
            evidence_text="reckoned as on 01.08.2026",
            page_number=1,
            confidence=0.85,
            status="VERIFIED",
        )
    ]
    checked = agent._verify_and_cross_check_facts(facts, full_text=doc_text)
    assert checked[0].status == "CONTRADICTORY"
    assert "Age cut-off date" in checked[0].notes


def test_validation_gate_2c_exam_date_vs_application_deadline_disambiguation():
    """Gate 2c: Examination date extracted as application closing deadline is flagged CONTRADICTORY."""
    agent = VerificationAgent()
    doc_text = "The schedule of CBT examination date will be 24-11-2026 across centers."
    facts = [
        ExtractedFactItem(
            key="application_end_date",
            value="24-11-2026",
            evidence_text="schedule of CBT examination date will be 24-11-2026",
            page_number=1,
            confidence=0.80,
            status="VERIFIED",
        )
    ]
    checked = agent._verify_and_cross_check_facts(facts, full_text=doc_text)
    assert checked[0].status == "CONTRADICTORY"
    assert "Examination date" in checked[0].notes


def test_validation_gate_3_vacancy_sanity_and_post_wise_flagging():
    """Gate 3: Negative vacancies, question counts, and post-wise breakdowns are caught and flagged."""
    agent = VerificationAgent()

    # Negative vacancies
    f_neg = [
        ExtractedFactItem(
            key="total_vacancies",
            value="-5",
            evidence_text="-5 vacancies",
            page_number=1,
            confidence=0.9,
            status="VERIFIED",
        )
    ]
    checked = agent._verify_and_cross_check_facts(f_neg, full_text="-5 vacancies")
    assert checked[0].status == "CONTRADICTORY"

    # Number of questions mistaken for vacancies
    f_q = [
        ExtractedFactItem(
            key="total_vacancies",
            value="100",
            evidence_text="test comprises 100 questions of 1 mark each",
            page_number=1,
            confidence=0.9,
            status="VERIFIED",
        )
    ]
    checked_q = agent._verify_and_cross_check_facts(f_q, full_text="test comprises 100 questions of 1 mark each")
    assert checked_q[0].status == "CONTRADICTORY"
    assert "refers to questions" in checked_q[0].notes

    # Post-specific count in tabular recruitment notice flagged for review
    doc_tab = "Name of post: Assistant Director (1 post), Lecturer (5 posts). Tabular breakdown below."
    f_post = [
        ExtractedFactItem(
            key="total_vacancies",
            value="1",
            evidence_text="post of Assistant Director (1 post)",
            page_number=1,
            confidence=0.85,
            status="VERIFIED",
        )
    ]
    checked_p = agent._verify_and_cross_check_facts(f_post, full_text=doc_tab)
    assert checked_p[0].status == "POST_WISE_BREAKDOWN_FLAGGED_FOR_REVIEW"


def test_validation_gate_4_notice_number_sanity():
    """Gate 4: Notice number containing no digits or dictionary words is marked UNVERIFIED."""
    agent = VerificationAgent()
    facts = [
        ExtractedFactItem(
            key="notice_number",
            value="ADVERTISEMENT",
            evidence_text="ADVERTISEMENT",
            page_number=1,
            confidence=0.8,
            status="VERIFIED",
        )
    ]
    checked = agent._verify_and_cross_check_facts(facts, full_text="ADVERTISEMENT")
    assert checked[0].status == "UNVERIFIED"
    assert "contains no digits" in checked[0].notes


def test_validation_gate_5_fee_sanity_and_category_flagging():
    """Gate 5: Concession-only category fees (e.g. SC/ST: Nil) are flagged for human review."""
    agent = VerificationAgent()
    doc_text = "Application fee for SC/ST/Women candidates is Nil."
    facts = [
        ExtractedFactItem(
            key="application_fee",
            value="Nil",
            evidence_text="Application fee for SC/ST/Women candidates is Nil",
            page_number=1,
            confidence=0.8,
            status="VERIFIED",
        )
    ]
    checked = agent._verify_and_cross_check_facts(facts, full_text=doc_text)
    assert checked[0].status == "CATEGORY_FEE_FLAGGED_FOR_REVIEW"
    assert "concession only" in checked[0].notes


def test_validation_gate_7_truncated_eligibility_flagging():
    """Gate 7: Incomplete eligibility criteria ending with conjunction or comma are flagged."""
    agent = VerificationAgent()
    doc_text = "Candidates must possess a Bachelor's Degree in Engineering or"
    facts = [
        ExtractedFactItem(
            key="eligibility_qualification",
            value="Bachelor's Degree in Engineering or",
            evidence_text=doc_text,
            page_number=1,
            confidence=0.85,
            status="VERIFIED",
        )
    ]
    checked = agent._verify_and_cross_check_facts(facts, full_text=doc_text)
    assert checked[0].status == "TRUNCATED_ELIGIBILITY_FLAGGED_FOR_REVIEW"
    assert "dangling conjunction" in checked[0].notes


# =========================================================================
# 4. QA Gate Enforcement Tests
# =========================================================================

def test_qa_gate_blocks_draft_with_review_flagged_facts(test_db: Path):
    """Verify that any draft with facts flagged for review strictly fails QA Check 3."""
    with get_db(test_db) as conn:
        # Create notice version
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, raw_text, page_count, retrieved_at
            ) VALUES ('nv_gate_1', 'not_gate_01', 1, 'https://tnpsc.gov.in/notices/ae2026.pdf', 'hash123',
                      'PDF', 'data/doc.pdf', 'Official notification text', 1, '2026-10-24T00:00:00Z')
            """
        )
        # Insert extracted fact with POST_WISE_BREAKDOWN_FLAGGED_FOR_REVIEW status
        conn.execute(
            """
            INSERT INTO extracted_facts (
                id, notice_version_id, fact_key, fact_value, confidence,
                evidence_text, page_number, verified_status, verification_notes, created_at
            ) VALUES ('f_vac_1', 'nv_gate_1', 'total_vacancies', '185', 0.85,
                      'post of Assistant Director: 185 posts', 1, 'POST_WISE_BREAKDOWN_FLAGGED_FOR_REVIEW',
                      'Sub-post breakdown flagged for review', '2026-10-24T00:00:00Z')
            """
        )
        # Create blog article and article version
        conn.execute(
            """
            INSERT INTO blog_articles (
                id, canonical_notice_id, template_type, current_version_id, status, title, slug, created_at, updated_at
            ) VALUES ('art_gate_1', 'not_gate_01', 'recruitment', 'arv_gate_1', 'DRAFT',
                      'TNPSC Assistant Engineer Recruitment 2026', 'tnpsc-ae-2026', '2026-10-24T00:00:00Z', '2026-10-24T00:00:00Z')
            """
        )
        draft_md = (
            "# TNPSC Assistant Engineer Recruitment 2026\n\n"
            "Tamil Nadu Public Service Commission has announced 185 vacancies for Assistant Engineer. "
            "For full details and application form, visit https://tnpsc.gov.in/notices/ae2026.pdf\n\n"
            "Editorial review and analysis provided by Testkart Editorial Team."
        )
        conn.execute(
            """
            INSERT INTO article_versions (
                id, article_id, version_number, title, content_markdown,
                content_hash, generated_by, created_at
            ) VALUES ('arv_gate_1', 'art_gate_1', 1, 'TNPSC Assistant Engineer Recruitment 2026',
                      ?, 'hash_art_1', 'agent_writer', '2026-10-24T00:00:00Z')
            """,
            (draft_md,),
        )

    qa = QualityAssuranceAgent(db_path=test_db)
    passed, score, checks = qa.inspect_and_evaluate("arv_gate_1")
    assert passed is False, "Draft with POST_WISE_BREAKDOWN_FLAGGED_FOR_REVIEW must fail QA"
    failing_rules = [c.rule_name for c in checks if not c.passed]
    assert "rule_no_contradictory_facts" in failing_rules


# =========================================================================
# 5. Dataset Independence and Integrity Verification
# =========================================================================

def test_independent_validation_dataset_manifest_integrity():
    """Verify that the new validation dataset has >= 50 notices and zero hash overlap with baseline sets."""
    new_manifest_path = Path("NEW_VALIDATION_DATASET_MANIFEST.json")
    assert new_manifest_path.exists(), "NEW_VALIDATION_DATASET_MANIFEST.json must exist"

    with open(new_manifest_path, "r", encoding="utf-8") as f:
        new_manifest = json.load(f)

    doc_dict = new_manifest.get("documents", {})
    assert len(doc_dict) >= 50, f"Independent validation dataset must contain at least 50 notices, found {len(doc_dict)}"

    # Confirm all files exist on disk
    new_hashes = set()
    val_dir = Path("data/new_validation_notices")
    for fname, item in doc_dict.items():
        p = val_dir / fname
        assert p.exists(), f"Notice file {p} referenced in manifest does not exist"
        assert item["size_bytes"] > 0
        new_hashes.add(item["sha256"])

    # Load frozen held-out manifest (33 notices)
    frozen_manifest_path = Path("FROZEN_HELD_OUT_DATASET_MANIFEST.json")
    assert frozen_manifest_path.exists(), "FROZEN_HELD_OUT_DATASET_MANIFEST.json must exist"
    with open(frozen_manifest_path, "r", encoding="utf-8") as f:
        frozen_manifest = json.load(f)

    frozen_hashes = {info["sha256"] for info in frozen_manifest.get("documents", {}).values()}
    assert len(frozen_hashes) == 33, f"Frozen dataset must have 33 unique notices, found {len(frozen_hashes)}"

    # Assert 0 collisions with frozen baseline
    collisions_frozen = new_hashes.intersection(frozen_hashes)
    assert len(collisions_frozen) == 0, f"Contamination detected! New validation set shares hashes with frozen set: {collisions_frozen}"

    # Load development manifest (13 notices)
    dev_manifest_path = Path("DEVELOPMENT_SET_MANIFEST.json")
    if dev_manifest_path.exists():
        with open(dev_manifest_path, "r", encoding="utf-8") as f:
            dev_manifest = json.load(f)
        dev_hashes = {info["sha256"] for info in dev_manifest.get("documents", {}).values()}
        collisions_dev = new_hashes.intersection(dev_hashes)
        assert len(collisions_dev) == 0, f"Contamination detected! New validation set shares hashes with development set: {collisions_dev}"
