# -*- coding: utf-8 -*-
import sqlite3
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
conn = sqlite3.connect(ROOT_DIR / "careermap.db")
cur = conn.cursor()

cities = ['Bursa', 'İstanbul', 'Eskişehir', 'Ankara', 'İzmir']
print("=" * 95)
print(f"{'Şehir':<12} | {'DB Toplam':<10} | {'Karantina':<10} | {'Aktif (Arayüz)':<15} | {'Tel Olan':<10} | {'Eposta':<10} | {'Web Olan':<10}")
print("-" * 95)

for c in cities:
    cur.execute("SELECT count(1) FROM employers WHERE city = ?", (c,))
    total = cur.fetchone()[0]
    cur.execute("SELECT count(1) FROM employers WHERE city = ? AND research_status = 'quarantined'", (c,))
    quar = cur.fetchone()[0]
    cur.execute("SELECT count(1) FROM employers WHERE city = ? AND research_status != 'quarantined'", (c,))
    active = cur.fetchone()[0]
    cur.execute("SELECT count(1) FROM employers WHERE city = ? AND research_status != 'quarantined' AND phone != '' AND phone IS NOT NULL", (c,))
    phone = cur.fetchone()[0]
    cur.execute("SELECT count(1) FROM employers WHERE city = ? AND research_status != 'quarantined' AND email != '' AND email IS NOT NULL", (c,))
    email = cur.fetchone()[0]
    cur.execute("SELECT count(1) FROM employers WHERE city = ? AND research_status != 'quarantined' AND website != '' AND website IS NOT NULL", (c,))
    web = cur.fetchone()[0]
    print(f"{c:<12} | {total:<10} | {quar:<10} | {active:<15} | {phone:<10} | {email:<10} | {web:<10}")

print("=" * 95)
conn.close()

