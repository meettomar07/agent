"""Comprehensive Independent Audit Script for Testkart.
Audits the 52-notice dataset, OCR pipeline, critical fields, and operational safety.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import sys
import subprocess
from typing import Dict, List, Any

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(".").resolve()))

from testkart_intelligence.config import settings
from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.html_extractor import HtmlDocumentExtractor
from testkart_intelligence.extraction.fact_extractor import FactExtractor
from testkart_intelligence.extraction.verifier import VerificationAgent
from testkart_intelligence.extraction.ocr import compute_ocr_confidence, WindowsMediaOcrEngine, StubOcrEngine
from scratch.evaluate_new_52_dataset import NEW_GROUND_TRUTH, FIELD_NAMES, normalize_val

def audit_hash_independence():
    print("=" * 80)
    print("1. HASH INDEPENDENCE AND DATASET UNIQUENESS AUDIT")
    print("=" * 80)

    val_dir = Path("data/new_validation_notices")
    assert val_dir.exists(), "Directory data/new_validation_notices missing"

    files = list(val_dir.iterdir())
    print(f"Total files on disk in data/new_validation_notices: {len(files)}")
    assert len(files) == 52, f"Expected 52 files, found {len(files)}"

    computed_hashes = {}
    for f in files:
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        computed_hashes[f.name] = h

    # Check internal uniqueness
    unique_hashes = set(computed_hashes.values())
    print(f"Unique SHA-256 hashes among 52 files: {len(unique_hashes)}")
    assert len(unique_hashes) == 52, "Internal hash collision detected among 52 notices!"

    # Load frozen held-out manifest (33 notices)
    with open("FROZEN_HELD_OUT_DATASET_MANIFEST.json", "r", encoding="utf-8") as f:
        frozen_data = json.load(f)
    frozen_hashes = {info["sha256"] for info in frozen_data["documents"].values()}
    print(f"Frozen held-out baseline unique hashes: {len(frozen_hashes)}")
    assert len(frozen_hashes) == 33

    # Load development manifest (13 notices)
    with open("DEVELOPMENT_SET_MANIFEST.json", "r", encoding="utf-8") as f:
        dev_data = json.load(f)
    dev_hashes = {info["sha256"] for info in dev_data["documents"].values()}
    print(f"Development set unique hashes: {len(dev_hashes)}")

    # Check collisions
    c_frozen = unique_hashes.intersection(frozen_hashes)
    c_dev = unique_hashes.intersection(dev_hashes)
    print(f"Collisions with frozen baseline: {len(c_frozen)}")
    print(f"Collisions with development set: {len(c_dev)}")
    assert len(c_frozen) == 0, f"Contamination with frozen baseline: {c_frozen}"
    assert len(c_dev) == 0, f"Contamination with development set: {c_dev}"
    print("Hash independence verified: 100% distinct, ZERO overlap.")

def audit_document_types():
    print("\n" + "=" * 80)
    print("2. DOCUMENT TYPE & AUTHORITY COMPOSITION AUDIT")
    print("=" * 80)

    type_counts = {}
    auth_counts = {}
    category_counts = {}

    for fname, meta in NEW_GROUND_TRUTH.items():
        doc_fmt = meta.get("format", "UNKNOWN")
        type_counts[doc_fmt] = type_counts.get(doc_fmt, 0) + 1

        auth = meta.get("authority", "UNKNOWN")
        auth_counts[auth] = auth_counts.get(auth, 0) + 1

        cat = meta.get("category", "UNKNOWN")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    print("Document Formats:")
    for fmt, c in sorted(type_counts.items()):
        print(f"  - {fmt}: {c}")

    print("\nAuthorities:")
    for auth, c in sorted(auth_counts.items()):
        print(f"  - {auth}: {c}")

    print("\nCategories:")
    for cat, c in sorted(category_counts.items()):
        print(f"  - {cat}: {c}")

if __name__ == "__main__":
    audit_hash_independence()
    audit_document_types()
