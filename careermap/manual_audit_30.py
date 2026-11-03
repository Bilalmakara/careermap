import sqlite3
import json
from pathlib import Path

DB_PATH = Path("careermap/careermap.db")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 16 Poliklinik
cursor.execute("""
SELECT employer_id, name, employer_type, district, address, phone, phone_type, phone_source_url, 
       phone_verification_status, email, email_type, email_source_url, email_verification_status,
       website, website_source_url, website_verification_status, contact_form_url, research_notes
FROM employers 
WHERE employer_type LIKE '%poliklinik%'
ORDER BY id ASC
LIMIT 16
""")
clinics = [dict(r) for r in cursor.fetchall()]

# 16 Bireysel Muayenehane
cursor.execute("""
SELECT employer_id, name, employer_type, district, address, phone, phone_type, phone_source_url, 
       phone_verification_status, email, email_type, email_source_url, email_verification_status,
       website, website_source_url, website_verification_status, contact_form_url, research_notes
FROM employers 
WHERE employer_type LIKE '%muayenehane%'
ORDER BY id ASC
LIMIT 16
""")
offices = [dict(r) for r in cursor.fetchall()]

sample_32 = clinics + offices

with open("careermap/manual_sample_32.json", "w", encoding="utf-8") as f:
    json.dump(sample_32, f, ensure_ascii=False, indent=2)

print(f"Extracted {len(sample_32)} sample employers (16 clinics + 16 offices)")
conn.close()

