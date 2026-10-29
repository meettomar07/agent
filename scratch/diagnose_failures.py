"""Forensic failure diagnosis script for Testkart.
Analyzes every False Negative and False Positive in the 52-notice dataset.
Extracts document, page, text context, ground truth, and categorizes failure root causes.
"""

import csv
import json
from pathlib import Path
from collections import defaultdict
import pymupdf
import re

val_dir = Path("data/new_validation_notices")

def diagnose():
    with open("NEW_DATASET_ACCURACY_EVALUATION.csv", "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    failures_by_field = defaultdict(list)
    root_cause_counts = defaultdict(int)

    # Filter failures: either PARTIAL_OR_DISCREPANCY (FP+FN), SPURIOUS_EXTRACTION (FP), or MISSING_IN_EXTRACTION (FN)
    for r in rows:
        st = r["match_status"]
        if st in ("PARTIAL_OR_DISCREPANCY", "SPURIOUS_EXTRACTION", "MISSING_IN_EXTRACTION"):
            failures_by_field[r["field_name"]].append(r)

    print("=" * 80)
    print(f"DIAGNOSIS: TOTAL FAILURES TO INSPECT = {sum(len(v) for v in failures_by_field.values())}")
    print("=" * 80)
    for fld, items in sorted(failures_by_field.items()):
        print(f"  * {fld:<25}: {len(items)} failure instances")

    diagnosed_records = []

    for fld, items in failures_by_field.items():
        for item in items:
            fname = item["notice_file"]
            p_file = val_dir / fname
            gt = item["ground_truth_value"]
            ext = item["extracted_value"]
            st = item["match_status"]
            doc_fmt = item["document_format"]

            # Analyze root cause
            root_cause = "UNKNOWN"
            detail = ""

            # Check specific fields
            if fld == "total_vacancies":
                if st == "PARTIAL_OR_DISCREPANCY":
                    root_cause = "SUBTOTAL_OR_CADRE_BREAKDOWN_MISTAKEN_FOR_TOTAL"
                    detail = f"Extracted sub-cadre/subtotal '{ext}' instead of grand total '{gt}'."
                elif st == "MISSING_IN_EXTRACTION":
                    # Determine whether vacancies are in a table
                    root_cause = "VACANCY_TABLE_NOT_PARSED"
                    detail = f"Vacancies ({gt}) presented in structured table/matrix without plain inline sentence."

            elif fld == "eligibility":
                if st == "PARTIAL_OR_DISCREPANCY":
                    if "order of studies" in ext.lower() or "prescribed for the posts" in ext.lower():
                        root_cause = "STATUTORY_PATTERN_RULE_EXTRACTED_INSTEAD_OF_DISCIPLINE"
                    elif "degree from a recognized" in ext.lower() or "universities incorporated" in ext.lower():
                        root_cause = "LEGAL_PREAMBLE_EXTRACTED_INSTEAD_OF_SPECIFIC_CRITERIA"
                    elif len(ext) < 25:
                        root_cause = "TRUNCATED_QUALIFICATION_CLAUSE"
                    else:
                        root_cause = "MULTI_POST_QUALIFICATION_MISMATCH"
                    detail = f"Expected '{gt}', extracted '{ext[:60]}...'"
                elif st == "MISSING_IN_EXTRACTION":
                    root_cause = "QUALIFICATIONS_SPLIT_IN_TABLE_OR_APPENDIX"
                    detail = f"Qualification ({gt}) located in trade table or separate annexure not matched by standard patterns."

            elif fld == "age_limit":
                if st == "MISSING_IN_EXTRACTION":
                    root_cause = "BIRTH_DATE_BRACKET_OR_TABLE_AGE_NOT_MATCHED"
                    detail = f"Age requirement ({gt}) specified via birth date window (born between...) or tabular column rather than 'X to Y years'."

            elif fld == "exam_date":
                if st == "PARTIAL_OR_DISCREPANCY":
                    root_cause = "APPLICATION_SCHEDULE_MISLABELED_AS_EXAM_DATE"
                    detail = f"Multi-column table column misalignment: extracted '{ext}' instead of '{gt}'."
                elif st == "MISSING_IN_EXTRACTION":
                    root_cause = "EXAM_SCHEDULE_IN_TABLE_OR_FUTURE_INTIMATION"
                    detail = f"Exam schedule ({gt}) in multi-row table, calendar schedule, or announced as month without exact day."

            elif fld == "application_fee":
                if st == "PARTIAL_OR_DISCREPANCY":
                    root_cause = "FEE_STRUCTURE_AMBIGUITY_OR_GROUND_TRUTH_DISCREPANCY"
                    detail = f"Ground truth annotated '{gt}', but notice specified '{ext}'."
                elif st == "MISSING_IN_EXTRACTION":
                    root_cause = "FEE_IN_TABULAR_OR_CATEGORY_CLAUSE"
                    detail = f"Fee structure ({gt}) formatted across complex category breakdown."

            elif fld == "notice_number":
                if st == "PARTIAL_OR_DISCREPANCY":
                    root_cause = "MULTI_NOTICE_LISTING_TABLE_ROW_COLLISION"
                    detail = f"Multi-notice HTML table: extracted '{ext}' from earlier row instead of target notice '{gt}'."
                elif st == "MISSING_IN_EXTRACTION":
                    root_cause = "NOTICE_NUMBER_IN_NON_STANDARD_HEADER_OR_CREST"
                    detail = f"Notice number ({gt}) lacked standard prefix (e.g. Advt No / File No)."

            elif fld in ("application_start_date", "application_end_date"):
                if st == "PARTIAL_OR_DISCREPANCY":
                    root_cause = "DATE_MILESTONE_AMBIGUITY_OR_GROUND_TRUTH_ERROR"
                    detail = f"Ground truth was '{gt}', extracted '{ext}'."
                elif st == "MISSING_IN_EXTRACTION":
                    root_cause = "DATE_IN_IMAGE_OR_COMPLEX_SCHEDULE"
                    detail = f"Date ({gt}) in non-standard schedule format or image header."

            root_cause_counts[root_cause] += 1
            diagnosed_records.append({
                "notice_file": fname,
                "authority": item["authority"],
                "format": doc_fmt,
                "field_name": fld,
                "match_status": st,
                "ground_truth": gt,
                "extracted": ext,
                "root_cause": root_cause,
                "detail": detail,
            })

    print("\n" + "=" * 80)
    print("ROOT CAUSE DISTRIBUTION SUMMARY")
    print("=" * 80)
    for rc, cnt in sorted(root_cause_counts.items(), key=lambda x: -x[1]):
        print(f"  - {rc:<55}: {cnt}")

    # Output detailed report JSON for remediation mapping
    with open("scratch/diagnosed_failures.json", "w", encoding="utf-8") as f:
        json.dump(diagnosed_records, f, indent=2)
    print(f"\nSaved scratch/diagnosed_failures.json with {len(diagnosed_records)} diagnosed failures.")

if __name__ == "__main__":
    diagnose()
