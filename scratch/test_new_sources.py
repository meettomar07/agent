import httpx
from testkart_intelligence.discovery.parser import ListingParser

targets = {
    'MPSC': 'https://mpsc.gov.in',
    'APPSC': 'https://psc.ap.gov.in',
    'OPSC': 'https://www.opsc.gov.in',
    'PPSC': 'https://ppsc.gov.in',
    'DRDO_RAC': 'https://rac.gov.in',
}

for code, url in targets.items():
    try:
        r = httpx.get(url, timeout=8.0, verify=False, follow_redirects=True, headers={'User-Agent': 'Mozilla/5.0'})
        candidates = ListingParser.parse_listing(r.text, str(r.url))
        print(f"{code:<10} | Final URL: {r.url} | Raw bytes: {len(r.content)} | Parsed candidates: {len(candidates)}")
        for c in candidates[:3]:
            print(f"   * {c['title'][:65]} -> {c['url'][:65]}")
    except Exception as e:
        print(f"{code:<10} | Error: {e}")
