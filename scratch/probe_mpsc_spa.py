import httpx, re

r = httpx.get('https://mpsc.gov.in', timeout=8.0, verify=False, follow_redirects=True, headers={'User-Agent': 'Mozilla/5.0'})
scripts = re.findall(r'src=["\']([^"\']+\.js)["\']', r.text)
print('Scripts found in MPSC:', scripts)
for s in scripts:
    js_url = f"https://mpsc.gov.in{s}" if s.startswith('/') else s
    js_res = httpx.get(js_url, timeout=8.0, verify=False)
    apis = re.findall(r'https?://[a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)+', js_res.text)
    print(f"APIs in {s[:30]}:", [a for a in apis if 'api' in a or 'mpsc' in a][:5])
