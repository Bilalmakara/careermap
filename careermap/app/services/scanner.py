"""CareerMap V1.4 Çok Kaynaklı İletişim İstihbaratı ve Araştırma Motoru (Scanner).
- Kanıt tabanlı kimlik doğrulama (`website_identity_matcher.py`).
- Çok sayfalı saygılı tarama (`contact_page_crawler.py`).
- `phonenumbers` destekli numara normalizasyonu ve e-posta analizi.
- Araştırma notları (`research_notes`) ve denenen kaynaklar (`attempted_sources`).
"""
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
import requests

from ..professions.registry import ProfessionRegistry
from ..discovery.official_source import fetch_official_sources
from ..discovery.osm_source import fetch_osm_records
from ..discovery.tdb_source import query_tdb_dentist
from ..enrichment.website_discovery import discover_and_extract_website_contacts
from ..enrichment.web_search_discovery import discover_employer_via_web_search
from ..enrichment.search_adapters import SearchRouter
from ..enrichment.phone_extractor import format_phone
from ..matching.deduplicator import deduplicate_records
from ..matching.confidence import assess_records_quality
from ..database.db import (
    save_employers, query_employers, get_cache_info,
    canonical_id, get_employer_contacts, get_connection,
    upsert_employer, upsert_contact
)

logger = logging.getLogger("careermap.services.scanner")

def run_pipeline(
    profession_id: str = "dentist",
    city: str = "Eskişehir",
    force_refresh: bool = False,
    enrich_web_intelligence: bool = True,
    enrich_tdb: bool = True,
    max_tdb_lookups: int = 250
) -> List[Dict[str, Any]]:
    """CareerMap V1.4 Çok Kaynaklı İletişim İstihbaratı Boru Hattı."""
    profession = ProfessionRegistry.get(profession_id)
    if not profession:
        raise ValueError(f"Bilinmeyen meslek: {profession_id}")

    # Önbellek kontrolü
    cache_info = get_cache_info(profession_id, city)
    if not force_refresh and cache_info and cache_info.get("total_count", 0) > 0:
        logger.info(f"Önbellekten hızlı yükleniyor: {profession_id} - {city} ({cache_info.get('total_count')} kayıt)")
        return query_employers(profession_id, city, include_contacts=True)

    logger.info(f"=== CareerMap V1.4 İstihbarat Taraması Başlatıldı: {profession.name} - {city} ===")
    raw_records: List[Dict[str, Any]] = []
    official_status = "success"
    osm_status = "unknown"
    error_logs = []

    # 1. Resmî Kurum Kayıtları (Eskişehir İl Sağlık Müdürlüğü)
    try:
        official_recs = fetch_official_sources(profession, city)
        raw_records.extend(official_recs)
        logger.info(f"Resmî kaynaktan {len(official_recs)} kayıt alındı.")
    except Exception as e:
        official_status = "failed"
        error_logs.append(f"Resmî kaynak hatası: {e}")
        logger.error(f"Resmî kaynak hatası: {e}")

    # 2. OpenStreetMap (Odaklı bölge sorguları)
    try:
        osm_recs, osm_report = fetch_osm_records(profession, city)
        osm_status = osm_report["status"]
        if osm_report.get("failed_attempts"):
            error_logs.append("OSM: " + "; ".join(osm_report["failed_attempts"]))
        if osm_recs:
            raw_records.extend(osm_recs)
            logger.info(f"OSM'den {len(osm_recs)} işletme keşfedildi.")
    except Exception as e:
        osm_status = "failed"
        error_logs.append(f"OSM hatası: {e}")
        logger.error(f"OSM hatası: {e}")

    # 3. Akıllı Tekilleştirme
    merged_records = deduplicate_records(raw_records, profession)

    for r in merged_records:
        if not r.get("employer_id"):
            r["employer_id"] = canonical_id(r.get("name", ""), r.get("district", ""), r.get("employer_type", ""))
        r.setdefault("contacts", [])
        r.setdefault("attempted_sources", "")
        r.setdefault("research_notes", "")

    # 4. TDB Güvenli Sicil Entegrasyonu (Token bazlı ad-soyad teyidi)
    if enrich_tdb and profession_id == "dentist":
        tdb_session = requests.Session()
        tdb_lookups = 0
        logger.info(f"TDB resmî sicil kuyruğu başlatılıyor (Maks: {max_tdb_lookups})...")
        
        for r in merged_records:
            if tdb_lookups >= max_tdb_lookups:
                break
                
            needs_tdb = (
                not r.get("phone") or r.get("phone_verification_status") != "verified"
            ) and (
                "muayenehane" in r.get("employer_type", "").lower() or r.get("name", "").startswith("Dt")
            )

            if needs_tdb:
                tdb_data = query_tdb_dentist(r["name"], city, tdb_session)
                tdb_lookups += 1
                r["attempted_sources"] = (r.get("attempted_sources", "") + ", TDB Sicil").strip(", ")
                
                if tdb_data:
                    if tdb_data.get("phone"):
                        formatted_p = format_phone(tdb_data["phone"])
                        r["phone"] = formatted_p
                        r["phone_source_url"] = tdb_data["source_url"]
                        r["phone_type"] = "personal_registry"
                        r["phone_verification_status"] = tdb_data.get("verification_status", "verified")
                        
                        if tdb_data.get("district") and not r.get("district"):
                            r["district"] = tdb_data["district"]
                        if not r.get("source_type") or "TDB" not in r["source_type"]:
                            r["source_type"] = (r.get("source_type") or "") + " + TDB Resmî Sicil"
                            
                        r["contacts"].append({
                            "contact_type": "phone",
                            "contact_value": formatted_p,
                            "contact_category": "personal_registry",
                            "source_url": tdb_data["source_url"],
                            "source_type": "tdb",
                            "discovery_method": "tdb_registry",
                            "evidence_text": "TDB Sicil Oda Kaydı (Tam ad-soyad teyitli)",
                            "confidence_category": "kaynakli",
                            "verification_status": "verified"
                        })
                        r["research_notes"] = (r.get("research_notes", "") + "; TDB'den telefon doğrulandı").strip("; ")
                    elif tdb_data.get("verification_status") == "manual_review":
                        r["phone_verification_status"] = "manual_review"
                        r["research_notes"] = (r.get("research_notes", "") + "; TDB: Çoklu aynı isimli hekim").strip("; ")
                else:
                    r["research_notes"] = (r.get("research_notes", "") + "; TDB: Sicil kaydı bulunamadı").strip("; ")
                time.sleep(0.08)

    # 5. V1.4 Web İstihbaratı (Kimlik Eşleme, Saygılı Tarama, Form & İletişim Çıkarma)
    if enrich_web_intelligence:
        web_session = requests.Session()
        logger.info("V1.4 Web İstihbarat Motoru başlatılıyor...")
        
        for r in merged_records:
            r["attempted_sources"] = (r.get("attempted_sources", "") + ", Web Keşfi").strip(", ")
            web_data = discover_and_extract_website_contacts(r, web_session)
            
            if web_data.get("website"):
                r["website"] = web_data["website"]
                r["website_source_url"] = web_data["website_source_url"]
                r["website_verification_status"] = web_data["website_verification_status"]
                
                if web_data.get("contact_form_url"):
                    r["contact_form_url"] = web_data["contact_form_url"]
                if web_data.get("career_url"):
                    r["career_url"] = web_data["career_url"]
                if web_data.get("research_notes"):
                    r["research_notes"] = (r.get("research_notes", "") + "; " + web_data["research_notes"]).strip("; ")
                
                # Çıkarılan kanıtlı çoklu kontakları ekle
                if web_data.get("contacts"):
                    r["contacts"].extend(web_data["contacts"])
                    
                    # Birincil e-posta seçimi
                    email_contacts = [c for c in web_data["contacts"] if c["contact_type"] == "email"]
                    if email_contacts and not r.get("email"):
                        # Kariyer öncelikli sıralama
                        email_contacts.sort(key=lambda x: (
                            x.get("contact_category") != "career",
                            x.get("contact_category") != "general"
                        ))
                        best_email = email_contacts[0]
                        r["email"] = best_email["contact_value"]
                        r["email_type"] = best_email.get("contact_category", "general")
                        r["email_source_url"] = best_email.get("source_url", "")
                        r["email_verification_status"] = "verified"

                    # Birincil kurumsal telefon seçimi
                    phone_contacts = [c for c in web_data["contacts"] if c["contact_type"] == "phone"]
                    if phone_contacts and not r.get("phone"):
                        best_phone = phone_contacts[0]
                        r["phone"] = best_phone["contact_value"]
                        r["phone_type"] = best_phone.get("contact_category", "corporate")
                        r["phone_source_url"] = best_phone.get("source_url", "")
                        r["phone_verification_status"] = "verified"

            elif web_data.get("research_notes"):
                r["research_notes"] = (r.get("research_notes", "") + "; " + web_data["research_notes"]).strip("; ")
            
            time.sleep(0.05)

    # 6. Alan Bazlı Kalite Değerlendirmesi
    assessed_records = assess_records_quality(merged_records, profession)

    # 7. Kalıcı Kayıt (UPSERT & employer_contacts)
    error_summary = " | ".join(error_logs) if error_logs else None
    save_employers(
        profession_id=profession_id,
        city=city,
        records=assessed_records,
        osm_status=osm_status,
        official_status=official_status,
        error_log=error_summary
    )

    logger.info(f"V1.4 Taraması tamamlandı. Toplam tekil kayıt: {len(assessed_records)}")
    return assessed_records

def run_pilot_v1_4(
    sample_size_clinics: int = 10,
    sample_size_offices: int = 10,
    city: str = "Eskişehir"
) -> Dict[str, Any]:
    """
    V1.4-A Kontrollü 20 İşletmelik Pilot Karşılaştırma Testi.
    - 10 Özel Poliklinik
    - 10 Bireysel Muayenehane
    Kimlik eşleştirme, phonenumbers normalizasyonu, form ayrımı ve kanıt izlerini ölçer.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT * FROM employers 
    WHERE employer_type LIKE '%poliklinik%' 
    ORDER BY id ASC LIMIT ?
    """, (sample_size_clinics,))
    clinics = [dict(r) for r in cursor.fetchall()]
    
    cursor.execute("""
    SELECT * FROM employers 
    WHERE employer_type LIKE '%muayenehane%' 
    ORDER BY id ASC LIMIT ?
    """, (sample_size_offices,))
    offices = [dict(r) for r in cursor.fetchall()]
    conn.close()

    pilot_pool = clinics + offices
    logger.info(f"V1.4 Pilot test başlatıldı: {len(clinics)} poliklinik, {len(offices)} muayenehane.")

    baseline_stats = {
        "total_records": len(pilot_pool),
        "clinics_count": len(clinics),
        "offices_count": len(offices),
        "phones": sum(1 for r in pilot_pool if (r.get("phone") or "").strip()),
        "emails": sum(1 for r in pilot_pool if (r.get("email") or "").strip()),
        "websites": sum(1 for r in pilot_pool if (r.get("website") or "").strip()),
        "contact_forms": sum(1 for r in pilot_pool if (r.get("contact_form_url") or "").strip())
    }

    tdb_session = requests.Session()
    web_session = requests.Session()
    
    audit_diffs: List[Dict[str, Any]] = []

    for r in pilot_pool:
        old_p = (r.get("phone") or "").strip()
        old_e = (r.get("email") or "").strip()
        old_w = (r.get("website") or "").strip()
        old_f = (r.get("contact_form_url") or "").strip()

        r.setdefault("contacts", [])
        r.setdefault("attempted_sources", "")
        r.setdefault("research_notes", "")

        # 1. TDB Sorgusu
        is_office = "muayenehane" in r.get("employer_type", "").lower() or r.get("name", "").startswith("Dt")
        if is_office and not old_p:
            tdb_data = query_tdb_dentist(r["name"], city, tdb_session)
            r["attempted_sources"] = (r.get("attempted_sources", "") + ", TDB").strip(", ")
            if tdb_data and tdb_data.get("phone"):
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
                    "evidence_text": "TDB Sicil Kaydı",
                    "confidence_category": "kaynakli",
                    "verification_status": "verified"
                })
            time.sleep(0.08)

        # 2. V1.4 Web İstihbaratı (Kimlik Eşleme, Saygılı Tarama, Form & İletişim Çıkarma)
        r["attempted_sources"] = (r.get("attempted_sources", "") + ", Web").strip(", ")
        web_data = discover_and_extract_website_contacts(r, web_session)
        if web_data.get("website"):
            r["website"] = web_data["website"]
            r["website_source_url"] = web_data["website_source_url"]
            r["website_verification_status"] = web_data["website_verification_status"]
            if web_data.get("contact_form_url"):
                r["contact_form_url"] = web_data["contact_form_url"]
            if web_data.get("career_url"):
                r["career_url"] = web_data["career_url"]
            if web_data.get("contacts"):
                r["contacts"].extend(web_data["contacts"])
                
                # E-posta güncelleme
                web_emails = [c for c in web_data["contacts"] if c["contact_type"] == "email"]
                if web_emails and not r.get("email"):
                    web_emails.sort(key=lambda x: (x.get("contact_category") != "career", x.get("contact_category") != "general"))
                    best_e = web_emails[0]
                    r["email"] = best_e["contact_value"]
                    r["email_type"] = best_e.get("contact_category", "general")
                    r["email_source_url"] = best_e.get("source_url", "")
                    r["email_verification_status"] = "verified"

                # Telefon güncelleme
                web_phones = [c for c in web_data["contacts"] if c["contact_type"] == "phone"]
                if web_phones and not r.get("phone"):
                    best_p = web_phones[0]
                    r["phone"] = best_p["contact_value"]
                    r["phone_type"] = best_p.get("contact_category", "corporate")
                    r["phone_source_url"] = best_p.get("source_url", "")
                    r["phone_verification_status"] = "verified"

        new_p = (r.get("phone") or "").strip()
        new_e = (r.get("email") or "").strip()
        new_w = (r.get("website") or "").strip()
        new_f = (r.get("contact_form_url") or "").strip()

        audit_diffs.append({
            "name": r["name"],
            "employer_type": r["employer_type"],
            "district": r["district"],
            "old_phone": old_p,
            "new_phone": new_p,
            "old_email": old_e,
            "new_email": new_e,
            "old_website": old_w,
            "new_website": new_w,
            "old_contact_form": old_f,
            "new_contact_form": new_f,
            "is_improved": (new_p != old_p) or (new_e != old_e) or (new_w != old_w) or (new_f != old_f),
            "contacts_count": len(r["contacts"]),
            "research_notes": r.get("research_notes", ""),
            "attempted_sources": r.get("attempted_sources", "")
        })

    # Veritabanına kaydet
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today_str = datetime.now().strftime("%Y-%m-%d")
    for r in pilot_pool:
        upsert_employer(cursor, r, "dentist", city, today_str, now_str)
    conn.commit()
    conn.close()

    v1_4_stats = {
        "total_records": len(pilot_pool),
        "phones": sum(1 for r in pilot_pool if (r.get("phone") or "").strip()),
        "emails": sum(1 for r in pilot_pool if (r.get("email") or "").strip()),
        "websites": sum(1 for r in pilot_pool if (r.get("website") or "").strip()),
        "contact_forms": sum(1 for r in pilot_pool if (r.get("contact_form_url") or "").strip())
    }

    return {
        "baseline_stats": baseline_stats,
        "v1_4_stats": v1_4_stats,
        "improved_count": sum(1 for d in audit_diffs if d["is_improved"]),
        "audit_diffs": audit_diffs
    }

def run_pilot_v1_5(
    city: str = "Eskişehir",
    target_count: int = 30,
    conn: Optional[Any] = None
) -> Dict[str, Any]:
    """
    CareerMap V1.5 Web Arama Keşif Pilotu.
    - Web sitesi bulunamayan 30 gerçek işletmeyi (mevcut 7 poliklinik + 23 muayenehane) seçer.
    - FreeSerp tabanlı SearchRouter ve Deep Crawler ile araştırır.
    - Yeni site, telefon, e-posta ve associated_clinic bağlantılarını kanıtlarıyla kaydeder.
    """
    logger.info(f"=== CareerMap V1.5 Web Arama Pilotu Başlatılıyor ({target_count} İşletme) ===")
    
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True

    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM employers 
    WHERE (website = '' OR website IS NULL)
    ORDER BY CASE WHEN employer_type LIKE '%poliklinik%' THEN 1 ELSE 2 END, id ASC
    """)
    all_missing = [dict(r) for r in cursor.fetchall()]

    clinics = [r for r in all_missing if "poliklinik" in r.get("employer_type", "").lower()]
    offices = [r for r in all_missing if "poliklinik" not in r.get("employer_type", "").lower()]

    # Mevcut 7 poliklinik + 23 muayenehane = 30 işletme
    sample_clinics = clinics[:10]  # Envanterde 7 adet var
    needed_offices = target_count - len(sample_clinics)
    sample_offices = offices[:needed_offices]
    pilot_pool = sample_clinics + sample_offices

    baseline_stats = {
        "total_records": len(pilot_pool),
        "polyclinics": len(sample_clinics),
        "private_offices": len(sample_offices),
        "phones": sum(1 for r in pilot_pool if (r.get("phone") or "").strip()),
        "emails": sum(1 for r in pilot_pool if (r.get("email") or "").strip()),
        "websites": sum(1 for r in pilot_pool if (r.get("website") or "").strip()),
        "contact_forms": sum(1 for r in pilot_pool if (r.get("contact_form_url") or "").strip())
    }

    search_router = SearchRouter()
    web_session = requests.Session()
    audit_diffs: List[Dict[str, Any]] = []

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today_str = datetime.now().strftime("%Y-%m-%d")

    for idx, r in enumerate(pilot_pool, 1):
        emp_id = r["employer_id"]
        old_p = (r.get("phone") or "").strip()
        old_e = (r.get("email") or "").strip()
        old_w = (r.get("website") or "").strip()
        old_f = (r.get("contact_form_url") or "").strip()

        print(f"[{idx:02d}/{len(pilot_pool)}] Araştırılıyor: {r['name']} ({r['employer_type']}) - {r['district']}")
        logger.info(f"[{idx:02d}/{len(pilot_pool)}] Araştırılıyor: {r['name']} ({r['employer_type']})")

        # V1.5 Web Arama Keşif Boru Hattı
        search_result = discover_employer_via_web_search(r, session=web_session, search_router=search_router)

        new_contacts = search_result.get("contacts", [])
        if new_contacts:
            for c in new_contacts:
                upsert_contact(cursor, emp_id, c, today_str)

        # Yeni web sitesi
        if search_result.get("website"):
            r["website"] = search_result["website"]
            r["website_source_url"] = search_result.get("website_source_url", search_result["website"])
            r["website_verification_status"] = search_result.get("website_verification_status", "observed_on_source")
            if search_result.get("contact_form_url"):
                r["contact_form_url"] = search_result["contact_form_url"]
            if search_result.get("career_url"):
                r["career_url"] = search_result["career_url"]
            if search_result.get("whatsapp_url"):
                r["whatsapp_url"] = search_result["whatsapp_url"]

        # Yeni e-posta
        new_emails = [c for c in new_contacts if c["contact_type"] == "email" and c.get("verification_status") != "invalid"]
        if new_emails and not r.get("email"):
            # Kariyer önceliği
            new_emails.sort(key=lambda x: (x.get("contact_category") != "career", x.get("contact_category") != "general"))
            best_e = new_emails[0]
            r["email"] = best_e["contact_value"]
            r["email_type"] = best_e.get("contact_category", "general")
            r["email_source_url"] = best_e.get("source_url", "")
            r["email_verification_status"] = best_e.get("verification_status", "observed_on_source")
            r["is_email_found"] = True

        # Yeni telefon
        new_phones = [c for c in new_contacts if c["contact_type"] == "phone" and c.get("verification_status") != "invalid"]
        if new_phones and not r.get("phone"):
            best_p = new_phones[0]
            r["phone"] = best_p["contact_value"]
            r["phone_type"] = best_p.get("contact_category", "corporate")
            r["phone_source_url"] = best_p.get("source_url", "")
            r["phone_verification_status"] = best_p.get("verification_status", "observed_on_source")

        # Araştırma notu ve denenen kaynaklar
        sources = set(filter(None, (r.get("attempted_sources", "")).split(", ")))
        for s in search_result.get("attempted_sources", []):
            sources.add(s)
        r["attempted_sources"] = ", ".join(sorted(sources))
        r["research_notes"] = search_result.get("research_notes", r.get("research_notes", ""))
        r["updated_at"] = now_str

        # Güncelle ve hemen kaydet
        upsert_employer(cursor, r, "dentist", city, today_str, now_str)
        conn.commit()

        new_p = (r.get("phone") or "").strip()
        new_e = (r.get("email") or "").strip()
        new_w = (r.get("website") or "").strip()
        new_f = (r.get("contact_form_url") or "").strip()

        is_improved = (new_p != old_p) or (new_e != old_e) or (new_w != old_w) or (new_f != old_f)

        audit_diffs.append({
            "employer_id": r["employer_id"],
            "name": r["name"],
            "employer_type": r["employer_type"],
            "district": r["district"],
            "old_phone": old_p,
            "new_phone": new_p,
            "old_email": old_e,
            "new_email": new_e,
            "old_website": old_w,
            "new_website": new_w,
            "old_contact_form": old_f,
            "new_contact_form": new_f,
            "is_improved": is_improved,
            "has_associated_clinic": bool(search_result.get("associated_clinic")),
            "associated_clinic": search_result.get("associated_clinic"),
            "search_status": search_result.get("search_status"),
            "search_provider": search_result.get("search_provider"),
            "contacts_found_count": len(new_contacts),
            "research_notes": r.get("research_notes", ""),
            "attempted_sources": r.get("attempted_sources", "")
        })

    conn.commit()
    if close_conn:
        conn.close()

    v1_5_stats = {
        "total_records": len(pilot_pool),
        "polyclinics": len(sample_clinics),
        "private_offices": len(sample_offices),
        "phones": sum(1 for r in pilot_pool if (r.get("phone") or "").strip()),
        "emails": sum(1 for r in pilot_pool if (r.get("email") or "").strip()),
        "websites": sum(1 for r in pilot_pool if (r.get("website") or "").strip()),
        "contact_forms": sum(1 for r in pilot_pool if (r.get("contact_form_url") or "").strip())
    }

    return {
        "baseline_stats": baseline_stats,
        "v1_5_stats": v1_5_stats,
        "improved_count": sum(1 for d in audit_diffs if d["is_improved"]),
        "new_websites_count": v1_5_stats["websites"] - baseline_stats["websites"],
        "new_phones_count": v1_5_stats["phones"] - baseline_stats["phones"],
        "new_emails_count": v1_5_stats["emails"] - baseline_stats["emails"],
        "audit_diffs": audit_diffs
    }

run_pilot_v1_3 = run_pilot_v1_4

