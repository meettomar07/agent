import sqlite3

conn = sqlite3.connect('data/real_world_pilot_30day.db')
c = conn.cursor()
row = c.execute("SELECT content_markdown FROM article_versions WHERE article_id = 'art_bb6d87288e5c'").fetchone()
if row:
    print(row[0])
else:
    print("Article not found in article_versions")
conn.close()
