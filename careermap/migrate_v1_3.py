"""CareerMap V1.3 Veritabanı Migrasyon Betiği.
- careermap.db yedeğini alır (careermap.db.v1_2.bak).
- 'employers' tablosuna 'contact_form_url' sütununu ekler.
- 'employer_contacts' tablosunu oluşturur (contact_id, employer_id, contact_type, contact_value, contact_category, source_url, source_type, discovered_at, last_checked_at, verification_status).
- Mevcut 220 işverenin telefon, e-posta, web sitesi ve kariyer URL'lerini employer_contacts tablosuna güvenle aktarır.
"""
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent / "careermap.db"
BACKUP_PATH = Path(__file__).resolve().parent / "careermap.db.v1_2.bak"

def run_migration():
    if not DB_PATH.exists():
        print(f"Hata: Veritabanı bulunamadı: {DB_PATH}")
        return

    # 1. Yedek al
    print(f"1. Veritabanı yedekleniyor: {BACKUP_PATH}")
    shutil.copy2(DB_PATH, BACKUP_PATH)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 2. employers tablosuna contact_form_url ekle
    cursor.execute("PRAGMA table_info(employers)")
    columns = [col["name"] for col in cursor.fetchall()]
    if "contact_form_url" not in columns:
        print("2. 'contact_form_url' sütunu 'employers' tablosuna ekleniyor...")
        cursor.execute("ALTER TABLE employers ADD COLUMN contact_form_url TEXT DEFAULT ''")
    else:
        print("2. 'contact_form_url' sütunu zaten mevcut.")

    # 3. employer_contacts tablosunu oluştur
    print("3. 'employer_contacts' tablosu oluşturuluyor...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS employer_contacts (
        contact_id INTEGER PRIMARY KEY AUTOINCREMENT,
        employer_id TEXT NOT NULL,
        contact_type TEXT NOT NULL,
        contact_value TEXT NOT NULL,
        contact_category TEXT DEFAULT 'unknown',
        source_url TEXT DEFAULT '',
        source_type TEXT DEFAULT 'unknown',
        discovered_at TEXT,
        last_checked_at TEXT,
        verification_status TEXT DEFAULT 'unverified',
        FOREIGN KEY(employer_id) REFERENCES employers(employer_id) ON DELETE CASCADE,
        UNIQUE(employer_id, contact_type, contact_value)
    )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_contact_empid ON employer_contacts(employer_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_contact_type ON employer_contacts(contact_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_contact_verif ON employer_contacts(verification_status)")

    # 4. Mevcut 220 işverenin verilerini employer_contacts tablosuna aktar
    print("4. Mevcut iletişim bilgileri 'employer_contacts' tablosuna aktarılıyor...")
    cursor.execute("SELECT * FROM employers")
    employers = cursor.fetchall()
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    inserted_contacts = 0

    for emp in employers:
        emp_id = emp["employer_id"]
        source_type = emp["source_type"] or "official_health"
        last_checked = emp["source_last_checked"] or today_str
        
        # Telefon
        phone = (emp["phone"] or "").strip()
        if phone:
            cursor.execute("""
            INSERT OR IGNORE INTO employer_contacts 
            (employer_id, contact_type, contact_value, contact_category, source_url, source_type, discovered_at, last_checked_at, verification_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                emp_id, "phone", phone, emp["phone_type"] or "unknown",
                emp["phone_source_url"] or "", source_type,
                emp["observed_at"] or today_str, last_checked,
                emp["phone_verification_status"] or "unverified"
            ))
            if cursor.rowcount > 0:
                inserted_contacts += 1

        # E-posta
        email = (emp["email"] or "").strip()
        if email:
            cursor.execute("""
            INSERT OR IGNORE INTO employer_contacts 
            (employer_id, contact_type, contact_value, contact_category, source_url, source_type, discovered_at, last_checked_at, verification_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                emp_id, "email", email, emp["email_type"] or "unknown",
                emp["email_source_url"] or "", source_type,
                emp["observed_at"] or today_str, last_checked,
                emp["email_verification_status"] or "unverified"
            ))
            if cursor.rowcount > 0:
                inserted_contacts += 1

        # Web Sitesi
        website = (emp["website"] or "").strip()
        if website:
            cursor.execute("""
            INSERT OR IGNORE INTO employer_contacts 
            (employer_id, contact_type, contact_value, contact_category, source_url, source_type, discovered_at, last_checked_at, verification_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                emp_id, "website", website, "corporate",
                emp["website_source_url"] or website, source_type,
                emp["observed_at"] or today_str, last_checked,
                emp["website_verification_status"] or "unverified"
            ))
            if cursor.rowcount > 0:
                inserted_contacts += 1

        # Kariyer Sayfası
        career_url = (emp["career_url"] or "").strip()
        if career_url:
            cursor.execute("""
            INSERT OR IGNORE INTO employer_contacts 
            (employer_id, contact_type, contact_value, contact_category, source_url, source_type, discovered_at, last_checked_at, verification_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                emp_id, "career_page", career_url, "career",
                career_url, source_type,
                emp["observed_at"] or today_str, last_checked,
                "verified"
            ))
            if cursor.rowcount > 0:
                inserted_contacts += 1

    conn.commit()

    # İstatistikler
    cursor.execute("SELECT COUNT(*) FROM employer_contacts")
    total_contacts = cursor.fetchone()[0]
    cursor.execute("SELECT contact_type, COUNT(*) FROM employer_contacts GROUP BY contact_type")
    contact_breakdown = cursor.fetchall()

    conn.close()
    print(f"Migrasyon başarıyla tamamlandı!")
    print(f"Toplam aktarılan/kayıtlı iletişim sayısı: {total_contacts} (yeni eklenen: {inserted_contacts})")
    for r in contact_breakdown:
        print(f" - {r[0]}: {r[1]}")

if __name__ == "__main__":
    run_migration()

