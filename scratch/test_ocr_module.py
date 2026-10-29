import asyncio
import re
import pymupdf
import winocr

def compute_ocr_confidence(text: str, lines: list) -> float:
    if not text or len(text.strip()) < 10:
        return 0.0
    
    cleaned = text.strip()
    total_chars = len(cleaned)
    if total_chars == 0:
        return 0.0
        
    # Printable alphanumeric + standard punctuation
    valid_chars = sum(1 for c in cleaned if c.isalnum() or c in " .,:;()/-–'\"\n")
    char_validity = valid_chars / total_chars
    
    words = [w for w in re.split(r"\s+", cleaned) if w]
    if not words:
        return 0.0
        
    # Words with at least one letter and length >= 2
    word_has_letter = sum(1 for w in words if re.search(r"[a-zA-Z]", w))
    word_validity = word_has_letter / len(words)
    
    # Common official terminology bonus
    COMMON_TERMS = {"commission", "public", "service", "notice", "recruitment", "application", "examination",
                    "post", "posts", "dated", "candidate", "candidates", "government", "advertisement",
                    "advt", "date", "selection", "delhi", "national", "testing", "agency"}
    matched_terms = sum(1 for w in words if w.lower().strip(".,:;()-") in COMMON_TERMS)
    term_bonus = min(0.2, (matched_terms / max(1, len(words))) * 2.0)
    
    raw_score = (char_validity * 0.5) + (word_validity * 0.3) + term_bonus
    return round(min(1.0, max(0.0, raw_score)), 3)

def test_on_notice(pdf_path: str):
    doc = pymupdf.open(pdf_path)
    print(f"\n--- Testing {pdf_path} (Pages: {len(doc)}) ---")
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=150, alpha=True)
        async def run_ocr():
            op = winocr.recognize_bytes(pix.samples, pix.width, pix.height, "en")
            res = await winocr.to_coroutine(op)
            return winocr.picklify(res)
        res = asyncio.run(run_ocr())
        text = res.get("text", "")
        lines = res.get("lines", [])
        conf = compute_ocr_confidence(text, lines)
        print(f"Page {i+1}: text length={len(text)}, lines={len(lines)}, confidence={conf}")
        print(f"Preview:\n{text[:250]}...")
        if i >= 1:  # check first 2 pages max
            break
    doc.close()

if __name__ == "__main__":
    test_on_notice("data/validation_notices/notice_07_upsc_cancellation_advt_13_2025.pdf")
    test_on_notice("data/validation_notices/notice_08_upsc_app_delhi_clarification.pdf")
    test_on_notice("data/development_notices/dev_03_nta_exam_calendar_march_2027.pdf")
