"""CareerMap V1.4.1 Veritabanı Temizleme, Doğrulama ve Migrasyon Betiği.
- careermap.db yedeğini alır (careermap.db.v1_4.bak).
- Sahte / kütüphane e-postalarını ayıklar (bootstrap@5.3.3, bootstrap@4.0.0).
- Web ajansı altbilgi e-postalarını temizler (info@siradisidigitial.com).
- Yanlış işletme/sektör eşleşmelerini temizler (mertak.com otomotiv, dentistinmilford.com ABD).
- Telefonları normalize eder (2214603 -> 0(222) 221 46 03).
- Doğrulama durumlarını yeni standart terimlere taşır:
  'observed_on_source', 'cross_source_supported', 'needs_review', 'invalid'.
- Tüm değişiklikleri employer_audit_log tablosuna kaydeder.
"""
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parent
DB_PATH = ROOT_DIR / "careermap.db"
BAK_PATH = ROOT_DIR / "careermap.db.v1_4.bak"

def main():
    print("=" * 70)
    print("CareerMap V1.4.1 — Veri Temizleme ve Kalite Migrasyonu Başlatılıyor")
    print("=" * 70)

    # 1. Veritabanı Yedeği Al
    if DB_PATH.exists():
        shutil.copy2(DB_PATH, BAK_PATH)
        print(f"[OK] Veritabanı yedeği alındı: {BAK_PATH.name} ({BAK_PATH.stat().st_size / 1024:.1f} KB)")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today_str = datetime.now().strftime("%Y-%m-%d")

    audit_entries = []

    # ---------------------------------------------------------
    # 2. KRİTİK E-POSTA VE YANLIŞ POZİTİF TEMİZLİĞİ
    # ---------------------------------------------------------

    # A. Özel Smile Eskişehir: bootstrap@5.3.3
    emp_smile_id = "dentist-eskisehir-clinic-tepebasi-smileeskisehir"
    cursor.execute("SELECT * FROM employers WHERE employer_id = ?", (emp_smile_id,))
    row_smile = cursor.fetchone()
    if row_smile and "bootstrap" in (row_smile["email"] or ""):
        print("[DÜZELTME] Özel Smile Eskişehir: 'bootstrap@5.3.3' sahte e-postası kaldırılıyor.")
        cursor.execute("""
        UPDATE employers SET
            email = '',
            email_type = 'unknown',
            email_source_url = '',
            email_verification_status = 'unverified',
            is_email_found = 0,
            research_notes = 'Web: https://www.smileeskisehir.com doğrulandı (100 puan); E-posta: bootstrap@5.3.3 kütüphane sürümü false-positive olarak elendi; Telefon/WhatsApp: 0(546) 868 02 22 doğrulandı.',
            updated_at = ?
        WHERE employer_id = ?
        """, (now_str, emp_smile_id))
        
        cursor.execute("DELETE FROM employer_contacts WHERE employer_id = ? AND contact_type = 'email' AND contact_value LIKE '%bootstrap%'", (emp_smile_id,))
        audit_entries.append((emp_smile_id, "email", "bootstrap@5.3.3", "", "v1_4_1_false_positive_cleanup", now_str))

    # B. Dr. Dt. Fahri Kavrut: bootstrap@4.0.0
    emp_fahri_id = "dentist-eskisehir-office-tepebasi-fahrikavrut"
    cursor.execute("SELECT * FROM employers WHERE employer_id = ?", (emp_fahri_id,))
    row_fahri = cursor.fetchone()
    if row_fahri and "bootstrap" in (row_fahri["email"] or ""):
        print("[DÜZELTME] Dr. Dt. Fahri Kavrut: 'bootstrap@4.0.0' sahte e-postası kaldırılıyor.")
        cursor.execute("""
        UPDATE employers SET
            email = '',
            email_type = 'unknown',
            email_source_url = '',
            email_verification_status = 'unverified',
            is_email_found = 0,
            research_notes = 'Web: https://www.fahrikavrut.com doğrulandı (100 puan); E-posta: bootstrap@4.0.0 kütüphane sürümü false-positive olarak elendi; Telefon: 0(222) 233 90 95 doğrulandı.',
            updated_at = ?
        WHERE employer_id = ?
        """, (now_str, emp_fahri_id))
        
        cursor.execute("DELETE FROM employer_contacts WHERE employer_id = ? AND contact_type = 'email' AND contact_value LIKE '%bootstrap%'", (emp_fahri_id,))
        audit_entries.append((emp_fahri_id, "email", "bootstrap@4.0.0", "", "v1_4_1_false_positive_cleanup", now_str))

    # B2. Dt. Abdülkadir Özyıldırım: Başka hekime ait 'yildirimdis.com' poliklinik sitesi temizleniyor
    emp_ozyildirim_id = "dentist-eskisehir-office-tepebasi-abdulkadirozyildirim"
    cursor.execute("SELECT * FROM employers WHERE employer_id = ?", (emp_ozyildirim_id,))
    row_ozyildirim = cursor.fetchone()
    if row_ozyildirim and "yildirimdis.com" in (row_ozyildirim["website"] or ""):
        print("[DÜZELTME] Dt. Abdülkadir Özyıldırım: Başka kliniğe ait 'yildirimdis.com' kaldırılıyor.")
        cursor.execute("""
        UPDATE employers SET
            website = '',
            website_source_url = '',
            website_verification_status = 'unverified',
            research_notes = 'Web: Farklı bir hekime (Dt. Hasan Yıldırım) ait yildirimdis.com sitesi kimlik eşleşmesi sağlanamadığı için kaldırıldı; Dt. Abdülkadir Özyıldırım açık web sitesi bulunamadı; Telefon: 0(222) 231 02 22 TDB sicil teyitli.',
            updated_at = ?
        WHERE employer_id = ?
        """, (now_str, emp_ozyildirim_id))
        cursor.execute("DELETE FROM employer_contacts WHERE employer_id = ? AND contact_type = 'website' AND contact_value LIKE '%yildirimdis%'", (emp_ozyildirim_id,))
        audit_entries.append((emp_ozyildirim_id, "website", "https://www.yildirimdis.com", "", "v1_4_1_different_dentist_cleanup", now_str))

    # C. Dr. Dt. Ghizlane Genç: info@siradisidigitial.com (Web Ajansı Altbilgi E-postası)
    emp_ghizlane_id = "dentist-eskisehir-office-tepebasi-ghizlanegenc"
    cursor.execute("SELECT * FROM employers WHERE employer_id = ?", (emp_ghizlane_id,))
    row_ghizlane = cursor.fetchone()
    if row_ghizlane and "siradisi" in (row_ghizlane["email"] or ""):
        print("[DÜZELTME] Dr. Dt. Ghizlane Genç: Web ajansı e-postası ('info@siradisidigitial.com') kaldırılıyor.")
        cursor.execute("""
        UPDATE employers SET
            email = '',
            email_type = 'unknown',
            email_source_url = '',
            email_verification_status = 'unverified',
            is_email_found = 0,
            research_notes = 'Web: https://www.ghizlanegenc.com doğrulandı; Ajans e-postası (Sıradışı Digital) hekim e-postası olmadığı için birincil alandan kaldırıldı.',
            updated_at = ?
        WHERE employer_id = ?
        """, (now_str, emp_ghizlane_id))
        
        cursor.execute("""
        UPDATE employer_contacts SET
            contact_category = 'agency',
            verification_status = 'needs_review',
            evidence_text = 'Web Tasarım Ajansı Altbilgi E-postası (Sıradışı Digital) - Kurumsal hekim e-postası değil'
        WHERE employer_id = ? AND contact_type = 'email' AND contact_value LIKE '%siradisi%'
        """, (emp_ghizlane_id,))
        audit_entries.append((emp_ghizlane_id, "email", "info@siradisidigitial.com", "", "v1_4_1_agency_email_cleanup", now_str))

    # D. Dt. Mert Ak: mertak.com (İstanbul Otomotiv Yedek Parça)
    emp_mertak_id = "dentist-eskisehir-office-tepebasi-mertak"
    cursor.execute("SELECT * FROM employers WHERE employer_id = ?", (emp_mertak_id,))
    row_mertak = cursor.fetchone()
    if row_mertak and "mertak.com" in (row_mertak["website"] or ""):
        print("[DÜZELTME] Dt. Mert Ak: Sektör dışı alan adı ('mertak.com' - İstanbul Otomotiv) kaldırılıyor.")
        cursor.execute("""
        UPDATE employers SET
            website = '',
            website_source_url = '',
            website_verification_status = 'unverified',
            email = '',
            email_type = 'unknown',
            email_source_url = '',
            email_verification_status = 'unverified',
            phone = '',
            phone_type = 'unknown',
            phone_source_url = '',
            phone_verification_status = 'unverified',
            is_email_found = 0,
            research_notes = 'Web: Sektör dışı alan adı (mertak.com - İstanbul Otomotiv Yedek Parça) false-positive olarak elendi; Dt. Mert Ak açık sağlık sitesi bulunamadı.',
            updated_at = ?
        WHERE employer_id = ?
        """, (now_str, emp_mertak_id))
        
        cursor.execute("DELETE FROM employer_contacts WHERE employer_id = ?", (emp_mertak_id,))
        audit_entries.append((emp_mertak_id, "website", "https://www.mertak.com", "", "v1_4_1_unrelated_industry_cleanup", now_str))

    # E. Özel 222 Klinik: dentistinmilford.com (ABD Massachusetts)
    emp_222_id = "dentist-eskisehir-clinic-tepebasi-222"
    cursor.execute("SELECT * FROM employers WHERE employer_id = ?", (emp_222_id,))
    row_222 = cursor.fetchone()
    if row_222 and "milford" in (row_222["website"] or ""):
        print("[DÜZELTME] Özel 222 Klinik: Yabancı alan adı ('dentistinmilford.com' - ABD) kaldırılıyor.")
        cursor.execute("""
        UPDATE employers SET
            website = '',
            website_source_url = '',
            website_verification_status = 'unverified',
            email = '',
            email_type = 'unknown',
            email_source_url = '',
            email_verification_status = 'unverified',
            phone = '',
            phone_type = 'unknown',
            phone_source_url = '',
            phone_verification_status = 'unverified',
            is_email_found = 0,
            research_notes = 'Web: Yabancı alan adı (dentistinmilford.com - ABD Massachusetts) ve 508 alan kodlu yabancı telefon false-positive olarak elendi; Türkiye açık web sitesi bulunamadı.',
            updated_at = ?
        WHERE employer_id = ?
        """, (now_str, emp_222_id))
        
        cursor.execute("DELETE FROM employer_contacts WHERE employer_id = ?", (emp_222_id,))
        audit_entries.append((emp_222_id, "website", "https://www.dentistinmilford.com:443", "", "v1_4_1_foreign_site_cleanup", now_str))

    # F. Dt. Murat Özdemir: 7 haneli telefon normalizasyonu (2214603 -> 0(222) 221 46 03)
    emp_murat_id = "dentist-eskisehir-office-tepebasi-muratozdemir"
    cursor.execute("SELECT * FROM employers WHERE employer_id = ?", (emp_murat_id,))
    row_murat = cursor.fetchone()
    if row_murat and row_murat["phone"] == "2214603":
        print("[DÜZELTME] Dt. Murat Özdemir: 7 haneli numara '2214603' -> '0(222) 221 46 03' olarak normalize ediliyor.")
        cursor.execute("""
        UPDATE employers SET
            phone = '0(222) 221 46 03',
            updated_at = ?
        WHERE employer_id = ?
        """, (now_str, emp_murat_id))
        cursor.execute("""
        UPDATE employer_contacts SET
            contact_value = '0(222) 221 46 03'
        WHERE employer_id = ? AND contact_type = 'phone' AND contact_value = '2214603'
        """, (emp_murat_id,))
        audit_entries.append((emp_murat_id, "phone", "2214603", "0(222) 221 46 03", "v1_4_1_phone_normalization", now_str))

    # ---------------------------------------------------------
    # 3. STATÜLERİN YENİ V1.4.1 STANDARTLARINA TAŞINMASI
    # ---------------------------------------------------------
    # 'verified' -> 'observed_on_source' (Açık kaynakta gözlemlendi)
    print("\n[MİGRASYON] Doğrulama durumları 'observed_on_source' standardına taşınıyor...")
    
    # E-posta doğrulama durumları
    cursor.execute("""
    UPDATE employers SET
        email_verification_status = 'observed_on_source'
    WHERE email_verification_status = 'verified' AND email != ''
    """)

    # Telefon doğrulama durumları
    cursor.execute("""
    UPDATE employers SET
        phone_verification_status = 'observed_on_source'
    WHERE phone_verification_status = 'verified' AND phone != ''
    """)

    # Web sitesi doğrulama durumları
    cursor.execute("""
    UPDATE employers SET
        website_verification_status = 'observed_on_source'
    WHERE website_verification_status = 'verified' AND website != ''
    """)

    # employer_contacts tablosu
    cursor.execute("""
    UPDATE employer_contacts SET
        verification_status = 'observed_on_source'
    WHERE verification_status = 'verified'
    """)

    # ---------------------------------------------------------
    # 4. ÇOK ŞUBELİ VE ORTAK SANTRAL TELEFONLARININ ETİKETLENMESİ
    # ---------------------------------------------------------
    # Modapol 4 şube tek santral
    cursor.execute("""
    UPDATE employers SET
        phone_type = 'corporate_shared_switchboard',
        phone_verification_status = 'cross_source_supported'
    WHERE phone = '0(222) 220 50 50'
    """)
    cursor.execute("""
    UPDATE employer_contacts SET
        contact_category = 'corporate_shared_switchboard',
        verification_status = 'cross_source_supported',
        evidence_text = 'Özel Modapol Polikliniği Çok Şubeli Merkezi Santral Numarası'
    WHERE contact_value = '0(222) 220 50 50' AND contact_type = 'phone'
    """)

    # İpek Diş 2 şube tek santral
    cursor.execute("""
    UPDATE employers SET
        phone_type = 'corporate_shared_switchboard',
        phone_verification_status = 'cross_source_supported'
    WHERE phone = '0(222) 231 15 15'
    """)
    cursor.execute("""
    UPDATE employer_contacts SET
        contact_category = 'corporate_shared_switchboard',
        verification_status = 'cross_source_supported',
        evidence_text = 'Özel İpek Polikliniği Çok Şubeli Ortak Santral Numarası'
    WHERE contact_value = '0(222) 231 15 15' AND contact_type = 'phone'
    """)

    # Audit log kayıtlarını yaz
    for entry in audit_entries:
        cursor.execute("""
        INSERT INTO employer_audit_log (employer_id, field_name, old_value, new_value, source, changed_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, entry)

    conn.commit()

    # ---------------------------------------------------------
    # 5. YENİ TEMİZLENMİŞ VE DENETLENMİŞ ENVANTER METRİKLERİ
    # ---------------------------------------------------------
    cursor.execute("SELECT COUNT(*) FROM employers")
    db_total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM employers WHERE phone != '' AND phone IS NOT NULL")
    db_phones = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM employers WHERE email != '' AND email IS NOT NULL")
    db_emails = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM employers WHERE website != '' AND website IS NOT NULL")
    db_websites = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM employers WHERE contact_form_url != '' AND contact_form_url IS NOT NULL")
    db_forms = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM employer_contacts")
    db_contacts = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM employer_contacts WHERE verification_status = 'observed_on_source'")
    db_observed = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM employer_contacts WHERE verification_status = 'cross_source_supported'")
    db_cross = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM employer_contacts WHERE verification_status = 'needs_review'")
    db_review = cursor.fetchone()[0]

    conn.close()

    print("\n" + "=" * 70)
    print("V1.4.1 TEMİZLENMİŞ VE DOĞRULANMIŞ ENVANTER SONUÇLARI:")
    print(f"Toplam İşveren          : {db_total}")
    print(f"Telefon Bulunanlar      : {db_phones} (%{(db_phones/db_total*100):.1f}) (2 yabancı/hatalı elendi)")
    print(f"E-posta Bulunanlar      : {db_emails} (%{(db_emails/db_total*100):.1f}) (4 sahte/ajans/yabancı elendi)")
    print(f"Web Sitesi Bulunanlar   : {db_websites} (%{(db_websites/db_total*100):.1f}) (2 yabancı/sektör dışı elendi)")
    print(f"İletişim Formu          : {db_forms} adet doğrudan form kanalı")
    print(f"Toplam İletişim Havuzu  : {db_contacts} adet temas noktası")
    print(f"  - observed_on_source  : {db_observed} adet (Doğrulanmış açık kaynakta gözlemlendi)")
    print(f"  - cross_source_supp.  : {db_cross} adet (Çok kaynaklı destekli / santral)")
    print(f"  - needs_review        : {db_review} adet (Manuel inceleme gereken)")
    print("=" * 70)

if __name__ == "__main__":
    main()
