"""Targeted regression tests for classification, exam-date extraction, and parent-notice linking remediations."""

import hashlib
import json
from pathlib import Path
import sqlite3
import pytest

from testkart_intelligence.classification.classifier import NoticeClassifier, NoticeCategory
from testkart_intelligence.extraction.fact_extractor import FactExtractor
from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.html_extractor import HtmlDocumentExtractor


def test_admit_card_vs_exam_schedule_classification():
    """Timetables and exam schedules with secondary admit card mentions must NOT be classified as admit card releases."""
    # 1. Timetable with admit card mention in body
    title1 = "Combined Geo-Scientist (Preliminary) Examination 2027 Timetable and Schedule"
    body1 = "The Examination will be held on 18th February 2027 in two sessions. The e-Admit Cards will be uploaded 3 weeks before the examination."
    cat1 = NoticeClassifier.classify(title1, body1)
    assert cat1 == NoticeCategory.EXAM_DATE_ANNOUNCEMENT, f"Expected EXAM_DATE_ANNOUNCEMENT, got {cat1}"

    # 2. Examination schedule with admit card mention in body
    title2 = "Examination Schedule for Medical Officer (Allopathy) Screening Examination"
    body2 = "Date of Screening Examination: 15 December 2026. Admit cards will be available for download 7 days prior to exam."
    cat2 = NoticeClassifier.classify(title2, body2)
    assert cat2 == NoticeCategory.EXAM_DATE_ANNOUNCEMENT, f"Expected EXAM_DATE_ANNOUNCEMENT, got {cat2}"

    # 3. Pure Admit Card release announcement
    title3 = "Release of Hall Ticket / Admit Card for Combined Civil Services Examination II"
    body3 = "Candidates can download their Memorandum of Admission (Hall Ticket) using their login credentials."
    cat3 = NoticeClassifier.classify(title3, body3)
    assert cat3 == NoticeCategory.ADMIT_CARD_RELEASE, f"Expected ADMIT_CARD_RELEASE, got {cat3}"


def test_admission_exam_precedence_over_recruitment():
    """Admissions and entrance examination notices with application dates must not be classified as recruitment."""
    title = "Inviting Online Applications for Study Webs of Active Learning (SWAYAM) January 2027 Semester"
    body = "Dates for submission of online applications: 15.11.2026 to 15.12.2026. Eligibility: Students enrolled in university degree."
    facts = {
        "application_start_date": "15.11.2026",
        "application_end_date": "15.12.2026"
    }
    cat = NoticeClassifier.classify(title, body, facts=facts)
    assert cat == NoticeCategory.ADMISSION_OR_ENTRANCE_EXAM, f"Expected ADMISSION_OR_ENTRANCE_EXAM, got {cat}"


def test_standalone_admit_card_never_links_via_title_similarity():
    """Standalone admit card release must NEVER link to a recruitment notification on title words alone."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE canonical_notices (id TEXT PRIMARY KEY, source_id TEXT, title TEXT, notice_number TEXT, classification TEXT, first_discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    
    # Insert parent recruitment notice
    conn.execute(
        "INSERT INTO canonical_notices (id, source_id, title, notice_number, classification) VALUES (?, ?, ?, ?, ?)",
        ("parent_1", "src_tnpsc", "Combined Civil Services Examination II (Group II and IIA Services) Notification No. 08/2026", "Notification No. 08/2026", "RECRUITMENT_NOTIFICATION")
    )
    conn.commit()

    # Attempt to link standalone admit card notice
    parent_id, rel_type, conf, notes = NoticeClassifier.link_to_parent_notice(
        notice_id="admit_1",
        source_id="src_tnpsc",
        title="Release of Hall Ticket / Admit Card for Combined Civil Services Examination II",
        notice_number="Press Release No. 45/2026",
        category=NoticeCategory.ADMIT_CARD_RELEASE,
        conn=conn
    )

    assert parent_id is None, f"Expected None parent link for standalone admit card, but got {parent_id}"
    assert "title token matching is prohibited" in notes.lower()


def test_parent_linking_for_corrigenda_with_exact_and_normalized_notice_numbers():
    """Corrigenda and addenda must link accurately when notice numbers or child title markers match."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE canonical_notices (id TEXT PRIMARY KEY, source_id TEXT, title TEXT, notice_number TEXT, classification TEXT, first_discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")

    conn.execute(
        "INSERT INTO canonical_notices (id, source_id, title, notice_number, classification) VALUES (?, ?, ?, ?, ?)",
        ("parent_ssc", "src_ssc", "Notice of Constable (GD) in Central Armed Police Forces Examination, 2026", "Notice No. 3/1/2026-P&P-I", "RECRUITMENT_NOTIFICATION")
    )
    conn.commit()

    # Link corrigendum with prefix variation ("F.No. 3/1/2026-P&P-I" vs "Notice No. 3/1/2026-P&P-I")
    parent_id, rel_type, conf, notes = NoticeClassifier.link_to_parent_notice(
        notice_id="corr_ssc",
        source_id="src_ssc",
        title="Corrigendum to Constable (GD) in Central Armed Police Forces Examination, 2026",
        notice_number="F.No. 3/1/2026-P&P-I",
        category=NoticeCategory.CORRIGENDUM,
        conn=conn
    )

    assert parent_id == "parent_ssc", f"Expected parent_ssc, got {parent_id} ({notes})"
    assert conf >= 0.90


def test_exam_date_extraction_prose_and_multistage():
    """Verify robust extraction of prose dates, screening dates, and revised schedules."""
    # 1. Month, Year with comma
    p1 = [{"page_number": 1, "text": "Staff Selection Commission\nSchedule of Computer Based Examination: December, 2026\n"}]
    f1 = FactExtractor.extract_from_pages(p1, "SSC", "Exam Notice", "url")
    ed1 = next((f.value for f in f1 if f.key == "exam_date"), None)
    assert ed1 == "December, 2026", f"Expected 'December, 2026', got '{ed1}'"

    # 2. Prose "will be held on"
    p2 = [{"page_number": 1, "text": "Union Public Service Commission\nThe Examination will be held on 18th February 2027 in two sessions.\n"}]
    f2 = FactExtractor.extract_from_pages(p2, "UPSC", "Timetable", "url")
    ed2 = next((f.value for f in f2 if f.key == "exam_date"), None)
    assert ed2 == "18th February 2027", f"Expected '18th February 2027', got '{ed2}'"

    # 3. Plural "Dates of Examination"
    p3 = [{"page_number": 1, "text": "National Testing Agency\nDates of Examination: 17 and 18 January 2027\n"}]
    f3 = FactExtractor.extract_from_pages(p3, "NTA", "UGC NET", "url")
    ed3 = next((f.value for f in f3 if f.key == "exam_date"), None)
    assert ed3 == "17 and 18 January 2027", f"Expected '17 and 18 January 2027', got '{ed3}'"

    # 4. Screening examination
    p4 = [{"page_number": 1, "text": "UPPSC\nDate of Screening Examination: 15 December 2026 from 11:00 AM to 1:00 PM\n"}]
    f4 = FactExtractor.extract_from_pages(p4, "UPPSC", "MO Screening", "url")
    ed4 = next((f.value for f in f4 if f.key == "exam_date"), None)
    assert ed4 == "15 December 2026", f"Expected '15 December 2026', got '{ed4}'"


def test_eligibility_extraction_standalone_headers_and_qualifications():
    """Verify extraction of standalone Qualifications: headers and medical/law/student qualifications."""
    # 1. Standalone Qualifications: with MBBS
    p1 = [{"page_number": 1, "text": "UPSC Advt\nQualifications: A recognized MBBS degree qualification included in First Schedule.\n"}]
    f1 = FactExtractor.extract_from_pages(p1, "UPSC", "Medical Officer", "url")
    eq1 = next((f.value for f in f1 if f.key == "eligibility"), None)
    assert eq1 is not None and "MBBS" in eq1

    # 2. Standalone Eligibility: with student enrollment
    p2 = [{"page_number": 1, "text": "NTA Public Notice\nEligibility: Students enrolled in university degree or diploma courses.\n"}]
    f2 = FactExtractor.extract_from_pages(p2, "NTA", "SWAYAM", "url")
    eq2 = next((f.value for f in f2 if f.key == "eligibility"), None)
    assert eq2 is not None and "Students enrolled in" in eq2


def test_remediation_evaluation_dataset_isolation_and_integrity():
    """Verify that the fresh remediation evaluation dataset has zero hash collision against all prior manifests."""
    prior_manifests = [
        "DEVELOPMENT_SET_MANIFEST.json",
        "FROZEN_HELD_OUT_DATASET_MANIFEST.json",
        "GENERALIZATION_SET_MANIFEST.json",
        "INDEPENDENT_ACCURACY_AUDIT_MANIFEST.json",
        "NEW_VALIDATION_DATASET_MANIFEST.json",
        "PILOT_BATCH_2_MANIFEST.json",
        "PILOT_DATASET_MANIFEST.json",
        "VERIFICATION_SET_MANIFEST.json"
    ]
    prior_hashes = set()
    for mf in prior_manifests:
        p = Path(mf)
        if not p.exists(): continue
        data = json.loads(p.read_text(encoding="utf-8"))
        docs = data.get("documents") or data.get("notices") or data.get("items") or data
        if isinstance(docs, dict):
            for k, v in docs.items():
                if isinstance(v, dict):
                    h = v.get("sha256") or v.get("hash")
                    if h: prior_hashes.add(h)
        elif isinstance(docs, list):
            for v in docs:
                if isinstance(v, dict):
                    h = v.get("sha256") or v.get("hash")
                    if h: prior_hashes.add(h)

    assert len(prior_hashes) == 175, f"Expected 175 prior hashes, got {len(prior_hashes)}"

    rem_manifest = json.loads(Path("REMEDIATION_EVALUATION_MANIFEST.json").read_text(encoding="utf-8"))
    rem_hashes = {doc["sha256"] for doc in rem_manifest["documents"].values()}
    assert len(rem_hashes) == 15

    collision = prior_hashes.intersection(rem_hashes)
    assert len(collision) == 0, f"Detected hash collisions with prior manifests: {collision}"
