import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

def probe(url, name):
    try:
        r = httpx.get(url, timeout=8.0, verify=False, follow_redirects=True, headers=headers)
        soup = BeautifulSoup(r.text, 'html.parser')
        links = []
        for a in soup.find_all('a', href=True):
            text = a.get_text(strip=True)
            href = urljoin(str(r.url), a['href'])
            if any(k in text.lower() or k in href.lower() for k in ['advt', 'recruit', 'notif', 'announc', 'circular', 'job']):
                links.append((text, href))
        print(f"\n=== {name} ({len(links)} relevant links) ===")
        for t, h in links[:10]:
            print(f"  [{t[:40]}] -> {h}")
    except Exception as e:
        print(f"\n=== {name} ERROR: {e} ===")

probe('https://mpsc.gov.in', 'MPSC')
probe('https://psc.ap.gov.in', 'APPSC')
probe('https://www.opsc.gov.in/Public/OPSC/Default.aspx', 'OPSC')
probe('https://ppsc.gov.in', 'PPSC')
probe('https://rac.gov.in', 'DRDO_RAC')
