"""CareerMap V1.5 Web Arama Keşif ve Derin İletişim Pilot Karşılaştırma Testi.
- Web sitesi bulunamayan 30 gerçek işletme (7 Poliklinik + 23 Bireysel Muayenehane) üzerinde çalışır.
- FreeSerp tabanlı SearchRouter ve Deep Crawler entegrasyonu ile web sitesi, telefon, e-posta ve kurumsal bağlantıları araştırır.
- Sonuçları pilot_comparison_v1_5.json dosyasına kaydeder.
"""
import sys
import json
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from app.services.scanner import run_pilot_v1_5

def main():
    print("=" * 80)
    print("CareerMap V1.5 — 30 Web Sitesi Eksik İşletmelik Arama Keşif Pilotu Başlatılıyor")
    print("=" * 80)

    start_time = datetime.now()
    results = run_pilot_v1_5(city="Eskişehir", target_count=30)
    duration = (datetime.now() - start_time).total_seconds()

    base = results["baseline_stats"]
    v15 = results["v1_5_stats"]
    diffs = results["audit_diffs"]

    print("\n" + "=" * 80)
    print(f"V1.5 PİLOT METRİK ÖZETİ (Tamamlanma Süresi: {duration:.1f} sn)")
    print("=" * 80)
    print(f"Araştırılan İşletme Sayısı: {base['total_records']} (7 Poliklinik + 23 Bireysel Muayenehane)")
    print(f"Öncesi Web Sitesi         : {base['websites']} / {base['total_records']} (%{base['websites']/base['total_records']*100:.1f})")
    print(f"V1.5 Yeni Web Sitesi      : {v15['websites']} / {base['total_records']} (%{v15['websites']/base['total_records']*100:.1f}) (Net: +{results['new_websites_count']} site)")
    print(f"Telefon Doluluğu          : Önce={base['phones']} (%{base['phones']/base['total_records']*100:.1f}) -> V1.5={v15['phones']} (%{v15['phones']/base['total_records']*100:.1f}) (Net: +{results['new_phones_count']} tel)")
    print(f"E-posta Doluluğu          : Önce={base['emails']} (%{base['emails']/base['total_records']*100:.1f}) -> V1.5={v15['emails']} (%{v15['emails']/base['total_records']*100:.1f}) (Net: +{results['new_emails_count']} e-posta)")
    print(f"İletişim Formu Bulunanlar : Önce={base['contact_forms']} -> V1.5={v15['contact_forms']}")
    print(f"Zenginleşen Toplam İşletme: {results['improved_count']} / {base['total_records']} (%{results['improved_count']/base['total_records']*100:.1f})")

    print("\n" + "=" * 80)
    print("30 İŞLETME İÇİN ARAŞTIRMA VE KANIT DETAYLARI")
    print("=" * 80)
    for idx, d in enumerate(diffs, 1):
        status_tag = "[YENİ VERİ BULUNDU]" if d["is_improved"] else "[SİTE/İLETİŞİM AÇIKTA YOK]"
        assoc_tag = " [ASSOCIATED CLINIC]" if d.get("has_associated_clinic") else ""
        print(f"\n{idx:02d}. {d['name']} [{d['employer_type']} - {d['district']}]{status_tag}{assoc_tag}")
        print(f"    Web Sitesi    : {d['old_website'] or '---'}  -->  {d['new_website'] or '---'}")
        print(f"    Telefon       : {d['old_phone'] or '---'}  -->  {d['new_phone'] or '---'}")
        print(f"    E-posta       : {d['old_email'] or '---'}  -->  {d['new_email'] or '---'}")
        print(f"    İletişim Formu: {d['old_contact_form'] or '---'}  -->  {d['new_contact_form'] or '---'}")
        if d.get("has_associated_clinic"):
            ac = d["associated_clinic"]
            print(f"    Bağlantılı Kl.: {ac.get('clinic_name')} ({ac.get('clinic_url')})")
        print(f"    Arama Sağlayıcı: {d.get('search_provider', 'freeserp')} (Durum: {d.get('search_status', 'ok')})")
        print(f"    Kaynaklar     : {d.get('attempted_sources', '---')}")
        print(f"    Araştırma Notu: {d.get('research_notes', 'Bilgi bulunamadı.')}")

    # JSON Çıktısını Kaydet
    output_path = ROOT_DIR / "pilot_comparison_v1_5.json"
    results["metadata"] = {
        "generated_at": datetime.now().isoformat(),
        "duration_seconds": duration,
        "version": "CareerMap V1.5 Web Search Discovery & Deep Contact Extraction"
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n[OK] Pilot analiz verileri kaydedildi: {output_path}")

if __name__ == "__main__":
    main()

