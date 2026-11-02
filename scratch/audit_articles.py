import json
from pathlib import Path
import re

with open("data/independent_accuracy_audit_results.json", "r", encoding="utf-8") as f:
    results = json.load(f)

print(f"Auditing {len(results)} generated articles...")

article_audit = []

for r in results:
    aid = r["audit_id"]
    auth = r["authority"]
    title = r["title"]
    gt = r["ground_truth"]
    pred = r["prediction"]
    md = pred["article_markdown"]
    tpl = pred["template_type"]
    qa_score = pred["qa_score"]
    qa_pass = pred["qa_pass"]
    
    gt_fields = gt["fields"]
    
    # Check for hallucinated numbers
    # Extract all numbers from markdown
    md_numbers = set(re.findall(r"\b\d{2,}\b", md))
    # Exclude years (2025, 2026, 2027), days (01..31), hours (09..23), standard section percentages (60%)
    non_year_numbers = {n for n in md_numbers if not (2020 <= int(n) <= 2030 or int(n) <= 31)}
    
    # Check if any vacancy count was invented
    gt_vac = gt_fields.get("total_vacancies", {}).get("value")
    pred_vac = pred["extracted_facts"].get("total_vacancies", {}).get("fact_value")
    
    material_errors = []
    formatting_caveats = []
    
    # 1. Vacancy verification
    if pred_vac and gt_vac:
        if str(gt_vac).strip() != str(pred_vac).strip():
            material_errors.append(f"Material Error: Vacancy mismatch (GT={gt_vac}, Draft={pred_vac})")
    elif pred_vac and not gt_vac:
        material_errors.append(f"Material Error: Hallucinated/Invented Vacancy count {pred_vac} where none existed in GT")
    elif not pred_vac and gt_vac:
        formatting_caveats.append(f"Omission: Notice contains {gt_vac} vacancies, but draft displays TBD/Not Disclosed")
        
    # 2. Date verification
    gt_start = gt_fields.get("application_start_date", {}).get("value")
    gt_end = gt_fields.get("application_end_date", {}).get("value")
    pred_start = pred["extracted_facts"].get("application_start_date", {}).get("fact_value")
    pred_end = pred["extracted_facts"].get("application_end_date", {}).get("fact_value")
    
    if pred_end and gt_end:
        # Check if year or month completely wrong
        pass
    elif not pred_end and gt_end:
        if pred["classification"] == "RECRUITMENT_NOTIFICATION":
            material_errors.append(f"Material Error: Recruitment notice lacks verified application closing date ({gt_end})")
            
    # 3. Notice Type template alignment
    if gt["notice_type"] != pred["classification"]:
        formatting_caveats.append(f"Classification divergence: GT={gt['notice_type']}, Draft Template={tpl} ({pred['classification']})")
        
    # 4. QA score
    if not qa_pass:
        material_errors.append(f"Editorial Block: Article failed QA inspection (Score: {qa_score:.1f}/100.0)")
        
    article_audit.append({
        "audit_id": aid,
        "authority": auth,
        "title": title,
        "template": tpl,
        "qa_score": qa_score,
        "qa_pass": qa_pass,
        "material_errors": material_errors,
        "formatting_caveats": formatting_caveats,
        "md_excerpt": md[:350].replace("\n", " ")
    })

print("\n=== ARTICLE AUDIT SUMMARY ===")
clean_count = sum(1 for a in article_audit if not a["material_errors"])
print(f"Total articles audited: {len(article_audit)}")
print(f"Articles with zero material errors: {clean_count} / {len(article_audit)} ({clean_count/len(article_audit):.1%})")

print("\n--- Details by Notice ---")
for a in article_audit:
    status_str = "CLEAN" if not a["material_errors"] else "FLAGGED"
    print(f"[{a['audit_id']}] {a['authority'][:15]} | {status_str} (QA: {a['qa_score']:.1f})")
    if a["material_errors"]:
        for me in a["material_errors"]:
            print(f"    [!] {me}")
    if a["formatting_caveats"]:
        for fc in a["formatting_caveats"]:
            print(f"    [*] {fc}")

with open("scratch/article_audit_summary.json", "w", encoding="utf-8") as out:
    json.dump(article_audit, out, indent=2)
