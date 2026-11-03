"""CareerMap V1.4-A — 220 İşletmelik Tüm Envanter İletişim İstihbaratı ve Zenginleştirme Betiği.
- Çok Kaynaklı Araştırma: TDB Resmî Kamusal Sicil + OSM + Canlı Web İstihbaratı.
- Kimlik ve Sektör Doğrulaması (`website_identity_matcher`): Yanlış domain ve park siteleri engellenir.
- Standart Telefon Normalizasyonu (`phonenumbers`): 0(222) sabit hat ve 0(5XX) mobil ayrımı.
- Çok Biçimli E-posta Çıkarma: JSON-LD, microdata, obfuskasyon, kariyer önceliği.
- Form Ayrıştırma: İletişim/Kariyer Formu vs Hasta Randevu Formu.
- Kanıt İzleri & Şeffaf Gerekçeler: Her temas için discovery_method ve evidence_text;
  bulunamayanlar için attempted_sources ve research_notes.
- 7 Sekmeli Excel Çıktısı: test_output.xlsx
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
from app.enrichment.website_discovery import discover_and_extract_website_contacts
from app.enrichment.phone_extractor import format_phone
from app.matching.confidence import assess_records_quality
from app.exports.excel_exporter import generate_careermap_excel
from app.professions.registry import ProfessionRegistry

def main():
    print("=" * 80)
    print("CareerMap V1.4-A — 220 İşletmelik Tüm Envanter İstihbarat Taraması Başlatılıyor")
    print("=" * 80)

    start_time = datetime.now()
    today_str = start_time.strftime("%Y-%m-%d")
    now_str = start_time.strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM employers ORDER BY id ASC")
    employers = [dict(r) for r in cursor.fetchall()]
    conn.close()

    total = len(employers)
    print(f"Veritabanından {total} kayıt yüklendi.")

    # Başlangıç Metrikleri
    old_phones = sum(1 for r in employers if (r.get("phone") or "").strip())
    old_emails = sum(1 for r in employers if (r.get("email") or "").strip())
    old_websites = sum(1 for r in employers if (r.get("website") or "").strip())
    old_forms = sum(1 for r in employers if (r.get("contact_form_url") or "").strip())

    print(f"V1.3 / Mevcut Durum:")
    print(f" - Telefon       : {old_phones} (%{(old_phones/total*100):.1f})")
    print(f" - E-posta       : {old_emails} (%{(old_emails/total*100):.1f})")
    print(f" - Web Sitesi    : {old_websites} (%{(old_websites/total*100):.1f})")
    print(f" - İletişim Formu: {old_forms}")

    tdb_session = requests.Session()
    web_session = requests.Session()

    tdb_lookups = 0
    web_lookups = 0

    new_phones = 0
    new_emails = 0
    new_websites = 0
    new_forms = 0

    print("\n1. Aşama: Çok Kaynaklı Zenginleştirme ve Kanıt Çıkarma Yürütülüyor...")

    for idx, r in enumerate(employers, 1):
        r.setdefault("contacts", [])
        name = r["name"]
        emp_type = r.get("employer_type", "")
        phone = (r.get("phone") or "").strip()
        email = (r.get("email") or "").strip()
        web = (r.get("website") or "").strip()
        form = (r.get("contact_form_url") or "").strip()
        
        attempted = [a.strip() for a in (r.get("attempted_sources") or "Resmî Kurum Portalı").split(",") if a.strip()]
        notes = []
        if r.get("research_notes"):
            notes.append(r["research_notes"].strip("; "))

        # 1. TDB Kuyruğu: Muayenehane olup telefonu olmayan veya doğrulanmamış olanlar
        is_office = "muayenehane" in emp_type.lower() or name.startswith("Dt")
        if is_office and (not phone or r.get("phone_verification_status") != "verified"):
            if "TDB Sicil" not in attempted:
                attempted.append("TDB Sicil")
            tdb_data = query_tdb_dentist(name, "Eskişehir", tdb_session)
            tdb_lookups += 1
            if tdb_data:
                if tdb_data.get("phone"):
                    formatted_p = format_phone(tdb_data["phone"])
                    r["phone"] = formatted_p
                    r["phone_source_url"] = tdb_data["source_url"]
                    r["phone_type"] = "personal_registry"
                    r["phone_verification_status"] = tdb_data.get("verification_status", "verified")
                    r["contacts"].append({
                        "contact_type": "phone",
                        "contact_value": formatted_p,
                        "contact_category": "personal_registry",
                        "source_url": tdb_data["source_url"],
                        "source_type": "tdb",
                        "discovery_method": "tdb_registry",
                        "evidence_text": "TDB Sicil Oda Kaydı (Tam hekim ad-soyad teyitli)",
                        "confidence_category": "kaynakli",
                        "verification_status": "verified"
                    })
                    notes.append("TDB'den resmî oda sicil telefonu doğrulandı.")
                    if not phone:
                        new_phones += 1
                elif tdb_data.get("verification_status") == "manual_review":
                    r["phone_verification_status"] = "manual_review"
                    notes.append("TDB: Çoklu aynı isimli hekim, manuel inceleme gerekiyor.")
            else:
                notes.append("TDB: Açık sicil kaydı bulunamadı.")
            time.sleep(0.05)

        # 2. V1.4 Web İstihbaratı (Kimlik Eşleştirme + Saygılı Tarama + Form Ayrımı)
        if "Web Keşfi" not in attempted:
            attempted.append("Web Keşfi")
        web_lookups += 1
        
        web_data = discover_and_extract_website_contacts(r, web_session)
        if web_data.get("website"):
            if not web or web != web_data["website"]:
                r["website"] = web_data["website"]
                r["website_source_url"] = web_data["website_source_url"]
                r["website_verification_status"] = web_data["website_verification_status"]
                if not web:
                    new_websites += 1
            
            if web_data.get("contact_form_url") and not form:
                r["contact_form_url"] = web_data["contact_form_url"]
                new_forms += 1
            if web_data.get("career_url") and not r.get("career_url"):
                r["career_url"] = web_data["career_url"]
            if web_data.get("contacts"):
                r["contacts"].extend(web_data["contacts"])

                # E-posta seçimi (kariyer öncelikli)
                web_emails = [c for c in web_data["contacts"] if c["contact_type"] == "email"]
                if web_emails and not email:
                    web_emails.sort(key=lambda x: (x.get("contact_category") != "career", x.get("contact_category") != "general"))
                    best_e = web_emails[0]
                    r["email"] = best_e["contact_value"]
                    r["email_type"] = best_e.get("contact_category", "general")
                    r["email_source_url"] = best_e.get("source_url", "")
                    r["email_verification_status"] = "verified"
                    new_emails += 1

                # Telefon seçimi (eğer yoksa kurumsal web sitesi santrali)
                web_phones = [c for c in web_data["contacts"] if c["contact_type"] == "phone"]
                if web_phones and not r.get("phone"):
                    best_p = web_phones[0]
                    r["phone"] = best_p["contact_value"]
                    r["phone_type"] = best_p.get("contact_category", "corporate")
                    r["phone_source_url"] = best_p.get("source_url", "")
                    r["phone_verification_status"] = "verified"
                    new_phones += 1

            if web_data.get("research_notes"):
                notes.append(web_data["research_notes"])

        elif web_data.get("research_notes"):
            notes.append(web_data["research_notes"])

        r["attempted_sources"] = ", ".join(attempted)
        r["research_notes"] = "; ".join(dict.fromkeys(notes))  # Tekilleştirip birleştir

        if idx % 20 == 0 or idx == total:
            print(f"[{idx:03d}/{total}] işveren tamamlandı... (Yeni Tel: {new_phones}, Yeni Web: {new_websites}, Yeni E-posta: {new_emails}, Yeni Form: {new_forms})")

    # 3. Aşama: Alan Bazlı Kalite Değerlendirmesi
    prof = ProfessionRegistry.get("dentist")
    assessed = assess_records_quality(employers, prof)

    # 4. Aşama: Kalıcı Kayıt (employers, employer_contacts, employer_audit_log)
    print("\n2. Aşama: Veritabanı ve employer_contacts Tablosu Kalıcı Olarak Güncelleniyor...")
    conn = get_connection()
    cursor = conn.cursor()
    for r in assessed:
        upsert_employer(cursor, r, "dentist", "Eskişehir", today_str, now_str)
    conn.commit()

    # İstatistikleri Doğrudan SQLite'dan Al
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
    cursor.execute("SELECT COUNT(*) FROM employer_contacts WHERE discovery_method != 'unknown'")
    db_evidenced_contacts = cursor.fetchone()[0]
    conn.close()

    total_duration = (datetime.now() - start_time).total_seconds()

    print("\n" + "=" * 80)
    print(f"V1.4 TÜM ENVANTER SONUÇLARI (Tamamlanma Süresi: {total_duration:.1f} sn):")
    print(f"Toplam İşveren          : {db_total}")
    print(f"Telefon Bulunanlar      : V1.3={old_phones} (%{(old_phones/total*100):.1f}) -> V1.4={db_phones} (%{(db_phones/total*100):.1f})")
    print(f"E-posta Bulunanlar      : V1.3={old_emails} (%{(old_emails/total*100):.1f}) -> V1.4={db_emails} (%{(db_emails/total*100):.1f})")
    print(f"Web Sitesi Bulunanlar   : V1.3={old_websites} (%{(old_websites/total*100):.1f}) -> V1.4={db_websites} (%{(db_websites/total*100):.1f})")
    print(f"İletişim / Başvuru Formu: V1.3={old_forms} -> V1.4={db_forms} doğrudan form kanalı")
    print(f"employer_contacts Kaydı : {db_contacts} adet tekil temas noktası")
    print(f"Kanıtlı Kontak Kayıtları: {db_evidenced_contacts} adet")
    print("=" * 80)

    # 5. Aşama: 7 Sekmeli Excel'i Güncelle
    print("\n3. Aşama: test_output.xlsx Dosyası Üretiliyor...")
    excel_buf = generate_careermap_excel(assessed, "Diş Hekimi", "Eskişehir")
    out_excel = ROOT_DIR / "test_output.xlsx"
    with open(out_excel, "wb") as f:
        f.write(excel_buf.getvalue())
    print(f"Excel başarıyla kaydedildi: {out_excel} ({out_excel.stat().st_size / 1024:.1f} KB)")

if __name__ == "__main__":
    main()

