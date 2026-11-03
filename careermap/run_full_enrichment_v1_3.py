"""CareerMap V1.3 Tüm 220 İşletme Envanterinde İletişim Keşif ve Zenginleştirme Betiği.
- TDB Kuyruğu: Henüz telefonu doğrulanmamış hekimleri sorgular (token bazlı ad-soyad teyidi).
- Web Sitesi Keşfi: Web sitesi eksik veya doğrulanmamış poliklinik ve hekimleri araştırır.
- Web İletişim & Form: JSON-LD (@graph), form (<form>) ve e-postaları ayıklar.
- Kalıcı DB Kaydı: employers ve employer_contacts tablolarını günceller.
- 7 Sekmeli Excel: test_output.xlsx dosyasını üretir.
"""
import sys
import io
import time
import sqlite3
from pathlib import Path
from datetime import datetime
import requests

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from app.database.db import get_connection, upsert_employer, canonical_id
from app.discovery.tdb_source import query_tdb_dentist
from app.enrichment.website_discovery import discover_website_for_employer
from app.enrichment.email_extractor import extract_contact_from_website
from app.enrichment.phone_extractor import format_phone
from app.matching.confidence import assess_records_quality
from app.exports.excel_exporter import generate_careermap_excel
from app.professions.registry import ProfessionRegistry

def main():
    print("=" * 70)
    print("CareerMap V1.3 - 220 İşletmelik Tam Envanter Taraması Başlatılıyor")
    print("=" * 70)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM employers ORDER BY id ASC")
    employers = [dict(r) for r in cursor.fetchall()]
    conn.close()

    total = len(employers)
    print(f"Veritabanından {total} kayıt yüklendi.")

    # V1.2 Başlangıç Metrikleri
    old_phones = sum(1 for r in employers if (r.get("phone") or "").strip())
    old_emails = sum(1 for r in employers if (r.get("email") or "").strip())
    old_websites = sum(1 for r in employers if (r.get("website") or "").strip())
    old_forms = sum(1 for r in employers if (r.get("contact_form_url") or "").strip())

    print(f"V1.2 Başlangıç Durumu:")
    print(f" - Telefon: {old_phones} (%{(old_phones/total*100):.1f})")
    print(f" - E-posta: {old_emails} (%{(old_emails/total*100):.1f})")
    print(f" - Web Sitesi: {old_websites} (%{(old_websites/total*100):.1f})")
    print(f" - İletişim Formu: {old_forms}")

    tdb_session = requests.Session()
    web_session = requests.Session()

    tdb_lookups = 0
    web_disc_count = 0
    web_crawl_count = 0

    new_phones = 0
    new_emails = 0
    new_websites = 0
    new_forms = 0

    today_str = datetime.now().strftime("%Y-%m-%d")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("\n1. Aşama: TDB Sicil Kuyruğu ve Web Keşif Analizi Yürütülüyor...")
    for idx, r in enumerate(employers, 1):
        r.setdefault("contacts", [])
        name = r["name"]
        emp_type = r.get("employer_type", "")
        phone = (r.get("phone") or "").strip()
        email = (r.get("email") or "").strip()
        web = (r.get("website") or "").strip()
        form = (r.get("contact_form_url") or "").strip()

        # 1. TDB Kuyruğu: Muayenehane olup telefonu olmayan veya doğrulanmamış olanlar
        is_office = "muayenehane" in emp_type.lower() or name.startswith("Dt")
        if is_office and (not phone or r.get("phone_verification_status") != "verified"):
            tdb_data = query_tdb_dentist(name, "Eskişehir", tdb_session)
            tdb_lookups += 1
            if tdb_data:
                if tdb_data.get("phone") and not phone:
                    formatted_p = format_phone(tdb_data["phone"])
                    r["phone"] = formatted_p
                    r["phone_source_url"] = tdb_data["source_url"]
                    r["phone_type"] = "personal_registry"
                    r["phone_verification_status"] = tdb_data.get("verification_status", "verified")
                    new_phones += 1
                elif tdb_data.get("verification_status") == "manual_review":
                    r["phone_verification_status"] = "manual_review"
            time.sleep(0.08)

        # 2. Web Sitesi Keşfi: Web sitesi olmayanlar
        if not web or r.get("website_verification_status") != "verified":
            disc = discover_website_for_employer(r, web_session)
            if disc:
                r["website"] = disc["website"]
                r["website_source_url"] = disc["website_source_url"]
                r["website_verification_status"] = disc["status"]
                web = disc["website"]
                new_websites += 1
                web_disc_count += 1
            time.sleep(0.08)

        # 3. Web İletişim & Form Çıkarma
        if web:
            try:
                c_info = extract_contact_from_website(web, web_session)
                web_crawl_count += 1
                if c_info.get("email") and not email:
                    r["email"] = c_info["email"]
                    r["email_type"] = c_info.get("email_type", "general")
                    r["email_source_url"] = c_info["email_source_url"]
                    r["email_verification_status"] = "verified"
                    new_emails += 1
                if c_info.get("career_url") and not r.get("career_url"):
                    r["career_url"] = c_info["career_url"]
                if c_info.get("contact_form_url") and not form:
                    r["contact_form_url"] = c_info["contact_form_url"]
                    new_forms += 1
                if c_info.get("phone") and not r.get("phone"):
                    r["phone"] = format_phone(c_info["phone"])
                    r["phone_type"] = "corporate"
                    r["phone_source_url"] = c_info["phone_source_url"]
                    r["phone_verification_status"] = "verified"
                    new_phones += 1
                if c_info.get("contacts"):
                    r["contacts"].extend(c_info["contacts"])
            except Exception as e:
                pass
            time.sleep(0.05)

        if idx % 25 == 0 or idx == total:
            print(f"[{idx}/{total}] işveren tarandı... (Yeni Tel: {new_phones}, Yeni Web: {new_websites}, Yeni E-posta: {new_emails}, Yeni Form: {new_forms})")

    # Kalite Değerlendirmesi
    prof = ProfessionRegistry.get("dentist")
    assessed = assess_records_quality(employers, prof)

    # Kalıcı Kayıt (UPSERT)
    print("\n2. Aşama: Veritabanı ve employer_contacts Tablosu Güncelleniyor...")
    conn = get_connection()
    cursor = conn.cursor()
    for r in assessed:
        upsert_employer(cursor, r, "dentist", "Eskişehir", today_str, now_str)
    conn.commit()

    # İstatistikler
    cursor.execute("SELECT COUNT(*) FROM employers")
    db_total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM employers WHERE phone != ''")
    db_phones = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM employers WHERE email != ''")
    db_emails = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM employers WHERE website != ''")
    db_websites = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM employers WHERE contact_form_url != ''")
    db_forms = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM employer_contacts")
    db_contacts = cursor.fetchone()[0]
    conn.close()

    print("\n" + "=" * 70)
    print("V1.3 TÜM ENVANTER SONUÇLARI:")
    print(f"Toplam İşveren          : {db_total}")
    print(f"Telefon Bulunanlar      : V1.2={old_phones} (%{(old_phones/total*100):.1f}) -> V1.3={db_phones} (%{(db_phones/total*100):.1f})")
    print(f"E-posta Bulunanlar      : V1.2={old_emails} (%{(old_emails/total*100):.1f}) -> V1.3={db_emails} (%{(db_emails/total*100):.1f})")
    print(f"Web Sitesi Bulunanlar   : V1.2={old_websites} (%{(old_websites/total*100):.1f}) -> V1.3={db_websites} (%{(db_websites/total*100):.1f})")
    print(f"İletişim Formu          : V1.2={old_forms} -> V1.3={db_forms} doğrudan form kanalı")
    print(f"employer_contacts Kaydı : {db_contacts} adet tekil iletişim kaydı")
    print("=" * 70)

    # Excel Oluştur
    print("\n3. Aşama: test_output.xlsx (7 Sekmeli) Dosyası Üretiliyor...")
    excel_buf = generate_careermap_excel(assessed, "Diş Hekimi", "Eskişehir")
    out_excel = ROOT_DIR / "test_output.xlsx"
    with open(out_excel, "wb") as f:
        f.write(excel_buf.getvalue())
    print(f"Excel başarıyla kaydedildi: {out_excel} ({out_excel.stat().st_size / 1024:.1f} KB)")

if __name__ == "__main__":
    main()

