"""Tests for Pre-Production Held-Out Accuracy Evaluation across 33 real official notices."""

import hashlib
from pathlib import Path
import pytest

from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.html_extractor import HtmlDocumentExtractor
from testkart_intelligence.extraction.fact_extractor import FactExtractor


def test_held_out_dataset_completeness_and_uniqueness():
    """Verify that the held-out validation set contains >= 30 unique real notices across 5 sources."""
    val_dir = Path("data/validation_notices")
    assert val_dir.exists(), "validation_notices directory missing"

    notice_files = sorted(list(val_dir.glob("notice_*")))
    assert len(notice_files) >= 30, f"Expected >= 30 notices, found {len(notice_files)}"

    # Check hash uniqueness
    seen_hashes = set()
    for nf in notice_files:
        h = hashlib.sha256(nf.read_bytes()).hexdigest()
        assert h not in seen_hashes, f"Duplicate document hash detected in held-out set: {nf.name}"
        seen_hashes.add(h)

    # Check authority representation in filenames
    names_str = " ".join(f.name for f in notice_files)
    assert "ssc" in names_str
    assert "upsc" in names_str
    assert "nta" in names_str
    assert "uppsc" in names_str
    assert "tnpsc" in names_str


def test_held_out_extraction_omission_accuracy():
    """Confirm omission accuracy >= 90% on held-out set (preventing hallucinated facts on non-recruitment notices)."""
    from scratch.run_held_out_evaluation_33 import GROUND_TRUTH, EVAL_FIELDS, is_exact_match

    val_dir = Path("data/validation_notices")
    pdf_ext = PdfDocumentExtractor()
    html_ext = HtmlDocumentExtractor()

    tn_count = 0
    fp_count = 0

    for filename, doc_meta in GROUND_TRUTH.items():
        file_path = val_dir / filename
        if not file_path.exists():
            continue
        content_bytes = file_path.read_bytes()
        is_readable = doc_meta["readable"]
        gt_facts = doc_meta["facts"]
        fmt = doc_meta["format"]

        extracted_dict = {}
        if is_readable:
            if fmt == "TEXT_PDF":
                _, pages, _ = pdf_ext.extract(content_bytes)
            else:
                html_text = content_bytes.decode("utf-8", errors="replace")
                _, pages, _ = html_ext.extract(html_text)

            facts_list = FactExtractor.extract_from_pages(
                pages=pages,
                authority_name=doc_meta["authority"],
                notice_title=filename,
                official_url=f"https://official.gov.in/{filename}",
            )
            for f in facts_list:
                extracted_dict[f.key] = f.value

        for field in EVAL_FIELDS:
            gt_val = gt_facts.get(field, "N/A")
            ext_val = extracted_dict.get(field, "N/A")

            if gt_val == "N/A":
                if ext_val == "N/A":
                    tn_count += 1
                else:
                    fp_count += 1

    total_na = tn_count + fp_count
    omission_acc = tn_count / total_na if total_na > 0 else 1.0

    assert omission_acc >= 0.90, f"Omission accuracy {omission_acc:.2%} fell below 90% threshold"
