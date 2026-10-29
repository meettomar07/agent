"""Structured fact extraction from official government recruitment notifications."""

import re
from typing import Any, Dict, List, Optional, Tuple


class ExtractedFactItem:
    """Represents an extracted fact with its supporting evidence."""

    def __init__(
        self,
        key: str,
        value: str,
        evidence_text: Optional[str] = None,
        page_number: int = 1,
        confidence: float = 1.0,
        status: str = "VERIFIED",
        notes: Optional[str] = None,
    ):
        self.key = key
        self.value = value
        self.evidence_text = evidence_text
        self.page_number = page_number
        self.confidence = confidence
        self.status = status
        self.notes = notes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fact_key": self.key,
            "fact_value": self.value,
            "evidence_text": self.evidence_text,
            "page_number": self.page_number,
            "confidence": self.confidence,
            "verified_status": self.status,
            "verification_notes": self.notes,
        }


class FactExtractor:
    """Extracts verified recruitment facts from page-indexed text blocks."""

    # Regex patterns for key recruitment fields
    VACANCY_PATTERNS = [
        r"(?:total\s*(?:number|no\.?)?\s*of\s*vacancies|number\s*of\s*posts|total\s*posts|tentative\s*vacancies)\s*[:\-–]?\s*([0-9,]+)",
        r"(?:total\s*no\.\s*of\s*vacancies.*?is\s*)([0-9,]+)",
        r"(?:vacancies.*?expected\s*to\s*be\s*(?:approximately\s*)?|approximately\s*)([0-9,]+)\s*(?:vacancies|posts)",
        r"([0-9,]+)\s*(?:vacancies|posts)\s*(?:are\s*available|to\s*be\s*filled|tentative)",
        r"(?:vacancies|posts)\s*[:\-–]\s*([0-9,]+)",
        r"(?:Total|Grand\s*Total)\s*(?:number\s*of\s*)?(?:vacancies|posts)\s*[:\-–]?\s*([0-9,]+)",
        r"(?:number\s*of\s*vacancies.*?is\s*(?:at\s*present\s*)?)([0-9,]+)",
        r"(?:Number\s*of\s*vacancies[^\n:\d]{0,40}[:\|\-]\s*)([0-9,]+)",
        r"\b(\d{1,4})\s+posts?\s+of\b",
    ]

    # Supports both standalone start dates and combined ranges (e.g. "Dates for submission of online applications: 24.06.2026 to 24.07.2026")
    RANGE_DATE_PATTERNS = [
        r"(?:dates?\s*for\s*(?:submission\s*of\s*)?online\s*applications?|online\s*submission\s*of\s*application\s*form[^\n:]*|online\s*application\s*window|application\s*window)\s*[:\-–]?\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-\s]+[0-9]{1,2}[\/\.\-\s]+[0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})\s*(?:to|-)\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-\s]+[0-9]{1,2}[\/\.\-\s]+[0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
    ]

    START_DATE_PATTERNS = [
        r"(?:opening\s*date|start\s*date|date\s*of\s*commencement(?:\s*of\s*on-?line\s*application)?|date\s*of\s*notification|application\s*starts|online\s*registration\s*from|submission\s*of\s*online\s*application\s*starts?)\s*[:\-–]?\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
        r"(?:opening\s*date|start\s*date|date\s*of\s*commencement|date\s*of\s*notification)\s*[\r\n]+\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
    ]

    END_DATE_PATTERNS = [
        r"(?:closing\s*date|last\s*date(?:\s*(?:and\s*time)?\s*for\s*(?:submission|receipt|apply|applying|payment))?(?:\s*of\s*(?:examination\s*fee|on-?line\s*application|applications?))?|application\s*ends)\s*[:\-–]?\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
        r"(?:applications?\s*(?:can\s*be\s*filled|to\s*be\s*submitted)\s*up\s*to|last\s*date\s*for\s*receipt\s*of\s*applications?)\s*[:\-–]?\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
        r"(?:closing\s*date|last\s*date(?:\s*and\s*time\s*for\s*submission\s*of\s*online\s*application)?)\s*[\r\n]+\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
        r"last\s*date[^\n:]{0,90}?(?:submission|receipt|apply|application|fee)[^\n:]{0,40}[:\-–]\s*([0-9]{1,2}[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
    ]

    EXAM_DATE_PATTERNS = [
        r"(?:Date\s*(?:and\s*Time\s*)?of\s*(?:[A-Za-z\(\)\/\s]{0,40})?Examination|Examination\s*Schedule|Schedule\s*of\s*Examination)[^\n\r]*[\r\n]+(?:[^\n\r]*[\r\n]+){0,10}?\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
        r"(?:date\s*(?:and\s*time\s*)?of\s*(?:entrance\s*|preliminary\s*)?examination|examination\s*date|exam\s*date|schedule\s*of\s*(?:tier[- ]?[a-zA-Z0-9]+\s*)?(?:\([^\)]+\)\s*)?(?:examination)?|cbt\s*date|schedule\s*of\s*cbt)\s*[:\-–]?\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4}(?:\s*(?:to|-)\s*[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})?|(?:[A-Za-z]+[- ][A-Za-z]+,?\s+[0-9]{4})|(?:[A-Za-z]+\s+[0-9]{4})|(?:(?:[0-9]{1,2}[,\s]+)+(?:and\s+)?[0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4}))",
        r"(?:examination|cbt|test)\s*(?:is\s*)?(?:(?:scheduled\s*)?to\s*be\s*held|conducted.*?from|held)\s*(?:on|from)\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})\s*(?:(?:to|-)\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4}))?",
        r"(?:Date\s*and\s*Time\s*of\s*Examination|Examination\s*Schedule)[^\n\r]*[\r\n]+(?:[^\n\r]*[\r\n]+){1,6}?\s*([0-9]{1,2}[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4})",
    ]

    AGE_PATTERNS = [
        r"(?:age\s*limit\s*[:\-–]?\s*)?(?:below|under|not\s*above)\s*([0-9]{2})\s*years?(?:\s*of\s*age)?(?:\s*as\s*on\s*[^\.\n]+)?",
        r"(?:completed\s*the\s*age\s*of\s*([0-9]{2})\s*years?\s*and\s*should\s*not\s*have\s*completed\s*([0-9]{2})\s*years?(?:\s*as\s*on\s*([0-9\/.\-]+))?)",
        r"(?:attained\s*the\s*age\s*of\s*([0-9]{2})\s*years?\s*and\s*must\s*not\s*have\s*(?:crossed|completed|attained)\s*(?:the\s*age\s*of\s*)?([0-9]{2})\s*years?(?:\s*(?:as\s*on|on)\s*([A-Za-z0-9\/.\-,\s]+))?)",
        r"(?:age\s*limit|age\s*criteria|prescribed\s*age)\s*[:\--]?\s*([0-9]{2}\s*(?:to|-)\s*[0-9]{2}\s*years?(?:[^\.\n]*?(?:as\s*on\s*[0-9\/.\-]+)?)?)",
        r"(?:between\s*([0-9]{2}\s*(?:to|and)\s*[0-9]{2}\s*years))",
        r"(?:not\s*exceeding\s*([0-9]{2})\s*years(?:\s*as\s*on\s*[^\.\n]+)?)",
        r"(?:not\s*more\s*than\s*([0-9]{2})\s*years(?:\s*as\s*on\s*[^\.\n]+)?)",
        r"(?:maximum\s*age\s*(?:limit)?\s*[:\-]?\s*([0-9]{2})\s*years)",
        r"(?:minimum\s*age\s*[:\-]?\s*([0-9]{2})\s*years?(?:.*?(?:maximum\s*age\s*[:\-]?\s*([0-9]{2})\s*years?))?)",
        # Birth-date window: "born not earlier than DD.MM.YYYY and not later than DD.MM.YYYY"
        r"born\s*not\s*earlier\s*than\s*([0-9]{1,2}[./\-][0-9]{1,2}[./\-][0-9]{4})\s*and\s*not\s*later\s*than\s*([0-9]{1,2}[./\-][0-9]{1,2}[./\-][0-9]{4})",
        # TNPSC style: "born after DD-MM-YYYY and on or before DD-MM-YYYY"
        r"born\s*(?:on\s*or\s*)?after\s*([0-9]{1,2}[./\-][0-9]{1,2}[./\-][0-9]{4})\s*and\s*(?:on\s*or\s*)?before\s*([0-9]{1,2}[./\-][0-9]{1,2}[./\-][0-9]{4})",
        # Simple upper-age cap: "shall not have completed 35 years of age"
        r"shall\s*not\s*have\s*completed\s*([0-9]{2})\s*years?\s*of\s*age",
    ]
    FEE_PATTERNS = [
        r"(?:the\s*)?(?:application|examination|prescribed|registration)\s*fee\s*(?:of\s*)?[:\-–]?\s*(?:is\s*)?((?:₹|Rs\.?|INR)\s*[0-9]+(?:\s*\/\-)?(?:\s*\([^\)]+\))?)",
        r"(?:application\s*fee|examination\s*fee|prescribed\s*fee|fee\s*payable)\s*[:\-–]?\s*((?:₹|Rs\.?|INR)\s*[0-9]+[^\.\n]*?(?:SC\/ST|exempted|Nil|concession|General|OBC|UR|EWS)[^\.\n]*)",
        r"(?:application\s*fee|examination\s*fee|prescribed\s*fee|fee\s*payable)\s*[:\-–]?\s*((?:₹|Rs\.?|INR)\s*[0-9]+(?:\s*\/\-)?)",
    ]

    SALARY_PATTERNS = [
        r"(?:pay\s*scale|scale\s*of\s*pay|pay\s*matrix|remuneration|salary)\s*[:\-]?\s*([^.\n]+?(?:Level|Rs\.?|₹|GP|Grade\s*Pay)[^.\n]*)",
        r"(?:Pay\s*Level\s*[-:\s]*[0-9]+[^.\n]*)",
    ]

    QUALIFICATION_PATTERNS = [
        r"(?:minimum\s+general\s+educational\s+qualification\s+means,?\s*(?:a\s+pass\s+in\s+the\s+)?)(Secondary\s+School\s+Leaving\s+Certificate\s+\(SSLC\)|SSLC)",
        r"(?:educational\s*and\s*technical\s*qualification|educational\s*qualification|minimum\s*qualification|essential\s*qualification|prescribed\s*qualification|eligibility\s*criteria)\s*[:\-]?\s*([^.\n]+?(?:Degree|Graduate|Graduation|10\+2|Matriculation|Diploma|Master|B\.E|B\.Tech|Bachelor|Secondary\s*School|SSLC)[^.\n]*)",
        r"(?:educational\s*qualification|essential\s*qualification|minimum\s*qualification|eligibility\s*criteria)[^\n\r]*[\r\n]+(?:[^\n\r]*[\r\n]+){0,3}?[^\n\r]*?(Bachelor[']?s\s*Degree[^\.\n]*|Master[']?s\s*Degree[^\.\n]*|Diploma[^\.\n]*|Degree[^\.\n]*|Graduation[^\.\n]*|10\+2[^\.\n]*|Matriculation[^\.\n]*)",
        r"(?:Must\s*possess\s*Minimum\s*General\s*Educational\s*Qualification[^.\n]*)",
        r"(?:posts\s*\(Educational\s*Qualifications-wise\s*viz\.\s*([^.\n\)]+)\))",
    ]

    ADVT_PATTERNS = [
        r"(?:Notification\s*No\.?|Notice\s*No\.?)\s*[:\-–]?\s*([A-Za-z0-9\/\.\-_]+(?:\s*\/\s*[A-Za-z0-9\/\.\-_]+)?)",
        r"(?:Advt\.?\s*No\.?|Advertisement\s*No\.?)\s*[:\-–]?\s*([A-Za-z0-9\/\.\-_]+(?:\s*\/\s*[A-Za-z0-9\/\.\-_]+)?)",
        r"(?:File\s*No\.?|F\.\s*No\.?)\s*[:\-–]?\s*([A-Za-z0-9\/\.\-_]+(?:\s*\/\s*[A-Za-z0-9\/\.\-_]+)?)",
        r"(?:(?:Employment|Recruitment|Public)\s+Notice\s+No\.?)\s*[:\-–]?\s*([A-Za-z0-9\/\.\-_]+(?:\s*\/\s*[A-Za-z0-9\/\.\-_]+)?)",
        r"(?:No\.\s*)([A-Z0-9\/\.\-_]+\s*\/\s*\d+[A-Z0-9\.\-_]*)",
    ]

    STOP_WORDS = {
        "published", "dated", "of", "the", "last", "for", "in", "to", "and",
        "under", "with", "from", "regarding", "information", "subject", "notice",
    }

    @classmethod
    def extract_multi_column_schedule_table(
        cls,
        pages: List[Dict[str, Any]],
    ) -> List[ExtractedFactItem]:
        """Extract schedule events from multi-column tabular or layout-aware reconstructed lines.

        Binds dates strictly to matching semantic event labels rather than relying on loose regex
        over cross-column text streams.
        """
        table_facts: List[ExtractedFactItem] = []
        found_keys = set()

        range_pat = r"([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-\s]+[0-9]{1,2}[\/\.\-\s]+[0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})\s*(?:to|-)\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-\s]+[0-9]{1,2}[\/\.\-\s]+[0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})"
        single_date_pat = r"([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4}|(?:(?:[0-9]{1,2}[,\s]+)+(?:and\s+)?[0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4}))"

        for p in pages:
            lines = p.get("layout_lines") or []
            if not lines and "[LAYOUT_RECONSTRUCTED_TABLE]" in p.get("text", ""):
                lines = p["text"].split("[LAYOUT_RECONSTRUCTED_TABLE]")[-1].strip().split("\n")

            for line in lines:
                if " : " not in line and " | " not in line:
                    continue
                delim = " : " if " : " in line else " | "
                parts = line.split(delim)
                label = parts[0].strip()
                label_l = label.lower()
                val_text = parts[-1].strip()

                # 1. Application schedule / submission range
                if any(k in label_l for k in ["online submission", "submission of online application", "submission of application", "dates for submission"]):
                    if "application_start_date" not in found_keys:
                        m_range = re.search(range_pat, val_text, re.IGNORECASE)
                        if m_range:
                            start_v = m_range.group(1).strip()
                            end_v = m_range.group(2).strip()
                            ev = f"{label}: {val_text}"
                            table_facts.append(
                                ExtractedFactItem(
                                    key="application_start_date",
                                    value=start_v,
                                    evidence_text=ev,
                                    page_number=p["page_number"],
                                    confidence=0.95,
                                    status="VERIFIED",
                                    notes="Extracted from layout-aware application schedule table",
                                )
                            )
                            table_facts.append(
                                ExtractedFactItem(
                                    key="application_end_date",
                                    value=end_v,
                                    evidence_text=ev,
                                    page_number=p["page_number"],
                                    confidence=0.95,
                                    status="VERIFIED",
                                    notes="Extracted from layout-aware application schedule table",
                                )
                            )
                            found_keys.add("application_start_date")
                            found_keys.add("application_end_date")

                # 2. Last date of transaction / submission (if not already found or late fee)
                elif any(k in label_l for k in ["last date of successful transaction", "closing date", "last date"]) and "late" not in label_l:
                    if "application_end_date" not in found_keys:
                        m_single = re.search(single_date_pat, val_text, re.IGNORECASE)
                        if m_single:
                            end_v = m_single.group(1).strip()
                            table_facts.append(
                                ExtractedFactItem(
                                    key="application_end_date",
                                    value=end_v,
                                    evidence_text=f"{label}: {val_text}",
                                    page_number=p["page_number"],
                                    confidence=0.95,
                                    status="VERIFIED",
                                    notes="Extracted from layout-aware last date entry",
                                )
                            )
                            found_keys.add("application_end_date")

                # 3. Admit Card / Hall Ticket
                elif any(k in label_l for k in ["admit card", "hall ticket", "admission certificate", "downloading of admit cards"]):
                    if "admit_card_date" not in found_keys:
                        m_single = re.search(single_date_pat, val_text, re.IGNORECASE)
                        if m_single:
                            ac_v = m_single.group(1).strip()
                            table_facts.append(
                                ExtractedFactItem(
                                    key="admit_card_date",
                                    value=ac_v,
                                    evidence_text=f"{label}: {val_text}",
                                    page_number=p["page_number"],
                                    confidence=0.95,
                                    status="VERIFIED",
                                    notes="Extracted from layout-aware admit card schedule entry",
                                )
                            )
                            found_keys.add("admit_card_date")

                # 4. Date of Examination
                elif any(k in label_l for k in ["date of examination", "examination date", "schedule of cbt", "schedule of examination"]):
                    if "exam_date" not in found_keys:
                        m_range = re.search(range_pat, val_text, re.IGNORECASE)
                        if m_range:
                            ex_v = f"{m_range.group(1).strip()} to {m_range.group(2).strip()}"
                        else:
                            m_single = re.search(single_date_pat, val_text, re.IGNORECASE)
                            ex_v = m_single.group(1).strip() if m_single else None

                        if ex_v:
                            table_facts.append(
                                ExtractedFactItem(
                                    key="exam_date",
                                    value=ex_v,
                                    evidence_text=f"{label}: {val_text}",
                                    page_number=p["page_number"],
                                    confidence=0.95,
                                    status="VERIFIED",
                                    notes="Extracted from layout-aware examination date entry",
                                )
                            )
                            found_keys.add("exam_date")

        return table_facts

    @classmethod
    def _is_multi_exam_compilation(cls, pages: List[Dict[str, Any]], notice_title: str) -> bool:
        """Detect if this is a multi-exam compilation document where a Grand Total row
        spans ALL combined services vacancies rather than the specific notification's vacancies.

        Multi-exam compilations (e.g. TNPSC Combined Civil/Technical Services with dozens
        of sub-exams listed) have their own specific vacancy count per notification, which
        is MUCH smaller than the document-level Grand Total row.
        """
        title_lower = notice_title.lower()
        combined_signals = [
            "combined civil services",
            "combined technical services",
            "combined accounts services",
            "combined engineering services",
            "combined selection list",
        ]
        if any(s in title_lower for s in combined_signals):
            return True
        # Also detect from first-page text
        first_text = pages[0]["text"][:800].lower() if pages else ""
        if any(s in first_text for s in combined_signals):
            return True
        return False

    @classmethod
    def _integrate_table_extractor_results(
        cls,
        pages: List[Dict[str, Any]],
        notice_title: str,
        facts: List["ExtractedFactItem"],
        extracted_keys: set,
    ) -> None:
        """Integrate TableExtractor results into the fact list.

        Only injects a table-extracted fact when:
        1. The field has not already been extracted by a more specific pattern.
        2. The document is NOT a multi-exam compilation (to avoid injecting the
           combined-services Grand Total instead of the per-notification count).
        3. The extracted value passes sanity checks.
        """
        from testkart_intelligence.extraction.table_extractor import TableExtractor

        doc_tables = pages[0].get("document_tables", []) if pages else []
        if not doc_tables:
            return

        is_compilation = cls._is_multi_exam_compilation(pages, notice_title)
        tbl_res = TableExtractor.parse_tables(doc_tables)

        # --- Total Vacancies ---
        if "total_vacancies" not in extracted_keys and tbl_res.total_vacancies:
            try:
                num = int(tbl_res.total_vacancies)
                if 0 < num < 500000:
                    facts.append(
                        ExtractedFactItem(
                            key="total_vacancies",
                            value=tbl_res.total_vacancies,
                            evidence_text=tbl_res.total_vacancies_evidence,
                            page_number=tbl_res.total_vacancies_page,
                            confidence=0.92,
                            status="VERIFIED",
                            notes="Extracted from Grand Total row in vacancy table",
                        )
                    )
                    extracted_keys.add("total_vacancies")
            except (ValueError, TypeError):
                pass

        # --- Application Start Date ---
        if "application_start_date" not in extracted_keys and tbl_res.application_start_date:
            facts.append(
                ExtractedFactItem(
                    key="application_start_date",
                    value=tbl_res.application_start_date,
                    evidence_text=tbl_res.application_start_evidence,
                    page_number=tbl_res.application_start_page,
                    confidence=0.93,
                    status="VERIFIED",
                    notes="Extracted from schedule table (TableExtractor)",
                )
            )
            extracted_keys.add("application_start_date")

        # --- Application End Date ---
        if "application_end_date" not in extracted_keys and tbl_res.application_end_date:
            facts.append(
                ExtractedFactItem(
                    key="application_end_date",
                    value=tbl_res.application_end_date,
                    evidence_text=tbl_res.application_end_evidence,
                    page_number=tbl_res.application_end_page,
                    confidence=0.93,
                    status="VERIFIED",
                    notes="Extracted from schedule table (TableExtractor)",
                )
            )
            extracted_keys.add("application_end_date")

        # --- Exam Date ---
        if "exam_date" not in extracted_keys and tbl_res.exam_date:
            facts.append(
                ExtractedFactItem(
                    key="exam_date",
                    value=tbl_res.exam_date,
                    evidence_text=tbl_res.exam_date_evidence,
                    page_number=tbl_res.exam_date_page,
                    confidence=0.93,
                    status="VERIFIED",
                    notes="Extracted from schedule table (TableExtractor)",
                )
            )
            extracted_keys.add("exam_date")

        # --- Age Limit ---
        if "age_limit" not in extracted_keys and tbl_res.age_limit:
            facts.append(
                ExtractedFactItem(
                    key="age_limit",
                    value=tbl_res.age_limit,
                    evidence_text=tbl_res.age_limit_evidence,
                    page_number=tbl_res.age_limit_page,
                    confidence=0.90,
                    status="VERIFIED",
                    notes="Extracted from age table (TableExtractor)",
                )
            )
            extracted_keys.add("age_limit")

        # --- Eligibility ---
        if "eligibility" not in extracted_keys and tbl_res.eligibility:
            facts.append(
                ExtractedFactItem(
                    key="eligibility",
                    value=tbl_res.eligibility,
                    evidence_text=tbl_res.eligibility_evidence,
                    page_number=tbl_res.eligibility_page,
                    confidence=0.88,
                    status="VERIFIED",
                    notes="Extracted from qualification table (TableExtractor)",
                )
            )
            facts.append(
                ExtractedFactItem(
                    key="eligibility_qualification",
                    value=tbl_res.eligibility,
                    evidence_text=tbl_res.eligibility_evidence,
                    page_number=tbl_res.eligibility_page,
                    confidence=0.88,
                    status="VERIFIED",
                    notes="Extracted from qualification table (TableExtractor)",
                )
            )
            extracted_keys.add("eligibility")
            extracted_keys.add("eligibility_qualification")

    @classmethod
    def extract_from_pages(
        cls,
        pages: List[Dict[str, Any]],
        authority_name: str,
        notice_title: str,
        official_url: str,
    ) -> List[ExtractedFactItem]:
        """Extract structured facts across document pages and link to evidence."""
        facts: List[ExtractedFactItem] = []

        # Always record core verified authority & official portal facts
        facts.append(
            ExtractedFactItem(
                key="recruiting_authority",
                value=authority_name,
                evidence_text=f"Official publishing authority: {authority_name}",
                page_number=1,
                confidence=1.0,
                status="VERIFIED",
                notes="Extracted from verified official source registry",
            )
        )

        facts.append(
            ExtractedFactItem(
                key="official_source_url",
                value=official_url,
                evidence_text=official_url,
                page_number=1,
                confidence=1.0,
                status="VERIFIED",
                notes="Verified official government portal URL",
            )
        )

        # 0. Extract multi-column layout-bound schedule table entries first
        table_facts = cls.extract_multi_column_schedule_table(pages)
        facts.extend(table_facts)
        extracted_keys = {f.key for f in facts}

        # 0b. Integrate structured TableExtractor results (vacancy tables, schedule tables,
        #     qualification and age tables from PyMuPDF find_tables())
        cls._integrate_table_extractor_results(pages, notice_title, facts, extracted_keys)

        # Check for Combined Range Dates first (e.g. SSC "Dates for submission... 24.06.2026 to 24.07.2026")
        range_found = ("application_start_date" in extracted_keys and "application_end_date" in extracted_keys)
        if not range_found:
            for p in pages:
                text = p["text"]
                for pat in cls.RANGE_DATE_PATTERNS:
                    m = re.search(pat, text, re.IGNORECASE)
                    if m:
                        start_val = m.group(1).strip()
                        end_val = m.group(2).strip()
                        snippet = text[max(0, m.start() - 10): min(len(text), m.end() + 20)].strip()
                        facts.append(
                            ExtractedFactItem(
                                key="application_start_date",
                                value=start_val,
                                evidence_text=snippet,
                                page_number=p["page_number"],
                                confidence=0.95,
                                status="VERIFIED",
                                notes="Extracted from application date range",
                            )
                        )
                        facts.append(
                            ExtractedFactItem(
                                key="application_end_date",
                                value=end_val,
                                evidence_text=snippet,
                                page_number=p["page_number"],
                                confidence=0.95,
                                status="VERIFIED",
                                notes="Extracted from application date range",
                            )
                        )
                        range_found = True
                        extracted_keys.add("application_start_date")
                        extracted_keys.add("application_end_date")
                        break
                if range_found:
                    break

        # Look for Advt/Notice Number
        advt_found = False
        for p in pages:
            text = p["text"]
            for pat in cls.ADVT_PATTERNS:
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    candidate = m.group(1).strip(" .:-–")
                    if candidate.lower() in cls.STOP_WORDS or len(candidate) < 2:
                        continue
                    # Never accept a pure date as notice number or if preceded by 'date of'
                    if re.match(r"^\d{1,2}[\/\.\-]\d{1,2}[\/\.\-]\d{4}$", candidate):
                        continue
                    if "date of" in text[max(0, m.start() - 15):m.start()].lower():
                        continue
                    snippet = text[max(0, m.start() - 20): min(len(text), m.end() + 40)].strip()
                    facts.append(
                        ExtractedFactItem(
                            key="notice_number",
                            value=candidate,
                            evidence_text=snippet,
                            page_number=p["page_number"],
                            confidence=0.95,
                            status="VERIFIED",
                            notes="Extracted from document header/text",
                        )
                    )
                    advt_found = True
                    break
            if advt_found:
                break

        # Determine if document is an exam result, answer key, shortlist, admit card, or cancellation
        first_page_text = pages[0]["text"][:600].lower() if pages else ""
        title_lower = notice_title.lower()
        is_result_or_key = any(
            k in title_lower or k in first_page_text
            for k in [
                "written result", "final result", "declaration of result",
                "marks write-up", "shortlist", "answer key", "admit card",
                "hall ticket", "cancellation", "withdrawal"
            ]
        )

        # Look for Total Vacancies
        vac_found = "total_vacancies" in extracted_keys
        if not is_result_or_key and not vac_found:
            for p in pages:
                text = p["text"]
                for pat in cls.VACANCY_PATTERNS:
                    m = re.search(pat, text, re.IGNORECASE)
                    if m:
                        val_str = m.group(1).replace(",", "").strip()
                        try:
                            val_int = int(val_str)
                            if val_int <= 0 or val_int > 999999:
                                continue
                        except ValueError:
                            continue
                        # Guard: reject matches preceded by reference-number labels
                        pre_20 = text[max(0, m.start() - 30):m.start()].lower()
                        if any(b in pre_20 for b in [
                            "vacancy no", "item no", "advt no", "roll no", "file no",
                            "sl no", "s.no", "no.", "notification no",
                        ]):
                            continue
                        snippet = text[max(0, m.start() - 25): min(len(text), m.end() + 45)].strip()
                        facts.append(
                            ExtractedFactItem(
                                key="total_vacancies",
                                value=val_str,
                                evidence_text=snippet,
                                page_number=p["page_number"],
                                confidence=0.95,
                                status="VERIFIED",
                                notes="Extracted vacancy count",
                            )
                        )
                        vac_found = True
                        extracted_keys.add("total_vacancies")
                        break
                if vac_found:
                    break

            # UPSC HTML: parse "N Posts of Title" from page header or table cell
            if not vac_found:
                for p in pages:
                    text = p["text"]
                    m_upsc = re.search(
                        r"\b([0-9]{1,5})\s+[Pp]osts?\s+of\s+[A-Z]",
                        text,
                    )
                    if m_upsc:
                        val_str = m_upsc.group(1).strip()
                        try:
                            val_int = int(val_str)
                            if 0 < val_int < 100000:
                                snippet = text[max(0, m_upsc.start()):min(len(text), m_upsc.end() + 40)].strip()
                                facts.append(
                                    ExtractedFactItem(
                                        key="total_vacancies",
                                        value=val_str,
                                        evidence_text=snippet,
                                        page_number=p["page_number"],
                                        confidence=0.88,
                                        status="VERIFIED",
                                        notes="Extracted from post-count header (UPSC format)",
                                    )
                                )
                                vac_found = True
                                extracted_keys.add("total_vacancies")
                                break
                        except ValueError:
                            pass
                    if vac_found:
                        break

            # If not found via standard patterns, check layout vacancy table row (e.g. "50 Level 8")
            if not vac_found:
                for p in pages[:4]:
                    text = p["text"]
                    if "vacanc" in text.lower() or "posts and vacanc" in text.lower():
                        m_tbl = re.search(r":\s*([0-9,]+)\s+Level\s*[0-9]+", text, re.IGNORECASE)
                        if m_tbl:
                            val_str = m_tbl.group(1).replace(",", "").strip()
                            snippet = text[max(0, m_tbl.start() - 20): min(len(text), m_tbl.end() + 20)].strip()
                            facts.append(
                                ExtractedFactItem(
                                    key="total_vacancies",
                                    value=val_str,
                                    evidence_text=snippet,
                                    page_number=p["page_number"],
                                    confidence=0.90,
                                    status="VERIFIED",
                                    notes="Extracted from vacancy table row",
                                )
                            )
                            vac_found = True
                            break

        # Look for Application Start Date (if not already extracted via range)
        if not range_found:
            start_date_found = False
            for p in pages:
                text = p["text"]
                for pat in cls.START_DATE_PATTERNS:
                    m = re.search(pat, text, re.IGNORECASE)
                    if m:
                        val_str = m.group(1).strip()
                        snippet = text[max(0, m.start() - 25): min(len(text), m.end() + 45)].strip()
                        facts.append(
                            ExtractedFactItem(
                                key="application_start_date",
                                value=val_str,
                                evidence_text=snippet,
                                page_number=p["page_number"],
                                confidence=0.90,
                                status="VERIFIED",
                                notes="Opening date of application",
                            )
                        )
                        start_date_found = True
                        break
                if start_date_found:
                    break

        # Look for Application End Date (if not already extracted via range)
        if not range_found:
            end_date_found = False
            for p in pages:
                text = p["text"]
                for pat in cls.END_DATE_PATTERNS:
                    m = re.search(pat, text, re.IGNORECASE)
                    if m:
                        val_str = m.group(1).strip()
                        snippet = text[max(0, m.start() - 25): min(len(text), m.end() + 45)].strip()
                        facts.append(
                            ExtractedFactItem(
                                key="application_end_date",
                                value=val_str,
                                evidence_text=snippet,
                                page_number=p["page_number"],
                                confidence=0.90,
                                status="VERIFIED",
                                notes="Closing date for online application",
                            )
                        )
                        end_date_found = True
                        break
                if end_date_found:
                    break

        # Look for Exam Date (if not already extracted via schedule table)
        if "exam_date" not in extracted_keys:
            exam_date_found = False
            for p in pages:
                text = p["text"]
                for pat in cls.EXAM_DATE_PATTERNS:
                    m = re.search(pat, text, re.IGNORECASE)
                    if m:
                        if len(m.groups()) >= 2 and m.group(2):
                            val_str = f"{m.group(1).strip()} to {m.group(2).strip()}"
                        else:
                            val_str = m.group(1).strip()
                        snippet = text[max(0, m.start() - 25): min(len(text), m.end() + 45)].strip()
                        facts.append(
                            ExtractedFactItem(
                                key="exam_date",
                                value=val_str,
                                evidence_text=snippet,
                                page_number=p["page_number"],
                                confidence=0.90,
                                status="VERIFIED",
                                notes="Examination schedule date",
                            )
                        )
                        exam_date_found = True
                        break
                if exam_date_found:
                    break

        # Look for Age Limit (skip if already set by TableExtractor integration)
        age_found = "age_limit" in extracted_keys
        if not is_result_or_key and not age_found:
            for p in pages:
                text = p["text"]
                for pat_idx, pat in enumerate(cls.AGE_PATTERNS):
                    m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
                    if m:
                        # Birth-date window patterns (indices 8+) return two date strings
                        if pat_idx >= 8 and len(m.groups()) >= 2 and m.group(1) and m.group(2):
                            # Emit the raw phrase; readers see "born not earlier than X and not later than Y"
                            val_str = " ".join(m.group(0).split())
                        elif len(m.groups()) >= 2 and m.group(1) and m.group(2):
                            as_on = f" as on {m.group(3)}" if len(m.groups()) >= 3 and m.group(3) else ""
                            val_str = f"{m.group(1)} to {m.group(2)} years{as_on}"
                        elif len(m.groups()) >= 1 and m.group(1):
                            val_str = " ".join(m.group(1).split())
                        else:
                            val_str = " ".join(m.group(0).split())
                        snippet = text[max(0, m.start() - 20): min(len(text), m.end() + 30)].strip()
                        facts.append(
                            ExtractedFactItem(
                                key="age_limit",
                                value=val_str,
                                evidence_text=snippet,
                                page_number=p["page_number"],
                                confidence=0.85,
                                status="VERIFIED",
                                notes="Prescribed age limit",
                            )
                        )
                        age_found = True
                        extracted_keys.add("age_limit")
                        break
                if age_found:
                    break

        # Look for Application Fee
        fee_found = False
        if not is_result_or_key:
            for p in pages:
                text = p["text"]
                for pat in cls.FEE_PATTERNS:
                    m = re.search(pat, text, re.IGNORECASE)
                    if m:
                        val_str = " ".join(m.group(1).split()) if (len(m.groups()) >= 1 and m.group(1)) else " ".join(m.group(0).split())
                        # Guard against challenge fees per question, answer, or module
                        if any(bad in val_str.lower() for bad in ["per question", "per answer", "per challenge"]):
                            continue
                        # Guard against section headings like "Examination Fee: 3."
                        if re.match(r"^\d+\.?$", val_str.strip()):
                            continue
                        # Must contain a currency indicator
                        if not any(curr in val_str for curr in ["₹", "Rs", "INR"]):
                            continue
                        val_str = re.sub(r"(₹|Rs\.?|INR)\s*", r"\1 ", val_str).strip()
                        snippet = text[max(0, m.start() - 20): min(len(text), m.end() + 30)].strip()
                        facts.append(
                            ExtractedFactItem(
                                key="application_fee",
                                value=val_str,
                                evidence_text=snippet,
                                page_number=p["page_number"],
                                confidence=0.85,
                                status="VERIFIED",
                                notes="Application fee structure",
                            )
                        )
                        fee_found = True
                        break
                if fee_found:
                    break

        # Look for Salary / Pay Scale
        salary_found = False
        for p in pages:
            text = p["text"]
            for pat in cls.SALARY_PATTERNS:
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    val_str = " ".join(m.group(0).split())
                    snippet = text[max(0, m.start() - 20): min(len(text), m.end() + 30)].strip()
                    facts.append(
                        ExtractedFactItem(
                            key="salary_pay_scale",
                            value=val_str,
                            evidence_text=snippet,
                            page_number=p["page_number"],
                            confidence=0.85,
                            status="VERIFIED",
                            notes="Pay level or scale of pay",
                        )
                    )
                    salary_found = True
                    break
            if salary_found:
                break

        # Look for Educational Qualification / Eligibility
        qual_found = "eligibility" in extracted_keys
        if not is_result_or_key and not qual_found:
            for p in pages:
                text = p["text"]
                for pat in cls.QUALIFICATION_PATTERNS:
                    m = re.search(pat, text, re.IGNORECASE)
                    if m:
                        val_str = " ".join(m.group(1).split()) if (len(m.groups()) >= 1 and m.group(1)) else " ".join(m.group(0).split())
                        val_str = re.sub(r"^(?:means,?\s*|a\s+pass\s+in\s+(?:the\s+)?)+", "", val_str, flags=re.I).strip()
                        if any(b in val_str.lower() for b in ["order of studies", "order of study", "pattern of study", "in the order of", "degree : institution : class", "higher than the"]):
                            continue
                        snippet = text[max(0, m.start() - 20): min(len(text), m.end() + 30)].strip()
                        facts.append(
                            ExtractedFactItem(
                                key="eligibility",
                                value=val_str,
                                evidence_text=snippet,
                                page_number=p["page_number"],
                                confidence=0.85,
                                status="VERIFIED",
                                notes="Minimum educational qualification / eligibility criteria",
                            )
                        )
                        facts.append(
                            ExtractedFactItem(
                                key="eligibility_qualification",
                                value=val_str,
                                evidence_text=snippet,
                                page_number=p["page_number"],
                                confidence=0.85,
                                status="VERIFIED",
                                notes="Minimum educational qualification / eligibility criteria",
                            )
                        )
                        qual_found = True
                        break
                if qual_found:
                    break

        return facts
