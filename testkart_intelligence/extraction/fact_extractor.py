"""Structured fact extraction from official government recruitment notifications."""

import re
from typing import Any, Dict, List, Optional, Tuple

from testkart_intelligence.extraction.date_normalizer import DateNormalizer


class ExtractedFactItem:
    """Represents an extracted fact with its supporting evidence, normalized representation, and provenance."""

    def __init__(
        self,
        key: str,
        value: str,
        evidence_text: Optional[str] = None,
        page_number: int = 1,
        confidence: float = 1.0,
        status: str = "VERIFIED",
        notes: Optional[str] = None,
        normalized_value: Optional[str] = None,
        extraction_method: str = "PDF_TEXT",
        document_hash: Optional[str] = None,
        source_url: Optional[str] = None,
    ):
        self.key = key
        self.value = value
        self.evidence_text = evidence_text
        self.page_number = page_number
        self.confidence = confidence
        self.status = status
        self.notes = notes
        self.normalized_value = normalized_value or DateNormalizer.normalize_recruitment_value(key, value)
        self.extraction_method = extraction_method
        self.document_hash = document_hash
        self.source_url = source_url

    @property
    def fact_type(self) -> str:
        return self.key

    @property
    def fact_value(self) -> str:
        return self.value

    @property
    def verified_status(self) -> str:
        return self.status

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fact_key": self.key,
            "fact_value": self.value,
            "fact_type": self.key,
            "normalized_value": self.normalized_value,
            "evidence_text": self.evidence_text,
            "page_number": self.page_number,
            "confidence": self.confidence,
            "extraction_method": self.extraction_method,
            "verified_status": self.status,
            "verification_notes": self.notes,
            "document_hash": self.document_hash,
            "source_url": self.source_url,
        }


class FactExtractor:
    """Extracts verified recruitment facts from page-indexed text blocks."""

    # Regex patterns for key recruitment fields
    VACANCY_PATTERNS = [
        r"(?:total\s*(?:number|no\.?)?\s*of\s*vacancies|number\s*of\s*posts|total\s*posts|tentative\s*vacancies)\s*[:\-–]?\s*([0-9,]+)",
        r"(?:total\s*no\.\s*of\s*vacancies.*?is\s*)([0-9,]+)",
        r"(?:Total\s*(?:No\.?\s*of\s*)?Vacancies)\s*[:\-–]?\s*([0-9,]+)",
        r"(?:total\s*vacancies\s*(?:are\s*)?(?:revised|enhanced|increased)\s*from\s*[0-9,]+\s*to\s*[:\-–]?\s*)([0-9,]+)",
        r"(?:total\s*vacancies\s*(?:are\s*)?(?:revised|enhanced|increased)\s*to\s*[:\-–]?\s*)([0-9,]+)",
        r"(?:vacancies\s*(?:revised|enhanced|increased)\s*to\s*[:\-–]?\s*)([0-9,]+)",
        r"(?:vacancies\s*(?:are\s*)?enhanced\s*from\s*[0-9,]+\s*to\s*)([0-9,]+)",
        r"(?:vacancies.*?expected\s*to\s*be\s*(?:approximately\s*)?|approximately\s*)([0-9,]+)\s*(?:vacancies|posts)",
        r"([0-9,]+)\s*(?:vacancies|posts)\s*(?:are\s*available|to\s*be\s*filled|tentative)",
        r"(?:vacancies|posts)\s*[:\-–]\s*([0-9,]+)",
        r"(?:Total|Grand\s*Total)\s*(?:number\s*of\s*)?(?:vacancies|posts)\s*[:\-–]?\s*([0-9,]+)",
        r"(?:number\s*of\s*vacancies.*?is\s*(?:at\s*present\s*)?)([0-9,]+)",
        r"(?:Number\s*of\s*vacancies[^\n:\d]{0,40}[:\|\-]\s*)([0-9,]+)",
        r"\b(\d{1,4})\s+posts?\s+of\b",
    ]

    PUBLICATION_DATE_PATTERNS = [
        r"(?:date\s*of\s*(?:notification|issue|advertisement)|notification\s*date|notice\s*dated?|advt\.?\s*date)\s*[:\-–]?\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
        r"(?:New\s+Delhi|Prayagraj|Patna|Chennai|Bhopal|Bengaluru|Chandigarh|Kolkata)[,\s]+dated\s*(?:the\s*)?([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
        r"(?:^|[\r\n])\s*(?:Dated|Date)\s*[:\-–]\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
    ]

    # Supports both standalone start dates and combined ranges (e.g. "Dates for submission of online applications: 24.06.2026 to 24.07.2026")
    RANGE_DATE_PATTERNS = [
        r"(?:dates?\s*for\s*(?:submission\s*of\s*)?online\s*applications?|online\s*submission\s*of\s*application\s*form[^\n:]*|online\s*application\s*window|application\s*window)\s*[:\-–]?\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-\s]+[0-9]{1,2}[\/\.\-\s]+[0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})\s*(?:to|-)\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-\s]+[0-9]{1,2}[\/\.\-\s]+[0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
        r"(?:applications?\s*(?:are\s*)?invited\s*(?:online\s*)?from\s*)([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})\s*(?:to|-)\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
        r"(?:(?:stage\s*[0-9IIVv]+\s*)?(?:online\s*)?(?:registration|application)\s*(?:starts?|commences?)\s*(?:from)?\s*)([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})\s*(?:to|-)\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
        r"(?:(?:candidates\s*(?:can|may)\s*)?apply\s*(?:online\s*)?from\s*)([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})\s*(?:to|-)\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
    ]

    START_DATE_PATTERNS = [
        r"(?:opening\s*date(?:\s*(?:for|of)\s*(?:submission|application|online\s*application))?|start\s*date|date\s*of\s*commencement(?:\s*of\s*on-?line\s*application)?|application\s*commencement\s*date|commencement\s*date|commencement\s*of\s*(?:online\s*)?application|application\s*starts|online\s*registration\s*(?:commences\s*|starts\s*)?from|submission\s*of\s*online\s*application\s*starts?)\s*[:\-–]?\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
        r"(?:opening\s*date|start\s*date|date\s*of\s*commencement|commencement\s*date)\s*[\r\n]+\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
    ]

    END_DATE_PATTERNS = [
        r"(?:(?:last|closing)\s*date[^\n:]{0,60}?(?:extended|rescheduled)\s*(?:up\s*)?to\s*)([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
        r"(?:closing\s*date[^\n:]{0,50}?|last\s*date(?:\s*(?:and\s*time)?\s*for\s*(?:submission|receipt|apply|applying))(?:\s*of\s*(?:on-?line\s*application|applications?))?|application\s*ends)\s*(?:is\s*|[:\-–]\s*)([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
        r"(?:applications?\s*(?:can\s*be\s*filled|to\s*be\s*submitted)\s*up\s*to|last\s*date\s*for\s*receipt\s*of\s*applications?)\s*[:\-–]?\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
        r"(?:closing\s*date|last\s*date(?:\s*and\s*time\s*for\s*submission\s*of\s*online\s*application)?)\s*[\r\n]+\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
        r"last\s*date[^\n:]{0,90}?(?:submission|receipt|apply|application)[^\n:]{0,60}?(?:\s*is\s*|[:\-–]\s*)([0-9]{1,2}[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
    ]

    FEE_DEADLINE_PATTERNS = [
        r"(?:last\s*date(?:\s*and\s*time)?\s*(?:for\s*(?:making\s*)?(?:online\s*)?(?:fee\s*payment|payment\s*of\s*(?:online\s*)?fee|generation\s*of\s*offline\s*challan)|of\s*fee\s*payment))\s*(?:is\s*|[:\-–]\s*)([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
        r"(?:fee\s*payment\s*deadline|fee\s*to\s*be\s*paid\s*by|last\s*date\s*for\s*(?:payment\s*of\s*)?fee)\s*[:\-–]?\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
    ]

    CORRECTION_WINDOW_PATTERNS = [
        r"(?:dates?\s*(?:of|for)\s*(?:'|\")?window\s*for\s*application\s*form\s*correction(?:'|\")?|window\s*for\s*application\s*form\s*correction|correction\s*window|application\s*correction\s*window)\s*[:\-–]?\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})\s*(?:to|-)\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
    ]

    ADMIT_CARD_PATTERNS = [
        r"(?:downloading\s*of\s*admit\s*cards?|admit\s*card\s*release\s*date|e-?admit\s*card\s*download|admission\s*certificate\s*download|hall\s*ticket\s*release\s*date)\s*[:\-–]?\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
    ]

    RESULT_DATE_PATTERNS = [
        r"(?:declaration\s*of\s*result|result\s*announcement\s*date|tentative\s*date\s*of\s*result|result\s*date)\s*[:\-–]?\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
    ]

    AGE_REFERENCE_DATE_PATTERNS = [
        r"(?:crucial\s*date\s*for\s*(?:determining\s*)?age\s*(?:limit)?|age\s*(?:limit\s*)?reckoned\s*as\s*on|age\s*(?:limit\s*)?as\s*on)\s*[:\-–]?\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
    ]

    EXAM_DATE_PATTERNS = [
        # 1. Header or Label followed by colon or dash
        r"(?:Dates?\s*(?:and\s*Time\s*)?of\s*(?:[A-Za-z\(\)\/\s]{0,40})?Examination|Revised\s*(?:examination\s*)?schedule|Schedule\s*of\s*(?:tier[- ]?[a-zA-Z0-9]+\s*)?(?:\([^\)]+\)\s*)?(?:[A-Za-z0-9\(\)\/\s\-]{0,40})?Examination|Schedule\s*of\s*(?:tier[- ]?[a-zA-Z0-9]+\s*)?(?:\([^\)]+\)\s*)?|Examination\s*Schedule|Time\s*Table|Schedule\s*of\s*CBT|CBT\s*Date|Date\s*of\s*Screening\s*Examination)\s*[\):\-–]?\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+(?:to|-)\s+[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4}(?:\s*(?:to|-)\s*[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})?|(?:[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4}\s+and\s+[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})|(?:(?:[0-9]{1,2}(?:st|nd|rd|th)?[,\s]+)+(?:and\s+)?[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})|(?:[A-Za-z]+,?\s+[0-9]{4})|(?:[A-Za-z]+[- ][A-Za-z]+,?\s+[0-9]{4}))",
        # 2. Prose sentence: "The Examination will be held on ...", "is scheduled to be held on ...", "conducted from ..."
        r"(?:The\s+)?(?:Examination|CBT|Test|Screening\s+test)\s*(?:will\s*be\s*held\s*on|is\s*(?:scheduled\s*)?to\s*be\s*held\s*on|to\s*be\s*conducted\s*on|conducted\s*from|commencing\s*from|held\s*on)\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+(?:to|-)\s+[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4}(?:\s*(?:to|-)\s*[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})?|(?:[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4}\s+and\s+[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})|(?:(?:[0-9]{1,2}(?:st|nd|rd|th)?[,\s]+)+(?:and\s+)?[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})|(?:[A-Za-z]+,?\s+[0-9]{4}))",
        # 3. Multiline header: "Date of Examination ... \n 15.03.2027"
        r"(?:Dates?\s*(?:and\s*Time\s*)?of\s*(?:[A-Za-z\(\)\/\s]{0,40})?Examination|Examination\s*Schedule|Schedule\s*of\s*Examination|Schedule\s*of\s*CBT)[^\n\r]*[\r\n]+(?:[^\n\r]*[\r\n]+){0,10}?\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+(?:to|-)\s+[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4}|(?:[A-Za-z]+,?\s+[0-9]{4}))",
        # 4. Standard fallback for simple "examination date: DD/MM/YYYY"
        r"(?:examination\s*date|exam\s*date)\s*[:\-–]?\s*([0-9]{1,2}[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})",
    ]

    AGE_PATTERNS = [
        r"(?:age\s*limit\s*[:\-–]?\s*)?(?:below|under|not\s*above)\s*([0-9]{2})\s*years?(?:\s*of\s*age)?(?:\s*as\s*on\s*[^\.\n]+)?",
        r"(?:completed\s*the\s*age\s*of\s*([0-9]{2})\s*years?\s*and\s*should\s*not\s*have\s*completed\s*([0-9]{2})\s*years?(?:\s*as\s*on\s*([0-9\/.\-]+))?)",
        r"(?:attained\s*the\s*age\s*of\s*([0-9]{2})\s*years?\s*and\s*must\s*not\s*have\s*(?:crossed|completed|attained)\s*(?:the\s*age\s*of\s*)?([0-9]{2})\s*years?(?:\s*(?:as\s*on|on)\s*([A-Za-z0-9\/.\-,\s]+))?)",
        r"(?:age\s*limit|age\s*criteria|prescribed\s*age)\s*[:\--]?\s*([0-9]{2}\s*(?:to|-)\s*[0-9]{2}\s*years?(?:[^\.\n]*?(?:as\s*on\s*[0-9\/.\-]+)?)?)",
        r"(?:between\s*([0-9]{2}\s*(?:to|and)\s*[0-9]{2}\s*years))",
        r"(?:not\s*exceeding\s*([0-9]{2}\s*years(?:\s*as\s*on\s*[^\.\n]+)?))",
        r"(?:age\s*limit\s*[:\-–]\s*)(Not\s*exceeding\s*[0-9]{2}\s*years[^\.\n]*)",
        r"(?:not\s*more\s*than\s*([0-9]{2})\s*years(?:\s*as\s*on\s*[^\.\n]+)?)",
        r"(?:maximum\s*age\s*(?:limit)?\s*[:\-]?\s*([0-9]{2})\s*years)",
        r"(?:minimum\s*age\s*[:\-]?\s*([0-9]{2})\s*years?(?:.*?(?:maximum\s*age\s*[:\-]?\s*([0-9]{2})\s*years?))?)",
        # Birth-date window: "born not earlier than DD.MM.YYYY and not later than DD.MM.YYYY" or "born between ... to ..."
        r"born\s*between\s*([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})\s*(?:to|and)\s*([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})",
        r"born\s*not\s*earlier\s*than\s*([0-9]{1,2}[./\-][0-9]{1,2}[./\-][0-9]{4})\s*and\s*not\s*later\s*than\s*([0-9]{1,2}[./\-][0-9]{1,2}[./\-][0-9]{4})",
        # TNPSC style: "born after DD-MM-YYYY and on or before DD-MM-YYYY"
        r"born\s*(?:on\s*or\s*)?after\s*([0-9]{1,2}[./\-][0-9]{1,2}[./\-][0-9]{4})\s*and\s*(?:on\s*or\s*)?before\s*([0-9]{1,2}[./\-][0-9]{1,2}[./\-][0-9]{4})",
        # Simple upper-age cap: "shall not have completed 35 years of age"
        r"shall\s*not\s*have\s*completed\s*([0-9]{2})\s*years?\s*of\s*age",
        # RIMC fractional age limit: 11.5 to 13 years
        r"\b(11\.5|11\s*½)\s*(?:to|-)\s*(13)\s*years?",
        # Table / section pattern for state PSCs: Minimum Age ... (\d{2}) ... Maximum Age ... (\d{2})
        r"(?:Minimum\s*Age[^\n\d]{0,40}?([0-9]{2})\s*(?:years|Years)?[^\n]*?(?:Maximum\s*Age[^\n\d]{0,40}?([0-9]{2})\s*years?))",
        # completed the age of 21/26 years ... Others: 32/34 years
        r"(?:completed\s*(?:the\s*)?age\s*of\s*([0-9]{2})\s*years?[^\n]*?(?:Others|‘OTHERS’|\"Others\"|Maximum\s*Age)[^\n\d]{0,60}?([0-9]{2})\s*years?)",
        # Dedicated Others maximum age: Others ... 32/34 years
        r"(?:Others|‘OTHERS’|\"Others\")[^\n\d]{0,60}?([0-9]{2})\s*years?(?:\s*\(Should\s*not\s*have\s*Completed\))?",
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
        # Explicit Qualifications: or Eligibility: line header
        r"(?:^|[\r\n])\s*(?:Qualifications?|Eligibility)\s*[:\-–]\s*([^\n\r]+)",
        # SSLC
        r"(?:minimum\s+general\s+educational\s+qualification\s+means,?\s*(?:a\s+pass\s+in\s+the\s+)?)(Secondary\s+School\s+Leaving\s+Certificate\s+\(SSLC\)|SSLC)",
        # Educational qualification followed by details
        r"(?:educational\s*and\s*technical\s*qualification|educational\s*qualification|minimum\s*qualification|essential\s*qualification|prescribed\s*qualification|eligibility\s*criteria)\s*(?:is\s*(?:amended|modified)\s*as\s*(?:under)?\s*)?[:\-–]?\s*([^.\n]+?(?:Degree|Graduate|Graduation|10\+2|12th|Matriculation|Diploma|Master|B\.E|B\.Tech|Bachelor|Secondary\s*School|SSLC|MBBS|Law|LLB|Ayurvedic|Unani|MD|MS|DNB|enrolled\s*in)[^.\n]*)",
        # Multiline qualification
        r"(?:educational\s*qualification|essential\s*qualification|minimum\s*qualification|eligibility\s*criteria)[^\n\r]*[\r\n]+(?:[^\n\r]*[\r\n]+){0,4}?[^\n\r]*?(Bachelor[']?s\s*Degree[^\.\n]*|Master[']?s\s*Degree[^\.\n]*|Diploma[^\.\n]*|Degree[^\.\n]*|Graduation[^\.\n]*|10\+2[^\.\n]*|12th[^\.\n]*|Matriculation[^\.\n]*|MBBS[^\.\n]*|Law[^\.\n]*|Class\s*VII[^\.\n]*)",
        # Qualification and Experience table format
        r"(?:Qualification\s*and\s*Experience|Educational\s*Qualification[^\n\r]*)[^\n\r]*[\r\n]+(?:[^\n\r]*[\r\n]+){0,6}?[^\n\r]*?(B\.L\.[^\.\n]*|Degree\s*in\s*Law[^\.\n]*|Bachelor[']?s\s*Degree[^\.\n]*|Master[']?s\s*Degree[^\.\n]*|Diploma\s*in\s*[A-Za-z\s]+|Diploma[^\.\n]*|Class\s*VII[^\.\n]*|Matriculation[^\.\n]*|SSLC[^\.\n]*)",
        # Standalone "Must possess..."
        r"(?:Must\s*possess\s*(?:a\s*)?(?:Bachelor[']?s\s*Degree|Master[']?s\s*Degree|Degree|Diploma|Minimum\s*General\s*Educational\s*Qualification)[^.\n]*)",
        # Departmental circular condition
        r"(?:Only\s+departmental\s+candidates\s+serving\s+regularly[^.\n]*)",
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
        doc_hash: Optional[str] = None,
        source_url: Optional[str] = None,
    ) -> List[ExtractedFactItem]:
        """Extract schedule events from multi-column tabular or layout-aware reconstructed lines.

        Binds dates strictly to matching semantic event labels rather than relying on loose regex
        over cross-column text streams.
        """
        table_facts: List[ExtractedFactItem] = []
        found_keys = set()

        range_pat = r"([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-\s]+[0-9]{1,2}[\/\.\-\s]+[0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+[0-9]{4})\s*(?:to|-)\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-\s]+[0-9]{1,2}[\/\.\-\s]+[0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+[0-9]{4})"
        day_range_pat = r"([0-9]{1,2}(?:st|nd|rd|th)?)\s*(?:to|-)\s*([0-9]{1,2}(?:st|nd|rd|th)?)\s+([A-Za-z]+),?\s+([0-9]{4})"
        month_range_pat = r"([0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+),?\s*(?:to|-)\s*([0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+),?\s+([0-9]{4})"
        single_date_pat = r"([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+[0-9]{4}|(?:(?:[0-9]{1,2}[,\s]+)+(?:and\s+)?[0-9]{1,2}\s+[A-Za-z]+,?\s+[0-9]{4}))"

        def _parse_schedule_val_date(val: str) -> Optional[Tuple[str, str]]:
            """Returns (formatted_val, raw_evidence)."""
            if not val:
                return None
            m_dr = re.search(day_range_pat, val, re.I)
            if m_dr:
                d1, d2, mo, yr = m_dr.groups()
                return f"{d1} {mo} {yr} to {d2} {mo} {yr}", val.strip()
            m_mr = re.search(month_range_pat, val, re.I)
            if m_mr:
                d1_m, d2_m, yr = m_mr.groups()
                return f"{d1_m} {yr} to {d2_m} {yr}", val.strip()
            m_r = re.search(range_pat, val, re.I)
            if m_r:
                return f"{m_r.group(1).strip()} to {m_r.group(2).strip()}", val.strip()
            m_s = re.search(single_date_pat, val, re.I)
            if m_s:
                return m_s.group(1).strip(), val.strip()
            return None

        for p in pages:
            lines = []
            if p.get("text"):
                lines.extend(p["text"].splitlines())
            if p.get("layout_lines"):
                for ll in p["layout_lines"]:
                    lines.extend(ll.splitlines())
            if "[LAYOUT_RECONSTRUCTED_TABLE]" in p.get("text", ""):
                lines.extend(p["text"].split("[LAYOUT_RECONSTRUCTED_TABLE]")[-1].strip().splitlines())

            for line in lines:
                line = line.strip()
                if " : " not in line and " | " not in line and "\t" not in line and " - " not in line:
                    continue
                delim = " : " if " : " in line else (" | " if " | " in line else ("\t" if "\t" in line else " - "))
                parts = line.split(delim)
                label = parts[0].strip()
                label_l = label.lower()
                val_text = parts[-1].strip()

                # 1. Publication Date in table
                if any(k in label_l for k in ["date of notification", "date of publication", "advt date", "date of advertisement", "notification date"]):
                    if "publication_date" not in found_keys:
                        m_single = re.search(single_date_pat, val_text, re.IGNORECASE)
                        if m_single:
                            pub_v = m_single.group(1).strip()
                            table_facts.append(
                                ExtractedFactItem(
                                    key="publication_date",
                                    value=pub_v,
                                    evidence_text=f"{label}: {val_text}",
                                    page_number=p["page_number"],
                                    confidence=0.96,
                                    status="VERIFIED",
                                    notes="Extracted from schedule table notification date entry",
                                    extraction_method="TABLE_EXTRACTOR",
                                    document_hash=doc_hash,
                                    source_url=source_url,
                                )
                            )
                            found_keys.add("publication_date")

                # 2a. Standalone Opening Date in table
                elif any(k in label_l for k in ["opening date", "commencement", "submission starts", "registration starts", "application starts"]):
                    if "application_start_date" not in found_keys:
                        m_single = re.search(single_date_pat, val_text, re.IGNORECASE)
                        if m_single:
                            start_v = m_single.group(1).strip()
                            table_facts.append(
                                ExtractedFactItem(
                                    key="application_start_date",
                                    value=start_v,
                                    evidence_text=f"{label}: {val_text}",
                                    page_number=p["page_number"],
                                    confidence=0.96,
                                    status="VERIFIED",
                                    notes="Extracted from schedule table opening date entry",
                                    extraction_method="TABLE_EXTRACTOR",
                                    document_hash=doc_hash,
                                    source_url=source_url,
                                )
                            )
                            found_keys.add("application_start_date")

                # 2b. Standalone Closing Date in table
                elif any(k in label_l for k in ["closing date", "last date for submission", "last date and time for submission", "last date to apply", "closing date for online submission", "last date of online application", "closing date of application"]) and "fee" not in label_l and "late" not in label_l and "correction" not in label_l and "window" not in label_l:
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
                                    extraction_method="TABLE_EXTRACTOR",
                                    document_hash=doc_hash,
                                    source_url=source_url,
                                )
                            )
                            found_keys.add("application_end_date")

                # 2c. Application schedule / submission range
                elif any(k in label_l for k in ["online submission", "submission of online application", "submission of application", "dates for submission"]) and "last date" not in label_l and "closing date" not in label_l and "correction" not in label_l:
                    if "application_start_date" not in found_keys or "application_end_date" not in found_keys:
                        m_range = re.search(range_pat, val_text, re.IGNORECASE)
                        if m_range:
                            start_v = m_range.group(1).strip()
                            end_v = m_range.group(2).strip()
                            ev = f"{label}: {val_text}"
                            if "application_start_date" not in found_keys:
                                table_facts.append(
                                    ExtractedFactItem(
                                        key="application_start_date",
                                        value=start_v,
                                        evidence_text=ev,
                                        page_number=p["page_number"],
                                        confidence=0.95,
                                        status="VERIFIED",
                                        notes="Extracted from layout-aware application schedule table",
                                        extraction_method="TABLE_EXTRACTOR",
                                        document_hash=doc_hash,
                                        source_url=source_url,
                                    )
                                )
                                found_keys.add("application_start_date")
                            if "application_end_date" not in found_keys:
                                table_facts.append(
                                    ExtractedFactItem(
                                        key="application_end_date",
                                        value=end_v,
                                        evidence_text=ev,
                                        page_number=p["page_number"],
                                        confidence=0.95,
                                        status="VERIFIED",
                                        notes="Extracted from layout-aware application schedule table",
                                        extraction_method="TABLE_EXTRACTOR",
                                        document_hash=doc_hash,
                                        source_url=source_url,
                                    )
                                )
                                found_keys.add("application_end_date")

                # 3. Fee payment deadline (distinct from application closing date)
                elif any(k in label_l for k in ["fee payment", "payment of fee", "transaction of fee", "making online fee payment"]):
                    if "fee_payment_deadline" not in found_keys:
                        m_single = re.search(single_date_pat, val_text, re.IGNORECASE)
                        if m_single:
                            fee_v = m_single.group(1).strip()
                            table_facts.append(
                                ExtractedFactItem(
                                    key="fee_payment_deadline",
                                    value=fee_v,
                                    evidence_text=f"{label}: {val_text}",
                                    page_number=p["page_number"],
                                    confidence=0.95,
                                    status="VERIFIED",
                                    notes="Extracted from schedule table fee payment entry",
                                    extraction_method="TABLE_EXTRACTOR",
                                    document_hash=doc_hash,
                                    source_url=source_url,
                                )
                            )
                            found_keys.add("fee_payment_deadline")

                # 4. Correction window
                elif any(k in label_l for k in ["correction window", "application form correction", "window for correction"]):
                    if "correction_window_start_date" not in found_keys:
                        m_range = re.search(range_pat, val_text, re.IGNORECASE)
                        if m_range:
                            c_start = m_range.group(1).strip()
                            c_end = m_range.group(2).strip()
                            ev = f"{label}: {val_text}"
                            table_facts.append(
                                ExtractedFactItem(
                                    key="correction_window_start_date",
                                    value=c_start,
                                    evidence_text=ev,
                                    page_number=p["page_number"],
                                    confidence=0.95,
                                    status="VERIFIED",
                                    notes="Extracted from correction window schedule entry",
                                    extraction_method="TABLE_EXTRACTOR",
                                    document_hash=doc_hash,
                                    source_url=source_url,
                                )
                            )
                            table_facts.append(
                                ExtractedFactItem(
                                    key="correction_window_end_date",
                                    value=c_end,
                                    evidence_text=ev,
                                    page_number=p["page_number"],
                                    confidence=0.95,
                                    status="VERIFIED",
                                    notes="Extracted from correction window schedule entry",
                                    extraction_method="TABLE_EXTRACTOR",
                                    document_hash=doc_hash,
                                    source_url=source_url,
                                )
                            )
                            found_keys.add("correction_window_start_date")
                            found_keys.add("correction_window_end_date")

                # 5. Last date of application submission (if not already found via range)
                elif any(k in label_l for k in ["closing date", "last date for submission", "last date to apply", "closing date for online submission"]) and "fee" not in label_l and "late" not in label_l:
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
                                    extraction_method="TABLE_EXTRACTOR",
                                    document_hash=doc_hash,
                                    source_url=source_url,
                                )
                            )
                            found_keys.add("application_end_date")

                # 6. Admit Card / Hall Ticket
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
                                    extraction_method="TABLE_EXTRACTOR",
                                    document_hash=doc_hash,
                                    source_url=source_url,
                                )
                            )
                            found_keys.add("admit_card_date")

                # 7. Date of Examination
                elif any(k in label_l for k in ["date of examination", "examination date", "schedule of cbt", "schedule of tier", "examination", "schedule of examination", "date and time of examination", "date of written examination", "paper-i", "paper – i", "paper 1", "tier-i", "cbt date", "proposed dates", "dates of examination", "dates of exam"]) and any(e in label_l for e in ["exam", "cbt", "test", "paper", "dates"]):
                    if "exam_date" not in found_keys:
                        res_dt = _parse_schedule_val_date(val_text)
                        if res_dt:
                            ex_v = res_dt[0]
                            table_facts.append(
                                ExtractedFactItem(
                                    key="exam_date",
                                    value=ex_v,
                                    evidence_text=f"{label}: {val_text}",
                                    page_number=p["page_number"],
                                    confidence=0.95,
                                    status="VERIFIED",
                                    notes="Extracted from layout-aware examination date entry",
                                    extraction_method="TABLE_EXTRACTOR",
                                    document_hash=doc_hash,
                                    source_url=source_url,
                                )
                            )
                            found_keys.add("exam_date")

                # 8. Result Date
                elif any(k in label_l for k in ["declaration of result", "result date", "tentative result"]):
                    if "result_date" not in found_keys:
                        m_single = re.search(single_date_pat, val_text, re.IGNORECASE)
                        if m_single:
                            res_v = m_single.group(1).strip()
                            table_facts.append(
                                ExtractedFactItem(
                                    key="result_date",
                                    value=res_v,
                                    evidence_text=f"{label}: {val_text}",
                                    page_number=p["page_number"],
                                    confidence=0.95,
                                    status="VERIFIED",
                                    notes="Extracted from layout-aware result date entry",
                                    extraction_method="TABLE_EXTRACTOR",
                                    document_hash=doc_hash,
                                    source_url=source_url,
                                )
                            )
                            found_keys.add("result_date")

            # 2. Vertical layout lookahead (where label and date are on separate adjacent lines)
            clean_lines = [l.strip() for l in lines if l.strip()]
            for i, cl in enumerate(clean_lines):
                cl_l = cl.lower()
                # Notification date
                if any(k in cl_l for k in ["date of notification", "date of publication", "advt date", "date of advertisement"]) and "publication_date" not in found_keys:
                    for k in range(1, 4):
                        if i + k < len(clean_lines):
                            res_dt = _parse_schedule_val_date(clean_lines[i+k])
                            if res_dt:
                                table_facts.append(ExtractedFactItem(
                                    key="publication_date", value=res_dt[0], evidence_text=f"{cl}: {clean_lines[i+k]}",
                                    page_number=p["page_number"], confidence=0.95, status="VERIFIED",
                                    notes="Extracted from vertical schedule block", extraction_method="TABLE_EXTRACTOR",
                                    document_hash=doc_hash, source_url=source_url,
                                ))
                                found_keys.add("publication_date")
                                break
                # Application end date
                elif any(k in cl_l for k in ["last date for submission", "last date and time for submission", "closing date of online application", "closing date for submission", "last date to apply"]) and "application_end_date" not in found_keys and "fee" not in cl_l and "correction" not in cl_l and "window" not in cl_l and not cl_l.startswith("after "):
                    for k in range(1, 4):
                        if i + k < len(clean_lines):
                            res_dt = _parse_schedule_val_date(clean_lines[i+k])
                            if res_dt:
                                table_facts.append(ExtractedFactItem(
                                    key="application_end_date", value=res_dt[0], evidence_text=f"{cl}: {clean_lines[i+k]}",
                                    page_number=p["page_number"], confidence=0.95, status="VERIFIED",
                                    notes="Extracted from vertical schedule block", extraction_method="TABLE_EXTRACTOR",
                                    document_hash=doc_hash, source_url=source_url,
                                ))
                                found_keys.add("application_end_date")
                                break
                # Examination date
                elif any(k in cl_l for k in ["date of written examination", "date of examination", "schedule of cbt", "date and time of examination", "schedule of examination"]) and "exam_date" not in found_keys:
                    for k in range(1, 20):
                        if i + k < len(clean_lines):
                            next_line = clean_lines[i+k]
                            if any(hdr in next_line.lower() for hdr in ["5. qualification", "4. qualification", "5. age", "note:", "annexure"]):
                                break
                            res_dt = _parse_schedule_val_date(next_line)
                            if res_dt:
                                table_facts.append(ExtractedFactItem(
                                    key="exam_date", value=res_dt[0], evidence_text=f"{cl} ... {next_line}",
                                    page_number=p["page_number"], confidence=0.95, status="VERIFIED",
                                    notes="Extracted from vertical examination schedule block", extraction_method="TABLE_EXTRACTOR",
                                    document_hash=doc_hash, source_url=source_url,
                                ))
                                found_keys.add("exam_date")
                                break

        return table_facts

    @classmethod
    def _is_multi_exam_compilation(cls, pages: List[Dict[str, Any]], notice_title: str) -> bool:
        """Detect if this is a multi-exam compilation document."""
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
        doc_hash: Optional[str] = None,
        source_url: Optional[str] = None,
    ) -> None:
        """Integrate TableExtractor results into the fact list."""
        from testkart_intelligence.extraction.table_extractor import TableExtractor

        doc_tables = pages[0].get("document_tables", []) if pages else []
        if not doc_tables:
            return

        is_compilation = cls._is_multi_exam_compilation(pages, notice_title)
        tbl_res = TableExtractor.parse_tables(doc_tables)

        # --- Total Vacancies ---
        if "total_vacancies" not in extracted_keys and tbl_res.total_vacancies:
            is_single_post = "Single Post Table Row" in (tbl_res.total_vacancies_evidence or "")
            narrative_total = None
            for p in pages[:8]:
                m_narr = re.search(r"Total\s*(?:No\.?\s*of\s*)?Vacancies\s*[:\-–]?\s*([0-9,]+)", p.get("text", ""), re.I)
                if m_narr:
                    v_clean = m_narr.group(1).replace(",", "").strip()
                    if v_clean and int(v_clean) > 0:
                        narrative_total = (v_clean, m_narr.group(0), p["page_number"])
                        break

            if narrative_total and is_single_post:
                facts.append(
                    ExtractedFactItem(
                        key="total_vacancies",
                        value=narrative_total[0],
                        evidence_text=narrative_total[1],
                        page_number=narrative_total[2],
                        confidence=0.95,
                        status="VERIFIED",
                        notes="Extracted from explicit narrative total vacancies (supersedes single-post table estimate)",
                        extraction_method="PDF_TEXT",
                        document_hash=doc_hash,
                        source_url=source_url,
                    )
                )
                extracted_keys.add("total_vacancies")
            else:
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
                                extraction_method="TABLE_EXTRACTOR",
                                document_hash=doc_hash,
                                source_url=source_url,
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
                    extraction_method="TABLE_EXTRACTOR",
                    document_hash=doc_hash,
                    source_url=source_url,
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
                    extraction_method="TABLE_EXTRACTOR",
                    document_hash=doc_hash,
                    source_url=source_url,
                )
            )
            extracted_keys.add("application_end_date")

        # --- Exam Date ---
        if tbl_res.exam_date:
            if "exam_date" in extracted_keys:
                for f in facts:
                    if f.key == "exam_date":
                        f.value = tbl_res.exam_date
                        f.evidence_text = tbl_res.exam_date_evidence
                        f.page_number = tbl_res.exam_date_page
                        f.notes = "Extracted from schedule table (TableExtractor)"
                        f.extraction_method = "TABLE_EXTRACTOR"
                        break
            else:
                facts.append(
                    ExtractedFactItem(
                        key="exam_date",
                        value=tbl_res.exam_date,
                        evidence_text=tbl_res.exam_date_evidence,
                        page_number=tbl_res.exam_date_page,
                        confidence=0.93,
                        status="VERIFIED",
                        notes="Extracted from schedule table (TableExtractor)",
                        extraction_method="TABLE_EXTRACTOR",
                        document_hash=doc_hash,
                        source_url=source_url,
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
                    extraction_method="TABLE_EXTRACTOR",
                    document_hash=doc_hash,
                    source_url=source_url,
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
                    extraction_method="TABLE_EXTRACTOR",
                    document_hash=doc_hash,
                    source_url=source_url,
                )
            )
            extracted_keys.add("eligibility")

    @classmethod
    def extract_from_pages(
        cls,
        pages: List[Dict[str, Any]],
        authority_name: str,
        notice_title: str,
        official_url: str,
        doc_hash: Optional[str] = None,
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
                extraction_method="REGISTRY",
                document_hash=doc_hash,
                source_url=official_url,
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
                extraction_method="REGISTRY",
                document_hash=doc_hash,
                source_url=official_url,
            )
        )

        # 0. Extract multi-column layout-bound schedule table entries first
        table_facts = cls.extract_multi_column_schedule_table(pages, doc_hash=doc_hash, source_url=official_url)
        facts.extend(table_facts)
        extracted_keys = {f.key for f in facts}

        # 0b. Integrate structured TableExtractor results
        cls._integrate_table_extractor_results(pages, notice_title, facts, extracted_keys, doc_hash=doc_hash, source_url=official_url)

        # 1. Publication Date extraction (distinct from application start date!)
        pub_found = "publication_date" in extracted_keys
        if not pub_found:
            for p in pages:
                text = p["text"]
                for pat in cls.PUBLICATION_DATE_PATTERNS:
                    m = re.search(pat, text, re.IGNORECASE)
                    if m:
                        pub_val = m.group(1).strip()
                        snippet = text[max(0, m.start() - 15): min(len(text), m.end() + 25)].strip()
                        facts.append(
                            ExtractedFactItem(
                                key="publication_date",
                                value=pub_val,
                                evidence_text=snippet,
                                page_number=p["page_number"],
                                confidence=0.95,
                                status="VERIFIED",
                                notes="Official notification publication date",
                                extraction_method="PDF_TEXT",
                                document_hash=doc_hash,
                                source_url=official_url,
                            )
                        )
                        pub_found = True
                        extracted_keys.add("publication_date")
                        break
                if pub_found:
                    break

        # 2. Check for Combined Range Dates (e.g. SSC "Dates for submission... 24.06.2026 to 24.07.2026")
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
                                extraction_method="PDF_TEXT",
                                document_hash=doc_hash,
                                source_url=official_url,
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
                                extraction_method="PDF_TEXT",
                                document_hash=doc_hash,
                                source_url=official_url,
                            )
                        )
                        range_found = True
                        extracted_keys.add("application_start_date")
                        extracted_keys.add("application_end_date")
                        break
                if range_found:
                    break

        # 3. Look for Advt/Notice Number
        advt_found = False
        for p in pages:
            text = p["text"]
            for pat in cls.ADVT_PATTERNS:
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    candidate = m.group(1).strip(" .:-–")
                    if candidate.lower() in cls.STOP_WORDS or len(candidate) < 2:
                        continue
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
                            extraction_method="PDF_TEXT",
                            document_hash=doc_hash,
                            source_url=official_url,
                        )
                    )
                    advt_found = True
                    break
            if advt_found:
                break

        # Determine document nature
        first_page_text = pages[0]["text"][:600].lower() if pages else ""
        title_lower = notice_title.lower()
        is_result_or_key = any(
            k in title_lower or (k in first_page_text and k not in ("admit card", "hall ticket"))
            for k in [
                "written result", "final result", "declaration of result",
                "marks write-up", "shortlist", "answer key", "admit card",
                "hall ticket", "cancellation", "withdrawal"
            ]
        )

        # 4. Total Vacancies
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
                                extraction_method="PDF_TEXT",
                                document_hash=doc_hash,
                                source_url=official_url,
                            )
                        )
                        vac_found = True
                        extracted_keys.add("total_vacancies")
                        break
                if vac_found:
                    break

            if not vac_found:
                for p in pages:
                    text = p["text"]
                    m_upsc = re.search(r"\b([0-9]{1,5})\s+[Pp]osts?\s+of\s+[A-Z]", text)
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
                                        extraction_method="PDF_TEXT",
                                        document_hash=doc_hash,
                                        source_url=official_url,
                                    )
                                )
                                vac_found = True
                                extracted_keys.add("total_vacancies")
                                break
                        except ValueError:
                            pass
                    if vac_found:
                        break

        # 5. Look for Application Start Date (if not already extracted via range)
        if not range_found and "application_start_date" not in extracted_keys:
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
                                extraction_method="PDF_TEXT",
                                document_hash=doc_hash,
                                source_url=official_url,
                            )
                        )
                        start_date_found = True
                        extracted_keys.add("application_start_date")
                        break
                if start_date_found:
                    break

        # 6. Look for Application End Date (if not already extracted via range)
        if not range_found and "application_end_date" not in extracted_keys:
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
                                extraction_method="PDF_TEXT",
                                document_hash=doc_hash,
                                source_url=official_url,
                            )
                        )
                        end_date_found = True
                        extracted_keys.add("application_end_date")
                        break
                if end_date_found:
                    break

        # 7. Fee Payment Deadline (distinct from application closing date!)
        if "fee_payment_deadline" not in extracted_keys:
            fee_dl_found = False
            for p in pages:
                text = p["text"]
                for pat in cls.FEE_DEADLINE_PATTERNS:
                    m = re.search(pat, text, re.IGNORECASE)
                    if m:
                        val_str = m.group(1).strip()
                        snippet = text[max(0, m.start() - 25): min(len(text), m.end() + 45)].strip()
                        facts.append(
                            ExtractedFactItem(
                                key="fee_payment_deadline",
                                value=val_str,
                                evidence_text=snippet,
                                page_number=p["page_number"],
                                confidence=0.92,
                                status="VERIFIED",
                                notes="Fee payment deadline",
                                extraction_method="PDF_TEXT",
                                document_hash=doc_hash,
                                source_url=official_url,
                            )
                        )
                        fee_dl_found = True
                        extracted_keys.add("fee_payment_deadline")
                        break
                if fee_dl_found:
                    break

        # 8. Correction Window Start & End Dates
        if "correction_window_start_date" not in extracted_keys:
            corr_found = False
            for p in pages:
                text = p["text"]
                for pat in cls.CORRECTION_WINDOW_PATTERNS:
                    m = re.search(pat, text, re.IGNORECASE)
                    if m:
                        c_start = m.group(1).strip()
                        c_end = m.group(2).strip()
                        snippet = text[max(0, m.start() - 20): min(len(text), m.end() + 30)].strip()
                        facts.append(
                            ExtractedFactItem(
                                key="correction_window_start_date",
                                value=c_start,
                                evidence_text=snippet,
                                page_number=p["page_number"],
                                confidence=0.92,
                                status="VERIFIED",
                                notes="Start of application form correction window",
                                extraction_method="PDF_TEXT",
                                document_hash=doc_hash,
                                source_url=official_url,
                            )
                        )
                        facts.append(
                            ExtractedFactItem(
                                key="correction_window_end_date",
                                value=c_end,
                                evidence_text=snippet,
                                page_number=p["page_number"],
                                confidence=0.92,
                                status="VERIFIED",
                                notes="End of application form correction window",
                                extraction_method="PDF_TEXT",
                                document_hash=doc_hash,
                                source_url=official_url,
                            )
                        )
                        corr_found = True
                        extracted_keys.add("correction_window_start_date")
                        extracted_keys.add("correction_window_end_date")
                        break
                if corr_found:
                    break

        # 9. Admit Card Release Date
        if "admit_card_date" not in extracted_keys:
            ac_found = False
            for p in pages:
                text = p["text"]
                for pat in cls.ADMIT_CARD_PATTERNS:
                    m = re.search(pat, text, re.IGNORECASE)
                    if m:
                        ac_val = m.group(1).strip()
                        snippet = text[max(0, m.start() - 20): min(len(text), m.end() + 30)].strip()
                        facts.append(
                            ExtractedFactItem(
                                key="admit_card_date",
                                value=ac_val,
                                evidence_text=snippet,
                                page_number=p["page_number"],
                                confidence=0.90,
                                status="VERIFIED",
                                notes="Admit card release date",
                                extraction_method="PDF_TEXT",
                                document_hash=doc_hash,
                                source_url=official_url,
                            )
                        )
                        ac_found = True
                        extracted_keys.add("admit_card_date")
                        break
                if ac_found:
                    break

        # 10. Result Declaration Date
        if "result_date" not in extracted_keys:
            res_found = False
            for p in pages:
                text = p["text"]
                for pat in cls.RESULT_DATE_PATTERNS:
                    m = re.search(pat, text, re.IGNORECASE)
                    if m:
                        res_val = m.group(1).strip()
                        snippet = text[max(0, m.start() - 20): min(len(text), m.end() + 30)].strip()
                        facts.append(
                            ExtractedFactItem(
                                key="result_date",
                                value=res_val,
                                evidence_text=snippet,
                                page_number=p["page_number"],
                                confidence=0.90,
                                status="VERIFIED",
                                notes="Declaration of result date",
                                extraction_method="PDF_TEXT",
                                document_hash=doc_hash,
                                source_url=official_url,
                            )
                        )
                        res_found = True
                        extracted_keys.add("result_date")
                        break
                if res_found:
                    break

        # 11. Exam Date (if not already extracted via schedule table)
        if "exam_date" not in extracted_keys:
            exam_date_found = False
            for p in pages:
                if p["page_number"] > 15:
                    continue
                text = p["text"]
                for pat in cls.EXAM_DATE_PATTERNS:
                    m = re.search(pat, text, re.IGNORECASE)
                    if m:
                        if len(m.groups()) >= 2 and m.group(2):
                            val_str = f"{m.group(1).strip()} to {m.group(2).strip()}"
                        else:
                            val_str = m.group(1).strip()
                        m_year = re.search(r"\b(20[0-2][0-9])\b", val_str)
                        if m_year and int(m_year.group(1)) < 2022:
                            continue
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
                                extraction_method="PDF_TEXT",
                                document_hash=doc_hash,
                                source_url=official_url,
                            )
                        )
                        exam_date_found = True
                        extracted_keys.add("exam_date")
                        break
                if exam_date_found:
                    break

        # 12. Age Reference Date (as on DD.MM.YYYY)
        if "age_reference_date" not in extracted_keys:
            age_ref_found = False
            for p in pages:
                text = p["text"]
                for pat in cls.AGE_REFERENCE_DATE_PATTERNS:
                    m = re.search(pat, text, re.IGNORECASE)
                    if m:
                        ref_val = m.group(1).strip()
                        snippet = text[max(0, m.start() - 20): min(len(text), m.end() + 30)].strip()
                        facts.append(
                            ExtractedFactItem(
                                key="age_reference_date",
                                value=ref_val,
                                evidence_text=snippet,
                                page_number=p["page_number"],
                                confidence=0.92,
                                status="VERIFIED",
                                notes="Crucial date for age determination",
                                extraction_method="PDF_TEXT",
                                document_hash=doc_hash,
                                source_url=official_url,
                            )
                        )
                        age_ref_found = True
                        extracted_keys.add("age_reference_date")
                        break
                if age_ref_found:
                    break

        # 13. Age Limit (and split min/max)
        age_found = "age_limit" in extracted_keys
        if not is_result_or_key and not age_found:
            for p in pages:
                text = p["text"]
                for pat_idx, pat in enumerate(cls.AGE_PATTERNS):
                    m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
                    if m:
                        if pat_idx >= 10 and len(m.groups()) >= 2 and m.group(1) and m.group(2):
                            val_str = " ".join(m.group(0).split())
                        elif len(m.groups()) >= 2 and m.group(1) and m.group(2):
                            as_on = f" as on {m.group(3)}" if len(m.groups()) >= 3 and m.group(3) else ""
                            val_str = f"{m.group(1)} to {m.group(2)} years{as_on}"
                            # Also emit age_min and age_max
                            try:
                                min_age = m.group(1).strip()
                                max_age = m.group(2).strip()
                                facts.append(
                                    ExtractedFactItem(
                                        key="age_min",
                                        value=min_age,
                                        evidence_text=m.group(0),
                                        page_number=p["page_number"],
                                        confidence=0.90,
                                        status="VERIFIED",
                                        notes="Minimum age requirement",
                                        extraction_method="PDF_TEXT",
                                        document_hash=doc_hash,
                                        source_url=official_url,
                                    )
                                )
                                facts.append(
                                    ExtractedFactItem(
                                        key="age_max",
                                        value=max_age,
                                        evidence_text=m.group(0),
                                        page_number=p["page_number"],
                                        confidence=0.90,
                                        status="VERIFIED",
                                        notes="Maximum age requirement",
                                        extraction_method="PDF_TEXT",
                                        document_hash=doc_hash,
                                        source_url=official_url,
                                    )
                                )
                            except Exception:
                                pass
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
                                extraction_method="PDF_TEXT",
                                document_hash=doc_hash,
                                source_url=official_url,
                            )
                        )
                        age_found = True
                        extracted_keys.add("age_limit")
                        break
                if age_found:
                    break

        # 14. Application Fee
        fee_found = False
        if not is_result_or_key:
            for p in pages:
                text = p["text"]
                for pat in cls.FEE_PATTERNS:
                    m = re.search(pat, text, re.IGNORECASE)
                    if m:
                        val_str = " ".join(m.group(1).split()) if (len(m.groups()) >= 1 and m.group(1)) else " ".join(m.group(0).split())
                        if any(bad in val_str.lower() for bad in ["per question", "per answer", "per challenge"]):
                            continue
                        if re.match(r"^\d+\.?$", val_str.strip()):
                            continue
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
                                extraction_method="PDF_TEXT",
                                document_hash=doc_hash,
                                source_url=official_url,
                            )
                        )
                        fee_found = True
                        break
                if fee_found:
                    break

        # 15. Salary / Pay Scale
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
                            extraction_method="PDF_TEXT",
                            document_hash=doc_hash,
                            source_url=official_url,
                        )
                    )
                    salary_found = True
                    break
            if salary_found:
                break

        # 16. Educational Qualification / Eligibility
        qual_found = "eligibility" in extracted_keys
        if not is_result_or_key and not qual_found:
            for p in pages:
                text = p["text"]
                for pat in cls.QUALIFICATION_PATTERNS:
                    m = re.search(pat, text, re.IGNORECASE)
                    if m:
                        val_str = " ".join(m.group(1).split()) if (len(m.groups()) >= 1 and m.group(1)) else " ".join(m.group(0).split())
                        val_str = re.sub(r"^(?:means,?\s*|a\s+pass\s+in\s+(?:the\s+)?)+", "", val_str, flags=re.I).strip()
                        if any(b in val_str.lower() for b in ["order of studies", "order of study", "pattern of study", "in the order of", "degree : institution : class", "higher than the", "emergency commissioned", "short service commissioned", "for age relaxation", "age relaxation"]):
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
                                extraction_method="PDF_TEXT",
                                document_hash=doc_hash,
                                source_url=official_url,
                            )
                        )
                        qual_found = True
                        break
                if qual_found:
                    break

        return facts
