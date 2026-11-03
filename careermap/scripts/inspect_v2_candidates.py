import sqlite3
import json

conn = sqlite3.connect("careermap/careermap.db")
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("""
SELECT employer_id, name, employer_type, district, phone, email, website, whatsapp_url, contact_form_url
FROM employers
WHERE email != '' OR whatsapp_url != ''
ORDER BY 
    (CASE WHEN email != '' AND whatsapp_url != '' THEN 3 WHEN email != '' THEN 2 ELSE 1 END) DESC,
    employer_type DESC,
    name ASC
LIMIT 15
""")

rows = [dict(r) for r in c.fetchall()]
print(f"Total matching clinics found: {len(rows)}")
for idx, r in enumerate(rows[:12], 1):
    print(f"{idx}. {r['name']} [{r['employer_type']} - {r['district']}]")
    print(f"   Email: {r['email']} | Tel: {r['phone']}")
    print(f"   WA: {r['whatsapp_url']} | Web: {r['website']} | Form: {r['contact_form_url']}")

conn.close()

