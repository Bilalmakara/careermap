# -*- coding: utf-8 -*-
import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.enrichment.web_search_discovery import is_third_party_directory

conn = sqlite3.connect(ROOT_DIR / "careermap.db")
cur = conn.cursor()

cur.execute("SELECT employer_id, name, city, website FROM employers WHERE website != '' AND website IS NOT NULL")
rows = cur.fetchall()
cleaned = 0
bad_substrings = [
    'alomaliye', 'busiad', 'asosjournal', 'sondakika', 'kamyonum',
    'esnafsiteleri', 'teknolojikogretmenler', 'templatemonster', 'forum',
    'tarimorman', 'nilufer.bel.tr', 'haber', 'gazete'
]

for eid, name, city, web in rows:
    web_lower = web.lower()
    if is_third_party_directory(web) or any(bad in web_lower for bad in bad_substrings):
        print(f"Clearing bad website for {name} ({city}): {web}")
        cur.execute("UPDATE employers SET website = '', website_source_url = '', website_verification_status = 'unverified' WHERE employer_id = ?", (eid,))
        cleaned += 1

conn.commit()
print(f"Total bad websites cleared: {cleaned}")
conn.close()

