from testkart_intelligence.discovery.fetcher import SafeFetcher

fetcher = SafeFetcher()
try:
    content, ctype, final_url, status = fetcher.fetch('https://nta.ac.in/Download/Notice/Notice_20250514161031.pdf')
    print("Fetch succeeded! Length:", len(content), "ctype:", ctype, "status:", status)
except Exception as e:
    print("Fetch error:", type(e), e)
