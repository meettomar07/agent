from pathlib import Path
import pymupdf

val_dir = Path("data/validation_notices")
new_notices = [
    "notice_23_nta_cuet_ug_cancellation.pdf",
    "notice_24_nta_deputation_extension.pdf",
    "notice_25_ssc_revised_je_capf_dates.pdf",
    "notice_26_tnpsc_group_2_services.pdf",
    "notice_27_upsc_geo_scientist_time_table.html",
    "notice_28_upsc_cds_ii_written_result.html",
    "notice_29_uppsc_samiksha_adhikari_session.html",
    "notice_30_ssc_chsl_final_result.pdf",
    "notice_31_ssc_steno_marks_writeup.pdf",
    "notice_32_nta_sainik_school_corrigendum.pdf",
    "notice_33_nta_neet_ug_corrigendum.pdf",
]

for name in new_notices:
    p = val_dir / name
    ext = p.suffix.lower()
    print("=" * 70)
    print(f"FILE: {name} ({p.stat().st_size} bytes)")
    if ext == ".pdf":
        doc = pymupdf.open(p)
        print(f"Pages: {len(doc)}")
        for pno in range(min(len(doc), 3)):
            text = doc[pno].get_text()
            print(f"--- Page {pno+1} ---")
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            for line in lines[:10]:
                print(" ", line.encode("ascii", errors="replace").decode("ascii"))
        doc.close()
    else:
        text = p.read_text(encoding="utf-8", errors="replace")
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        print("HTML lines:")
        for line in lines[:12]:
            print(" ", line[:100].encode("ascii", errors="replace").decode("ascii"))
