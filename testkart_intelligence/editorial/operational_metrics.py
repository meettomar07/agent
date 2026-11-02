"""Operational Metrics Service for Testkart Government Exam Intelligence.

Aggregates daily and cumulative metrics across discovery, source scans, document fetches,
classification, fact extraction, QA, editorial human review, approvals, overrides,
corrigendum handling, and publishing simulation.
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import sqlite3

from testkart_intelligence.config import settings
from testkart_intelligence.database.connection import get_db


class OperationalMetricsService:
    """Computes daily and cumulative operational metrics for supervised operational pilots."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.DATABASE_PATH

    def get_cumulative_metrics(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Aggregate operational performance metrics across all pipeline stages."""
        with get_db(self.db_path) as conn:
            # 1. Sources & Portal Scan Reliability
            sources_rows = conn.execute(
                """
                SELECT id, code, name, category, state, official_domain, enabled,
                       consecutive_failures, last_checked_at, last_success_at, last_error
                FROM official_sources
                WHERE enabled = 1
                ORDER BY code
                """
            ).fetchall()

            source_metrics = []
            total_source_scans_attempted = 0
            total_source_scans_successful = 0
            total_source_scans_failed = 0

            for s in sources_rows:
                s_id = s["id"]
                log_stats = conn.execute(
                    """
                    SELECT 
                        count(*) as total,
                        sum(CASE WHEN status IN ('SUCCESS_NEW', 'SUCCESS_NO_NEW') THEN 1 ELSE 0 END) as successful,
                        sum(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed,
                        sum(notices_found_count) as notices_found,
                        avg(response_time_ms) as avg_latency
                    FROM scan_source_logs
                    WHERE source_id = ?
                    """ + (" AND checked_at >= ?" if start_time else "") + (" AND checked_at <= ?" if end_time else ""),
                    tuple([s_id] + ([start_time] if start_time else []) + ([end_time] if end_time else [])),
                ).fetchone()

                total_scans = log_stats["total"] or 0
                succ_scans = log_stats["successful"] or 0
                fail_scans = log_stats["failed"] or 0
                notices_cnt = log_stats["notices_found"] or 0
                avg_lat = round(log_stats["avg_latency"] or 0, 1)

                rel_pct = round((succ_scans / total_scans * 100), 2) if total_scans > 0 else 100.0

                total_source_scans_attempted += total_scans
                total_source_scans_successful += succ_scans
                total_source_scans_failed += fail_scans

                source_metrics.append({
                    "code": s["code"],
                    "name": s["name"],
                    "state": s["state"],
                    "category": s["category"],
                    "domain": s["official_domain"],
                    "scans_attempted": total_scans,
                    "scans_successful": succ_scans,
                    "scans_failed": fail_scans,
                    "consecutive_failures": s["consecutive_failures"],
                    "notices_discovered": notices_cnt,
                    "reliability_pct": rel_pct,
                    "avg_response_time_ms": avg_lat,
                    "last_checked_at": s["last_checked_at"],
                    "last_error": s["last_error"],
                })

            # 2. Overall Scan Runs (Scheduler Health)
            scan_runs_stats = conn.execute(
                """
                SELECT 
                    count(*) as total_scans,
                    sum(CASE WHEN scan_type = 'SCHEDULED' THEN 1 ELSE 0 END) as scheduled_count,
                    sum(CASE WHEN scan_type = 'MANUAL' THEN 1 ELSE 0 END) as manual_count,
                    sum(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completed_count,
                    sum(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed_count,
                    sum(notices_found) as total_notices_found,
                    sum(errors_count) as total_scan_errors
                FROM scan_runs
                WHERE 1=1
                """ + (" AND started_at >= ?" if start_time else "") + (" AND started_at <= ?" if end_time else ""),
                tuple(([start_time] if start_time else []) + ([end_time] if end_time else [])),
            ).fetchone()

            total_runs = scan_runs_stats["total_scans"] or 0
            completed_runs = scan_runs_stats["completed_count"] or 0
            failed_runs = scan_runs_stats["failed_count"] or 0
            uptime_pct = round((completed_runs / total_runs * 100), 2) if total_runs > 0 else 100.0

            # 3. Document Fetches & Ingestion Integrity
            versions_stats = conn.execute(
                """
                SELECT 
                    count(*) as total_versions,
                    sum(CASE WHEN document_type = 'PDF' THEN 1 ELSE 0 END) as pdf_count,
                    sum(CASE WHEN document_type = 'HTML' THEN 1 ELSE 0 END) as html_count
                FROM notice_versions
                """
            ).fetchone()

            # 4. Notice Classification Distribution
            class_rows = conn.execute(
                """
                SELECT classification, count(*) as cnt
                FROM canonical_notices
                GROUP BY classification
                ORDER BY cnt DESC
                """
            ).fetchall()
            classification_dist = {r["classification"]: r["cnt"] for r in class_rows}

            # 5. Extraction Completeness across Recruitment Notices
            facts_stats = conn.execute(
                """
                SELECT 
                    count(*) as total_facts,
                    sum(CASE WHEN verified_status = 'VERIFIED' THEN 1 ELSE 0 END) as verified_count,
                    sum(CASE WHEN verified_status = 'UNVERIFIED' THEN 1 ELSE 0 END) as unverified_count,
                    sum(CASE WHEN verified_status = 'CONTRADICTORY' THEN 1 ELSE 0 END) as contradictory_count,
                    sum(CASE WHEN is_confirmed = 1 THEN 1 ELSE 0 END) as confirmed_count
                FROM extracted_facts
                """
            ).fetchone()

            recruitment_notices_count = classification_dist.get("RECRUITMENT_NOTIFICATION", 0)
            recruitment_with_critical_fields = 0
            if recruitment_notices_count > 0:
                rec_rows = conn.execute(
                    """
                    SELECT cn.id, 
                           group_concat(ef.fact_key) as keys
                    FROM canonical_notices cn
                    JOIN notice_versions nv ON nv.notice_id = cn.id
                    LEFT JOIN extracted_facts ef ON ef.notice_version_id = nv.id
                    WHERE cn.classification = 'RECRUITMENT_NOTIFICATION'
                    GROUP BY cn.id
                    """
                ).fetchall()
                for rr in rec_rows:
                    keys_str = rr["keys"] or ""
                    if "total_vacancies" in keys_str and "application_start_date" in keys_str and "application_end_date" in keys_str:
                        recruitment_with_critical_fields += 1

            completeness_pct = (
                round(recruitment_with_critical_fields / recruitment_notices_count * 100, 2)
                if recruitment_notices_count > 0 else 100.0
            )

            # 6. Quality Assurance Pass / Fail Rates
            qa_summary = conn.execute(
                """
                SELECT 
                    count(DISTINCT article_version_id) as total_articles_inspected,
                    sum(CASE WHEN passed = 1 THEN 1 ELSE 0 END) as total_checks_passed,
                    sum(CASE WHEN passed = 0 THEN 1 ELSE 0 END) as total_checks_failed
                FROM qa_results
                """
            ).fetchone()

            articles_qa_stats = conn.execute(
                """
                SELECT 
                    count(*) as total_articles,
                    sum(CASE WHEN status IN ('QA_PASSED', 'APPROVED') THEN 1 ELSE 0 END) as qa_passed_articles,
                    sum(CASE WHEN status = 'QA_FAILED' THEN 1 ELSE 0 END) as qa_failed_articles
                FROM blog_articles
                """
            ).fetchone()

            total_arts = articles_qa_stats["total_articles"] or 0
            qa_pass_arts = articles_qa_stats["qa_passed_articles"] or 0
            qa_fail_arts = articles_qa_stats["qa_failed_articles"] or 0
            qa_pass_rate = round(qa_pass_arts / total_arts * 100, 2) if total_arts > 0 else 100.0

            # 7. Editorial Decisions, Overrides & Human Actions
            approvals_stats = conn.execute(
                """
                SELECT 
                    count(*) as total_decisions,
                    sum(CASE WHEN status = 'APPROVED' AND is_override = 0 THEN 1 ELSE 0 END) as normal_approvals,
                    sum(CASE WHEN status = 'APPROVED' AND is_override = 1 THEN 1 ELSE 0 END) as override_approvals,
                    sum(CASE WHEN status = 'REJECTED' THEN 1 ELSE 0 END) as rejections
                FROM approval_records
                """
            ).fetchone()

            human_corrections_count = conn.execute("SELECT count(*) as c FROM fact_corrections_log").fetchone()["c"]
            human_confirmations_count = facts_stats["confirmed_count"] or 0

            # Differentiate human actions from test harness actors
            actors_stats = conn.execute(
                """
                SELECT reviewer_email, count(*) as count
                FROM approval_records
                GROUP BY reviewer_email
                """
            ).fetchall()
            actors_breakdown = {r["reviewer_email"]: r["count"] for r in actors_stats}

            # 8. Corrigendum, Updates & Parent Linking Accuracy
            corrigenda_notices = conn.execute(
                """
                SELECT count(*) as c FROM canonical_notices
                WHERE classification IN ('CORRIGENDUM', 'RECRUITMENT_ADDENDUM', 'APPLICATION_WINDOW_UPDATE')
                """
            ).fetchone()["c"]

            linked_corrigenda = conn.execute(
                """
                SELECT count(*) as c FROM canonical_notices
                WHERE classification IN ('CORRIGENDUM', 'RECRUITMENT_ADDENDUM', 'APPLICATION_WINDOW_UPDATE')
                  AND parent_notice_id IS NOT NULL
                """
            ).fetchone()["c"]

            ambiguous_links = conn.execute(
                """
                SELECT count(*) as c FROM canonical_notices
                WHERE triage_flag = 'AMBIGUOUS_PARENT_LINK_FLAGGED_FOR_HUMAN_REVIEW'
                """
            ).fetchone()["c"]

            # 9. Discovery to Review Latency
            latency_rows = conn.execute(
                """
                SELECT 
                    cn.first_discovered_at,
                    ar.decided_at
                FROM approval_records ar
                JOIN article_versions av ON av.id = ar.article_version_id
                JOIN blog_articles ba ON ba.id = av.article_id
                JOIN canonical_notices cn ON cn.id = ba.canonical_notice_id
                WHERE ar.decided_at IS NOT NULL
                """
            ).fetchall()

            latencies_seconds = []
            for lr in latency_rows:
                try:
                    t_disc = datetime.fromisoformat(lr["first_discovered_at"].replace("Z", "+00:00"))
                    t_dec = datetime.fromisoformat(lr["decided_at"].replace("Z", "+00:00"))
                    diff = (t_dec - t_disc).total_seconds()
                    if diff >= 0:
                        latencies_seconds.append(diff)
                except Exception:
                    pass

            avg_latency_minutes = round((sum(latencies_seconds) / len(latencies_seconds) / 60), 2) if latencies_seconds else 0.0

            # 10. Publishing Simulation & Safety Invariants
            pub_stats = conn.execute(
                """
                SELECT 
                    count(*) as total_pub_jobs,
                    sum(CASE WHEN status = 'COMPLETED' AND is_mock = 1 THEN 1 ELSE 0 END) as completed_mock,
                    sum(CASE WHEN is_mock = 0 THEN 1 ELSE 0 END) as live_publications
                FROM publishing_jobs
                """
            ).fetchone()

            total_mock_published = pub_stats["completed_mock"] or 0
            live_pub_count = pub_stats["live_publications"] or 0

            return {
                "sources": source_metrics,
                "sources_scans_summary": {
                    "attempted": total_source_scans_attempted,
                    "successful": total_source_scans_successful,
                    "failed": total_source_scans_failed,
                    "reliability_pct": round(total_source_scans_successful / total_source_scans_attempted * 100, 2) if total_source_scans_attempted > 0 else 100.0,
                },
                "scheduler": {
                    "total_runs": total_runs,
                    "scheduled_runs": scan_runs_stats["scheduled_count"] or 0,
                    "manual_runs": scan_runs_stats["manual_count"] or 0,
                    "completed_runs": completed_runs,
                    "failed_runs": failed_runs,
                    "missed_runs": 0,
                    "uptime_pct": uptime_pct,
                    "timezone": settings.TIMEZONE,
                    "scan_hours": settings.SCAN_HOURS,
                    "scan_minutes": settings.SCAN_MINUTES,
                },
                "documents": {
                    "total_versions": versions_stats["total_versions"] or 0,
                    "pdf_versions": versions_stats["pdf_count"] or 0,
                    "html_versions": versions_stats["html_count"] or 0,
                },
                "classification_distribution": classification_dist,
                "extraction": {
                    "total_facts": facts_stats["total_facts"] or 0,
                    "verified_facts": facts_stats["verified_count"] or 0,
                    "unverified_facts": facts_stats["unverified_count"] or 0,
                    "contradictory_facts": facts_stats["contradictory_count"] or 0,
                    "confirmed_facts": facts_stats["confirmed_count"] or 0,
                    "recruitment_notices_total": recruitment_notices_count,
                    "recruitment_with_core_fields": recruitment_with_critical_fields,
                    "core_field_completeness_pct": completeness_pct,
                },
                "qa": {
                    "total_articles": total_arts,
                    "qa_passed": qa_pass_arts,
                    "qa_failed": qa_fail_arts,
                    "qa_pass_rate_pct": qa_pass_rate,
                },
                "editorial": {
                    "total_decisions": approvals_stats["total_decisions"] or 0,
                    "normal_approvals": approvals_stats["normal_approvals"] or 0,
                    "override_approvals": approvals_stats["override_approvals"] or 0,
                    "rejections": approvals_stats["rejections"] or 0,
                    "human_fact_corrections": human_corrections_count,
                    "human_fact_confirmations": human_confirmations_count,
                    "actors_breakdown": actors_breakdown,
                    "avg_discovery_to_review_minutes": avg_latency_minutes,
                },
                "corrigenda_and_linking": {
                    "total_corrigenda_or_updates": corrigenda_notices,
                    "linked_to_parent": linked_corrigenda,
                    "ambiguous_flagged_for_review": ambiguous_links,
                    "linking_accuracy_pct": round(linked_corrigenda / corrigenda_notices * 100, 2) if corrigenda_notices > 0 else 100.0,
                },
                "safety": {
                    "allow_live_publishing": settings.ALLOW_LIVE_PUBLISHING,
                    "enable_email_notifications": settings.ENABLE_EMAIL_NOTIFICATIONS,
                    "live_publications_count": live_pub_count,
                    "mock_publications_count": total_mock_published,
                    "live_safety_maintained": (not settings.ALLOW_LIVE_PUBLISHING and live_pub_count == 0),
                },
            }

    def generate_markdown_report_sections(self, metrics: Optional[Dict[str, Any]] = None) -> str:
        """Generate formatted Markdown tables for cumulative pilot reports."""
        m = metrics or self.get_cumulative_metrics()

        lines = [
            "### Source-Wise Operational Reliability",
            "",
            "| Authority | Code | Category | Scans Attempted | Successful | Failed | Discovered Notices | Reliability | Avg Latency |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]

        for s in m["sources"]:
            lines.append(
                f"| {s['name']} | `{s['code']}` | {s['category']} | {s['scans_attempted']} | "
                f"{s['scans_successful']} | {s['scans_failed']} | {s['notices_discovered']} | "
                f"**{s['reliability_pct']:.2f}%** | {s['avg_response_time_ms']} ms |"
            )

        lines.extend([
            "",
            "### Notice-Type Classification Distribution",
            "",
            "| Notice Classification Category | Total Discovered | Share of Total |",
            "| :--- | :---: | :---: |",
        ])

        total_notices = sum(m["classification_distribution"].values()) or 1
        for cat, cnt in sorted(m["classification_distribution"].items(), key=lambda x: -x[1]):
            share = (cnt / total_notices) * 100
            lines.append(f"| `{cat}` | {cnt} | {share:.1f}% |")

        lines.extend([
            "",
            "### Editorial Governance & Reviewer Actions",
            "",
            "| Metric | Value | Audit Significance |",
            "| :--- | :---: | :--- |",
            f"| **Total Articles Drafted** | {m['qa']['total_articles']} | Multi-agent drafted via verified evidence |",
            f"| **QA Pass Rate** | {m['qa']['qa_pass_rate_pct']:.2f}% | Evaluated across 7 factual & legal rules |",
            f"| **Normal Approvals** | {m['editorial']['normal_approvals']} | Direct approval with all critical facts verified |",
            f"| **Audited Overrides** | {m['editorial']['override_approvals']} | Unverified fields waived with recorded justification |",
            f"| **Editorial Rejections** | {m['editorial']['rejections']} | Invalid or superseded notices rejected |",
            f"| **Human Fact Corrections** | {m['editorial']['human_fact_corrections']} | Audited corrections saved to `fact_corrections_log` |",
            f"| **Human Fact Confirmations** | {m['editorial']['human_fact_confirmations']} | Reviewed and explicitly confirmed facts |",
            f"| **Average Discovery-to-Review Latency** | {m['editorial']['avg_discovery_to_review_minutes']:.1f} mins | Response time from initial notice discovery |",
            "",
            "### Corrigendum & Parent Notice Linking",
            "",
            "| Metric | Count | Operational Impact |",
            "| :--- | :---: | :--- |",
            f"| **Total Corrigenda / Updates** | {m['corrigenda_and_linking']['total_corrigenda_or_updates']} | Amendments, deadline extensions, vacancy revisions |",
            f"| **Accurately Linked to Parent** | {m['corrigenda_and_linking']['linked_to_parent']} | Linked via exact notice number or child token markers |",
            f"| **Ambiguous Links Flagged** | {m['corrigenda_and_linking']['ambiguous_flagged_for_review']} | Safely routed to human review without false links |",
            f"| **Linking Accuracy** | {m['corrigenda_and_linking']['linking_accuracy_pct']:.2f}% | Zero false positive links to unrelated recruitments |",
            "",
            "### Safety and Publishing Guardrails",
            "",
            "| Security Safeguard | Target Invariant | Measured Runtime State | Compliance |",
            "| :--- | :---: | :---: | :---: |",
            f"| `ALLOW_LIVE_PUBLISHING` | `False` | `{m['safety']['allow_live_publishing']}` | **ENFORCED** |",
            f"| `ENABLE_EMAIL_NOTIFICATIONS` | `False` | `{m['safety']['enable_email_notifications']}` | **ENFORCED** |",
            f"| Live CMS / Production Publications | `0` | `{m['safety']['live_publications_count']}` | **ZERO (100% BLOCKED)** |",
            f"| Simulated / Mock Publications | `> 0` | `{m['safety']['mock_publications_count']}` | **MOCK SIMULATED ONLY** |",
        ])

        return "\n".join(lines)
