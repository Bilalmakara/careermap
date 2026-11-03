"""CareerMap V1.3 - 20 İşletmelik Kontrollü Pilot Karşılaştırma Testi.
- 10 Özel Poliklinik
- 10 Bireysel Muayenehane
V1.2 ile V1.3 arasındaki telefon, e-posta, web sitesi ve iletişim formu keşif farklarını ölçer.
"""
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from app.services.scanner import run_pilot_v1_3

def main():
    print("=" * 70)
    print("CareerMap V1.3 - 20 İşletmelik Pilot Karşılaştırma Başlatılıyor")
    print("=" * 70)

    results = run_pilot_v1_3(sample_size_clinics=10, sample_size_offices=10, city="Eskişehir")

    base = results["baseline_stats"]
    v13 = results["v1_3_stats"]

    print("\n--- ÖZET KARŞILAŞTIRMA METRİKLERİ ---")
    print(f"Araştırılan Toplam İşveren : {base['total_records']} (10 Poliklinik + 10 Muayenehane)")
    print(f"Telefon Bulunanlar         : V1.2={base['phones']} -> V1.3={v13['phones']} (+{results['new_phones_found']} yeni)")
    print(f"E-posta Bulunanlar         : V1.2={base['emails']} -> V1.3={v13['emails']} (+{results['new_emails_found']} yeni)")
    print(f"Web Sitesi Bulunanlar      : V1.2={base['websites']} -> V1.3={v13['websites']} (+{results['new_websites_found']} yeni)")
    print(f"İletişim Formu Bulunanlar  : V1.2={base['contact_forms']} -> V1.3={v13['contact_forms']} (+{results['new_forms_found']} yeni)")

    print("\n--- 20 İŞLETMENİN DETAYLI KARŞILAŞTIRMASI ---")
    improved_count = 0
    for idx, d in enumerate(results["audit_diffs"], 1):
        status_flag = "[GELİŞTİ]" if d["is_improved"] else "[DEĞİŞMEDİ]"
        if d["is_improved"]:
            improved_count += 1
        print(f"\n{idx}. {d['name']} ({d['employer_type']} - {d['district']}) {status_flag}")
        print(f"   Telefon : {d['old_phone'] or 'Yok'} -> {d['new_phone'] or 'Yok'}")
        print(f"   E-posta : {d['old_email'] or 'Yok'} -> {d['new_email'] or 'Yok'}")
        print(f"   Web     : {d['old_website'] or 'Yok'} -> {d['new_website'] or 'Yok'}")
        print(f"   Form    : {d['old_contact_form'] or 'Yok'} -> {d['new_contact_form'] or 'Yok'}")

    print(f"\nToplam Geliştirilen İşletme: {improved_count} / 20")

    # Çıktıyı JSON olarak kaydet
    out_file = ROOT_DIR / "pilot_comparison_v1_3.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nDetaylı pilot verisi kaydedildi: {out_file}")

if __name__ == "__main__":
    main()

