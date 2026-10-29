import sqlite3

conn = sqlite3.connect("data/testkart.db")
c = conn.cursor()

for auth in ["src_ssc", "src_upsc", "src_nta", "src_tnpsc", "src_uppsc"]:
    rows = c.execute("SELECT id, title, classification, normalized_url FROM canonical_notices WHERE source_id = ? LIMIT 6", (auth,)).fetchall()
    print(f"\n=== {auth} ({len(rows)} sample notices) ===")
    for r in rows:
        print(f"  {r[0]}: [{r[2]}] {r[1][:60]} -> {r[3]}")
