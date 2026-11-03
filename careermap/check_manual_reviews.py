import sqlite3

conn = sqlite3.connect("careermap/careermap.db")
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("SELECT employer_id, name, employer_type, website, website_verification_status, phone, phone_verification_status, email, email_verification_status FROM employers WHERE website_verification_status = 'manual_review' OR phone_verification_status = 'manual_review' OR email_verification_status = 'manual_review'")
rows = c.fetchall()
print(f"MANUAL REVIEW COUNT: {len(rows)}")
for r in rows:
    print(dict(r))

conn.close()

