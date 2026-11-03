"""CareerMap V1.2 Veritabanı Migrasyon ve Tekilleştirme Onarım Scripti.
439 mükerrer kaydı inceleyip tekil ve tutarlı 220 işveren envanterine dönüştürür.
"""
import sqlite3
import re
import unicodedata
from pathlib import Path
from collections import defaultdict
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent / "careermap.db"

def canonical_id(name: str, district: str, employer_type: str) -> str:
    """İşletme veya hekim için deterministik, çakışmayan kararlı kimlik üretir."""
    # Türkçe küçük harf
    s = name.replace("I", "ı").replace("İ", "i").lower()
    s = s.translate(str.maketrans("çğıöşü", "cgiosu"))
    s = unicodedata.normalize("NFKD", s)
    
    # Şube tespiti (Şubeler farklı kimlik almalıdır!)
    branch = ""
    for b in ["camlica", "emek", "sakarya", "doktorlar", "bati", "subesi"]:
        if b in s:
            branch = f"-{b}"
            break
            
    is_office = "muayenehane" in employer_type.lower() or s.startswith("dt")
    prefix = "office" if is_office else "clinic"
    
    # Unvan ve genel kelimeleri temizle
    clean_name = re.sub(r"\b(ozel|agiz|ve|dis|sagligi|poliklinigi|poliklinik|klinik|muayenehanesi|muayenehane|dt|dr)\b", " ", s)
    clean_name = re.sub(r"[^a-z0-9]", "", clean_name)
    
    # İlçe
    dist_slug = ""
    if district:
        d = district.replace("I", "ı").replace("İ", "i").lower()
        d = d.translate(str.maketrans("çğıöşü", "cgiosu"))
        d = re.sub(r"[^a-z0-9]", "", d)
        if d:
            dist_slug = f"-{d}"
            
    return f"dentist-eskisehir-{prefix}{dist_slug}-{clean_name[:40]}{branch}"

def run_migration():
    print("=== CareerMap V1.2 Veritabanı Migrasyonu Başlatılıyor ===")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Mevcut durum
    cursor.execute("SELECT COUNT(*) FROM employers")
    initial_count = cursor.fetchone()[0]
    print(f"Migrasyon Öncesi Toplam Kayıt: {initial_count}")

    cursor.execute("SELECT * FROM employers")
    raw_rows = [dict(r) for r in cursor.fetchall()]

    # Kayıtları kararlı employer_id'ye göre grupla
    grouped = defaultdict(list)
    for row in raw_rows:
        emp_type = row.get("employer_type") or "Genel"
        dist = row.get("district") or ""
        name = row.get("name") or ""
        emp_id = canonical_id(name, dist, emp_type)
        grouped[emp_id].append(row)

    print(f"Tespit Edilen Tekil İşveren Kimliği Sayısı: {len(grouped)}")

    # Her grup için en zengin ve doğrulanmış kaydı birleştir
    unified_records = []
    audit_entries = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today_str = datetime.now().strftime("%Y-%m-%d")

    for emp_id, records in grouped.items():
        base = dict(records[0])
        base["employer_id"] = emp_id

        # Varsa yeni sürümdeki ('verified', 'unverified') kaydı öncelikli al
        new_ver_rec = next((r for r in records if r.get("verification_status") in ["verified", "unverified"]), None)
        old_ver_rec = next((r for r in records if r.get("verification_status") in ["Doğrulandı", "Kontrol Edilmeli"]), None)

        if new_ver_rec:
            base = dict(new_ver_rec)
            base["employer_id"] = emp_id

        # İletişim bilgilerini en dolu ve kaynaklı olanla birleştir
        for r in records:
            if not base.get("phone") and r.get("phone"):
                base["phone"] = r["phone"]
                base["phone_source_url"] = r.get("phone_source_url", "")
            if not base.get("email") and r.get("email"):
                base["email"] = r["email"]
                base["email_source_url"] = r.get("email_source_url", "")
            if not base.get("website") and r.get("website"):
                base["website"] = r["website"]
                base["website_source_url"] = r.get("website_source_url", "")
            if not base.get("address") and r.get("address"):
                base["address"] = r["address"]
            if not base.get("district") and r.get("district"):
                base["district"] = r["district"]

        # Alan bazlı doğrulama durumlarını belirle
        phone = (base.get("phone") or "").strip()
        phone_src = (base.get("phone_source_url") or "").strip()
        email = (base.get("email") or "").strip()
        email_src = (base.get("email_source_url") or "").strip()
        web = (base.get("website") or "").strip()
        web_src = (base.get("website_source_url") or "").strip()

        # Telefon doğrulama durumu
        if phone and "tdb.org.tr" in phone_src:
            phone_status = "verified"
            phone_type = "personal_registry" if "muayenehane" in base.get("employer_type", "").lower() else "corporate"
        elif phone and phone_src:
            phone_status = "verified"
            phone_type = "corporate"
        elif phone:
            phone_status = "manual_review"
            phone_type = "unknown"
        else:
            phone_status = "unverified"
            phone_type = "unknown"

        # E-posta doğrulama durumu
        if email and email_src:
            email_status = "verified"
            email_type = "career" if any(k in email for k in ["ik@", "kariyer@", "hr@"]) else "general"
        elif email:
            email_status = "manual_review"
            email_type = "general"
        else:
            email_status = "unverified"
            email_type = "unknown"

        # Web sitesi doğrulama durumu
        if web and web_src:
            web_status = "verified"
        elif web:
            web_status = "manual_review"
        else:
            web_status = "unverified"

        # Araştırma durumu
        research_status = "completed" if (phone or email or web) else "pending"

        base["phone_type"] = phone_type
        base["phone_verification_status"] = phone_status
        base["email_type"] = email_type
        base["email_verification_status"] = email_status
        base["website_verification_status"] = web_status
        base["business_status"] = "active"
        base["research_status"] = research_status
        base["source_last_checked"] = today_str
        base["observed_at"] = today_str
        base["contact_last_verified"] = today_str if (phone_status == "verified" or email_status == "verified") else None

        if len(records) > 1:
            audit_entries.append((emp_id, "deduplication_merge", f"{len(records)} kayıt", "1 tekil kayıt", "v1.2_migration", now_str))

        unified_records.append(base)

    # Yeni V1.2 Şeması
    cursor.execute("DROP TABLE IF EXISTS employers_v1_2")
    cursor.execute("""
    CREATE TABLE employers_v1_2 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employer_id TEXT UNIQUE NOT NULL,
        profession_id TEXT NOT NULL,
        city TEXT NOT NULL,
        district TEXT,
        name TEXT NOT NULL,
        employer_type TEXT,
        address TEXT,
        phone TEXT,
        phone_type TEXT DEFAULT 'unknown',
        phone_source_url TEXT,
        phone_verification_status TEXT DEFAULT 'unverified',
        email TEXT,
        email_type TEXT DEFAULT 'unknown',
        email_source_url TEXT,
        email_verification_status TEXT DEFAULT 'unverified',
        website TEXT,
        website_source_url TEXT,
        website_verification_status TEXT DEFAULT 'unverified',
        career_url TEXT,
        source_urls TEXT,
        source_type TEXT,
        business_status TEXT DEFAULT 'active',
        research_status TEXT DEFAULT 'pending',
        confidence_score INTEGER DEFAULT 50,
        confidence_level TEXT DEFAULT 'Orta',
        is_email_found INTEGER DEFAULT 0,
        source_last_checked TEXT,
        contact_last_verified TEXT,
        observed_at TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """)

    for r in unified_records:
        cursor.execute("""
        INSERT INTO employers_v1_2 (
            employer_id, profession_id, city, district, name, employer_type,
            address, phone, phone_type, phone_source_url, phone_verification_status,
            email, email_type, email_source_url, email_verification_status,
            website, website_source_url, website_verification_status, career_url,
            source_urls, source_type, business_status, research_status,
            confidence_score, confidence_level, is_email_found,
            source_last_checked, contact_last_verified, observed_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            r["employer_id"],
            r.get("profession_id", "dentist"),
            r.get("city", "Eskişehir"),
            r.get("district", ""),
            r.get("name", ""),
            r.get("employer_type", "Genel İşveren"),
            r.get("address", ""),
            r.get("phone", ""),
            r.get("phone_type", "unknown"),
            r.get("phone_source_url", ""),
            r.get("phone_verification_status", "unverified"),
            r.get("email", ""),
            r.get("email_type", "unknown"),
            r.get("email_source_url", ""),
            r.get("email_verification_status", "unverified"),
            r.get("website", ""),
            r.get("website_source_url", ""),
            r.get("website_verification_status", "unverified"),
            r.get("career_url", ""),
            r.get("source_urls", ""),
            r.get("source_type", ""),
            r.get("business_status", "active"),
            r.get("research_status", "pending"),
            r.get("confidence_score", 50),
            r.get("confidence_level", "Orta"),
            1 if (r.get("email") or "").strip() else 0,
            r.get("source_last_checked", today_str),
            r.get("contact_last_verified"),
            r.get("observed_at", today_str),
            now_str,
            now_str
        ))

    # Eski tabloyu yenisiyle değiştir
    cursor.execute("DROP TABLE employers")
    cursor.execute("ALTER TABLE employers_v1_2 RENAME TO employers")

    # İndeksleri kur
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_emp_uid ON employers(employer_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_emp_prof_city ON employers(profession_id, city)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_emp_district ON employers(district)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_emp_phone_verif ON employers(phone_verification_status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_emp_email_verif ON employers(email_verification_status)")

    # Audit logları ekle
    for entry in audit_entries:
        cursor.execute("""
        INSERT INTO employer_audit_log (employer_id, field_name, old_value, new_value, source, changed_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, entry)

    cursor.execute("SELECT COUNT(*) FROM employers")
    final_count = cursor.fetchone()[0]

    cursor.execute("SELECT employer_type, COUNT(*) FROM employers GROUP BY employer_type")
    type_counts = dict(cursor.fetchall())

    cursor.execute("SELECT phone_verification_status, COUNT(*) FROM employers GROUP BY phone_verification_status")
    phone_verif = dict(cursor.fetchall())

    cursor.execute("SELECT email_verification_status, COUNT(*) FROM employers GROUP BY email_verification_status")
    email_verif = dict(cursor.fetchall())

    conn.commit()
    conn.close()

    print("\n=== Migrasyon Tamamlandı! ===")
    print(f"Migrasyon Öncesi Kayıt Sayısı : {initial_count}")
    print(f"Migrasyon Sonrası Tekil Kayıt : {final_count}")
    print(f"Birleştirilen Mükerrer Sayısı : {initial_count - final_count}")
    print(f"Kurum Türü Dağılımı           : {type_counts}")
    print(f"Telefon Doğrulama Durumları   : {phone_verif}")
    print(f"E-posta Doğrulama Durumları   : {email_verif}")

if __name__ == "__main__":
    run_migration()

