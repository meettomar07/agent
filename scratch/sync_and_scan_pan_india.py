import sqlite3
from pathlib import Path
from testkart_intelligence.registry.service import seed_sources_if_empty, SourceRegistryService
from testkart_intelligence.discovery.engine import DiscoveryEngine
from testkart_intelligence.database.connection import get_db

db_path = Path("data/real_world_pilot_30day.db")

# 1. Seed newly added sources from sources.json
with get_db(db_path) as conn:
    count = seed_sources_if_empty(conn)

registry = SourceRegistryService(db_path)
enabled = registry.list_sources(enabled_only=True)
print(f"Total enabled sources: {len(enabled)}")

# 2. Target new Pan-India sources for scan
new_codes = ["WBPSC", "APPSC_AR", "NPSC", "MPSC_MZ", "TPSC", "SPSC"]
print(f"Scanning new Pan-India sources with full AI enrichment: {new_codes}...")

engine = DiscoveryEngine(db_path=db_path)

total_new_notices = 0
for code in new_codes:
    print(f"\n--- Scanning source {code} ---")
    try:
        res = engine.run_scan(scan_type="MANUAL", source_code=code, auto_enrich=True)
        found = res.get("notices_found", 0)
        total_new_notices += found
        print(f"Result for {code}: {found} new recruitment notices found.")
    except Exception as e:
        print(f"Error scanning {code}: {e}")

print(f"\nTotal new notices discovered and enriched across Pan-India additions: {total_new_notices}")

conn = sqlite3.connect(db_path)
c = conn.cursor()
notices = c.execute("SELECT COUNT(*) FROM canonical_notices").fetchone()[0]
articles = c.execute("SELECT COUNT(*) FROM blog_articles WHERE status = 'QA_PASSED'").fetchone()[0]
print(f"Final State: Total Canonical Notices: {notices} | QA Passed Articles: {articles}")
conn.close()
