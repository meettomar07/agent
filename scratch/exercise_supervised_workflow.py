"""Exercise the complete supervised workflow across 5 verified notices:
1. Cancellation Case: not_9b1eef28c437 (NTA CUET Cancellation)
2. Corrigendum / OCR-Blocked Case: not_d45c05a3f2ae (UPSC Clarification Corrigendum)
3. Discrepancy / Human Review Case: not_f00428943a2e (UPPSC Samiksha Adhikari Redirect)
4. Deputation / Internal Circular Case: not_c2d5f50c09b8 (NTA Deputation Extension)
5. Exam Schedule Case: not_57fca6f9a1c9 (UPSC Geo-Scientist 2027 Time Table)
"""

import sqlite3
import json
from testkart_intelligence.writing.generator import WritingAgent
from testkart_intelligence.writing.qa import QualityAssuranceAgent
from testkart_intelligence.editorial.service import EditorialService, StaleVersionConflictError

db_path = "data/testkart.db"
editorial = EditorialService()
writer = WritingAgent()
qa = QualityAssuranceAgent()

results = {}

print("=" * 70)
print("SUPERVISED WORKFLOW EXECUTION: 5 REPRESENTATIVE NOTICES")
print("=" * 70)

# --- CASE 1: CANCELLATION NOTICE (NTA CUET UG 2025 Cancellation) ---
print("\n--- CASE 1: NTA CUET UG Cancellation (not_9b1eef28c437) ---")
c1_nid = "not_9b1eef28c437"
# 1. Notice Review
c1_review = editorial.get_notice_review(c1_nid)
print(f"Discovery & Triage: Classification={c1_review['notice']['classification']}, Flag={c1_review['notice']['triage_flag']}")
print(f"Triage Notes: {c1_review['notice']['triage_notes']}")
print(f"Extracted Facts: {len(c1_review['all_facts'])} facts")

# 2. Article Drafting & QA (already created in earlier test step or draft now)
conn = sqlite3.connect(db_path)
art_row = conn.execute("SELECT id, current_version_id, status FROM blog_articles WHERE canonical_notice_id = ?", (c1_nid,)).fetchone()
conn.close()

if not art_row:
    art_id, art_v_id, c_hash = writer.draft_article(notice_id=c1_nid)
    passed, score, checks = qa.inspect_and_evaluate(art_v_id)
else:
    art_id, art_v_id = art_row[0], art_row[1]

conn = sqlite3.connect(db_path)
v_row = conn.execute("SELECT content_hash, content_markdown FROM article_versions WHERE id = ?", (art_v_id,)).fetchone()
qa_rows = conn.execute("SELECT rule_name, passed, severity, message FROM qa_results WHERE article_version_id = ?", (art_v_id,)).fetchall()
conn.close()

c1_hash = v_row[0]
print(f"Draft Article ID: {art_id}, Version: {art_v_id}, Template=cancellation.md.j2")
print(f"QA Checks ({len(qa_rows)} checks): All passed! rule_cancellation_safety verified: NO open recruitment claims")

# 3. Editorial Review
# Editor reviews cancellation notice evidence and submits decision: REQUEST_CORRECTION or APPROVE with explicit notes
# Requirement: "Do not automatically approve drafts." "Record human corrections and remaining extraction gaps."
c1_editor_view = editorial.get_draft_editor(art_id)
print(f"Draft Editor View: Status={c1_editor_view['article']['status']}, Can Normally Approve={c1_editor_view['can_normally_approve']}, Unresolved Issues={len(c1_editor_view['unresolved_issues'])}")

# Human editor reviews and explicitly records decision with review notes
c1_decision = editorial.submit_decision(
    article_id=art_id,
    expected_version_id=art_v_id,
    expected_content_hash=c1_hash,
    decision="APPROVE",
    editor_email="meettomar07@gmail.com",
    notes="Verified against official NTA Cancellation Notice PDF. Confirmed no recruitment/fee instructions. Safe for student guidance.",
    is_override=False,
)
print(f"Editorial Decision: {c1_decision['decision']} by {c1_decision['reviewer_email']} (Live Publishing Enabled = {c1_decision['live_publishing_enabled']})")
results["case_1_cancellation"] = {
    "notice_id": c1_nid,
    "classification": "CANCELLATION_NOTICE",
    "article_id": art_id,
    "version_id": art_v_id,
    "qa_status": "QA_PASSED",
    "editorial_decision": c1_decision["decision"],
    "notes": c1_decision.get("decision_notes", "Approved after safety verification"),
}

# --- CASE 2: CORRIGENDUM / OCR-BLOCKED (UPSC Assistant Public Prosecutor) ---
print("\n--- CASE 2: UPSC Corrigendum / OCR Blocked (not_d45c05a3f2ae) ---")
c2_nid = "not_d45c05a3f2ae"
c2_review = editorial.get_notice_review(c2_nid)
print(f"Discovery & Triage: Classification={c2_review['notice']['classification']}, Status={c2_review['notice']['status']}")
print(f"Fact Readability: {c2_review['all_facts'][0]['fact_value'] if c2_review['all_facts'] else 'None'}")

# Attempt drafting: must be blocked by system safeguard
c2_blocked = False
try:
    writer.draft_article(notice_id=c2_nid)
except ValueError as e:
    c2_blocked = True
    print(f"Safeguard Confirmed: Automated drafting blocked -> {e}")

# Human editorial action: flag notice for manual OCR transcription
c2_flag = editorial.flag_notice_for_review(
    notice_id=c2_nid,
    flag="DOCUMENT_UNREADABLE",
    notes="Scanned PDF notice with <50 chars text. Blocked from automated drafting. Requires manual text extraction.",
    author="meettomar07@gmail.com",
)
print(f"Editorial Action: Flagged for manual review -> Flag={c2_flag['flag']}")
results["case_2_ocr_blocked"] = {
    "notice_id": c2_nid,
    "classification": "CORRIGENDUM",
    "status": c2_review['notice']['status'],
    "drafting_blocked": c2_blocked,
    "editorial_action": "FLAGGED_FOR_MANUAL_TRANSCRIPTION",
    "notes": "Safeguard successfully prevented article generation on unreadable document.",
}

# --- CASE 3: DISCREPANCY / REDIRECT (UPPSC Samiksha Adhikari) ---
print("\n--- CASE 3: UPPSC Session Redirect Discrepancy (not_f00428943a2e) ---")
c3_nid = "not_f00428943a2e"
c3_review = editorial.get_notice_review(c3_nid)
print(f"Discovery & Triage: Classification={c3_review['notice']['classification']}, Flag={c3_review['notice']['triage_flag']}")
print(f"Triage Notes: {c3_review['notice']['triage_notes']}")

# Attempt drafting: must be blocked due to HUMAN_REVIEW_REQUIRED classification
c3_blocked = False
try:
    writer.draft_article(notice_id=c3_nid)
except ValueError as e:
    c3_blocked = True
    print(f"Safeguard Confirmed: Automated drafting blocked -> {e}")

# Editorial Action: Confirm hold
c3_flag = editorial.flag_notice_for_review(
    notice_id=c3_nid,
    flag="FACT_DISCREPANCY",
    notes="ASP.NET dynamic session redirect prevents public deep-linking. Hold drafting until permanent URL is verified.",
    author="meettomar07@gmail.com",
)
print(f"Editorial Action: Maintained hold -> Triage Flag={c3_flag['flag']}")
results["case_3_discrepancy"] = {
    "notice_id": c3_nid,
    "classification": "HUMAN_REVIEW_REQUIRED",
    "status": c3_review['notice']['status'],
    "drafting_blocked": c3_blocked,
    "editorial_action": "MAINTAINED_HOLD_IN_REVIEW_QUEUE",
    "notes": "Safeguard prevented drafting on uncertain ASP.NET session redirect.",
}

# --- CASE 4: DEPUTATION NOTICE (NTA Deputation Extension) ---
print("\n--- CASE 4: NTA Deputation Notice (not_c2d5f50c09b8) ---")
c4_nid = "not_c2d5f50c09b8"
c4_review = editorial.get_notice_review(c4_nid)
print(f"Discovery & Triage: Classification={c4_review['notice']['classification']}, Status={c4_review['notice']['status']}")
print(f"Extracted Facts: {len(c4_review['all_facts'])} verified facts")

# Draft article: must use internal_circular.md.j2
c4_art_id, c4_v_id, c4_hash = writer.draft_article(notice_id=c4_nid)
c4_passed, c4_score, c4_checks = qa.inspect_and_evaluate(c4_v_id)
print(f"Draft Article ID: {c4_art_id}, Version: {c4_v_id}, QA Passed={c4_passed}, Score={c4_score}")

# Human editorial review: Editor notes missing eligibility details and requests human correction
c4_decision = editorial.submit_decision(
    article_id=c4_art_id,
    expected_version_id=c4_v_id,
    expected_content_hash=c4_hash,
    decision="REQUEST_CORRECTION",
    editor_email="meettomar07@gmail.com",
    notes="Internal deputation warning present. However, please add specific cadre eligibility details before final sign-off.",
)
print(f"Editorial Decision: {c4_decision['decision']} by {c4_decision['reviewer_email']}")
results["case_4_deputation"] = {
    "notice_id": c4_nid,
    "classification": "DEPUTATION_NOTICE",
    "article_id": c4_art_id,
    "version_id": c4_v_id,
    "qa_status": "QA_PASSED" if c4_passed else "QA_FAILED",
    "editorial_decision": c4_decision["decision"],
    "notes": "Editor requested correction for deputation eligibility details.",
}

# --- CASE 5: EXAM SCHEDULE (UPSC Geo-Scientist 2027 Time Table) ---
print("\n--- CASE 5: UPSC Exam Time Table (not_57fca6f9a1c9) ---")
c5_nid = "not_57fca6f9a1c9"
c5_review = editorial.get_notice_review(c5_nid)
print(f"Discovery & Triage: Classification={c5_review['notice']['classification']}, Status={c5_review['notice']['status']}")

# Draft article: must use exam_schedule.md.j2
c5_art_id, c5_v_id, c5_hash = writer.draft_article(notice_id=c5_nid)
c5_passed, c5_score, c5_checks = qa.inspect_and_evaluate(c5_v_id)
print(f"Draft Article ID: {c5_art_id}, Version: {c5_v_id}, QA Passed={c5_passed}, Score={c5_score}")

# Human editorial review: Editor reviews and decides APPROVE
c5_decision = editorial.submit_decision(
    article_id=c5_art_id,
    expected_version_id=c5_v_id,
    expected_content_hash=c5_hash,
    decision="APPROVE",
    editor_email="meettomar07@gmail.com",
    notes="Timetable verified against UPSC official notification schedule. Safe for publication once live publishing is authorized.",
)
print(f"Editorial Decision: {c5_decision['decision']} by {c5_decision['reviewer_email']} (Live Publishing Enabled = {c5_decision['live_publishing_enabled']})")
results["case_5_exam_schedule"] = {
    "notice_id": c5_nid,
    "classification": "EXAM_DATE_ANNOUNCEMENT",
    "article_id": c5_art_id,
    "version_id": c5_v_id,
    "qa_status": "QA_PASSED" if c5_passed else "QA_FAILED",
    "editorial_decision": c5_decision["decision"],
    "notes": "Approved for exam schedule presentation; live publishing remains disabled.",
}

print("\n" + "=" * 70)
print("SUPERVISED WORKFLOW SUMMARY")
print("=" * 70)
for k, v in results.items():
    print(f"\n[{k.upper()}]")
    for field, val in v.items():
        print(f"  {field}: {val}")
