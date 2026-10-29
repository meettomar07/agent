import sqlite3
conn = sqlite3.connect('data/testkart.db')
c = conn.cursor()
r = c.execute("SELECT document_hash, storage_path FROM notice_versions WHERE notice_id = 'not_9b1eef28c437'").fetchone()
print("Cancel notice:", r)

# Also check 3f118317887e and 84f9c79be72d in data/validation_notices
# notice_06 is notice_06_ssc_je_tentative_vacancy.pdf
# notice_07 is notice_07_upsc_cancellation_advt_13_2025.pdf
