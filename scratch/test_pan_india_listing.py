from testkart_intelligence.discovery.fetcher import SafeFetcher
from testkart_intelligence.discovery.parser import ListingParser

fetcher = SafeFetcher()

sources_to_test = [
    ('WBPSC', 'https://psc.wb.gov.in/'),
    ('HPPSC', 'https://hppsc.hp.gov.in/CommonControls/ViewContinuousLinkPage?qs=mhlKjiXMMItGo46f60VBXX8%2B1SQ83OzVLj9MfDScpvboDSdMygkK4iLV47Bu%2FJzMpJLanI%2BihrK9p8W6JsSQUgHTy39NyiuO%2BFtbEmiPQyc%3D'),
    ('SPSC', 'https://spsc.sikkim.gov.in/Advertisement.html'),
    ('TPSC', 'https://tpsc.tripura.gov.in/direct-recruitment'),
    ('NPSC', 'https://npsc.nagaland.gov.in/advertisement'),
    ('APPSC_AR', 'https://appsc.gov.in/Index/sub_page/doc2195/Advertisements'),
    ('MPSC_MZ', 'https://mpsc.mizoram.gov.in/page/advertisement-2026-2027'),
    ('GOAPSC', 'https://gpsc.goa.gov.in/advertisements/'),
]

for code, url in sources_to_test:
    try:
        content, ctype, final_url, el = fetcher.fetch(url)
        html = content.decode('utf-8', errors='ignore')
        candidates = ListingParser.parse_listing(html, url)
        print(f"[{code}] Found {len(candidates)} candidate notices:")
        for c in candidates[:3]:
            print(f"    - {c['title'][:70]} ({c['document_type']}) -> {c['url'][:70]}")
    except Exception as e:
        print(f"[{code}] FAILED: {type(e).__name__} - {e}")
