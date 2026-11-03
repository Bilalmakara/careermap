"""CareerMap V1.4-A Kontrollü Pilot Karşılaştırma Testi.
- 12 Özel Diş Polikliniği
- 12 Bireysel Diş Hekimi Muayenehanesi (Toplam 24 İşletme)
Ölçülen kabiliyetler:
1. Alan adı tahmini yerine kimlik ve sektör eşleştirme doğrulaması (`website_identity_matcher`).
2. Google `phonenumbers` kütüphanesiyle standart telefon normalizasyonu (`0(222) XXX XX XX` ve `0(5XX) XXX XX XX`).
3. Çok sayfalı tarama ile İletişim Formu vs Hasta Randevu Formu ayrımı.
4. Çok biçimli e-posta çıkarma (mailto, microdata, obfuskasyon, JSON-LD) ve kariyer önceliği.
5. Her iletişim bilgisi için kanıt izi (`discovery_method`, `evidence_text`, `confidence_category`).
6. Bulunamayan iletişim bilgileri için şeffaf araştırma notu ve denenen kaynaklar.
"""
import sys
import json
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from app.services.scanner import run_pilot_v1_4

def main():
    print("=" * 80)
    print("CareerMap V1.4-A — 24 İşletmelik Pilot Karşılaştırma Testi Başlatılıyor")
    print("=" * 80)
    
    start_time = datetime.now()
    results = run_pilot_v1_4(sample_size_clinics=12, sample_size_offices=12, city="Eskişehir")
    duration = (datetime.now() - start_time).total_seconds()
    
    base = results["baseline_stats"]
    v14 = results["v1_4_stats"]
    diffs = results["audit_diffs"]
    
    print("\n" + "=" * 80)
    print(f"PILOT METRİK ÖZETİ (Tamamlanma Süresi: {duration:.1f} sn)")
    print("=" * 80)
    print(f"Araştırılan Toplam İşveren : {base['total_records']} (12 Poliklinik + 12 Bireysel Muayenehane)")
    print(f"Telefon Bulunanlar         : Önce={base['phones']} ({base['phones']/base['total_records']*100:.1f}%) -> V1.4={v14['phones']} ({v14['phones']/base['total_records']*100:.1f}%)")
    print(f"E-posta Bulunanlar         : Önce={base['emails']} ({base['emails']/base['total_records']*100:.1f}%) -> V1.4={v14['emails']} ({v14['emails']/base['total_records']*100:.1f}%)")
    print(f"Web Sitesi Bulunanlar      : Önce={base['websites']} ({base['websites']/base['total_records']*100:.1f}%) -> V1.4={v14['websites']} ({v14['websites']/base['total_records']*100:.1f}%)")
    print(f"İletişim Formu Bulunanlar  : Önce={base['contact_forms']} -> V1.4={v14['contact_forms']}")
    print(f"İletişim Verisi Zenginleşen: {results['improved_count']} / {base['total_records']} (%{results['improved_count']/base['total_records']*100:.1f})")

    print("\n" + "=" * 80)
    print("DETAYLI İŞLETME İNCELEMESİ (KANITLAR VE GEREKÇELER)")
    print("=" * 80)
    for idx, d in enumerate(diffs, 1):
        status_tag = "[GELİŞTİRİLDİ]" if d["is_improved"] else "[DEĞİŞMEDİ]"
        print(f"\n{idx:02d}. {d['name']} [{d['employer_type']} - {d['district']}] {status_tag}")
        print(f"    Telefon       : {d['old_phone'] or '---'}  -->  {d['new_phone'] or '---'}")
        print(f"    E-posta       : {d['old_email'] or '---'}  -->  {d['new_email'] or '---'}")
        print(f"    Web Sitesi    : {d['old_website'] or '---'}  -->  {d['new_website'] or '---'}")
        print(f"    İletişim Formu: {d['old_contact_form'] or '---'}  -->  {d['new_contact_form'] or '---'}")
        print(f"    Kontak Sayısı : {d.get('contacts_count', 0)} adet kanıtlı kayıt")
        print(f"    Kaynaklar     : {d.get('attempted_sources', '---')}")
        print(f"    Araştırma Notu: {d.get('research_notes', 'Bilgi bulunamadı.')}")

    # JSON Çıktısını Kaydet
    output_path = ROOT_DIR / "pilot_comparison_v1_4.json"
    results["metadata"] = {
        "generated_at": datetime.now().isoformat(),
        "duration_seconds": duration,
        "version": "CareerMap V1.4-A Contact Intelligence"
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n[OK] Pilot analiz verileri JSON dosyasına kaydedildi: {output_path}")

if __name__ == "__main__":
    main()

