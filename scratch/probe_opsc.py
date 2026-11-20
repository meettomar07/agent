import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin

headers = {'User-Agent': 'Mozilla/5.0'}

def check_opsc():
    url = 'https://www.opsc.gov.in/Public/OPSC/Default.aspx'
    r = httpx.get(url, timeout=8.0, verify=False, follow_redirects=True, headers=headers)
    soup = BeautifulSoup(r.text, 'html.parser')
    print("OPSC marquee/whatsnew links:")
    for a in soup.find_all('a', href=True):
        t = a.get_text(strip=True)
        h = urljoin(str(r.url), a['href'])
        if len(t) > 10:
            print(" -", t[:60], "->", h[:60])

check_opsc()
