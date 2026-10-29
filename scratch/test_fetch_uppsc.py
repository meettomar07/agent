from testkart_intelligence.discovery.fetcher import SafeFetcher
from bs4 import BeautifulSoup

fetcher = SafeFetcher()
url = "https://uppsc.up.nic.in/CandidatePages/Notifications.aspx"

try:
    content, ctype, status, final_url = fetcher.fetch(url)
    print("Status:", status)
    print("Content len:", len(content))
    soup = BeautifulSoup(content, "html.parser")
    links = soup.find_all("a")
    print(f"Total links: {len(links)}")
    for a in links:
        href = a.get("href", "")
        text = " ".join(a.text.split())
        if "advertisement" in href.lower() or "view" in href.lower() or "notif" in href.lower():
            print("  Link:", text, "->", href)
except Exception as e:
    print("UPPSC fetch error:", e)
