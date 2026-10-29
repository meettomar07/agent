import json
import subprocess
import sys
import time

def run_ocr_subprocess(pdf_path: str):
    t0 = time.time()
    code = f"""
import json, asyncio, pymupdf, winocr
from testkart_intelligence.extraction.ocr import compute_ocr_confidence

doc = pymupdf.open(r'{pdf_path}')
pages = []
for i, page in enumerate(doc):
    pix = page.get_pixmap(dpi=150, alpha=True)
    async def run():
        op = winocr.recognize_bytes(pix.samples, pix.width, pix.height, 'en')
        res = await winocr.to_coroutine(op)
        return winocr.picklify(res)
    res = asyncio.run(run())
    text = res.get('text', '').strip()
    lines = res.get('lines', [])
    conf = compute_ocr_confidence(text, lines)
    pages.append({{
        'page_number': i + 1,
        'text': text,
        'ocr_confidence': conf,
        'is_scanned': True,
        'lines_count': len(lines)
    }})
doc.close()
print(json.dumps(pages))
"""
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    t1 = time.time()
    if res.returncode != 0:
        print("Subprocess error:", res.stderr)
        return None
    pages = json.loads(res.stdout.strip())
    print(f"Subprocess OCR finished in {t1 - t0:.2f}s, pages: {len(pages)}")
    return pages

if __name__ == "__main__":
    pages = run_ocr_subprocess("data/validation_notices/notice_07_upsc_cancellation_advt_13_2025.pdf")
    if pages:
        print("Page 1 preview:", pages[0]["text"][:200])
        print("Confidence:", pages[0]["ocr_confidence"])
