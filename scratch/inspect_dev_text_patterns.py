from pathlib import Path
import pymupdf
import re

dev_dir = Path("data/development_notices")
dev_files = [
    "dev_08_tnpsc_ctse_diploma_recruitment.pdf",
    "dev_09_tnpsc_cts_non_interview_posts.pdf",
    "dev_10_upsc_homoeopathic_physician_notice.html",
    "dev_11_upsc_vice_principal_gnctd_notice.html",
    "dev_13_tnpsc_special_competitive_exam.pdf",
    "dev_05_nta_nittt_exam_schedule.pdf",
]

for df in dev_files:
    p = dev_dir / df
    ext = p.suffix.lower()
    print("=" * 70)
    print(f"FILE: {df}")
    if ext == ".pdf":
        doc = pymupdf.open(p)
        print(f"Pages: {len(doc)}")
        # Look for dates, vacancies, fee, age, qualification in first 5 pages
        for pno in range(min(len(doc), 5)):
            txt = doc[pno].get_text()
            for kw in ["important dates", "date of notification", "last date", "submission of online", "vacancies", "examination fee", "age limit", "qualification"]:
                matches = [line.strip() for line in txt.split("\n") if kw in line.lower()]
                if matches:
                    print(f"  [p.{pno+1}] Keyword '{kw}':")
                    for m in matches[:3]:
                        print("   ", m.encode("ascii", errors="replace").decode("ascii"))
        doc.close()
    else:
        txt = p.read_text(encoding="utf-8", errors="replace")
        for kw in ["vacancy", "vacancies", "date", "fee", "age", "qualification"]:
            matches = [line.strip() for line in txt.split("\n") if kw in line.lower() and len(line.strip()) < 120]
            if matches:
                print(f"  Keyword '{kw}':")
                for m in matches[:3]:
                    print("   ", m.encode("ascii", errors="replace").decode("ascii"))
