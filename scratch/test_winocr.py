import winocr
import pymupdf
from pathlib import Path

def test_ocr(pdf_path: str):
    doc = pymupdf.open(pdf_path)
    print(f"Total pages: {len(doc)}")
    for i in range(min(len(doc), 2)):
        page = doc[i]
        pix = page.get_pixmap(dpi=150)
        png_bytes = pix.tobytes("png")
        print(f"Page {i+1} bytes: {len(png_bytes)}")
        
        try:
            res = winocr.recognize_bytes(png_bytes, "en-US")
            print("recognize_bytes result keys:", res.keys() if isinstance(res, dict) else type(res))
            if isinstance(res, dict):
                print("Text preview:\n", res.get("text", "")[:400])
                print("Lines count:", len(res.get("lines", [])))
            else:
                print("Result preview:\n", str(res)[:400])
            return res
        except Exception as e:
            print("recognize_bytes error:", e)
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_ocr("data/validation_notices/notice_07_upsc_cancellation_advt_13_2025.pdf")
