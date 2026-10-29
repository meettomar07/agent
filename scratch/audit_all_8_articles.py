import sqlite3
import csv
import re
from pathlib import Path

conn = sqlite3.connect("data/testkart.db")
c = conn.cursor()

articles = c.execute("""
    SELECT ba.id, ba.canonical_notice_id, ba.template_type, ba.status, ba.title,
           cn.authority_name, cn.classification, cn.normalized_url,
           av.id as version_id, av.version_number, av.content_markdown
    FROM blog_articles ba
    JOIN canonical_notices cn ON ba.canonical_notice_id = cn.id
    JOIN article_versions av ON ba.current_version_id = av.id
    ORDER BY ba.created_at ASC
""").fetchall()

print(f"Total articles in database: {len(articles)}")

audit_records = []

for a in articles:
    art_id, cn_id, template, status, title, auth, cls, url, v_id, v_num, md = a
    print(f"[{art_id}] v{v_num} | {cls} | {status} | {title[:60]}")
    
    # Fetch extracted facts for this notice
    facts = c.execute("""
        SELECT ef.fact_key, ef.fact_value, ef.verified_status, ef.evidence_text, ef.page_number
        FROM extracted_facts ef
        JOIN notice_versions nv ON ef.notice_version_id = nv.id
        WHERE nv.notice_id = ?
    """, (cn_id,)).fetchall()
    
    for f in facts:
        f_key, f_val, f_status, f_ev, f_page = f
        audit_records.append({
            "article_id": art_id,
            "version_id": v_id,
            "notice_id": cn_id,
            "authority": auth,
            "classification": cls,
            "template_applied": template,
            "field_name": f_key,
            "claimed_value": f_val,
            "verified_status": f_status,
            "page_number": f_page if f_page else "N/A",
            "evidence_quote": f_ev[:100].replace("\n", " ") if f_ev else "N/A",
            "official_source_url": url,
            "article_status": status,
        })

# Write updated PILOT_ARTICLE_FACT_AUDIT.csv
out_path = Path("PILOT_ARTICLE_FACT_AUDIT.csv")
with open(out_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(audit_records[0].keys()))
    writer.writeheader()
    writer.writerows(audit_records)

print(f"\nWritten {len(audit_records)} fact audit entries to {out_path}")
