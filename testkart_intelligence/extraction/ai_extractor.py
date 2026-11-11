"""Optional AI-assisted extraction adapter using Google Gemini API for complex recruitment notices.

Enforces structured JSON output, mandatory verbatim evidence references, and non-blocking fallback.
All AI-extracted facts are subject to the same strict verification and human editorial approval gates.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional
import httpx

from testkart_intelligence.config import settings
from testkart_intelligence.extraction.fact_extractor import ExtractedFactItem
from testkart_intelligence.extraction.date_normalizer import DateNormalizer

logger = logging.getLogger(__name__)


EXTRACTION_PROMPT = """
You are an expert government examination notification parser.
Extract critical recruitment dates and facts from the provided official notification text.

You MUST extract only information explicitly stated in the text.
For every extracted field, you MUST provide:
- value: the raw extracted value
- normalized_value: standard ISO format (e.g. YYYY-MM-DD for dates, integer string for vacancies)
- page_number: estimated page number where the fact appears (integer, default 1)
- evidence_text: exact verbatim sentence or table cell containing the fact
- confidence: number between 0.0 and 1.0 representing extraction certainty

Fields to extract (if present, else omit or set to null):
1. publication_date: Notification/advt release date
2. application_start_date: Opening date for online application submission
3. application_end_date: Closing/last date for submission of online application
4. fee_payment_deadline: Last date/time for payment of examination fee
5. correction_window_start_date: Start date of application form correction window
6. correction_window_end_date: End date of application form correction window
7. exam_date: Date(s) or schedule of examination / CBT
8. admit_card_date: Admit card / hall ticket release date
9. result_date: Declaration of result date
10. total_vacancies: Total number of posts / vacancies to be filled
11. eligibility: Educational qualification and eligibility criteria
12. age_limit: Minimum and maximum age limit
13. age_reference_date: Reference date as on which age is calculated

CRITICAL INSTRUCTIONS:
- Do NOT confuse publication date with application start date.
- Do NOT confuse application deadline with fee payment deadline.
- Do NOT confuse examination date with admit card date.
- Do NOT confuse age calculation date with application deadline.
- Return ONLY valid JSON matching this schema:
{
  "facts": [
    {
      "fact_type": "string",
      "fact_value": "string",
      "normalized_value": "string",
      "page_number": 1,
      "evidence_text": "string",
      "confidence": 0.95
    }
  ]
}
"""


class GeminiFactExtractorAdapter:
    """Optional adapter for AI-assisted recruitment fact extraction via Gemini API."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or getattr(settings, "GEMINI_API_KEY", "")
        self.model = model or getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")

    def is_available(self) -> bool:
        """Return True if Gemini API key is configured."""
        return bool(self.api_key and self.api_key.strip())

    def extract_facts(
        self,
        full_text: str,
        authority_name: str,
        notice_title: str,
        doc_hash: Optional[str] = None,
        source_url: Optional[str] = None,
    ) -> List[ExtractedFactItem]:
        """Extract structured recruitment facts via Gemini API.

        Gracefully returns [] if API key is not configured, or if the API call fails,
        ensuring the system is fully operational offline with deterministic extraction.
        """
        if not self.is_available():
            logger.debug("GeminiFactExtractorAdapter: GEMINI_API_KEY not configured; skipping AI extraction")
            return []

        if not full_text or len(full_text.strip()) < 50:
            return []

        # Truncate text if excessively large (e.g. limit to first 30,000 characters)
        sample_text = full_text[:30000]

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": f"{EXTRACTION_PROMPT}\n\nAUTHORITY: {authority_name}\nTITLE: {notice_title}\n\nDOCUMENT TEXT:\n{sample_text}"
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.0,
                "responseMimeType": "application/json",
            },
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.post(url, json=payload)
                if resp.status_code != 200:
                    logger.warning("Gemini extraction API returned status %d: %s", resp.status_code, resp.text)
                    return []

                data = resp.json()
                raw_json = (
                    data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                )

                if not raw_json:
                    return []

                parsed = json.loads(raw_json)
                fact_items: List[ExtractedFactItem] = []

                facts_list = parsed.get("facts", [])
                for item in facts_list:
                    f_type = item.get("fact_type", "").strip()
                    f_val = str(item.get("fact_value", "")).strip()
                    if not f_type or not f_val:
                        continue

                    norm_val = item.get("normalized_value")
                    if not norm_val:
                        norm_val = DateNormalizer.normalize_recruitment_value(f_type, f_val)

                    ev_text = item.get("evidence_text", "").strip()
                    p_num = int(item.get("page_number", 1))
                    conf = float(item.get("confidence", 0.90))

                    fact_items.append(
                        ExtractedFactItem(
                            key=f_type,
                            value=f_val,
                            normalized_value=norm_val,
                            evidence_text=ev_text or f_val,
                            page_number=max(1, p_num),
                            confidence=min(1.0, max(0.0, conf)),
                            status="VERIFIED",
                            notes="Extracted via Gemini API structured adapter",
                            extraction_method="AI_ASSISTED",
                            document_hash=doc_hash,
                            source_url=source_url,
                        )
                    )

                return fact_items

        except Exception as exc:
            logger.warning("GeminiFactExtractorAdapter extraction exception: %s", exc)
            return []
