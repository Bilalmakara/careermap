"""CareerMap V1.6 Veri Temizleme ve Kalite Güvence Betiği.
Dizin sayfalarını (firmaportal, hekimhane, istebudoktor, dishekimleri, ilandan, eskisehir.net)
ve 0850 çağrı merkezi numaralarını temizler.
"""
import sqlite3
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
db_path = ROOT_DIR / "careermap.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. 0850 telefonları temizle
cursor.execute("UPDATE employers SET phone = '', phone_verification_status = 'unverified', phone_source_url = '' WHERE phone LIKE '0(850)%'")
cursor.execute("DELETE FROM employer_contacts WHERE contact_value LIKE '0(850)%'")

# 2. Portal e-postalarını temizle (firmaportal, hekimhane vb.)
cursor.execute("UPDATE employers SET email = '', email_verification_status = 'unverified', email_source_url = '', is_email_found = 0 WHERE email LIKE '%@firmaportal.com' OR email LIKE '%@hekimhane.com.tr'")
cursor.execute("DELETE FROM employer_contacts WHERE contact_value LIKE '%@firmaportal.com' OR contact_value LIKE '%@hekimhane.com.tr'")

# 3. Dizin ve haber sitelerini temizle
dir_domains = ['firmaportal.com', 'hekimhane.com.tr', 'istebudoktor.com.tr', 'dishekimleri.net', 'ilandan.com', 'eskisehir.net']
for d in dir_domains:
    cursor.execute("UPDATE employers SET website = '', website_verification_status = 'unverified', website_source_url = '' WHERE website LIKE ?", (f"%{d}%",))
    cursor.execute("DELETE FROM employer_contacts WHERE contact_value LIKE ? OR source_url LIKE ?", (f"%{d}%", f"%{d}%"))

conn.commit()

# Mevcut sayıları denetle
cursor.execute("""
SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN website != '' AND website IS NOT NULL THEN 1 ELSE 0 END) as websites,
    SUM(CASE WHEN phone != '' AND phone IS NOT NULL THEN 1 ELSE 0 END) as phones,
    SUM(CASE WHEN email != '' AND email IS NOT NULL THEN 1 ELSE 0 END) as emails,
    SUM(CASE WHEN whatsapp_url != '' AND whatsapp_url IS NOT NULL THEN 1 ELSE 0 END) as whatsapp,
    SUM(CASE WHEN contact_form_url != '' AND contact_form_url IS NOT NULL THEN 1 ELSE 0 END) as contact_forms,
    SUM(CASE WHEN (phone != '' AND phone IS NOT NULL) 
                 OR (email != '' AND email IS NOT NULL) 
                 OR (contact_form_url != '' AND contact_form_url IS NOT NULL) 
                 OR (whatsapp_url != '' AND whatsapp_url IS NOT NULL) THEN 1 ELSE 0 END) as reachable
FROM employers
""")
row = cursor.fetchone()
print(f"Audit sonrası metrikler:")
print(f"  Toplam İşveren   : {row[0]}")
print(f"  Web Siteleri     : {row[1]} (%{row[1]/row[0]*100:.2f})")
print(f"  Telefonlar       : {row[2]} (%{row[2]/row[0]*100:.2f})")
print(f"  E-postalar       : {row[3]} (%{row[3]/row[0]*100:.2f})")
print(f"  WhatsApp         : {row[4]} (%{row[4]/row[0]*100:.2f})")
print(f"  İletişim Formları: {row[5]}")
print(f"  Ulaşılabilirlik  : {row[6]} / {row[0]} (%{row[6]/row[0]*100:.2f})")

conn.close()

