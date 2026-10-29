"""Verification Agent and Document Ingestion Pipeline."""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import sqlite3
from dateutil import parser as date_parser

from testkart_intelligence.config import settings
from testkart_intelligence.database.connection import get_db
from testkart_intelligence.discovery.fetcher import SafeFetcher
from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.html_extractor import HtmlDocumentExtractor
from testkart_intelligence.extraction.fact_extractor import FactExtractor, ExtractedFactItem


class VerificationAgent:
    """Verifies extracted facts against original official evidence and stores immutable versions."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path
        self.pdf_extractor = PdfDocumentExtractor()
        self.html_extractor = HtmlDocumentExtractor()

    def process_and_verify_document(
        self,
        notice_id: str,
        doc_bytes: bytes,
        doc_url: str,
        content_type: str,
    ) -> Tuple[str, List[ExtractedFactItem]]:
        """Ingest document, extract text, verify facts against evidence, and store version.

        Returns:
            Tuple of (version_id, verified_facts_list)
        """
        doc_hash = SafeFetcher.compute_sha256(doc_bytes)
        now_iso = datetime.now(timezone.utc).isoformat()

        # Determine document type (PDF vs HTML)
        is_pdf = doc_url.lower().endswith(".pdf") or "application/pdf" in content_type.lower() or doc_bytes[:4] == b"%PDF"
        doc_type = "PDF" if is_pdf else "HTML"
        ext = "pdf" if is_pdf else "html"

        # 1. Save document to immutable storage path
        settings.DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
        storage_path = settings.DOCUMENTS_DIR / f"{doc_hash}.{ext}"
        if not storage_path.exists():
            with open(storage_path, "wb") as f:
                f.write(doc_bytes)

        # 2. Extract text and page structure
        if is_pdf:
            full_text, pages, page_count = self.pdf_extractor.extract(doc_bytes)
        else:
            html_text = doc_bytes.decode("utf-8", errors="replace")
            full_text, pages, page_count = self.html_extractor.extract(html_text)

        with get_db(self.db_path) as conn:
            # Fetch canonical notice metadata
            notice_row = conn.execute(
                "SELECT id, source_id, authority_name, title, category, state FROM canonical_notices WHERE id = ?",
                (notice_id,),
            ).fetchone()
            if not notice_row:
                raise ValueError(f"Canonical notice {notice_id} not found")

            # Determine next version number
            last_v = conn.execute(
                "SELECT max(version_number) as max_v FROM notice_versions WHERE notice_id = ?",
                (notice_id,),
            ).fetchone()
            next_version = (last_v["max_v"] or 0) + 1

            version_id = f"ver_{uuid.uuid4().hex[:12]}"

            # 3. Insert immutable notice_version record
            conn.execute(
                """
                INSERT INTO notice_versions (
                    id, notice_id, version_number, document_url, document_hash,
                    document_type, storage_path, raw_text, page_count, retrieved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    notice_id,
                    next_version,
                    doc_url,
                    doc_hash,
                    doc_type,
                    str(storage_path),
                    full_text,
                    page_count,
                    now_iso,
                ),
            )

            # 4. Determine canonical status based on document readability and OCR
            is_scanned = any(p.get("is_scanned") for p in pages) or "[SCANNED DOCUMENT" in full_text
            has_legacy_font = "[LEGACY_NON_UNICODE_FONT_DETECTED" in full_text or any(p.get("has_legacy_font") for p in pages)

            ocr_confidences = [p.get("ocr_confidence", 0.0) for p in pages if p.get("is_scanned")]
            avg_ocr_confidence = (sum(ocr_confidences) / len(ocr_confidences)) if ocr_confidences else 0.0
            has_valid_ocr_text = any(
                len(p.get("text", "").strip()) >= 50
                and not p.get("text", "").startswith("[SCANNED DOCUMENT")
                for p in pages
            )
            ocr_meets_threshold = (avg_ocr_confidence >= 0.60) and has_valid_ocr_text

            if has_legacy_font:
                canonical_status = "NON_UNICODE_ENCODING_FLAGGED_FOR_HUMAN_REVIEW"
            elif is_scanned and not ocr_meets_threshold:
                canonical_status = "SCANNED_OCR_BLOCKED_FLAGGED_FOR_HUMAN_REVIEW"
            elif is_scanned and ocr_meets_threshold:
                canonical_status = "SCANNED_OCR_PROCESSED"
            else:
                canonical_status = "EXTRACTED"

            # 5. Extract structured facts (or route to human review if scanned/unreadable)
            if canonical_status == "SCANNED_OCR_BLOCKED_FLAGGED_FOR_HUMAN_REVIEW":
                extracted_facts = [
                    ExtractedFactItem(
                        key="document_readability",
                        value="SCANNED_DOCUMENT_OCR_UNAVAILABLE",
                        evidence_text="Page text density < 50 characters; OCR unconfigured or low confidence",
                        page_number=1,
                        confidence=0.0,
                        status="SCANNED_OCR_BLOCKED_FLAGGED_FOR_HUMAN_REVIEW",
                        notes="Document is scanned image; automated OCR unavailable or low confidence; flagged for human verification",
                    )
                ]
            else:
                extracted_facts = FactExtractor.extract_from_pages(
                    pages=pages,
                    authority_name=notice_row["authority_name"],
                    notice_title=notice_row["title"],
                    official_url=doc_url,
                )
                if is_scanned and ocr_meets_threshold:
                    extracted_facts.append(
                        ExtractedFactItem(
                            key="document_readability",
                            value="SCANNED_DOCUMENT_OCR_PROCESSED",
                            evidence_text=f"Local OCR extracted text across {page_count} page(s) (avg confidence: {avg_ocr_confidence:.2f})",
                            page_number=1,
                            confidence=round(avg_ocr_confidence, 2),
                            status="VERIFIED",
                            notes=f"Processed via local Windows Media OCR with empirical confidence {avg_ocr_confidence:.2f}",
                        )
                    )

            # 6. Run verification & contradiction checks on facts
            verified_facts = self._verify_and_cross_check_facts(extracted_facts, full_text)

            # 7. Insert verified facts into extracted_facts table
            for fact in verified_facts:
                fact_id = f"fct_{uuid.uuid4().hex[:12]}"
                conn.execute(
                    """
                    INSERT INTO extracted_facts (
                        id, notice_version_id, fact_key, fact_value, confidence,
                        evidence_text, page_number, verified_status, verification_notes, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        fact_id,
                        version_id,
                        fact.key,
                        fact.value,
                        fact.confidence,
                        fact.evidence_text,
                        fact.page_number,
                        fact.status,
                        fact.notes,
                        now_iso,
                    ),
                )

            # Update canonical notice status
            conn.execute(
                "UPDATE canonical_notices SET status = ?, last_updated_at = ? WHERE id = ?",
                (canonical_status, now_iso, notice_id),
            )

            # Classify notice and link to parent recruitment notice if applicable
            from testkart_intelligence.classification.classifier import NoticeClassifier
            NoticeClassifier.classify_and_update(notice_id, conn)

        return version_id, verified_facts

    def _verify_and_cross_check_facts(
        self,
        facts: List[ExtractedFactItem],
        full_text: str,
    ) -> List[ExtractedFactItem]:
        """Verify each fact against original text, check logical consistency, and flag contradictions."""
        import re
        fact_map: Dict[str, ExtractedFactItem] = {f.key: f for f in facts}

        # Check 1: Existence of supporting quote in full document text (for document-extracted facts)
        for fact in facts:
            if fact.key in ("recruiting_authority", "official_source_url"):
                # Registry facts are verified via official domain allowlist
                continue

            # Structured table facts extracted by TableExtractor from document table rows
            if fact.notes and "TableExtractor" in fact.notes:
                continue

            if fact.evidence_text and fact.status == "VERIFIED":
                # Check if evidence snippet exists in raw text
                snippet = fact.evidence_text.strip()
                cleaned_snippet = re.sub(r"^(?:Age Table|Qualification Table|Schedule Table|Table Row)[^:]*:\s*", "", snippet)
                if (
                    snippet not in full_text
                    and cleaned_snippet not in full_text
                    and fact.value not in full_text
                ):
                    fact.status = "UNVERIFIED"
                    fact.notes = "Supporting quote not found verbatim in official document text"

        # Check 2: Contradiction between start date and end date, and deadline integrity
        if "application_start_date" in fact_map and "application_end_date" in fact_map:
            start_f = fact_map["application_start_date"]
            end_f = fact_map["application_end_date"]
            try:
                dt_start = date_parser.parse(start_f.value, dayfirst=True)
                dt_end = date_parser.parse(end_f.value, dayfirst=True)
                if dt_end < dt_start:
                    end_f.status = "CONTRADICTORY"
                    end_f.notes = f"Application closing date ({end_f.value}) is before start date ({start_f.value})"
            except Exception:
                pass

        # Check 2b: Prevent age-limit cut-off dates from being confused with application schedule dates
        for d_key in ("application_start_date", "application_end_date"):
            if d_key in fact_map:
                d_f = fact_map[d_key]
                ev_lower = (d_f.evidence_text or "").lower()
                if any(cut in ev_lower for cut in ("as on", "crucial date", "cut-off date for age", "age reckoning", "age as on", "reckoned as on")) and not any(sub in ev_lower for sub in ("submission", "apply", "closing", "last date", "commencement")):
                    d_f.status = "CONTRADICTORY"
                    d_f.notes = f"Age cut-off date ({d_f.value}) mistaken for application schedule date"

        # Check 2c: Disambiguate examination dates from application deadlines
        if "application_end_date" in fact_map:
            end_f = fact_map["application_end_date"]
            ev_lower = (end_f.evidence_text or "").lower()
            is_exam_label = any(term in ev_lower for term in ("date of examination", "schedule of cbt", "examination date", "cbt date", "tier-1 exam", "tier-2 exam", "examination will be held on", "test to be held"))
            has_app_label = any(app_term in ev_lower for app_term in ("online submission", "apply", "receipt of application", "submission of online", "application form", "closing date", "last date"))
            if is_exam_label and not has_app_label:
                end_f.status = "CONTRADICTORY"
                end_f.notes = f"Examination date ({end_f.value}) mistaken for application closing deadline"

        if "exam_date" in fact_map:
            exam_f = fact_map["exam_date"]
            ev_lower = (exam_f.evidence_text or "").lower()
            is_app_label = any(term in ev_lower for term in ("submission of online application", "submission of application", "dates for submission", "opening date", "closing date", "online application window", "last date to apply"))
            has_exam_label = any(term in ev_lower for term in ("exam", "cbt", "test", "held on", "schedule of tier", "examination"))
            if is_app_label and not has_exam_label:
                exam_f.status = "CONTRADICTORY"
                exam_f.notes = f"Application submission date ({exam_f.value}) mistaken for exam date"

        # Check 3: Vacancy value must be positive integer and not question/mark count or sub-post count
        if "total_vacancies" in fact_map:
            vac_f = fact_map["total_vacancies"]
            try:
                val = int(vac_f.value)
                if val <= 0:
                    vac_f.status = "CONTRADICTORY"
                    vac_f.notes = f"Invalid non-positive vacancy count: {val}"
                else:
                    ev = (vac_f.evidence_text or "").lower()
                    if any(k in ev for k in ("question", "mark", "shift", "item", "section")):
                        vac_f.status = "CONTRADICTORY"
                        vac_f.notes = f"Extracted number {val} refers to questions/examination structure, not vacancies"
                    elif any(p_term in ev for p_term in ("assistant", "deputy", "director", "officer", "lecturer", "professor")) and not any(tot in ev for tot in ("total", "grand total", "aggregate")):
                        if re.search(r"distribution of vacancies|breakup of vacancies|tabular breakdown|breakdown", full_text, re.IGNORECASE):
                            vac_f.status = "POST_WISE_BREAKDOWN_FLAGGED_FOR_REVIEW"
                            vac_f.notes = f"Extracted value {vac_f.value} appears to be a post-specific vacancy count rather than aggregate total"
            except ValueError:
                vac_f.status = "UNVERIFIED"
                vac_f.notes = f"Vacancy value is not a valid integer: {vac_f.value}"

        # Check 4: Notice number sanity (must contain at least one digit, not plain dictionary words)
        if "notice_number" in fact_map:
            nn_f = fact_map["notice_number"]
            val = nn_f.value.strip()
            if not re.search(r"\d", val) or val.lower() in ("will", "dated", "notice", "advertisement"):
                nn_f.status = "UNVERIFIED"
                nn_f.notes = f"Notice identifier '{val}' contains no digits or is a common word"

        # Check 5: Fee sanity (must contain currency indicator and distinguish universal from category fees)
        if "application_fee" in fact_map:
            fee_f = fact_map["application_fee"]
            val = fee_f.value.strip()
            if val.lower().startswith("after completing") or len(val) > 100 or not any(sym in val for sym in ("₹", "Rs", "INR", "Nil", "Exempted")):
                fee_f.status = "UNVERIFIED"
                fee_f.notes = f"Application fee value '{val[:40]}' is malformed or contains procedural heading text"
            else:
                val_lower = val.lower()
                ev_lower = (fee_f.evidence_text or "").lower()
                concession_only = (
                    any(cat in val_lower or cat in ev_lower for cat in ("sc/st", "pwd", "handicapped", "women", "female", "reserved"))
                    and not any(gen in val_lower or gen in ev_lower for gen in ("general", "ur", "unreserved", "all other", "male", "others"))
                )
                if concession_only:
                    fee_f.status = "CATEGORY_FEE_FLAGGED_FOR_REVIEW"
                    fee_f.notes = f"Application fee '{val}' is category-specific (concession only); general/unreserved fee required"

        # Check 6: Age limit sanity (must not be an administrative instruction fragment)
        if "age_limit" in fact_map:
            age_f = fact_map["age_limit"]
            val = age_f.value.strip()
            if val.lower().startswith("candidates must have") or not re.search(r"\d{2}", val):
                age_f.status = "UNVERIFIED"
                age_f.notes = f"Age limit value '{val[:40]}' is malformed or contains procedural heading text"

        # Check 7: Eligibility Criteria Truncation check
        for q_key in ("eligibility", "eligibility_qualification"):
            if q_key in fact_map:
                qual_f = fact_map[q_key]
                q_val = qual_f.value.strip()
                truncated = False
                trunc_reason = ""
                if re.search(r"\b(?:or|and|from|with|possessing|in|of|to|for|viz\.?|etc\.?)\s*$", q_val, re.IGNORECASE):
                    truncated = True
                    trunc_reason = f"Ends with dangling conjunction/preposition '{q_val.split()[-1]}'"
                elif q_val.endswith(",") or q_val.endswith(":") or q_val.endswith(";"):
                    truncated = True
                    trunc_reason = "Ends with trailing punctuation delimiter"
                elif q_val.count("(") > q_val.count(")"):
                    truncated = True
                    trunc_reason = "Unclosed opening parenthesis"
                elif len(q_val) < 15 and not any(kw in q_val.lower() for kw in ("degree", "diploma", "10th", "12th", "graduate", "pg")):
                    truncated = True
                    trunc_reason = "String too short to represent complete qualification criteria"

                if truncated and qual_f.status == "VERIFIED":
                    qual_f.status = "TRUNCATED_ELIGIBILITY_FLAGGED_FOR_REVIEW"
                    qual_f.notes = f"Eligibility criteria text appears truncated across column/page boundaries ({trunc_reason}); flagged for review"

        return facts
