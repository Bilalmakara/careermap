# -*- coding: utf-8 -*-
import sqlite3
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
conn = sqlite3.connect(ROOT_DIR / "careermap.db")
cur = conn.cursor()

bad_terms = ['inşaat', 'insaat', 'moda plus', 'temel bilimler bölümü', 'temel bilimler bolumu', 'fakülte inşaatı', 'fakulte insaati']
quarantined_count = 0

for term in bad_terms:
    cur.execute("SELECT employer_id, name, city FROM employers WHERE lower(name) LIKE ?", (f"%{term}%",))
    for eid, name, city in cur.fetchall():
        print(f"Quarantining non-clinic entity: {name} ({city})")
        cur.execute("UPDATE employers SET research_status = 'quarantined', research_notes = 'Otomatik denetim: Klinik değil (inşaat/akademik/perakende)' WHERE employer_id = ?", (eid,))
        quarantined_count += 1

conn.commit()
print(f"Total non-clinics quarantined: {quarantined_count}")
conn.close()

