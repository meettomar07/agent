import sqlite3
import re

conn = sqlite3.connect("data/real_world_pilot_30day.db")
conn.row_factory = sqlite3.Row

# 1. Fetch all notices with their articles and metadata
notices = conn.execute("""
    SELECT cn.id, cn.authority_name, cn.title, cn.normalized_url,
           ba.id as article_id
    FROM canonical_notices cn
    LEFT JOIN blog_articles ba ON ba.canonical_notice_id = cn.id
""").fetchall()

print(f"Total notices before purge: {len(notices)}")

historical_ids = []
for n in notices:
    text = (n["title"] + " " + n["normalized_url"]).lower()
    
    # Check if there is an explicit past year strictly before 2025
    past_years = [int(y) for y in re.findall(r'\b(19\d\d|200\d|201\d|202[0-4])\b', text)]
    live_years = [int(y) for y in re.findall(r'\b(202[5-9]|203\d)\b', text)]
    
    # If it has past year(s) and NO live year (2025+), it is a historical cycle
    if past_years and not live_years:
        historical_ids.append(n["id"])
    # Check if URL explicitly points to archive directory
    elif re.search(r'/(archive|archived|previous|old_advertisements?|old_notices?)/', text):
        historical_ids.append(n["id"])

print(f"Identified {len(historical_ids)} historical past-cycle notices for deletion.")

# 2. Also check for identical title duplicates among remaining notices
# (e.g. ESIC identical titles or duplicate TNPSC)
remaining_notices = [n for n in notices if n["id"] not in historical_ids]
seen = {}
duplicate_ids = []
for n in remaining_notices:
    clean_title = re.sub(r'[^a-zA-Z0-9\s]', '', n["title"].lower()).strip()
    key = (n["authority_name"], clean_title)
    if key in seen:
        # Keep the one with the higher id or newer discovery
        duplicate_ids.append(n["id"])
    else:
        seen[key] = n

print(f"Identified {len(duplicate_ids)} redundant duplicate notices among remaining.")

all_purge_ids = list(set(historical_ids + duplicate_ids))
print(f"Total notices to purge: {len(all_purge_ids)}")

# Execute deletion in a single atomic transaction
with conn:
    # 1. Delete QA results
    conn.execute(
        f"""
        DELETE FROM qa_results
        WHERE article_version_id IN (
            SELECT av.id FROM article_versions av
            JOIN blog_articles ba ON av.article_id = ba.id
            WHERE ba.canonical_notice_id IN ({','.join(['?']*len(all_purge_ids))})
        )
        """,
        all_purge_ids,
    )
    
    # 2. Delete approval records
    conn.execute(
        f"""
        DELETE FROM approval_records
        WHERE article_version_id IN (
            SELECT av.id FROM article_versions av
            JOIN blog_articles ba ON av.article_id = ba.id
            WHERE ba.canonical_notice_id IN ({','.join(['?']*len(all_purge_ids))})
        )
        """,
        all_purge_ids,
    )
    
    # 3. Delete article versions
    conn.execute(
        f"""
        DELETE FROM article_versions
        WHERE article_id IN (
            SELECT id FROM blog_articles
            WHERE canonical_notice_id IN ({','.join(['?']*len(all_purge_ids))})
        )
        """,
        all_purge_ids,
    )
    
    # 4. Delete blog articles
    conn.execute(
        f"""
        DELETE FROM blog_articles
        WHERE canonical_notice_id IN ({','.join(['?']*len(all_purge_ids))})
        """,
        all_purge_ids,
    )
    
    # 5. Delete extracted facts
    conn.execute(
        f"""
        DELETE FROM extracted_facts
        WHERE notice_version_id IN (
            SELECT id FROM notice_versions
            WHERE notice_id IN ({','.join(['?']*len(all_purge_ids))})
        )
        """,
        all_purge_ids,
    )
    
    # 6. Delete notice versions
    conn.execute(
        f"""
        DELETE FROM notice_versions
        WHERE notice_id IN ({','.join(['?']*len(all_purge_ids))})
        """,
        all_purge_ids,
    )
    
    # 7. Delete canonical notices
    conn.execute(
        f"""
        DELETE FROM canonical_notices
        WHERE id IN ({','.join(['?']*len(all_purge_ids))})
        """,
        all_purge_ids,
    )

# Verify final counts
rem_notices = conn.execute("SELECT count(*) FROM canonical_notices").fetchone()[0]
rem_articles = conn.execute("SELECT count(*) FROM blog_articles").fetchone()[0]
qa_passed_articles = conn.execute("SELECT count(*) FROM blog_articles WHERE status = 'QA_PASSED'").fetchone()[0]

print(f"\nPurge completed successfully!")
print(f"Remaining Canonical Notices: {rem_notices}")
print(f"Remaining Blog Articles: {rem_articles}")
print(f"QA Passed Articles: {qa_passed_articles}")
print(f"QA Pass Rate: {qa_passed_articles / rem_articles * 100:.1f}%")
