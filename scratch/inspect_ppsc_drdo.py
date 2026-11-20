import httpx
from testkart_intelligence.discovery.parser import ListingParser
from testkart_intelligence.classification.classifier import NoticeClassifier

for name, url in [('DRDO_RAC', 'https://rac.gov.in'), ('PPSC', 'https://ppsc.gov.in')]:
    r = httpx.get(url, timeout=10.0, verify=False, follow_redirects=True, headers={'User-Agent': 'Mozilla/5.0'})
    candidates = ListingParser.parse_listing(r.text, str(r.url))
    print(f"\n=== {name}: {len(candidates)} candidates ===")
    for c in candidates:
        cat = NoticeClassifier.classify(c['title'], c['url'])
        print(f"[{cat.value}] {c['title'][:70]} -> {c['url'][:60]}")
