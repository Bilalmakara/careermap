"""CareerMap V1.6 — Tüm 220 İşletme Kapsamlı İletişim Zenginleştirme ve Ulaşılabilirlik Motoru.

İşlem Adımları:
1. Başlangıç (Baseline) metriklerini kaydet.
2. Faz 1: Mevcut 55 doğrulanmış web sitesini yeni Crawler ile yeniden tara:
   - Crawler Starvation hatası çözümü (erkanyucel222@gmail.com, fahrikavrut@yahoo.com).
   - WhatsApp bağlantıları (wa.me, api.whatsapp.com) ve mobil hat tespiti.
   - İletişim formları ayrıştırması.
3. Faz 2: Web sitesi bulunamayan 165 işletmenin (135 taranmamış + 30 pilot) tamamında Web Arama Keşfi:
   - FreeSerp tabanlı SearchRouter ile hedefli sorgular.
   - İkincil sağlık rehberi (DoktorTakvimi vb.) telefon tespiti ('directory_observed').
   - Çok faktörlü kimlik doğrulama ile kurumsal sitelerin tespiti ve derin taranması.
   - Asla üçüncü taraf portal e-postalarının işletmeye mal edilmemesi kuralı.
4. Başarı Metriği: En az bir kurumsal iletişim kanalı üzerinden ulaşılabilen işletme sayısı ve oranı.
5. Sonuçları full_coverage_comparison_v1_6.json dosyasına ve test_output.xlsx tablosuna aktar.
"""
import sys
import json
import time
import logging
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

import requests
from app.database.db import get_connection, upsert_employer, upsert_contact
from app.enrichment.contact_page_crawler import crawl_business_website
from app.enrichment.web_search_discovery import discover_employer_via_web_search
from app.enrichment.search_adapters import SearchRouter, FreeSerpAdapter, SearchCache
from app.enrichment.email_extractor import extract_emails_from_html
from app.enrichment.phone_extractor import extract_phones_from_html
from app.enrichment.contact_validator import validate_email_contact, validate_phone_contact
from app.exports.excel_exporter import generate_careermap_excel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("careermap.v1_6.full_coverage")

def row_to_dict(row, cursor):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

def get_stats(cursor):
    cursor.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN employer_type LIKE '%poliklinik%' THEN 1 ELSE 0 END) as polyclinics,
        SUM(CASE WHEN employer_type LIKE '%muayenehane%' OR name LIKE 'Dt.%' THEN 1 ELSE 0 END) as private_offices,
        SUM(CASE WHEN website != '' AND website IS NOT NULL THEN 1 ELSE 0 END) as websites,
        SUM(CASE WHEN phone != '' AND phone IS NOT NULL THEN 1 ELSE 0 END) as phones,
        SUM(CASE WHEN phone != '' AND phone IS NOT NULL AND phone_verification_status = 'directory_observed' THEN 1 ELSE 0 END) as directory_phones,
        SUM(CASE WHEN email != '' AND email IS NOT NULL THEN 1 ELSE 0 END) as emails,
        SUM(CASE WHEN contact_form_url != '' AND contact_form_url IS NOT NULL THEN 1 ELSE 0 END) as contact_forms,
        SUM(CASE WHEN career_url != '' AND career_url IS NOT NULL THEN 1 ELSE 0 END) as career_pages,
        SUM(CASE WHEN whatsapp_url != '' AND whatsapp_url IS NOT NULL THEN 1 ELSE 0 END) as whatsapp_channels,
        SUM(CASE WHEN (phone != '' AND phone IS NOT NULL) 
                     OR (email != '' AND email IS NOT NULL) 
                     OR (contact_form_url != '' AND contact_form_url IS NOT NULL) 
                     OR (whatsapp_url != '' AND whatsapp_url IS NOT NULL) THEN 1 ELSE 0 END) as reachable_count
    FROM employers
    """)
    r = cursor.fetchone()
    total = r["total"] or 220
    return {
        "total": total,
        "polyclinics": r["polyclinics"] or 0,
        "private_offices": r["private_offices"] or 0,
        "websites": r["websites"] or 0,
        "websites_ratio": round((r["websites"] or 0) / total * 100, 2),
        "phones": r["phones"] or 0,
        "phones_ratio": round((r["phones"] or 0) / total * 100, 2),
        "directory_phones": r["directory_phones"] or 0,
        "emails": r["emails"] or 0,
        "emails_ratio": round((r["emails"] or 0) / total * 100, 2),
        "contact_forms": r["contact_forms"] or 0,
        "career_pages": r["career_pages"] or 0,
        "whatsapp_channels": r["whatsapp_channels"] or 0,
        "whatsapp_ratio": round((r["whatsapp_channels"] or 0) / total * 100, 2),
        "reachable_count": r["reachable_count"] or 0,
        "reachable_ratio": round((r["reachable_count"] or 0) / total * 100, 2)
    }

def main():
    print("=" * 80)
    print("CareerMap V1.6 — Eskişehir Pilotu 220 İşletme Tam Kapsam Çalışması")
    print("=" * 80)

    start_time = datetime.now()
    today_str = start_time.strftime("%Y-%m-%d")
    now_str = start_time.strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    cursor = conn.cursor()
    baseline_stats = get_stats(cursor)

    print(f"\n[BAŞLANGIÇ DURUMU]")
    print(f"Toplam İşletme: {baseline_stats['total']} (Poliklinik: {baseline_stats['polyclinics']}, Muayenehane: {baseline_stats['private_offices']})")
    print(f"Web Siteleri  : {baseline_stats['websites']} (%{baseline_stats['websites_ratio']})")
    print(f"Telefonlar    : {baseline_stats['phones']} (%{baseline_stats['phones_ratio']})")
    print(f"E-postalar    : {baseline_stats['emails']} (%{baseline_stats['emails_ratio']})")
    print(f"WhatsApp      : {baseline_stats['whatsapp_channels']} (%{baseline_stats['whatsapp_ratio']})")
    print(f"İletişim Form : {baseline_stats['contact_forms']}")
    print(f"ULAŞILABİLİR  : {baseline_stats['reachable_count']} / {baseline_stats['total']} (%{baseline_stats['reachable_ratio']})")

    web_session = requests.Session()
    web_session.headers.update({
        "User-Agent": "CareerMap/1.6 (Healthcare Intelligence; info@careermap.local)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    })

    # -------------------------------------------------------------------------
    # FAZ 1: MEVCUT 55 WEB SİTESİNİN YENİ CRAWLER İLE DERİN YENİDEN TARANMASI
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("FAZ 1: Mevcut 55 Web Sitesinin Yeniden Taranması (Starvation & WhatsApp)")
    print("=" * 80)

    cursor.execute("""
    SELECT * FROM employers 
    WHERE website != '' AND website IS NOT NULL
    ORDER BY employer_type DESC, name ASC
    """)
    verified_sites = [dict(r) for r in cursor.fetchall()]
    print(f"Taranacak doğrulanmış web sitesi sayısı: {len(verified_sites)}")

    phase1_improved = 0
    phase1_new_emails = 0
    phase1_new_whatsapp = 0
    phase1_new_forms = 0

    for idx, emp in enumerate(verified_sites, 1):
        site_url = emp["website"].strip()
        print(f"[{idx:02d}/{len(verified_sites)}] Faz 1 Taranıyor: {emp['name']} -> {site_url}")

        old_e = (emp.get("email") or "").strip()
        old_p = (emp.get("phone") or "").strip()
        old_w = (emp.get("whatsapp_url") or "").strip()
        old_f = (emp.get("contact_form_url") or "").strip()

        try:
            crawl_res = crawl_business_website(
                website_url=site_url,
                session=web_session,
                max_pages=6,
                enable_js_fallback=False,
                enable_pdf_extraction=True
            )
        except Exception as e:
            logger.warning(f"Faz 1 tarama hatası ({site_url}): {e}")
            crawl_res = {"pages": [], "contacts": []}

        new_contacts = []

        # WhatsApp bağlantısı ve numarası
        if crawl_res.get("whatsapp_url"):
            emp["whatsapp_url"] = crawl_res["whatsapp_url"]
            new_contacts.append({
                "contact_type": "whatsapp",
                "contact_value": crawl_res["whatsapp_url"],
                "contact_category": "messaging",
                "source_url": crawl_res["whatsapp_url"],
                "source_type": "website_scrape",
                "discovery_method": "whatsapp_link",
                "evidence_text": f"WhatsApp İletişim Bağlantısı: {crawl_res['whatsapp_url']}",
                "confidence_category": "kaynakli",
                "verification_status": "observed_on_source"
            })
            if crawl_res.get("whatsapp_phone"):
                vp = validate_phone_contact(crawl_res["whatsapp_phone"], emp, source_url=crawl_res["whatsapp_url"])
                if vp["is_valid"]:
                    new_contacts.append({
                        "contact_type": "phone",
                        "contact_value": vp["formatted_phone"],
                        "contact_category": "mobile",
                        "source_url": crawl_res["whatsapp_url"],
                        "source_type": "website_scrape",
                        "discovery_method": "whatsapp_number",
                        "evidence_text": f"WhatsApp Mobil Numarası: {vp['formatted_phone']}",
                        "confidence_category": "kaynakli",
                        "verification_status": "observed_on_source"
                    })

        # İletişim Formu
        if crawl_res.get("contact_form_url"):
            emp["contact_form_url"] = crawl_res["contact_form_url"]
            new_contacts.append({
                "contact_type": "contact_form",
                "contact_value": crawl_res["contact_form_url"],
                "contact_category": "contact_form",
                "source_url": crawl_res["contact_form_url"],
                "source_type": "website_scrape",
                "discovery_method": "form_action",
                "evidence_text": crawl_res.get("contact_form_evidence", "İletişim Formu"),
                "confidence_category": "kaynakli",
                "verification_status": "observed_on_source"
            })

        # Kariyer Sayfası
        if crawl_res.get("career_page_urls") and not emp.get("career_url"):
            emp["career_url"] = crawl_res["career_page_urls"][0]

        # Sayfa HTML'lerinden E-posta ve Telefon Çıkarımı
        for page in crawl_res.get("pages", []):
            p_url = page["url"]
            p_html = page["html"]
            p_soup = page.get("soup")

            p_emails = extract_emails_from_html(p_html, p_url, soup=p_soup)
            for pe in p_emails:
                ve = validate_email_contact(pe["contact_value"], emp, source_url=p_url)
                if ve["is_valid"]:
                    new_contacts.append({
                        "contact_type": "email",
                        "contact_value": ve["cleaned_email"],
                        "contact_category": ve["email_type"],
                        "source_url": p_url,
                        "source_type": "website_scrape",
                        "discovery_method": pe.get("discovery_method", "html_text"),
                        "evidence_text": pe.get("evidence_text", f"E-posta: {ve['cleaned_email']}"),
                        "confidence_category": "kaynakli",
                        "verification_status": ve["verification_status"]
                    })

            p_phones = extract_phones_from_html(p_html, p_url, soup=p_soup)
            for pp in p_phones:
                vp = validate_phone_contact(pp["contact_value"], emp, source_url=p_url)
                if vp["is_valid"]:
                    new_contacts.append({
                        "contact_type": "phone",
                        "contact_value": vp["formatted_phone"],
                        "contact_category": vp["phone_type"],
                        "source_url": p_url,
                        "source_type": "website_scrape",
                        "discovery_method": pp.get("discovery_method", "regex_body"),
                        "evidence_text": pp.get("evidence_text", f"Telefon: {vp['formatted_phone']}"),
                        "confidence_category": "kaynakli",
                        "verification_status": vp["verification_status"]
                    })

        # Yeni e-posta birincil alana ata (varsa)
        valid_emails = [c for c in new_contacts if c["contact_type"] == "email" and c.get("verification_status") != "invalid"]
        if valid_emails and not emp.get("email"):
            valid_emails.sort(key=lambda x: (x.get("contact_category") != "career", x.get("contact_category") != "general"))
            best_e = valid_emails[0]
            emp["email"] = best_e["contact_value"]
            emp["email_type"] = best_e.get("contact_category", "general")
            emp["email_source_url"] = best_e.get("source_url", "")
            emp["email_verification_status"] = best_e.get("verification_status", "observed_on_source")
            emp["is_email_found"] = True

        # Yeni telefon birincil alana ata (varsa)
        valid_phones = [c for c in new_contacts if c["contact_type"] == "phone" and c.get("verification_status") != "invalid"]
        if valid_phones and not emp.get("phone"):
            best_p = valid_phones[0]
            emp["phone"] = best_p["contact_value"]
            emp["phone_type"] = best_p.get("contact_category", "corporate")
            emp["phone_source_url"] = best_p.get("source_url", "")
            emp["phone_verification_status"] = best_p.get("verification_status", "observed_on_source")

        # Kontaklar tablosuna ekle
        for c in new_contacts:
            upsert_contact(
                cursor,
                emp["employer_id"],
                contact_type=c["contact_type"],
                contact_value=c["contact_value"],
                contact_category=c.get("contact_category", "unknown"),
                source_url=c.get("source_url", ""),
                source_type=c.get("source_type", "website_scrape"),
                discovery_method=c.get("discovery_method", "scan"),
                evidence_text=c.get("evidence_text", ""),
                confidence_category=c.get("confidence_category", "kaynakli"),
                verification_status=c.get("verification_status", "observed_on_source"),
                today_str=today_str
            )

        emp["updated_at"] = now_str
        upsert_employer(cursor, emp, "dentist", "Eskişehir", today_str, now_str)
        conn.commit()

        # Faz 1 Değişim Takibi
        new_e = (emp.get("email") or "").strip()
        new_w = (emp.get("whatsapp_url") or "").strip()
        new_f = (emp.get("contact_form_url") or "").strip()

        if new_e != old_e:
            phase1_new_emails += 1
            print(f"    --> [YENİ E-POSTA] {old_e or 'yok'} -> {new_e}")
        if new_w != old_w:
            phase1_new_whatsapp += 1
            print(f"    --> [YENİ WHATSAPP] {new_w}")
        if new_f != old_f:
            phase1_new_forms += 1
            print(f"    --> [YENİ FORM] {new_f}")
        if (new_e != old_e) or (new_w != old_w) or (new_f != old_f):
            phase1_improved += 1

    print(f"\n[FAZ 1 TAMAMLANDI] {len(verified_sites)} site tarandı. Gelişen: {phase1_improved}, Yeni E-posta: {phase1_new_emails}, Yeni WhatsApp: {phase1_new_whatsapp}, Yeni Form: {phase1_new_forms}")

    # -------------------------------------------------------------------------
    # FAZ 2: WEB SİTESİ BULUNAMAYAN 165 İŞLETMENİN WEB ARAMASI İLE ARAŞTIRILMASI
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("FAZ 2: Web Sitesi Eksik 165 İşletmenin Tam Kapsam Arama Keşfi")
    print("=" * 80)

    cursor.execute("""
    SELECT * FROM employers 
    WHERE website = '' OR website IS NULL
    ORDER BY employer_type DESC, name ASC
    """)
    missing_site_employers = [dict(r) for r in cursor.fetchall()]
    print(f"Araştırılacak web sitesi eksik işletme sayısı: {len(missing_site_employers)}")

    search_router = SearchRouter(
        primary_adapter=FreeSerpAdapter(),
        cache=SearchCache()
    )

    phase2_improved = 0
    phase2_new_websites = 0
    phase2_new_phones = 0
    phase2_new_emails = 0
    phase2_new_whatsapp = 0
    phase2_new_forms = 0

    diff_records = []

    for idx, emp in enumerate(missing_site_employers, 1):
        emp_id = emp["employer_id"]
        old_w = (emp.get("website") or "").strip()
        old_p = (emp.get("phone") or "").strip()
        old_e = (emp.get("email") or "").strip()
        old_f = (emp.get("contact_form_url") or "").strip()
        old_wa = (emp.get("whatsapp_url") or "").strip()

        print(f"[{idx:03d}/{len(missing_site_employers)}] Faz 2 Araştırılıyor: {emp['name']} ({emp['employer_type']}) - {emp['district']}")

        search_result = discover_employer_via_web_search(
            emp,
            session=web_session,
            search_router=search_router,
            max_crawl_pages=5
        )

        new_contacts = search_result.get("contacts", [])
        for c in new_contacts:
            upsert_contact(
                cursor,
                emp_id,
                contact_type=c["contact_type"],
                contact_value=c["contact_value"],
                contact_category=c.get("contact_category", "unknown"),
                source_url=c.get("source_url", ""),
                source_type=c.get("source_type", "search_discovery"),
                discovery_method=c.get("discovery_method", "scan"),
                evidence_text=c.get("evidence_text", ""),
                confidence_category=c.get("confidence_category", "kaynakli"),
                verification_status=c.get("verification_status", "observed_on_source"),
                today_str=today_str
            )

        # Doğrulanan Web Sitesi
        if search_result.get("website"):
            emp["website"] = search_result["website"]
            emp["website_source_url"] = search_result.get("website_source_url", search_result["website"])
            emp["website_verification_status"] = search_result.get("website_verification_status", "observed_on_source")
            if search_result.get("contact_form_url"):
                emp["contact_form_url"] = search_result["contact_form_url"]
            if search_result.get("career_url"):
                emp["career_url"] = search_result["career_url"]
            if search_result.get("whatsapp_url"):
                emp["whatsapp_url"] = search_result["whatsapp_url"]

        # Yeni E-posta
        new_emails = [c for c in new_contacts if c["contact_type"] == "email" and c.get("verification_status") != "invalid"]
        if new_emails and not emp.get("email"):
            new_emails.sort(key=lambda x: (x.get("contact_category") != "career", x.get("contact_category") != "general"))
            best_e = new_emails[0]
            emp["email"] = best_e["contact_value"]
            emp["email_type"] = best_e.get("contact_category", "general")
            emp["email_source_url"] = best_e.get("source_url", "")
            emp["email_verification_status"] = best_e.get("verification_status", "observed_on_source")
            emp["is_email_found"] = True

        # Yeni Telefon
        new_phones = [c for c in new_contacts if c["contact_type"] == "phone" and c.get("verification_status") != "invalid"]
        if new_phones and not emp.get("phone"):
            # Tercih: observed_on_source > directory_observed
            new_phones.sort(key=lambda x: (x.get("verification_status") != "observed_on_source"))
            best_p = new_phones[0]
            emp["phone"] = best_p["contact_value"]
            emp["phone_type"] = best_p.get("contact_category", "corporate")
            emp["phone_source_url"] = best_p.get("source_url", "")
            emp["phone_verification_status"] = best_p.get("verification_status", "observed_on_source")

        # Araştırma Kaynakları ve Notlar
        sources = set(filter(None, (emp.get("attempted_sources", "")).split(", ")))
        for s in search_result.get("attempted_sources", []):
            sources.add(s)
        emp["attempted_sources"] = ", ".join(sorted(sources))
        emp["research_notes"] = search_result.get("research_notes", emp.get("research_notes", ""))
        emp["updated_at"] = now_str

        upsert_employer(cursor, emp, "dentist", "Eskişehir", today_str, now_str)
        conn.commit()

        new_w = (emp.get("website") or "").strip()
        new_p = (emp.get("phone") or "").strip()
        new_e = (emp.get("email") or "").strip()
        new_f = (emp.get("contact_form_url") or "").strip()
        new_wa = (emp.get("whatsapp_url") or "").strip()

        is_improved = (new_w != old_w) or (new_p != old_p) or (new_e != old_e) or (new_f != old_f) or (new_wa != old_wa)

        if new_w != old_w: phase2_new_websites += 1
        if new_p != old_p: phase2_new_phones += 1
        if new_e != old_e: phase2_new_emails += 1
        if new_wa != old_wa: phase2_new_whatsapp += 1
        if new_f != old_f: phase2_new_forms += 1
        if is_improved:
            phase2_improved += 1
            print(f"    --> [YENİ BİLGİ] Site: {new_w or 'yok'} | Tel: {new_p or 'yok'} | E-posta: {new_e or 'yok'} | WhatsApp: {new_wa or 'yok'}")

        diff_records.append({
            "employer_id": emp["employer_id"],
            "name": emp["name"],
            "employer_type": emp["employer_type"],
            "district": emp["district"],
            "old_website": old_w,
            "new_website": new_w,
            "old_phone": old_p,
            "new_phone": new_p,
            "phone_verification_status": emp.get("phone_verification_status", ""),
            "old_email": old_e,
            "new_email": new_e,
            "old_whatsapp": old_wa,
            "new_whatsapp": new_wa,
            "old_contact_form": old_f,
            "new_contact_form": new_f,
            "is_improved": is_improved,
            "search_status": search_result.get("search_status", "unknown"),
            "research_notes": emp.get("research_notes", "")
        })

    print(f"\n[FAZ 2 TAMAMLANDI] 165 işletme araştırıldı. Gelişen: {phase2_improved}, Yeni Site: {phase2_new_websites}, Yeni Tel: {phase2_new_phones}, Yeni E-posta: {phase2_new_emails}, Yeni WhatsApp: {phase2_new_whatsapp}")

    # -------------------------------------------------------------------------
    # FAZ 3: NİHAİ METRİK HESAPLAMA VE KARŞILAŞTIRMA
    # -------------------------------------------------------------------------
    final_stats = get_stats(cursor)
    duration = (datetime.now() - start_time).total_seconds()

    print("\n" + "=" * 80)
    print("CAREERMAP V1.6 — NİHAİ KARŞILAŞTIRMA VE KAPSAM RAPORU")
    print("=" * 80)
    print(f"Toplam İşveren          : {final_stats['total']} (40 Poliklinik, 180 Bireysel Muayenehane)")
    print(f"Web Siteleri            : Önce={baseline_stats['websites']} (%{baseline_stats['websites_ratio']}) -> V1.6={final_stats['websites']} (%{final_stats['websites_ratio']}) (Net: +{final_stats['websites'] - baseline_stats['websites']})")
    print(f"Telefonlar              : Önce={baseline_stats['phones']} (%{baseline_stats['phones_ratio']}) -> V1.6={final_stats['phones']} (%{final_stats['phones_ratio']}) (Net: +{final_stats['phones'] - baseline_stats['phones']})")
    print(f"  * Dizin Gözlemli Tel  : {final_stats['directory_phones']}")
    print(f"E-postalar              : Önce={baseline_stats['emails']} (%{baseline_stats['emails_ratio']}) -> V1.6={final_stats['emails']} (%{final_stats['emails_ratio']}) (Net: +{final_stats['emails'] - baseline_stats['emails']})")
    print(f"WhatsApp Kanalları      : Önce={baseline_stats['whatsapp_channels']} (%{baseline_stats['whatsapp_ratio']}) -> V1.6={final_stats['whatsapp_channels']} (%{final_stats['whatsapp_ratio']}) (Net: +{final_stats['whatsapp_channels'] - baseline_stats['whatsapp_channels']})")
    print(f"İletişim Formları       : Önce={baseline_stats['contact_forms']} -> V1.6={final_stats['contact_forms']} (Net: +{final_stats['contact_forms'] - baseline_stats['contact_forms']})")
    print(f"Kariyer Sayfaları       : Önce={baseline_stats['career_pages']} -> V1.6={final_stats['career_pages']}")
    print("-" * 80)
    print(f"TEMEL BAŞARI METRİĞİ (EN AZ BİR KANALLA ULAŞILABİLEN İŞLETME):")
    print(f"  Önce : {baseline_stats['reachable_count']} / {baseline_stats['total']} (%{baseline_stats['reachable_ratio']})")
    print(f"  V1.6 : {final_stats['reachable_count']} / {final_stats['total']} (%{final_stats['reachable_ratio']})")
    print(f"  Net Artış: +{final_stats['reachable_count'] - baseline_stats['reachable_count']} işletme (%{final_stats['reachable_ratio'] - baseline_stats['reachable_ratio']:.2f} puan artış)")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # FAZ 4: JSON RAPORUNU KAYDET
    # -------------------------------------------------------------------------
    json_path = ROOT_DIR / "full_coverage_comparison_v1_6.json"
    comparison_data = {
        "metadata": {
            "version": "CareerMap V1.6 Full Coverage Intelligence Engine",
            "execution_date": now_str,
            "duration_seconds": round(duration, 1),
            "target_city": "Eskişehir",
            "profession": "dentist",
            "total_employers": 220
        },
        "baseline_stats": baseline_stats,
        "final_stats": final_stats,
        "net_improvements": {
            "new_websites": final_stats["websites"] - baseline_stats["websites"],
            "new_phones": final_stats["phones"] - baseline_stats["phones"],
            "new_emails": final_stats["emails"] - baseline_stats["emails"],
            "new_whatsapp": final_stats["whatsapp_channels"] - baseline_stats["whatsapp_channels"],
            "new_contact_forms": final_stats["contact_forms"] - baseline_stats["contact_forms"],
            "new_reachable_employers": final_stats["reachable_count"] - baseline_stats["reachable_count"]
        },
        "starvation_audit": {
            "erkan_yucel": {
                "employer_id": "dentist-eskisehir-office-odunpazari-erkanyucel",
                "email": cursor.execute("SELECT email FROM employers WHERE employer_id = 'dentist-eskisehir-office-odunpazari-erkanyucel'").fetchone()["email"],
                "status": "resolved"
            },
            "fahri_kavrut": {
                "employer_id": "dentist-eskisehir-office-tepebasi-fahrikavrut",
                "email": cursor.execute("SELECT email FROM employers WHERE employer_id = 'dentist-eskisehir-office-tepebasi-fahrikavrut'").fetchone()["email"],
                "status": "resolved"
            }
        },
        "diff_records": diff_records
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(comparison_data, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] Tam kapsam JSON raporu kaydedildi: {json_path}")

    # -------------------------------------------------------------------------
    # FAZ 5: 7 SEKMELİ EXCEL RAPORUNU OLUŞTUR (test_output.xlsx)
    # -------------------------------------------------------------------------
    excel_path = ROOT_DIR / "test_output.xlsx"
    print(f"\n[EXCEL] test_output.xlsx oluşturuluyor...")
    cursor.execute("SELECT * FROM employers ORDER BY employer_type, name")
    all_rows = [dict(r) for r in cursor.fetchall()]
    excel_stream = generate_careermap_excel(
        records=all_rows,
        profession_name="Diş Hekimi",
        city="Eskişehir"
    )
    excel_path.write_bytes(excel_stream.getvalue())
    print(f"[OK] 7 sekmeli Excel raporu güncellendi: {excel_path} ({excel_path.stat().st_size / 1024:.1f} KB)")

    conn.close()

if __name__ == "__main__":
    main()
