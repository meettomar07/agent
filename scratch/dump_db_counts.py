import sqlite3

for db_path in ["data/testkart.db", "data/acceptance_test.db"]:
    print(f"=== {db_path} ===")
    conn = sqlite3.connect(db_path)
    tables = [t[0] for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    for t in tables:
        count = conn.execute(f"SELECT count(*) FROM [{t}]").fetchone()[0]
        print(f"  {t}: {count}")
