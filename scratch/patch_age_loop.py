"""Patch age extraction loop in fact_extractor.py."""

with open("testkart_intelligence/extraction/fact_extractor.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '''        # Look for Age Limit
        age_found = False
        if not is_result_or_key:
            for p in pages:
                text = p["text"]
                for pat in cls.AGE_PATTERNS:
                    m = re.search(pat, text, re.IGNORECASE)
                    if m:
                        if len(m.groups()) >= 2 and m.group(1) and m.group(2):
                            as_on = f" as on {m.group(3)}" if len(m.groups()) >= 3 and m.group(3) else ""
                            val_str = f"{m.group(1)} to {m.group(2)} years{as_on}"
                        elif len(m.groups()) >= 1 and m.group(1):
                            val_str = " ".join(m.group(1).split())
                        else:
                            val_str = " ".join(m.group(0).split())
                        snippet = text[max(0, m.start() - 20): min(len(text), m.end() + 30)].strip()
                        facts.append(
                            ExtractedFactItem(
                                key="age_limit",
                                value=val_str,
                                evidence_text=snippet,
                                page_number=p["page_number"],
                                confidence=0.85,
                                status="VERIFIED",
                                notes="Prescribed age limit",
                            )
                        )
                        age_found = True
                        break
                if age_found:
                    break'''

new = '''        # Look for Age Limit (skip if already set by TableExtractor integration)
        age_found = "age_limit" in extracted_keys
        if not is_result_or_key and not age_found:
            for p in pages:
                text = p["text"]
                for pat_idx, pat in enumerate(cls.AGE_PATTERNS):
                    m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
                    if m:
                        # Birth-date window patterns (indices 8+) return two date strings
                        if pat_idx >= 8 and len(m.groups()) >= 2 and m.group(1) and m.group(2):
                            # Emit the raw phrase; readers see "born not earlier than X and not later than Y"
                            val_str = " ".join(m.group(0).split())
                        elif len(m.groups()) >= 2 and m.group(1) and m.group(2):
                            as_on = f" as on {m.group(3)}" if len(m.groups()) >= 3 and m.group(3) else ""
                            val_str = f"{m.group(1)} to {m.group(2)} years{as_on}"
                        elif len(m.groups()) >= 1 and m.group(1):
                            val_str = " ".join(m.group(1).split())
                        else:
                            val_str = " ".join(m.group(0).split())
                        snippet = text[max(0, m.start() - 20): min(len(text), m.end() + 30)].strip()
                        facts.append(
                            ExtractedFactItem(
                                key="age_limit",
                                value=val_str,
                                evidence_text=snippet,
                                page_number=p["page_number"],
                                confidence=0.85,
                                status="VERIFIED",
                                notes="Prescribed age limit",
                            )
                        )
                        age_found = True
                        extracted_keys.add("age_limit")
                        break
                if age_found:
                    break'''

if old in content:
    new_content = content.replace(old, new, 1)
    with open("testkart_intelligence/extraction/fact_extractor.py", "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Age extraction loop patched successfully")
else:
    # Find by landmark
    idx = content.find("# Look for Age Limit")
    print(f"Block at index {idx}")
    print(repr(content[idx:idx+300]))
