"""Business logic and database service for the Local Editorial Review Interface."""

import hashlib
import json
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import sqlite3

from testkart_intelligence.config import settings
from testkart_intelligence.database.connection import get_db
from testkart_intelligence.writing.qa import QualityAssuranceAgent
from testkart_intelligence.publishing.guard import assert_live_publishing_disabled
from testkart_intelligence.editorial.security import is_safe_document_path, is_safe_official_url


class EditorialError(Exception):
    """Base exception for editorial operations."""
    pass


class StaleVersionConflictError(EditorialError):
    """Raised when an action is attempted on a stale draft version."""
    pass


class ApprovalBlockedError(EditorialError):
    """Raised when normal approval is blocked due to unverified facts or unreadable documents."""
    pass


class EditorialSecurityError(EditorialError):
    """Raised when an editorial security safeguard or override rule is violated."""
    pass


class EditorialService:
    """Manages dashboard data, notice evidence auditing, draft editing, and approval safeguards."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.DATABASE_PATH

    # --- 1. Dashboard Metrics and Views ---

    def get_dashboard_metrics(self) -> Dict[str, Any]:
        """Aggregate high-level counts for all editorial views."""
        with get_db(self.db_path) as conn:
            new_notices = conn.execute(
                "SELECT count(*) as c FROM canonical_notices WHERE status IN ('DISCOVERED', 'EXTRACTED')"
            ).fetchone()["c"]

            awaiting_review = conn.execute(
                "SELECT count(*) as c FROM blog_articles WHERE status IN ('DRAFT', 'QA_PASSED', 'PENDING_APPROVAL', 'CORRECTION_REQUESTED')"
            ).fetchone()["c"]

            blocked_notices = conn.execute(
                """
                SELECT count(*) as c FROM canonical_notices
                WHERE status IN (
                    'SCANNED_OCR_BLOCKED_FLAGGED_FOR_HUMAN_REVIEW',
                    'NON_UNICODE_ENCODING_FLAGGED_FOR_HUMAN_REVIEW',
                    'HUMAN_REVIEW_REQUIRED',
                    'EXTRACTION_FAILED'
                )
                """
            ).fetchone()["c"]

            blocked_articles = conn.execute(
                "SELECT count(*) as c FROM blog_articles WHERE status = 'QA_FAILED'"
            ).fetchone()["c"]

            revisions = conn.execute(
                """
                SELECT count(*) as c FROM canonical_notices
                WHERE (SELECT count(*) FROM notice_versions WHERE notice_id = canonical_notices.id) > 1
                   OR classification = 'CORRIGENDUM'
                   OR status = 'REVISED'
                """
            ).fetchone()["c"]

            approved = conn.execute(
                "SELECT count(*) as c FROM blog_articles WHERE status = 'APPROVED'"
            ).fetchone()["c"]

            rejected = conn.execute(
                "SELECT count(*) as c FROM blog_articles WHERE status = 'REJECTED'"
            ).fetchone()["c"]

            sources_active = conn.execute(
                "SELECT count(*) as c FROM official_sources WHERE enabled = 1"
            ).fetchone()["c"]

            sources_failed = conn.execute(
                "SELECT count(*) as c FROM official_sources WHERE consecutive_failures > 0"
            ).fetchone()["c"]

            total_notices = conn.execute("SELECT count(*) as c FROM canonical_notices").fetchone()["c"]
            current_opportunities = conn.execute(
                "SELECT count(*) as c FROM canonical_notices WHERE recency_status = 'CURRENT'"
            ).fetchone()["c"]
            historical_notices = conn.execute(
                "SELECT count(*) as c FROM canonical_notices WHERE recency_status = 'HISTORICAL'"
            ).fetchone()["c"]
            expired_notices = conn.execute(
                "SELECT count(*) as c FROM canonical_notices WHERE recency_status = 'EXPIRED'"
            ).fetchone()["c"]
            flagged_notices = conn.execute(
                "SELECT count(*) as c FROM canonical_notices WHERE triage_flag != 'NONE' OR classification = 'HUMAN_REVIEW_REQUIRED'"
            ).fetchone()["c"]
            recruitment_notices = conn.execute(
                "SELECT count(*) as c FROM canonical_notices WHERE classification = 'RECRUITMENT_NOTIFICATION'"
            ).fetchone()["c"]

            return {
                "new_notices": new_notices,
                "awaiting_review": awaiting_review,
                "blocked_total": blocked_notices + blocked_articles,
                "blocked_notices": blocked_notices,
                "blocked_articles": blocked_articles,
                "revisions": revisions,
                "approved": approved,
                "rejected": rejected,
                "sources_active": sources_active,
                "sources_failed": sources_failed,
                "total_notices": total_notices,
                "current_opportunities": current_opportunities,
                "historical_notices": historical_notices,
                "expired_notices": expired_notices,
                "flagged_notices": flagged_notices,
                "recruitment_notices": recruitment_notices,
                "live_publishing_enabled": False,
            }

    def list_notices_by_view(
        self,
        view: str = "new",
        limit: int = 50,
        authority: Optional[str] = None,
        category: Optional[str] = None,
        recency: Optional[str] = None,
        review_status: Optional[str] = None,
        pub_date: Optional[str] = None,
        deadline: Optional[str] = None,
        search: Optional[str] = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List notices based on specific editorial focus view with comprehensive multi-field filtering."""
        with get_db(self.db_path) as conn:
            params: List[Any] = []
            where_conditions: List[str] = []

            # Base view condition
            if view == "new":
                where_conditions.append("cn.status IN ('DISCOVERED', 'EXTRACTED')")
            elif view == "blocked":
                where_conditions.append("""
                    cn.status IN (
                        'SCANNED_OCR_BLOCKED_FLAGGED_FOR_HUMAN_REVIEW',
                        'NON_UNICODE_ENCODING_FLAGGED_FOR_HUMAN_REVIEW',
                        'HUMAN_REVIEW_REQUIRED',
                        'EXTRACTION_FAILED'
                    )
                """)
            elif view == "revisions":
                where_conditions.append("""
                    ((SELECT count(*) FROM notice_versions nv WHERE nv.notice_id = cn.id) > 1
                     OR cn.classification = 'CORRIGENDUM'
                     OR cn.status = 'REVISED'
                     OR cn.triage_flag IN ('REVISION_SERIES', 'PROPOSED_DUPLICATE'))
                """)
            elif view == "current":
                where_conditions.append("cn.recency_status = 'CURRENT'")
            elif view == "recruitment":
                where_conditions.append("cn.classification = 'RECRUITMENT_NOTIFICATION'")

            # Multi-field filters
            if authority and authority.strip() and authority.upper() != "ALL":
                where_conditions.append("(cn.authority_name = ? OR os.code = ? OR cn.authority_name LIKE ?)")
                auth_str = authority.strip()
                params.extend([auth_str, auth_str.upper(), f"%{auth_str}%"])

            if category and category.strip() and category.upper() != "ALL":
                where_conditions.append("cn.classification = ?")
                params.append(category.strip())

            if recency and recency.strip() and recency.upper() != "ALL":
                where_conditions.append("cn.recency_status = ?")
                params.append(recency.strip().upper())

            if review_status and review_status.strip() and review_status.upper() != "ALL":
                where_conditions.append("(cn.status = ? OR cn.triage_flag = ?)")
                rev_str = review_status.strip()
                params.extend([rev_str, rev_str])

            if pub_date and pub_date.strip():
                where_conditions.append("cn.published_date LIKE ?")
                params.append(f"%{pub_date.strip()}%")

            if deadline and (deadline == "1" or deadline.lower() == "true"):
                where_conditions.append("(cn.application_end_date IS NOT NULL AND cn.application_end_date != '')")

            if search and search.strip():
                where_conditions.append("(cn.title LIKE ? OR cn.notice_number LIKE ? OR cn.normalized_url LIKE ?)")
                q = f"%{search.strip()}%"
                params.extend([q, q, q])

            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else "WHERE 1=1"

            query = f"""
                SELECT cn.id, cn.authority_name, cn.notice_number, cn.title,
                       cn.normalized_url, cn.category, cn.state, cn.classification,
                       cn.status, cn.published_date, cn.application_start_date,
                       cn.application_end_date, cn.recency_status, cn.triage_flag,
                       cn.triage_notes, cn.first_discovered_at, cn.last_updated_at,
                       (SELECT count(*) FROM notice_versions nv WHERE nv.notice_id = cn.id) as version_count,
                       ba.id as article_id, ba.status as article_status
                FROM canonical_notices cn
                JOIN official_sources os ON os.id = cn.source_id
                LEFT JOIN blog_articles ba ON ba.canonical_notice_id = cn.id
                {where_clause}
                ORDER BY cn.first_discovered_at DESC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def flag_notice_for_review(
        self,
        notice_id: str,
        flag: str,
        notes: str,
        proposed_category: Optional[str] = None,
        author: str = "editorial_reviewer",
    ) -> Dict[str, Any]:
        """Flag a notice for human review due to bad classification, duplicate detection, or factual doubt."""
        with get_db(self.db_path) as conn:
            notice = conn.execute(
                "SELECT id, title, classification, triage_flag FROM canonical_notices WHERE id = ?",
                (notice_id,),
            ).fetchone()
            if not notice:
                raise ValueError(f"Notice {notice_id} not found")

            old_category = notice["classification"]
            now_iso = datetime.now(timezone.utc).isoformat()

            if proposed_category and proposed_category.strip():
                conn.execute(
                    """
                    UPDATE canonical_notices
                    SET triage_flag = ?,
                        triage_notes = ?,
                        classification = ?,
                        last_updated_at = ?
                    WHERE id = ?
                    """,
                    (flag, notes, proposed_category.strip(), now_iso, notice_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE canonical_notices
                    SET triage_flag = ?,
                        triage_notes = ?,
                        last_updated_at = ?
                    WHERE id = ?
                    """,
                    (flag, notes, now_iso, notice_id),
                )

            # Record in immutable audit log
            conn.execute(
                """
                INSERT INTO audit_events (
                    id, entity_type, entity_id, action, actor, payload_json, timestamp
                ) VALUES (?, 'canonical_notice', ?, 'NOTICE_FLAGGED_FOR_REVIEW', ?, ?, ?)
                """,
                (
                    f"aud_{uuid.uuid4().hex[:12]}",
                    notice_id,
                    author,
                    json.dumps({
                        "flag": flag,
                        "notes": notes,
                        "old_category": old_category,
                        "proposed_category": proposed_category,
                    }),
                    now_iso,
                ),
            )

            return {
                "status": "success",
                "notice_id": notice_id,
                "flag": flag,
                "notes": notes,
                "classification": proposed_category or old_category,
            }

    def list_articles_by_view(self, view: str = "awaiting", limit: int = 50) -> List[Dict[str, Any]]:
        """List blog articles based on editorial workflow status."""
        with get_db(self.db_path) as conn:
            params: List[Any] = []
            if view == "awaiting":
                where_clause = "WHERE ba.status IN ('DRAFT', 'QA_PASSED', 'PENDING_APPROVAL', 'CORRECTION_REQUESTED')"
            elif view == "blocked":
                where_clause = "WHERE ba.status = 'QA_FAILED'"
            elif view == "decided":
                where_clause = "WHERE ba.status IN ('APPROVED', 'REJECTED')"
            else:  # 'all'
                where_clause = "WHERE 1=1"

            query = f"""
                SELECT ba.id, ba.canonical_notice_id, ba.title, ba.template_type,
                       ba.status, ba.current_version_id, ba.updated_at, ba.created_at,
                       cn.authority_name, cn.classification as notice_classification,
                       av.version_number, av.generated_by, av.content_hash
                FROM blog_articles ba
                JOIN canonical_notices cn ON ba.canonical_notice_id = cn.id
                LEFT JOIN article_versions av ON ba.current_version_id = av.id
                {where_clause}
                ORDER BY ba.updated_at DESC
                LIMIT ?
            """
            params.append(limit)
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_scan_health_summary(self) -> Dict[str, Any]:
        """Retrieve portal scan execution metrics, error summaries, and health."""
        with get_db(self.db_path) as conn:
            sources = conn.execute(
                """
                SELECT id, code, name, category, state, official_domain, listing_url,
                       verification_status, enabled, consecutive_failures,
                       last_checked_at, last_success_at, last_error
                FROM official_sources
                ORDER BY enabled DESC, consecutive_failures DESC, code ASC
                """
            ).fetchall()

            recent_scans = conn.execute(
                """
                SELECT id, scan_type, status, started_at, completed_at,
                       sources_checked, notices_found, errors_count, error_summary
                FROM scan_runs
                ORDER BY started_at DESC
                LIMIT 10
                """
            ).fetchall()

            failed_logs = conn.execute(
                """
                SELECT sl.id, sl.scan_run_id, sl.status, sl.response_time_ms,
                       sl.error_message, sl.checked_at, s.code as source_code, s.name as source_name
                FROM scan_source_logs sl
                JOIN official_sources s ON sl.source_id = s.id
                WHERE sl.status = 'FAILED'
                ORDER BY sl.checked_at DESC
                LIMIT 20
                """
            ).fetchall()

            return {
                "sources": [dict(s) for s in sources],
                "recent_scans": [dict(sc) for sc in recent_scans],
                "failed_logs": [dict(fl) for fl in failed_logs],
            }

    # --- 2. Notice and Evidence Review Details ---

    def get_notice_review(self, notice_id: str) -> Dict[str, Any]:
        """Retrieve comprehensive evidence and verification details for an official notice."""
        with get_db(self.db_path) as conn:
            notice = conn.execute(
                "SELECT * FROM canonical_notices WHERE id = ?",
                (notice_id,),
            ).fetchone()
            if not notice:
                raise ValueError(f"Notice {notice_id} not found")

            versions = conn.execute(
                """
                SELECT id, notice_id, version_number, document_url, document_hash,
                       document_type, storage_path, page_count, retrieved_at
                FROM notice_versions
                WHERE notice_id = ?
                ORDER BY version_number DESC
                """,
                (notice_id,),
            ).fetchall()

            versions_list = [dict(v) for v in versions]
            latest_v = versions_list[0] if versions_list else None

            # Check safe document file availability
            safe_file_available = False
            if latest_v and latest_v.get("storage_path"):
                safe_path = is_safe_document_path(latest_v["storage_path"])
                safe_file_available = safe_path is not None

            # Readability & OCR warnings
            readability_warnings: List[str] = []
            if notice["status"] == "SCANNED_OCR_BLOCKED_FLAGGED_FOR_HUMAN_REVIEW":
                readability_warnings.append(
                    "SCANNED DOCUMENT WARNING: Text density is under 50 characters/page. "
                    "Automated text extraction was blocked. Manual review or high-precision OCR is required."
                )
            elif notice["status"] == "NON_UNICODE_ENCODING_FLAGGED_FOR_HUMAN_REVIEW":
                readability_warnings.append(
                    "NON-UNICODE ENCODING WARNING: Notice uses legacy 8-bit Devanagari font (e.g. Kruti Dev). "
                    "Raw extracted text contains unmapped ASCII glyphs. Requires human editorial verification."
                )
            elif notice["classification"] == "HUMAN_REVIEW_REQUIRED":
                readability_warnings.append(
                    "CLASSIFICATION CONFLICT: Contradictory or low-confidence classification signals detected. "
                    "Human review is required before drafting."
                )

            # Extracted facts grouped by status
            facts_by_status: Dict[str, List[Dict[str, Any]]] = {
                "VERIFIED": [],
                "UNVERIFIED": [],
                "CONTRADICTORY": [],
                "MISSING": [],
            }

            all_facts: List[Dict[str, Any]] = []
            if latest_v:
                facts_cursor = conn.execute(
                    """
                    SELECT id, fact_key, fact_value, confidence, evidence_text,
                           page_number, verified_status, verification_notes, created_at,
                           corrected_value, corrected_by, correction_reason, corrected_at,
                           is_confirmed, confirmed_by, confirmed_at
                    FROM extracted_facts
                    WHERE notice_version_id = ?
                    ORDER BY fact_key ASC
                    """,
                    (latest_v["id"],),
                )
                for f in facts_cursor.fetchall():
                    f_dict = dict(f)
                    all_facts.append(f_dict)
                    st = f_dict.get("verified_status", "UNVERIFIED")
                    if st in facts_by_status:
                        facts_by_status[st].append(f_dict)
                    else:
                        facts_by_status["UNVERIFIED"].append(f_dict)

            # Identification of missing / unverified critical fields
            missing_critical_fields: List[str] = []
            verified_keys = {f["fact_key"] for f in facts_by_status["VERIFIED"]}
            if notice["classification"] == "RECRUITMENT_NOTIFICATION":
                critical_fields = [
                    ("application_start_date", "Application Start Date"),
                    ("application_end_date", "Application Closing Date"),
                    ("exam_date", "Examination Date & Stages"),
                    ("total_vacancies", "Total Vacancies"),
                    ("eligibility", "Eligibility Requirements"),
                    ("age_limit", "Age Limit & Relaxations"),
                ]
                for key, label in critical_fields:
                    if key not in verified_keys:
                        missing_critical_fields.append(label)

            # Critical recruitment fields summary with confidence and confirmation flags
            critical_specs = [
                ("application_start_date", "Application Start Date"),
                ("application_end_date", "Application Closing Date"),
                ("exam_date", "Exam Date & Stages"),
                ("total_vacancies", "Total Vacancies"),
                ("eligibility", "Eligibility Requirements"),
                ("age_limit", "Age Limit & Relaxations"),
                ("application_fee", "Application Fee & Exemptions"),
            ]

            critical_fields_summary = []
            facts_by_key = {f["fact_key"]: f for f in all_facts}

            for f_key, label in critical_specs:
                f_entry = facts_by_key.get(f_key)
                if not f_entry:
                    critical_fields_summary.append({
                        "field_key": f_key,
                        "label": label,
                        "fact_id": None,
                        "machine_value": None,
                        "corrected_value": None,
                        "effective_value": None,
                        "confidence": 0.0,
                        "is_low_confidence": True,
                        "verified_status": "MISSING",
                        "is_confirmed": False,
                        "confirmed_by": None,
                        "confirmed_at": None,
                        "evidence_text": None,
                        "page_number": None,
                        "flag": "MISSING",
                    })
                else:
                    conf = f_entry.get("confidence")
                    conf = 1.0 if conf is None else float(conf)
                    v_stat = f_entry.get("verified_status", "UNVERIFIED")
                    is_conf = bool(f_entry.get("is_confirmed"))
                    has_corr = bool(f_entry.get("corrected_value"))

                    flag = "OK"
                    if has_corr:
                        flag = "CORRECTED"
                    elif is_conf:
                        flag = "CONFIRMED"
                    elif v_stat == "CONTRADICTORY":
                        flag = "CONTRADICTORY"
                    elif conf < 0.85:
                        flag = "LOW_CONFIDENCE"
                    else:
                        flag = "UNCONFIRMED"

                    critical_fields_summary.append({
                        "field_key": f_key,
                        "label": label,
                        "fact_id": f_entry["id"],
                        "machine_value": f_entry.get("fact_value"),
                        "corrected_value": f_entry.get("corrected_value"),
                        "effective_value": f_entry.get("corrected_value") or f_entry.get("fact_value"),
                        "confidence": conf,
                        "is_low_confidence": conf < 0.85,
                        "verified_status": v_stat,
                        "is_confirmed": is_conf,
                        "confirmed_by": f_entry.get("confirmed_by"),
                        "confirmed_at": f_entry.get("confirmed_at"),
                        "evidence_text": f_entry.get("evidence_text"),
                        "page_number": f_entry.get("page_number"),
                        "flag": flag,
                    })

            # Linked draft article if one exists
            article = conn.execute(
                """
                SELECT ba.id, ba.title, ba.status, ba.current_version_id, av.version_number
                FROM blog_articles ba
                LEFT JOIN article_versions av ON ba.current_version_id = av.id
                WHERE ba.canonical_notice_id = ?
                """,
                (notice_id,),
            ).fetchone()

            return {
                "notice": dict(notice),
                "versions": versions_list,
                "latest_version": latest_v,
                "safe_file_available": safe_file_available,
                "is_safe_url": is_safe_official_url(notice["normalized_url"]),
                "readability_warnings": readability_warnings,
                "facts_by_status": facts_by_status,
                "all_facts": all_facts,
                "critical_fields_summary": critical_fields_summary,
                "missing_critical_fields": missing_critical_fields,
                "linked_article": dict(article) if article else None,
            }

    # --- 3. Draft Editor & Side-by-Side Review ---

    def get_draft_editor(self, article_id: str) -> Dict[str, Any]:
        """Retrieve article draft details, latest version, QA results, and notice evidence for editing."""
        with get_db(self.db_path) as conn:
            article = conn.execute(
                "SELECT * FROM blog_articles WHERE id = ?",
                (article_id,),
            ).fetchone()
            if not article:
                raise ValueError(f"Article {article_id} not found")

            # Current version
            current_v = None
            if article["current_version_id"]:
                current_v = conn.execute(
                    "SELECT * FROM article_versions WHERE id = ?",
                    (article["current_version_id"],),
                ).fetchone()

            if not current_v:
                # Fallback to highest version_number if current_version_id is null
                current_v = conn.execute(
                    "SELECT * FROM article_versions WHERE article_id = ? ORDER BY version_number DESC LIMIT 1",
                    (article_id,),
                ).fetchone()

            if not current_v:
                raise ValueError(f"No version found for article {article_id}")

            current_v_dict = dict(current_v)

            # Linked notice
            notice_review = self.get_notice_review(article["canonical_notice_id"])

            # QA results for this version
            qa_rows = conn.execute(
                """
                SELECT id, passed, score, rule_name, severity, message, details_json, created_at
                FROM qa_results
                WHERE article_version_id = ?
                ORDER BY severity ASC, passed ASC
                """,
                (current_v_dict["id"],),
            ).fetchall()
            qa_results = [dict(q) for q in qa_rows]

            # Collect unresolved factual issues
            unresolved_issues: List[str] = []

            # 1. Readability blocks
            for rw in notice_review["readability_warnings"]:
                unresolved_issues.append(rw)

            # 2. Critical missing facts
            for m in notice_review["missing_critical_fields"]:
                unresolved_issues.append(f"CRITICAL FACT MISSING/UNVERIFIED: {m} is not verified from official evidence.")

            # 3. QA Errors
            for q in qa_results:
                if not q["passed"] and q["severity"] == "ERROR":
                    unresolved_issues.append(f"QA ERROR [{q['rule_name']}]: {q['message']}")

            # 4. Critical recruitment fields verification & confirmation check
            if notice_review["notice"].get("classification") == "RECRUITMENT_NOTIFICATION":
                for cf in notice_review.get("critical_fields_summary", []):
                    if cf["field_key"] in ("application_start_date", "application_end_date", "total_vacancies"):
                        if cf["verified_status"] == "CONTRADICTORY" and not cf["is_confirmed"] and not cf["corrected_value"]:
                            unresolved_issues.append(f"CRITICAL FACT CONTRADICTORY: {cf['label']} has conflicting values and must be resolved.")
                        elif cf["verified_status"] in ("UNVERIFIED", "MISSING") and not cf["is_confirmed"] and not cf["corrected_value"]:
                            unresolved_issues.append(f"CRITICAL FACT UNVERIFIED: {cf['label']} is not verified from official evidence.")

            # Version history
            versions_cursor = conn.execute(
                """
                SELECT id, version_number, content_hash, title, generated_by, created_at
                FROM article_versions
                WHERE article_id = ?
                ORDER BY version_number DESC
                """,
                (article_id,),
            )
            version_history = [dict(v) for v in versions_cursor.fetchall()]

            # Approval & Decision audit records
            approvals_cursor = conn.execute(
                """
                SELECT ar.id, ar.article_version_id, ar.status, ar.reviewer_email,
                       ar.decided_at, ar.decision_notes, ar.created_at, av.version_number
                FROM approval_records ar
                JOIN article_versions av ON ar.article_version_id = av.id
                WHERE av.article_id = ?
                ORDER BY ar.created_at DESC
                """,
                (article_id,),
            )
            approval_history = [dict(a) for a in approvals_cursor.fetchall()]

            # Audit events
            audit_cursor = conn.execute(
                """
                SELECT id, entity_type, entity_id, action, actor, payload_json, timestamp
                FROM audit_events
                WHERE (entity_type = 'blog_article' AND entity_id = ?)
                   OR (entity_type = 'approval_record' AND entity_id IN (
                       SELECT id FROM approval_records WHERE article_version_id IN (
                           SELECT id FROM article_versions WHERE article_id = ?
                       )
                   ))
                ORDER BY timestamp DESC
                LIMIT 30
                """,
                (article_id, article_id),
            )
            audit_events = [dict(ae) for ae in audit_cursor.fetchall()]

            can_normally_approve = (
                len(unresolved_issues) == 0
                and len(notice_review["readability_warnings"]) == 0
                and all(q["passed"] for q in qa_results if q["severity"] == "ERROR")
            )

            return {
                "article": dict(article),
                "current_version": current_v_dict,
                "notice_review": notice_review,
                "critical_fields_summary": notice_review.get("critical_fields_summary", []),
                "qa_results": qa_results,
                "unresolved_issues": unresolved_issues,
                "can_normally_approve": can_normally_approve,
                "version_history": version_history,
                "approval_history": approval_history,
                "audit_events": audit_events,
            }

    # --- 4. Draft Saving & Version Invalidation ---

    def save_draft(
        self,
        article_id: str,
        expected_version_id: str,
        title: str,
        content_markdown: str,
        editor_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Save editor edits to an article draft.

        Concurrency & Safeguard Invariants:
        - Prevents stale overwrites: expected_version_id must match current_version_id.
        - Generates an immutable new version and content hash.
        - Clearly tags author as 'human_editor:<email>'.
        - Resets article status to 'DRAFT'.
        - Automatically invalidates any existing pending or approved approval tokens!
        - Re-runs QA checks on the new draft version.
        - Records an audit trail log.
        """
        now = datetime.now(timezone.utc)
        editor_email = (editor_email or settings.OWNER_EMAIL).strip()
        now_iso = now.isoformat()
        clean_title = title.strip()
        clean_md = content_markdown.strip()

        if not clean_title:
            raise ValueError("Article title cannot be empty")
        if not clean_md:
            raise ValueError("Article markdown content cannot be empty")

        new_content_hash = hashlib.sha256(clean_md.encode("utf-8")).hexdigest()

        with get_db(self.db_path) as conn:
            # 1. Fetch current article state
            art = conn.execute(
                "SELECT id, current_version_id, status FROM blog_articles WHERE id = ?",
                (article_id,),
            ).fetchone()
            if not art:
                raise ValueError(f"Article {article_id} not found")

            # 2. Concurrency check: protect against stale browser tabs
            if art["current_version_id"] and art["current_version_id"] != expected_version_id:
                raise StaleVersionConflictError(
                    f"Conflict: Article '{article_id}' was modified by another session. "
                    f"Expected version '{expected_version_id}' but current active version is '{art['current_version_id']}'. "
                    "Please reload the editor to view the latest version."
                )

            # 3. Determine new version number
            last_v = conn.execute(
                "SELECT version_number FROM article_versions WHERE article_id = ? ORDER BY version_number DESC LIMIT 1",
                (article_id,),
            ).fetchone()
            new_version_num = (last_v["version_number"] + 1) if last_v else 1

            new_v_id = f"arv_{uuid.uuid4().hex[:12]}"
            author_tag = f"human_editor:{editor_email.strip()}"

            # 4. Insert new article version
            conn.execute(
                """
                INSERT INTO article_versions (
                    id, article_id, version_number, content_markdown, content_hash,
                    title, generated_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_v_id,
                    article_id,
                    new_version_num,
                    clean_md,
                    new_content_hash,
                    clean_title,
                    author_tag,
                    now_iso,
                ),
            )

            # 5. Safeguard: Invalidate prior approvals on edit!
            conn.execute(
                """
                UPDATE approval_records
                SET status = 'INVALIDATED'
                WHERE article_version_id IN (
                    SELECT id FROM article_versions WHERE article_id = ?
                ) AND status IN ('PENDING', 'APPROVED')
                """,
                (article_id,),
            )

            # 6. Update blog article current version & reset status to DRAFT
            conn.execute(
                """
                UPDATE blog_articles
                SET current_version_id = ?, title = ?, status = 'DRAFT', updated_at = ?
                WHERE id = ?
                """,
                (new_v_id, clean_title, now_iso, article_id),
            )

            # 7. Record audit trail
            conn.execute(
                """
                INSERT INTO audit_events (
                    id, entity_type, entity_id, action, actor, payload_json, timestamp
                ) VALUES (?, 'blog_article', ?, 'DRAFT_EDITED', ?, ?, ?)
                """,
                (
                    f"aud_{uuid.uuid4().hex[:12]}",
                    article_id,
                    author_tag,
                    json.dumps({
                        "old_version_id": expected_version_id,
                        "new_version_id": new_v_id,
                        "version_number": new_version_num,
                        "content_hash": new_content_hash,
                    }),
                    now_iso,
                ),
            )

        # 8. Run automated QA checks on the new version
        qa_agent = QualityAssuranceAgent(db_path=self.db_path)
        qa_passed, qa_score, qa_report = qa_agent.inspect_and_evaluate(article_version_id=new_v_id)

        # Update article status to QA_PASSED or QA_FAILED
        with get_db(self.db_path) as conn:
            new_status = "QA_PASSED" if qa_passed else "QA_FAILED"
            conn.execute(
                "UPDATE blog_articles SET status = ?, updated_at = ? WHERE id = ?",
                (new_status, now_iso, article_id),
            )

        return {
            "article_id": article_id,
            "version_id": new_v_id,
            "version_number": new_version_num,
            "content_hash": new_content_hash,
            "status": new_status,
            "qa_passed": qa_passed,
            "qa_score": qa_score,
            "generated_by": author_tag,
            "updated_at": now_iso,
        }

    # --- 5. Editorial Decision Workflow & Safeguards ---

    def submit_decision(
        self,
        article_id: str,
        expected_version_id: str,
        expected_content_hash: str,
        decision: str,  # 'APPROVE' | 'REJECT' | 'REQUEST_CORRECTION'
        editor_email: Optional[str] = None,
        notes: Optional[str] = None,
        is_override: bool = False,
        override_reason: Optional[str] = None,
        client_ip: str = "127.0.0.1",
    ) -> Dict[str, Any]:
        """Process an explicit editorial decision (Approve, Reject, or Request Correction).

        Safeguards Enforced:
        1. Concurrency Check: Stale version ID or mismatched content hash is rejected with StaleVersionConflictError.
        2. Normal Approval Guard: Unverified critical facts or unreadable source documents block standard approval.
        3. Audited Editorial Override: Permitted only with explicit flag, responsible editor ID, and non-empty justification.
        4. Invariant Assertion: Overrides and approvals update editorial status ONLY. Live publishing remains permanently disabled.
        5. Single-use Cryptographic Binding: Approval is locked to the exact version and SHA-256 content hash.
        """
        valid_decisions = ("APPROVE", "REJECT", "REQUEST_CORRECTION")
        if decision not in valid_decisions:
            raise ValueError(f"Invalid decision '{decision}'. Must be one of {valid_decisions}")

        # Strict hard boundary: assert live publishing is disabled
        assert_live_publishing_disabled()

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        editor_email_clean = (editor_email or settings.OWNER_EMAIL).strip()

        if not editor_email_clean or "@" not in editor_email_clean:
            raise EditorialSecurityError("A valid editor email address is required to record decisions.")

        with get_db(self.db_path) as conn:
            # 1. Fetch article and version details
            art = conn.execute(
                "SELECT id, canonical_notice_id, current_version_id, status FROM blog_articles WHERE id = ?",
                (article_id,),
            ).fetchone()
            if not art:
                raise ValueError(f"Article {article_id} not found")

            # 2. Concurrency checks
            if art["current_version_id"] != expected_version_id:
                raise StaleVersionConflictError(
                    f"Stale version conflict: Cannot record decision for version '{expected_version_id}'. "
                    f"The current active version is '{art['current_version_id']}'. Please reload."
                )

            v_row = conn.execute(
                "SELECT id, version_number, content_hash FROM article_versions WHERE id = ?",
                (expected_version_id,),
            ).fetchone()
            if not v_row:
                raise ValueError(f"Article version {expected_version_id} not found")

            if v_row["content_hash"] != expected_content_hash:
                raise StaleVersionConflictError(
                    f"Content hash mismatch: The draft content has been modified since it was loaded. "
                    f"Expected '{expected_content_hash}', got '{v_row['content_hash']}'. Please reload."
                )

            # 3. Handle Decision: APPROVE
            if decision == "APPROVE":
                # Check notice status and readability
                notice = conn.execute(
                    "SELECT status, classification FROM canonical_notices WHERE id = ?",
                    (art["canonical_notice_id"],),
                ).fetchone()

                is_unreadable = notice["status"] in (
                    "SCANNED_OCR_BLOCKED_FLAGGED_FOR_HUMAN_REVIEW",
                    "NON_UNICODE_ENCODING_FLAGGED_FOR_HUMAN_REVIEW",
                    "HUMAN_REVIEW_REQUIRED",
                )

                # Check QA results on this version
                qa_failures = conn.execute(
                    "SELECT rule_name, message FROM qa_results WHERE article_version_id = ? AND severity = 'ERROR' AND passed = 0",
                    (expected_version_id,),
                ).fetchall()

                has_qa_errors = len(qa_failures) > 0

                # Check critical facts for recruitment notices
                unverified_critical = []
                if notice["classification"] == "RECRUITMENT_NOTIFICATION":
                    critical_rows = conn.execute(
                        """
                        SELECT fact_key, fact_value, confidence, verified_status,
                               corrected_value, is_confirmed
                        FROM extracted_facts
                        WHERE notice_version_id = (
                            SELECT id FROM notice_versions WHERE notice_id = ? ORDER BY version_number DESC LIMIT 1
                        )
                        """,
                        (art["canonical_notice_id"],),
                    ).fetchall()

                    found_map = {r["fact_key"]: r for r in critical_rows}
                    core_keys = [
                        "application_start_date",
                        "application_end_date",
                        "total_vacancies",
                    ]
                    for k in core_keys:
                        if k not in found_map:
                            unverified_critical.append(k)
                        else:
                            row = found_map[k]
                            if row["verified_status"] == "CONTRADICTORY" and not row["is_confirmed"] and not row["corrected_value"]:
                                unverified_critical.append(k)
                            elif row["verified_status"] != "VERIFIED" and not row["is_confirmed"] and not row["corrected_value"]:
                                unverified_critical.append(k)

                    # Also check contradictory status on other recruitment fields
                    for k in ("exam_date", "eligibility", "age_limit"):
                        if k in found_map:
                            row = found_map[k]
                            if row["verified_status"] == "CONTRADICTORY" and not row["is_confirmed"] and not row["corrected_value"]:
                                unverified_critical.append(k)

                has_unverified_critical = len(unverified_critical) > 0

                # Evaluate normal approval safeguard vs audited override
                if is_override:
                    if not override_reason or len(override_reason.strip()) < 10:
                        raise EditorialSecurityError(
                            "Editorial override rejected: A specific justification (minimum 10 characters) "
                            "explaining how facts were verified from official sources is mandatory."
                        )
                    decision_note_final = (
                        f"[EDITORIAL_OVERRIDE by {editor_email_clean}]: {override_reason.strip()}"
                        + (f" | Additional Notes: {notes.strip()}" if notes else "")
                    )
                    audit_action = "EDITORIAL_OVERRIDE_APPROVED"
                elif is_unreadable or has_qa_errors or has_unverified_critical:
                    reasons = []
                    if is_unreadable:
                        reasons.append(f"Source notice is unreadable or flagged ({notice['status']})")
                    if has_unverified_critical:
                        reasons.append(f"Critical facts are unverified: {', '.join(unverified_critical)}")
                    if has_qa_errors:
                        reasons.append(f"QA checks failed with errors: {'; '.join(q['message'] for q in qa_failures)}")

                    raise ApprovalBlockedError(
                        "Normal approval is BLOCKED: " + " | ".join(reasons) + ". "
                        "An explicit, audited editorial override with recorded justification is required to proceed."
                    )
                else:
                    decision_note_final = notes.strip() if notes else "Direct editorial approval"
                    audit_action = "EDITORIAL_APPROVED"

                # Invalidate any lingering approval requests
                conn.execute(
                    "UPDATE approval_records SET status = 'INVALIDATED' WHERE article_version_id = ? AND status = 'PENDING'",
                    (expected_version_id,),
                )

                # Create immutable approval record
                raw_token = secrets.token_urlsafe(32)
                token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
                approval_id = f"appr_{uuid.uuid4().hex[:12]}"
                expires_at = now + timedelta(hours=settings.APPROVAL_TOKEN_EXPIRY_HOURS)

                conn.execute(
                    """
                    INSERT INTO approval_records (
                        id, article_version_id, content_hash, token_hash, reviewer_email,
                        status, expires_at, decided_at, decision_notes, client_ip, created_at
                    ) VALUES (?, ?, ?, ?, ?, 'APPROVED', ?, ?, ?, ?, ?)
                    """,
                    (
                        approval_id,
                        expected_version_id,
                        expected_content_hash,
                        token_hash,
                        editor_email_clean,
                        expires_at.isoformat(),
                        now_iso,
                        decision_note_final,
                        client_ip,
                        now_iso,
                    ),
                )

                # Update article status
                conn.execute(
                    "UPDATE blog_articles SET status = 'APPROVED', updated_at = ? WHERE id = ?",
                    (now_iso, article_id),
                )

                # Record Audit Event
                conn.execute(
                    """
                    INSERT INTO audit_events (
                        id, entity_type, entity_id, action, actor, payload_json, timestamp
                    ) VALUES (?, 'approval_record', ?, ?, ?, ?, ?)
                    """,
                    (
                        f"aud_{uuid.uuid4().hex[:12]}",
                        approval_id,
                        audit_action,
                        editor_email_clean,
                        json.dumps({
                            "article_id": article_id,
                            "article_version_id": expected_version_id,
                            "content_hash": expected_content_hash,
                            "is_override": is_override,
                            "override_reason": override_reason,
                            "notes": notes,
                            "live_publishing_enabled": False,
                        }),
                        now_iso,
                    ),
                )

                return {
                    "article_id": article_id,
                    "version_id": expected_version_id,
                    "decision": "APPROVED",
                    "approval_id": approval_id,
                    "is_override": is_override,
                    "decided_at": now_iso,
                    "reviewer_email": editor_email_clean,
                    "live_publishing_enabled": False,
                }

            # 4. Handle Decision: REJECT
            elif decision == "REJECT":
                rejection_notes = notes.strip() if notes else "Rejected during editorial review"

                # Invalidate existing pending approvals
                conn.execute(
                    "UPDATE approval_records SET status = 'INVALIDATED' WHERE article_version_id = ? AND status = 'PENDING'",
                    (expected_version_id,),
                )

                raw_token = secrets.token_urlsafe(32)
                token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
                approval_id = f"appr_{uuid.uuid4().hex[:12]}"

                conn.execute(
                    """
                    INSERT INTO approval_records (
                        id, article_version_id, content_hash, token_hash, reviewer_email,
                        status, expires_at, decided_at, decision_notes, client_ip, created_at
                    ) VALUES (?, ?, ?, ?, ?, 'REJECTED', ?, ?, ?, ?, ?)
                    """,
                    (
                        approval_id,
                        expected_version_id,
                        expected_content_hash,
                        token_hash,
                        editor_email_clean,
                        now_iso,
                        now_iso,
                        rejection_notes,
                        client_ip,
                        now_iso,
                    ),
                )

                conn.execute(
                    "UPDATE blog_articles SET status = 'REJECTED', updated_at = ? WHERE id = ?",
                    (now_iso, article_id),
                )

                conn.execute(
                    """
                    INSERT INTO audit_events (
                        id, entity_type, entity_id, action, actor, payload_json, timestamp
                    ) VALUES (?, 'blog_article', ?, 'EDITORIAL_REJECTED', ?, ?, ?)
                    """,
                    (
                        f"aud_{uuid.uuid4().hex[:12]}",
                        article_id,
                        editor_email_clean,
                        json.dumps({
                            "version_id": expected_version_id,
                            "notes": rejection_notes,
                        }),
                        now_iso,
                    ),
                )

                return {
                    "article_id": article_id,
                    "version_id": expected_version_id,
                    "decision": "REJECTED",
                    "decided_at": now_iso,
                    "reviewer_email": editor_email_clean,
                }

            # 5. Handle Decision: REQUEST_CORRECTION
            elif decision == "REQUEST_CORRECTION":
                correction_notes = notes.strip() if notes else "Editor requested corrections"

                conn.execute(
                    "UPDATE blog_articles SET status = 'CORRECTION_REQUESTED', updated_at = ? WHERE id = ?",
                    (now_iso, article_id),
                )

                conn.execute(
                    """
                    INSERT INTO audit_events (
                        id, entity_type, entity_id, action, actor, payload_json, timestamp
                    ) VALUES (?, 'blog_article', ?, 'CORRECTION_REQUESTED', ?, ?, ?)
                    """,
                    (
                        f"aud_{uuid.uuid4().hex[:12]}",
                        article_id,
                        editor_email_clean,
                        json.dumps({
                            "version_id": expected_version_id,
                            "notes": correction_notes,
                        }),
                        now_iso,
                    ),
                )

                return {
                    "article_id": article_id,
                    "version_id": expected_version_id,
                    "decision": "CORRECTION_REQUESTED",
                    "decided_at": now_iso,
                    "reviewer_email": editor_email_clean,
                }

    # --- 6. Reviewer Fact Correction and Confirmation ---

    def correct_fact(
        self,
        fact_id: str,
        corrected_value: str,
        reason: str,
        reviewer_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Allow reviewers to correct extracted recruitment values without overwriting machine values.

        Invariants:
        - Original fact_value is preserved intact.
        - corrected_value, corrected_by, correction_reason, and corrected_at are stored.
        - Immutable entry appended to fact_corrections_log.
        - Fact marked as confirmed and verified.
        - Any existing pending or approved approval records on linked articles are INVALIDATED!
        - Linked articles are reset to DRAFT status to require fresh review.
        - Audit trail event recorded.
        """
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        reviewer_email_clean = (reviewer_email or settings.OWNER_EMAIL).strip()
        clean_val = corrected_value.strip()
        clean_reason = reason.strip()

        if not clean_val:
            raise ValueError("Corrected fact value cannot be empty")
        if not clean_reason or len(clean_reason) < 3:
            raise ValueError("A valid correction reason (minimum 3 characters) is required")

        with get_db(self.db_path) as conn:
            fact = conn.execute(
                "SELECT * FROM extracted_facts WHERE id = ?",
                (fact_id,),
            ).fetchone()
            if not fact:
                raise ValueError(f"Extracted fact {fact_id} not found")

            old_effective = fact["corrected_value"] if fact["corrected_value"] is not None else fact["fact_value"]

            # Update extracted_facts
            conn.execute(
                """
                UPDATE extracted_facts
                SET corrected_value = ?,
                    corrected_by = ?,
                    correction_reason = ?,
                    corrected_at = ?,
                    is_confirmed = 1,
                    confirmed_by = ?,
                    confirmed_at = ?,
                    verified_status = 'VERIFIED'
                WHERE id = ?
                """,
                (
                    clean_val,
                    reviewer_email_clean,
                    clean_reason,
                    now_iso,
                    reviewer_email_clean,
                    now_iso,
                    fact_id,
                ),
            )

            # Insert fact corrections log
            log_id = f"fcl_{uuid.uuid4().hex[:12]}"
            conn.execute(
                """
                INSERT INTO fact_corrections_log (
                    id, fact_id, notice_version_id, fact_key, original_value,
                    corrected_value, reviewer_email, correction_reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log_id,
                    fact_id,
                    fact["notice_version_id"],
                    fact["fact_key"],
                    fact["fact_value"],
                    clean_val,
                    reviewer_email_clean,
                    clean_reason,
                    now_iso,
                ),
            )

            # Find linked articles and invalidate their approvals / reset status to DRAFT
            linked_articles = conn.execute(
                """
                SELECT ba.id, ba.status
                FROM blog_articles ba
                JOIN canonical_notices cn ON ba.canonical_notice_id = cn.id
                JOIN notice_versions nv ON nv.notice_id = cn.id
                WHERE nv.id = ?
                """,
                (fact["notice_version_id"],),
            ).fetchall()

            for art in linked_articles:
                art_id = art["id"]
                conn.execute(
                    """
                    UPDATE approval_records
                    SET status = 'INVALIDATED'
                    WHERE article_version_id IN (
                        SELECT id FROM article_versions WHERE article_id = ?
                    ) AND status IN ('PENDING', 'APPROVED')
                    """,
                    (art_id,),
                )
                if art["status"] == "APPROVED":
                    conn.execute(
                        "UPDATE blog_articles SET status = 'DRAFT', updated_at = ? WHERE id = ?",
                        (now_iso, art_id),
                    )

            # Record audit event
            conn.execute(
                """
                INSERT INTO audit_events (
                    id, entity_type, entity_id, action, actor, payload_json, timestamp
                ) VALUES (?, 'extracted_fact', ?, 'FACT_CORRECTED', ?, ?, ?)
                """,
                (
                    f"aud_{uuid.uuid4().hex[:12]}",
                    fact_id,
                    reviewer_email_clean,
                    json.dumps({
                        "fact_key": fact["fact_key"],
                        "original_value": fact["fact_value"],
                        "old_effective": old_effective,
                        "corrected_value": clean_val,
                        "reason": clean_reason,
                    }),
                    now_iso,
                ),
            )

        return {
            "fact_id": fact_id,
            "fact_key": fact["fact_key"],
            "original_value": fact["fact_value"],
            "corrected_value": clean_val,
            "corrected_by": reviewer_email_clean,
            "correction_reason": clean_reason,
            "corrected_at": now_iso,
            "is_confirmed": True,
        }

    def confirm_fact(
        self,
        fact_id: str,
        reviewer_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Explicitly confirm an extracted recruitment fact value.

        Invariants:
        - Marks fact as is_confirmed = 1 with timestamp and reviewer email.
        - If previously marked CONTRADICTORY, changes verified_status to VERIFIED.
        - Records audit event.
        """
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        reviewer_email_clean = (reviewer_email or settings.OWNER_EMAIL).strip()

        with get_db(self.db_path) as conn:
            fact = conn.execute(
                "SELECT * FROM extracted_facts WHERE id = ?",
                (fact_id,),
            ).fetchone()
            if not fact:
                raise ValueError(f"Extracted fact {fact_id} not found")

            conn.execute(
                """
                UPDATE extracted_facts
                SET is_confirmed = 1,
                    confirmed_by = ?,
                    confirmed_at = ?,
                    verified_status = CASE WHEN verified_status = 'CONTRADICTORY' THEN 'VERIFIED' ELSE verified_status END
                WHERE id = ?
                """,
                (reviewer_email_clean, now_iso, fact_id),
            )

            conn.execute(
                """
                INSERT INTO audit_events (
                    id, entity_type, entity_id, action, actor, payload_json, timestamp
                ) VALUES (?, 'extracted_fact', ?, 'FACT_CONFIRMED', ?, ?, ?)
                """,
                (
                    f"aud_{uuid.uuid4().hex[:12]}",
                    fact_id,
                    reviewer_email_clean,
                    json.dumps({
                        "fact_key": fact["fact_key"],
                        "effective_value": fact["corrected_value"] or fact["fact_value"],
                    }),
                    now_iso,
                ),
            )

        return {
            "fact_id": fact_id,
            "fact_key": fact["fact_key"],
            "is_confirmed": True,
            "confirmed_by": reviewer_email_clean,
            "confirmed_at": now_iso,
        }
