"""Quality Assurance Agent for validating factual consistency, structure, and security of blog drafts."""

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import sqlite3

from testkart_intelligence.config import settings
from testkart_intelligence.database.connection import get_db
from testkart_intelligence.security.allowlist import is_official_domain


class QACheckItem:
    def __init__(self, rule_name: str, passed: bool, severity: str, message: str, details: Optional[Dict[str, Any]] = None):
        self.rule_name = rule_name
        self.passed = passed
        self.severity = severity  # 'ERROR' | 'WARNING' | 'INFO'
        self.message = message
        self.details = details or {}


class QualityAssuranceAgent:
    """Runs automated verification and editorial checks on generated article drafts."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path

    def inspect_and_evaluate(self, article_version_id: str) -> Tuple[bool, float, List[QACheckItem]]:
        """Run all QA checks on an article version.

        Returns:
            Tuple of (overall_passed, score, list_of_checks)
        """
        now_iso = datetime.now(timezone.utc).isoformat()

        with get_db(self.db_path) as conn:
            # 1. Fetch article version and parent article/notice data
            row = conn.execute(
                """
                SELECT av.id as version_id, av.article_id, av.content_markdown, av.title,
                       ba.canonical_notice_id, cn.authority_name, cn.normalized_url,
                       cn.classification, cn.status as notice_status, nv.raw_text, nv.document_type
                FROM article_versions av
                JOIN blog_articles ba ON av.article_id = ba.id
                JOIN canonical_notices cn ON ba.canonical_notice_id = cn.id
                LEFT JOIN notice_versions nv ON nv.notice_id = cn.id
                WHERE av.id = ?
                ORDER BY nv.version_number DESC
                LIMIT 1
                """,
                (article_version_id,),
            ).fetchone()

            if not row:
                raise ValueError(f"Article version {article_version_id} not found")

            article_id = row["article_id"]
            markdown = row["content_markdown"]
            title = row["title"]
            authority = row["authority_name"]
            official_url = row["normalized_url"]
            classification = row["classification"]
            notice_status = row["notice_status"] or ""
            raw_text = row["raw_text"] or ""

            # 2. Fetch extracted facts and their statuses
            facts_cursor = conn.execute(
                """
                SELECT ef.fact_key, ef.fact_value, ef.verified_status, ef.evidence_text
                FROM extracted_facts ef
                JOIN notice_versions nv ON ef.notice_version_id = nv.id
                WHERE nv.notice_id = ?
                """,
                (row["canonical_notice_id"],),
            )
            facts = {f["fact_key"]: dict(f) for f in facts_cursor.fetchall()}

            checks: List[QACheckItem] = []

            # Check 0: Document readability and OCR stop
            is_unreadable = (
                notice_status in (
                    "SCANNED_OCR_BLOCKED_FLAGGED_FOR_HUMAN_REVIEW",
                    "NON_UNICODE_ENCODING_FLAGGED_FOR_HUMAN_REVIEW",
                    "HUMAN_REVIEW_REQUIRED",
                )
                or "[SCANNED DOCUMENT" in raw_text
                or "[LEGACY_NON_UNICODE_FONT" in raw_text
            )
            checks.append(
                QACheckItem(
                    rule_name="rule_document_readability",
                    passed=not is_unreadable,
                    severity="ERROR",
                    message="Cannot pass QA: source document is scanned or unreadable without verified OCR text extraction"
                    if is_unreadable
                    else "Source document readability verified",
                )
            )

            # Check 1: Official source link requirement
            urls_in_doc = re.findall(r"https?://[^\s\)\"\'>]+", markdown)
            has_official_link = any(is_official_domain(u) for u in urls_in_doc)
            checks.append(
                QACheckItem(
                    rule_name="rule_official_source_link",
                    passed=has_official_link,
                    severity="ERROR",
                    message="Article must contain at least one verified official government source link"
                    if not has_official_link
                    else "Official source link verified",
                )
            )

            # Check 2: Authority presence
            auth_in_text = authority.lower() in markdown.lower()
            checks.append(
                QACheckItem(
                    rule_name="rule_authority_name",
                    passed=auth_in_text,
                    severity="ERROR",
                    message=f"Recruiting authority '{authority}' must be explicitly named in the draft"
                    if not auth_in_text
                    else "Authority correctly referenced",
                )
            )

            # Check 3: Prevention of contradictory, malformed, or unverified facts in draft
            UNACCEPTABLE_STATUSES = (
                "CONTRADICTORY",
                "UNVERIFIED",
                "AMBIGUOUS_DEADLINE_FLAGGED_FOR_REVIEW",
                "CATEGORY_FEE_FLAGGED_FOR_REVIEW",
                "POST_WISE_BREAKDOWN_FLAGGED_FOR_REVIEW",
                "TRUNCATED_ELIGIBILITY_FLAGGED_FOR_REVIEW",
            )
            has_contradictory_facts = False
            contradictory_keys = []
            for k, f in facts.items():
                if f["verified_status"] in UNACCEPTABLE_STATUSES:
                    val = f["fact_value"].strip()
                    # Check if this invalid or unverified value was presented in draft as fact
                    if val and len(val) >= 2 and val in markdown:
                        has_contradictory_facts = True
                        contradictory_keys.append(f"{k}='{val[:30]}' ({f['verified_status']})")

            checks.append(
                QACheckItem(
                    rule_name="rule_no_contradictory_facts",
                    passed=not has_contradictory_facts,
                    severity="ERROR",
                    message=f"Draft includes unverified/contradictory facts: {contradictory_keys}"
                    if has_contradictory_facts
                    else "No unverified or contradictory facts included",
                )
            )

            # Check 4: Category-aware factual verification
            if classification == "RECRUITMENT_NOTIFICATION":
                has_dates = bool(
                    facts.get("application_start_date", {}).get("verified_status") == "VERIFIED"
                    or facts.get("application_end_date", {}).get("verified_status") == "VERIFIED"
                )
                has_unverified_date_placeholder = bool(
                    re.search(
                        r"(?:Online Application Start Date|Last Date to Apply Online|Application Start Date|Application Closing Date)[^\n|]*\|[^\n|]*(?:Requires Editor Review|Pending verification)",
                        markdown,
                        re.IGNORECASE,
                    )
                )
                dates_ok = has_dates and not has_unverified_date_placeholder
                checks.append(
                    QACheckItem(
                        rule_name="rule_recruitment_critical_dates",
                        passed=dates_ok,
                        severity="ERROR",
                        message="Recruitment notification lacks verified application schedule dates"
                        if not dates_ok
                        else "Recruitment application dates verified",
                    )
                )

                is_internal_mismatch = any(
                    re.search(p, f"{title} {official_url}".lower())
                    for p in [r"\bldce\b", r"\blimited\s+departmental\b", r"\bdeputation\b"]
                )
                if is_internal_mismatch:
                    checks.append(
                        QACheckItem(
                            rule_name="rule_recruitment_not_internal",
                            passed=False,
                            severity="ERROR",
                            message="Recruitment notification template applied to internal departmental / deputation notice",
                        )
                    )

            elif classification == "CANCELLATION_NOTICE":
                has_application_instructions = bool(
                    re.search(r"fill\s+in\s+the\s+online\s+application|pay\s+the\s+application\s+fee|register\s+using\s+valid\s+mobile", markdown, re.IGNORECASE)
                )
                checks.append(
                    QACheckItem(
                        rule_name="rule_cancellation_safety",
                        passed=not has_application_instructions,
                        severity="ERROR",
                        message="Cancellation notice must never include application steps or fee payment instructions"
                        if has_application_instructions
                        else "Cancellation safety verified: no application or payment instructions present",
                    )
                )

            elif classification in ("INTERNAL_CIRCULAR", "DEPUTATION_NOTICE"):
                has_public_recruitment_claims = bool(
                    re.search(
                        r"\bopen\s+to\s+(?:all\s+)?(?:citizens?|candidates?|freshers?)\b|\bdirect\s+recruitment\b|\bpublic\s+recruitment\b|\bany\s+graduate\s+can\s+apply\b",
                        markdown,
                        re.IGNORECASE,
                    )
                )
                has_internal_restriction_notice = bool(
                    re.search(
                        r"\binternal\b|\bdepartmental\b|\bdeputation\b|\bproper\s+channel\b|\bserving\s+employees?\b",
                        markdown,
                        re.IGNORECASE,
                    )
                )
                is_safe = not has_public_recruitment_claims and has_internal_restriction_notice
                checks.append(
                    QACheckItem(
                        rule_name="rule_internal_circular_safety",
                        passed=is_safe,
                        severity="ERROR",
                        message="Internal circular or deputation notice must clearly indicate internal/serving employee restriction and never generate open public recruitment claims"
                        if not is_safe
                        else "Internal circular safety verified: restriction to internal/deputation candidates confirmed",
                    )
                )

            # Check 5: Check for raw heading fragments in data fields
            has_heading_in_data = bool(
                re.search(r"(?:Application Fee|Age Limit|Fee)\s*[:\-]\s*(?:After completing the process|Candidates must have attained the age of)", markdown, re.IGNORECASE)
            )
            checks.append(
                QACheckItem(
                    rule_name="rule_no_heading_fragments_in_data",
                    passed=not has_heading_in_data,
                    severity="ERROR",
                    message="Draft contains raw heading fragments or procedural text in structured data fields"
                    if has_heading_in_data
                    else "No heading fragments in structured data fields",
                )
            )

            # Check 6: Title length & quality
            title_valid = settings.MIN_TITLE_LENGTH <= len(title) <= settings.MAX_TITLE_LENGTH
            checks.append(
                QACheckItem(
                    rule_name="rule_title_length",
                    passed=title_valid,
                    severity="ERROR",
                    message=f"Title length ({len(title)} chars) must be between {settings.MIN_TITLE_LENGTH} and {settings.MAX_TITLE_LENGTH}"
                    if not title_valid
                    else "Title length optimal",
                )
            )

            # Check 7: Article length / minimum depth
            word_count = len(markdown.split())
            length_valid = word_count >= 80
            checks.append(
                QACheckItem(
                    rule_name="rule_article_depth",
                    passed=length_valid,
                    severity="ERROR",
                    message=f"Article too short ({word_count} words). Minimum 80 words required."
                    if not length_valid
                    else f"Article depth adequate ({word_count} words)",
                )
            )

            # Check 8: Markdown formatting structure
            has_headings = bool(re.search(r"^##\s+", markdown, re.MULTILINE))
            has_structure = has_headings and ("|" in markdown or "-" in markdown)
            checks.append(
                QACheckItem(
                    rule_name="rule_markdown_structure",
                    passed=has_structure,
                    severity="WARNING",
                    message="Article should contain headings and tables or bulleted lists for readability"
                    if not has_structure
                    else "Article formatting structure valid",
                )
            )

            # Check 9: Testkart branding check (must have lowercase 'k')
            improper_branding = "TestKart" in markdown or "testKart" in markdown
            checks.append(
                QACheckItem(
                    rule_name="rule_testkart_branding",
                    passed=not improper_branding,
                    severity="ERROR",
                    message="Improper branding detected: Testkart must be spelled with a lowercase 'k'"
                    if improper_branding
                    else "Testkart branding correct",
                )
            )

            # 3. Calculate score & determination
            score = 100.0
            error_count = 0
            for c in checks:
                if not c.passed:
                    if c.severity == "ERROR":
                        score -= 40.0
                        error_count += 1
                    elif c.severity == "WARNING":
                        score -= 10.0

            score = max(0.0, score)
            overall_passed = (error_count == 0) and (score >= settings.MIN_QA_PASS_SCORE)

            # 4. Save results to qa_results table
            for c in checks:
                qa_id = f"qa_{uuid.uuid4().hex[:12]}"
                conn.execute(
                    """
                    INSERT INTO qa_results (
                        id, article_version_id, passed, score, rule_name, severity, message, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (qa_id, article_version_id, 1 if c.passed else 0, score, c.rule_name, c.severity, c.message, now_iso),
                )

            # 5. Update blog article status based on QA outcome
            new_status = "QA_PASSED" if overall_passed else "QA_FAILED"
            conn.execute(
                "UPDATE blog_articles SET status = ?, updated_at = ? WHERE id = ?",
                (new_status, now_iso, article_id),
            )

        return overall_passed, score, checks
