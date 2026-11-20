import sqlite3

conn = sqlite3.connect("data/real_world_pilot_30day.db")
conn.row_factory = sqlite3.Row

# 1. Exact title duplicates in canonical_notices
exact_dupes = conn.execute("""
    SELECT authority_name, title, count(*) as cnt, GROUP_CONCAT(id, ', ') as ids
    FROM canonical_notices
    GROUP BY authority_name, title
    HAVING cnt > 1
    ORDER BY cnt DESC
""").fetchall()

print(f"Exact title duplicate groups: {len(exact_dupes)}")
for r in exact_dupes:
    print(f"[{r['cnt']}x] [{r['authority_name']}] {r['title'][:70]} -> {r['ids']}")

# 2. Check blog_articles duplicates by title or canonical_notice_id
article_dupes = conn.execute("""
    SELECT canonical_notice_id, count(*) as cnt, GROUP_CONCAT(id, ', ') as ids
    FROM blog_articles
    GROUP BY canonical_notice_id
    HAVING cnt > 1
""").fetchall()
print(f"\nBlog articles with same canonical_notice_id: {len(article_dupes)}")
for r in article_dupes:
    print(f"[{r['cnt']}x] notice {r['canonical_notice_id']} -> {r['ids']}")

# 3. Check specific article the user is looking at: art_16e264b7b68b
art = conn.execute("SELECT * FROM blog_articles WHERE id = 'art_16e264b7b68b'").fetchone()
if art:
    print("\nUser active article:", dict(art))
    n = conn.execute("SELECT * FROM canonical_notices WHERE id = ?", (art["canonical_notice_id"],)).fetchone()
    print("Underlying notice:", dict(n))
    
    # Find all notices with similar title or APPSC Combined Competitive
    similar = conn.execute("""
        SELECT id, authority_name, title, normalized_url, first_discovered_at
        FROM canonical_notices
        WHERE title LIKE '%COMBINED C%' OR title LIKE '%Arunachal Pradesh Public Service Combined%'
    """).fetchall()
    print(f"\nSimilar notices to user's article ({len(similar)}):")
    for s in similar:
        print(f" - [{s['id']}] {s['title'][:80]} | URL: {s['normalized_url']}")
