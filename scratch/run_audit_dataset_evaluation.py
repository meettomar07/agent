import json
import sqlite3
from pathlib import Path
from collections import defaultdict

from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.html_extractor import HtmlDocumentExtractor
from testkart_intelligence.extraction.fact_extractor import FactExtractor
from testkart_intelligence.classification.classifier import NoticeClassifier, NoticeCategory

def is_date_match(pred: str, gt: str) -> bool:
    if not pred or not gt: return False
    p_clean = pred.lower().replace("-", "/").replace(".", "/").strip()
    g_clean = gt.lower().replace("-", "/").replace(".", "/").strip()
    if p_clean == g_clean: return True
    if g_clean in p_clean or p_clean in g_clean: return True
    return False

def is_val_match(pred: str, gt: str, field: str) -> bool:
    if not pred or not gt: return False
    if field in ("application_start_date", "application_end_date", "exam_date"):
        return is_date_match(pred, gt)
    p_clean = pred.lower().replace(",", "").strip()
    g_clean = gt.lower().replace(",", "").strip()
    if p_clean == g_clean: return True
    if field == "total_vacancies":
        return p_clean.split()[0] == g_clean.split()[0]
    if field in ("eligibility", "age_limit"):
        p_words = set(p_clean.split())
        g_words = set(g_clean.split())
        if len(g_words) > 0 and len(p_words & g_words) / len(g_words) >= 0.35:
            return True
    return False

def run_audit_evaluation():
    manifest = json.loads(Path("INDEPENDENT_ACCURACY_AUDIT_MANIFEST.json").read_text(encoding="utf-8"))
    ground_truth = json.loads(Path("INDEPENDENT_ACCURACY_AUDIT_GROUND_TRUTH.json").read_text(encoding="utf-8"))

    pdf_ext = PdfDocumentExtractor()
    html_ext = HtmlDocumentExtractor()

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE canonical_notices (id TEXT PRIMARY KEY, source_id TEXT, title TEXT, notice_number TEXT, classification TEXT, first_discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    conn.commit()

    cat_tp = defaultdict(int)
    cat_fp = defaultdict(int)
    cat_fn = defaultdict(int)
    confusion = defaultdict(lambda: defaultdict(int))
    all_categories = set()

    link_tp = 0
    link_fp = 0
    link_fn = 0
    link_tn = 0
    linking_details = []

    field_tp = defaultdict(int)
    field_fp = defaultdict(int)
    field_fn = defaultdict(int)
    field_tn = defaultdict(int)
    extraction_details = []

    # Pre-register known parents for corrigenda
    parent_seeds = [
        ("parent_ssc_je", "src_ssc", "Junior Engineer (Civil, Mechanical & Electrical) Examination, 2026", "HQ-EC033/7/2025-EC", "RECRUITMENT_NOTIFICATION"),
        ("parent_upsc_app", "src_upsc", "Advertisement No. 01/2026 for 140 Posts of Assistant Public Prosecutor", "Advt. No. 01/2026", "RECRUITMENT_NOTIFICATION"),
        ("parent_uppsc_comb", "src_uppsc", "Combined State / Upper Subordinate Services Examination 2026", "A-1/E-1/2026", "RECRUITMENT_NOTIFICATION"),
    ]
    for p in parent_seeds:
        conn.execute("INSERT OR REPLACE INTO canonical_notices (id, source_id, title, notice_number, classification) VALUES (?, ?, ?, ?, ?)", p)
    conn.commit()

    for fname, meta in manifest["documents"].items():
        gt = ground_truth.get(fname)
        if not gt: continue

        fpath = Path(meta["local_path"])
        if fname.endswith(".pdf"):
            full_text, pages, _ = pdf_ext.extract(fpath.read_bytes())
        else:
            full_text, pages, _ = html_ext.extract(fpath.read_text(encoding="utf-8"))

        facts_list = FactExtractor.extract_from_pages(
            pages,
            authority_name=meta["authority"],
            notice_title=meta["title"],
            official_url=meta["source_url"]
        )
        facts_dict = {f.key: f.value for f in facts_list}

        snippet = " ".join(p.get("text", "") for p in pages[:2])
        pred_cat = NoticeClassifier.classify(
            title=meta["title"],
            content_snippet=snippet,
            facts=facts_dict,
            url=meta["source_url"],
            authority_name=meta["authority"]
        )

        gt_cat_str = gt["notice_type"]
        all_categories.add(gt_cat_str)
        all_categories.add(pred_cat.value)
        confusion[gt_cat_str][pred_cat.value] += 1

        if pred_cat.value == gt_cat_str:
            cat_tp[gt_cat_str] += 1
        else:
            cat_fn[gt_cat_str] += 1
            cat_fp[pred_cat.value] += 1

        notice_num = facts_dict.get("notice_number") or gt.get("official_notice_number")
        notice_id = f"not_{meta['audit_id']}"
        conn.execute(
            "INSERT OR REPLACE INTO canonical_notices (id, source_id, title, notice_number, classification) VALUES (?, ?, ?, ?, ?)",
            (notice_id, meta["source_id"], meta["title"], notice_num, pred_cat.value)
        )
        conn.commit()

        parent_id, rel_type, rel_conf, notes = NoticeClassifier.link_to_parent_notice(
            notice_id=notice_id,
            source_id=meta["source_id"],
            title=meta["title"],
            notice_number=notice_num,
            category=pred_cat,
            conn=conn
        )

        gt_is_child = gt["is_child_notice"]
        if gt_is_child:
            if parent_id is not None:
                link_tp += 1
                linking_details.append(f"{fname}: TP linked to {parent_id}")
            else:
                link_fn += 1
                linking_details.append(f"{fname}: FN failed to link")
        else:
            if parent_id is not None:
                link_fp += 1
                linking_details.append(f"{fname}: FP falsely linked to {parent_id}")
            else:
                link_tn += 1

        for field_name, f_gt in gt["fields"].items():
            gt_status = f_gt["status"]
            gt_val = f_gt["value"]
            pred_val = facts_dict.get(field_name)

            if gt_status == "PRESENT":
                if pred_val and is_val_match(pred_val, gt_val, field_name):
                    field_tp[field_name] += 1
                elif pred_val:
                    field_fp[field_name] += 1
                    field_fn[field_name] += 1
                    extraction_details.append(f"{fname} [{field_name}]: MISMATCH (pred='{pred_val}', gt='{gt_val}')")
                else:
                    field_fn[field_name] += 1
                    extraction_details.append(f"{fname} [{field_name}]: MISSED (gt='{gt_val}')")
            elif gt_status in ("ABSENT", "NOT_APPLICABLE"):
                if pred_val:
                    field_fp[field_name] += 1
                    extraction_details.append(f"{fname} [{field_name}]: FP (pred='{pred_val}', gt={gt_status})")
                else:
                    field_tn[field_name] += 1

    total_docs = len(manifest["documents"])
    total_cat_tp = sum(cat_tp.values())
    cat_accuracy = total_cat_tp / total_docs

    print("=" * 60)
    print(f"AUDIT DATASET RE-EVALUATION ({total_docs} documents)")
    print("=" * 60)
    print(f"Overall Classification Accuracy: {cat_accuracy:.2%} ({total_cat_tp}/{total_docs})")
    print("\nConfusion Matrix:")
    for actual in sorted(all_categories):
        preds = confusion[actual]
        print(f"  Actual: {actual}")
        for p, cnt in sorted(preds.items()):
            print(f"    -> Predicted: {p}: {cnt}")

    link_p = link_tp / (link_tp + link_fp) if (link_tp + link_fp) else 0.0
    link_r = link_tp / (link_tp + link_fn) if (link_tp + link_fn) else 0.0
    link_f1 = 2 * link_p * link_r / (link_p + link_r) if (link_p + link_r) else 0.0
    print(f"\nParent Linking: TP={link_tp}, FP={link_fp}, FN={link_fn}, TN={link_tn} | Prec={link_p:.2%}, Rec={link_r:.2%}, F1={link_f1:.2%}")
    for d in linking_details:
        print(f"  {d}")

    print("\nField Extraction Performance:")
    print(f"{'Field':<24} | {'TP':<4} | {'FP':<4} | {'FN':<4} | {'TN':<4} | {'Precision':<9} | {'Recall':<9} | {'F1':<9}")
    print("-" * 80)
    for f in ["total_vacancies", "eligibility", "age_limit", "application_start_date", "application_end_date", "exam_date"]:
        tp = field_tp[f]
        fp = field_fp[f]
        fn = field_fn[f]
        tn = field_tn[f]
        p = tp / (tp + fp) if (tp + fp) else 0.0
        r = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) else 0.0
        print(f"{f:<24} | {tp:<4} | {fp:<4} | {fn:<4} | {tn:<4} | {p:<9.2%} | {r:<9.2%} | {f1:<9.2%}")

    print("\nExtraction Details / Remaining Misses:")
    for ed in extraction_details:
        print(f"  {ed}")

if __name__ == "__main__":
    run_audit_evaluation()
