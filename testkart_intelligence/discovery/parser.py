"""HTML listing page parser for official government portals."""

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urldefrag, urlparse
from bs4 import BeautifulSoup

from testkart_intelligence.security.allowlist import is_official_domain, validate_official_url


# Non-notice navigation keywords to ignore
NAVIGATION_IGNORE_KEYWORDS = {
    "home",
    "about us",
    "contact us",
    "sitemap",
    "feedback",
    "rti",
    "faq",
    "faqs",
    "tenders",
    "privacy policy",
    "terms & conditions",
    "skip to main content",
    "screen reader",
    "disclaimer",
    "copyright",
    "accessibility",
    "directory",
    "historical perspective",
    "constitutional provisions",
    "the commission",
    "functions",
    "secretariat",
    "divisions",
    "citizen's charter",
    "website policies",
    "web information manager",
    "equal opportunity policy",
    "forms & downloads",
    "government users",
    "central government",
    "state government",
    "helpline",
}

# Generic button / action link texts that should not serve as article titles
GENERIC_LINK_TEXTS = {
    "user instructions",
    "view advertisement",
    "click here",
    "download",
    "details",
    "view",
    "apply",
    "user help",
    "read more",
    "notice",
    "english",
    "hindi",
    "pdf",
}

# Regex for common Indian government notice/advertisement numbers
ADVT_PATTERNS = [
    r"(?:Advt\.?\s*(?:No\.?)?|Notification\s*(?:No\.?)?|Notice\s*(?:No\.?)?|Employment\s*Notice\s*(?:No\.?)?)\s*[:\-]?\s*([A-Za-z0-9\/\.\-_]+(?:\/\d{4})?)",
    r"(?:No\.?\s*)([A-Z0-9\/\.\-_]+(?:\/\d{4}))",
    r"\b([A-Z0-9]{1,4}(?:[\/\-][A-Za-z0-9]+)+\/\d{4})\b",
]

# Regex for date detection in listings (DD/MM/YYYY, DD-MM-YYYY, DD Month YYYY)
DATE_PATTERNS = [
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{4})\b",
    r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\b",
]


def normalize_notice_url(raw_url: str, base_url: str) -> str:
    """Resolve relative URLs and normalize by removing fragments and redundant tracking queries."""
    joined = urljoin(base_url, raw_url.strip())
    defragged, _ = urldefrag(joined)
    parsed = urlparse(defragged)
    # Reconstruct normalized URL
    normalized = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path}"
    if parsed.query:
        # Strip common tracking query params
        params = [p for p in parsed.query.split("&") if not p.startswith(("utm_", "fbclid", "ref="))]
        if params:
            normalized += "?" + "&".join(sorted(params))
    return normalized


def extract_advt_number(text: str) -> Optional[str]:
    """Attempt to extract official notice or advertisement number from title/context."""
    for pattern in ADVT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip(" .:-")
            # Ensure candidate is not merely a date like 25/11/2024
            if re.match(r"^\d{1,2}[/-]\d{1,2}[/-]\d{4}$", candidate):
                continue
            if len(candidate) >= 3:
                return candidate
    return None


def extract_notice_date(text: str) -> Optional[str]:
    """Attempt to extract published/notification date from listing row text."""
    for pattern in DATE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


class ListingParser:
    """Parses official government listing HTML pages to discover candidate notices."""

    @staticmethod
    def parse_json_listing(data: Any, base_url: str) -> List[Dict[str, Any]]:
        """Extract candidate notices from JSON response payload (e.g. SSC official API)."""
        candidates: List[Dict[str, Any]] = []
        seen_urls = set()

        items = []
        if isinstance(data, dict):
            # SSC format: {"statusCode": "200", "data": [...]}
            if isinstance(data.get("data"), list):
                items = data["data"]
            elif isinstance(data.get("items"), list):
                items = data["items"]
            elif isinstance(data.get("records"), list):
                items = data["records"]
        elif isinstance(data, list):
            items = data

        for item in items:
            if not isinstance(item, dict):
                continue

            headline = (
                item.get("headline")
                or item.get("title")
                or item.get("name")
                or item.get("subject")
                or ""
            ).strip()

            if not headline or len(headline) < 5:
                continue

            pdf_url = ""
            # Check attachments
            attachments = item.get("attachments") or []
            if isinstance(attachments, list) and attachments:
                first_att = attachments[0]
                if isinstance(first_att, dict):
                    fn = first_att.get("fileName")
                    if fn:
                        # Construct official SSC attachment URL
                        if "ssc.gov.in" in base_url:
                            pdf_url = f"https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/{fn}"
                        else:
                            pdf_url = urljoin(base_url, fn)

            if not pdf_url:
                raw_target = item.get("redirectUrl") or item.get("url") or ""
                if raw_target:
                    pdf_url = urljoin(base_url, raw_target)

            if not pdf_url:
                continue

            try:
                norm_url = normalize_notice_url(pdf_url, base_url)
                if not is_official_domain(norm_url):
                    continue
            except Exception:
                continue

            if norm_url in seen_urls:
                continue

            advt_no = extract_advt_number(headline)
            pub_date = (
                extract_notice_date(headline)
                or item.get("createdAt")
                or item.get("startDate")
            )
            doc_type = "PDF" if norm_url.lower().endswith(".pdf") or "pdf" in norm_url.lower() else "HTML"

            candidates.append({
                "title": headline[:250].strip(),
                "url": norm_url,
                "notice_number": advt_no,
                "published_date": str(pub_date)[:30] if pub_date else None,
                "document_type": doc_type,
            })
            seen_urls.add(norm_url)

        return candidates

    @staticmethod
    def parse_listing(html_content: str, base_url: str) -> List[Dict[str, Any]]:
        """Extract candidate notices from HTML content or JSON payloads.

        Returns a list of dicts:
        - title: str
        - url: str (normalized official URL)
        - notice_number: Optional[str]
        - published_date: Optional[str]
        - document_type: str ('PDF' | 'HTML')
        """
        stripped = html_content.strip()
        if (stripped.startswith("{") and stripped.endswith("}")) or (stripped.startswith("[") and stripped.endswith("]")):
            try:
                import json
                data = json.loads(stripped)
                return ListingParser.parse_json_listing(data, base_url)
            except Exception:
                pass

        soup = BeautifulSoup(html_content, "html.parser")
        candidates: List[Dict[str, Any]] = []
        seen_urls = set()

        # Strategy 1: Table-based listings (very common in Indian government portals)
        for row in soup.find_all("tr"):
            links = [
                a for a in row.find_all("a", href=True)
                if not a["href"].strip().startswith(("#", "javascript:", "mailto:", "tel:"))
            ]
            if not links:
                continue

            # Prioritize advertisement, notification, or PDF links over auxiliary links (e.g. Help, Apply)
            best_link = links[0]
            for lk in links:
                t_low = lk.get_text().lower()
                h_low = lk["href"].lower()
                if any(k in t_low or k in h_low for k in ["view_advertisement", "advertisement", "notification", ".pdf"]):
                    best_link = lk
                    break

            href = best_link.get("href", "").strip()
            try:
                norm_url = normalize_notice_url(href, base_url)
                if not is_official_domain(norm_url):
                    continue
            except Exception:
                continue

            if norm_url in seen_urls:
                continue

            # Extract row context
            row_text = " ".join(row.get_text(separator=" ").split())
            link_text = " ".join(best_link.get_text(separator=" ").split())

            # Determine title: if link_text is generic (e.g. "View Advertisement", "User Instructions"), derive from row cells
            title = link_text
            if not link_text or link_text.lower() in GENERIC_LINK_TEXTS or len(link_text) < 10:
                td_texts = [" ".join(td.get_text().split()) for td in row.find_all(["td", "th"])]
                cell_candidates = [
                    t for t in td_texts
                    if len(t) >= 10
                    and not any(k in t.lower() for k in GENERIC_LINK_TEXTS)
                    and not re.search(r"^\d{1,2}[/-]\d{1,2}[/-]\d{4}", t)
                    and not any(term in t.lower() for term in NAVIGATION_IGNORE_KEYWORDS)
                ]
                if cell_candidates:
                    title = max(cell_candidates, key=len)
                elif len(row_text) >= 10:
                    title = row_text

            if any(term in title.lower() for term in NAVIGATION_IGNORE_KEYWORDS) and len(title) < 25:
                continue

            advt_no = extract_advt_number(row_text) or extract_advt_number(title)
            pub_date = extract_notice_date(row_text)
            doc_type = "PDF" if norm_url.lower().endswith(".pdf") or "pdf" in norm_url.lower() else "HTML"

            candidates.append({
                "title": title[:250].strip(),
                "url": norm_url,
                "notice_number": advt_no,
                "published_date": pub_date,
                "document_type": doc_type,
            })
            seen_urls.add(norm_url)

        # Strategy 2: If no table rows matched (e.g. UPSC Drupal view listings) or mixed layout
        if not candidates:
            # Clean non-content containers (navbars, menus, footers, breadcrumbs, sidebars)
            for tag in soup.find_all(["nav", "header", "footer", "noscript", "style", "script"]):
                tag.decompose()
            for el in soup.find_all(id=lambda i: i and any(k in i.lower() for k in ["menu", "navbar", "nav", "header", "footer", "breadcrumb", "sidebar"])):
                el.decompose()
            for el in soup.find_all(class_=lambda c: c and any(k in " ".join(c).lower() for k in ["menu", "navbar", "nav", "header", "footer", "breadcrumb", "sidebar"])):
                el.decompose()

            for link_tag in soup.find_all("a", href=True):
                href = link_tag.get("href", "").strip()
                if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                    continue

                try:
                    norm_url = normalize_notice_url(href, base_url)
                    if not is_official_domain(norm_url):
                        continue
                except Exception:
                    continue

                if norm_url in seen_urls:
                    continue

                link_text = " ".join(link_tag.get_text(separator=" ").split())
                title_attr = link_tag.get("title", "").strip()
                title = link_text or title_attr

                if not title or len(title) < 8 or "{{" in title:
                    continue

                clean_lower = title.lower()
                if any(term in clean_lower for term in NAVIGATION_IGNORE_KEYWORDS):
                    continue

                advt_no = extract_advt_number(title)
                pub_date = extract_notice_date(title)
                doc_type = "PDF" if norm_url.lower().endswith(".pdf") or "pdf" in norm_url.lower() else "HTML"

                candidates.append({
                    "title": title[:250].strip(),
                    "url": norm_url,
                    "notice_number": advt_no,
                    "published_date": pub_date,
                    "document_type": doc_type,
                })
                seen_urls.add(norm_url)

        return candidates
