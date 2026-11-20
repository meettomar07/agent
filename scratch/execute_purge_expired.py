import sqlite3

conn = sqlite3.connect('data/real_world_pilot_30day.db')
conn.row_factory = sqlite3.Row

# Load purge plan
with open('scratch/find_genuinely_live.py') as f:
    code = f.read()
scope = {}
exec(code, scope)

expired_or_old = scope['expired_or_old']
expired_ids = [r["id"] for r in expired_or_old]

print(f"Purging {len(expired_ids)} expired / passed-away notices...")

# Perform deletion in transaction
with conn:
    # 1. Delete QA results for articles of expired notices
    conn.execute(
        f"""
        DELETE FROM qa_results
        WHERE article_version_id IN (
            SELECT av.id FROM article_versions av
            JOIN blog_articles ba ON av.article_id = ba.id
            WHERE ba.canonical_notice_id IN ({','.join(['?']*len(expired_ids))})
        )
        """,
        expired_ids,
    )

    # 2. Delete approval records for articles of expired notices
    conn.execute(
        f"""
        DELETE FROM approval_records
        WHERE article_version_id IN (
            SELECT av.id FROM article_versions av
            JOIN blog_articles ba ON av.article_id = ba.id
            WHERE ba.canonical_notice_id IN ({','.join(['?']*len(expired_ids))})
        )
        """,
        expired_ids,
    )

    # 3. Delete article versions
    conn.execute(
        f"""
        DELETE FROM article_versions
        WHERE article_id IN (
            SELECT id FROM blog_articles
            WHERE canonical_notice_id IN ({','.join(['?']*len(expired_ids))})
        )
        """,
        expired_ids,
    )

    # 4. Delete blog articles
    conn.execute(
        f"""
        DELETE FROM blog_articles
        WHERE canonical_notice_id IN ({','.join(['?']*len(expired_ids))})
        """,
        expired_ids,
    )

    # 5. Delete extracted facts for expired notice versions
    conn.execute(
        f"""
        DELETE FROM extracted_facts
        WHERE notice_version_id IN (
            SELECT id FROM notice_versions
            WHERE notice_id IN ({','.join(['?']*len(expired_ids))})
        )
        """,
        expired_ids,
    )

    # 6. Delete notice versions
    conn.execute(
        f"""
        DELETE FROM notice_versions
        WHERE notice_id IN ({','.join(['?']*len(expired_ids))})
        """,
        expired_ids,
    )

    # 7. Delete canonical notices
    conn.execute(
        f"""
        DELETE FROM canonical_notices
        WHERE id IN ({','.join(['?']*len(expired_ids))})
        """,
        expired_ids,
    )

# Verify count remaining
rem_count = conn.execute("SELECT count(*) FROM canonical_notices").fetchone()[0]
print(f"Successfully purged expired notices! Total remaining live notices: {rem_count}")

# Check not_f4c5077ef98a
check_f4 = conn.execute("SELECT count(*) FROM canonical_notices WHERE id = 'not_f4c5077ef98a'").fetchone()[0]
print(f"Check not_f4c5077ef98a (Indian Coast Guard expired): exists={bool(check_f4)}")
