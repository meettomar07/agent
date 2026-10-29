import sqlite3
conn = sqlite3.connect('data/testkart.db')
c = conn.cursor()
for table in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
    tname = table[0]
    cols = [col[1] for col in c.execute(f"PRAGMA table_info({tname})").fetchall()]
    print(f"Table: {tname}")
    print(f"  Columns: {cols}\n")
