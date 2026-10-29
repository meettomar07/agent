"""Audit probe for testing real official government portals."""

import json
import time
from datetime import datetime, timezone
import httpx
from bs4 import BeautifulSoup
from testkart_intelligence.security.allowlist import validate_official_url, extract_domain

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

def probe_all():
    with open("testkart_intelligence/registry/sources.json", "r", encoding="utf-8") as f:
        sources = json.load(f)

    results = []
    print(f"Probing {len(sources)} official sources...")

    for s in sources:
        code = s["code"]
        name = s["name"]
        url = s["listing_url"]
        domain = s["official_domain"]

        record = {
            "code": code,
            "name": name,
            "url": url,
            "domain": domain,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status_code": None,
            "final_url": None,
            "is_redirect": False,
            "redirect_hops": 0,
            "content_type": None,
            "content_length": 0,
            "notices_found": 0,
            "is_js_rendered": False,
            "reachable": False,
            "classification": "UNKNOWN",
            "notes": ""
        }

        try:
            # First check domain validation
            validate_official_url(url)
            
            # Perform real HTTP request with timeout
            with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=15.0, follow_redirects=True, verify=False) as client:
                t0 = time.time()
                resp = client.get(url)
                elapsed = time.time() - t0

                record["status_code"] = resp.status_code
                record["final_url"] = str(resp.url)
                record["redirect_hops"] = len(resp.history)
                record["is_redirect"] = len(resp.history) > 0
                record["content_type"] = resp.headers.get("Content-Type", "")
                record["content_length"] = len(resp.content)
                record["reachable"] = resp.status_code < 400

                if resp.status_code == 200:
                    text = resp.text
                    soup = BeautifulSoup(text, "html.parser")
                    
                    # Check if body has minimal content (common in SPAs / JS apps like React/Angular/Vue)
                    scripts = soup.find_all("script")
                    text_len = len(soup.get_text(strip=True))
                    
                    if "<noscript>" in text and text_len < 300:
                        record["is_js_rendered"] = True
                        record["classification"] = "JS_RENDERED"
                        record["notes"] = "Page appears to require JavaScript execution (SPA or client-side rendering)"
                    elif "robot" in text.lower() or "cloudflare" in text.lower() or "access denied" in text.lower() or "waf" in text.lower():
                        record["classification"] = "BLOCKED_WAF"
                        record["notes"] = "Blocked by WAF / Anti-Bot protection"
                    else:
                        # Count links that look like notices/PDFs
                        links = soup.find_all("a", href=True)
                        pdf_links = [l for l in links if ".pdf" in l["href"].lower()]
                        record["notices_found"] = len(pdf_links)
                        if len(pdf_links) > 0:
                            record["classification"] = "VERIFIED_ACTIVE"
                            record["notes"] = f"Found {len(pdf_links)} direct PDF notice links"
                        else:
                            record["classification"] = "VERIFIED_EMPTY_OR_HTML"
                            record["notes"] = f"Reachable ({len(links)} total links), but 0 direct PDF links in static HTML"
                else:
                    record["classification"] = "HTTP_ERROR"
                    record["notes"] = f"HTTP {resp.status_code}"

        except Exception as exc:
            record["reachable"] = False
            record["classification"] = "INACCESSIBLE"
            record["notes"] = f"Connection error: {type(exc).__name__}: {str(exc)[:100]}"

        print(f"[{record['code']}] Status: {record['status_code']} | Classification: {record['classification']} | Notes: {record['notes']}")
        results.append(record)

    with open("data/source_probe_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\nSaved probe results to data/source_probe_results.json")

if __name__ == "__main__":
    probe_all()
