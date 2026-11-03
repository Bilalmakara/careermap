"""CareerMap V1.4 Çok Kaynaklı Web Sitesi Keşif ve İletişim Zenginleştirme Motoru.
- Çok kaynaklı aday toplama (OSM etiketleri, kurumsal alan adı kalıpları, dizinler).
- `website_identity_matcher.py` ile kesin kimlik ve kanıt denetimi.
- `contact_page_crawler.py` ile çok sayfalı nazik tarama.
- `email_extractor.py` ve `phone_extractor.py` ile kanıtlı iletişim çıkarma.
"""
import logging
import re
import unicodedata
from typing import Optional, Dict, Any, List, Set
import requests

from .website_identity_matcher import match_website_identity, normalize_tr_text
from .contact_page_crawler import crawl_business_website
from .email_extractor import extract_emails_from_html
from .phone_extractor import extract_phones_from_html

logger = logging.getLogger("careermap.enrichment.discovery")

HEADERS = {
    "User-Agent": "CareerMap/1.4 (Healthcare Website Verification; info@careermap.local)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

def generate_domain_candidates(raw_name: str, employer_type: str) -> List[str]:
    """İşletme unvanından veya hekim ad-soyadından alan adı adayları (URL listesi) üretir."""
    is_office = "muayenehane" in employer_type.lower() or raw_name.strip().lower().startswith("dt")
    
    s = normalize_tr_text(raw_name)
    candidates: List[str] = []

    if is_office:
        clean = re.sub(r"^(?:prof\s*dr|doc\s*dr|dr\s*dt|dt|dr)\s+", "", s.strip())
        parts = [re.sub(r"[^a-z0-9]", "", p) for p in clean.split() if len(p) >= 2]
        
        if len(parts) >= 2:
            ad = "".join(parts[:-1])
            soyad = parts[-1]
            slug = f"{ad}{soyad}"
            
            domain_list = [
                f"https://www.dt{slug}.com",
                f"https://dt{slug}.com",
                f"https://www.dt{slug}.com.tr",
                f"https://dt{slug}.com.tr",
                f"https://www.dr{slug}.com",
                f"https://www.dr{slug}.com.tr",
                f"https://www.{slug}.com.tr",
                f"https://www.{slug}.com",
                f"https://{slug}.com.tr",
                f"https://www.{slug}dis.com",
                f"https://www.{slug}dental.com"
            ]
            if len(soyad) >= 4:
                domain_list.extend([
                    f"https://www.dt{soyad}.com",
                    f"https://www.dt{soyad}.com.tr"
                ])
            candidates.extend(domain_list)

        elif len(parts) == 1 and len(parts[0]) >= 3:
            slug = parts[0]
            candidates.append(f"https://www.dt{slug}.com")
            candidates.append(f"https://www.dt{slug}.com.tr")

    else:
        # Poliklinik ve Klinik Adayları
        clean = re.sub(r"\b(ozel|agiz|ve|dis|sagligi|poliklinigi|poliklinik|klinik|merkezi)\b", " ", s)
        slug = re.sub(r"[^a-z0-9]", "", clean)
        
        if len(slug) >= 3:
            domain_list = [
                f"https://www.{slug}.com.tr",
                f"https://www.{slug}.com",
                f"https://{slug}.com.tr",
                f"https://{slug}.com",
                f"https://www.{slug}dis.com.tr",
                f"https://www.{slug}dis.com",
                f"https://www.{slug}dental.com",
                f"https://www.{slug}eskisehir.com",
                f"https://www.{slug}diseskisehir.com",
                f"https://www.{slug}dentaleskisehir.com",
                f"https://www.dent{slug}.com",
                f"https://www.dent{slug}eskisehir.com",
                f"https://www.{slug}agizvedis.com"
            ]
            candidates.extend(domain_list)

    # Tekilleştirip sırayı koru
    seen = set()
    unique_candidates = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique_candidates.append(c)

    return unique_candidates

def verify_candidate_website(
    url: str,
    target_name: str,
    city: str = "Eskişehir",
    session: Optional[requests.Session] = None
) -> Optional[Dict[str, str]]:
    """Geriye dönük uyumluluk: Aday web sitesini doğrular."""
    if session is None:
        session = requests.Session()

    try:
        resp = session.get(url, headers=HEADERS, timeout=5, allow_redirects=True)
        if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", "").lower():
            target_emp = {"name": target_name, "city": city, "employer_type": "Genel İşveren"}
            match_res = match_website_identity(target_emp, resp.text, resp.url)
            if match_res["is_match"]:
                return {
                    "website": resp.url.rstrip("/"),
                    "website_source_url": resp.url.rstrip("/"),
                    "status": match_res["status"]
                }
    except Exception:
        pass

    return None

def discover_website_for_employer(
    employer: Dict[str, Any],
    session: Optional[requests.Session] = None
) -> Optional[Dict[str, str]]:
    """Geriye dönük uyumluluk: İşletme için web sitesi keşfeder."""
    candidates = generate_domain_candidates(employer.get("name", ""), employer.get("employer_type", ""))
    if not candidates:
        return None

    if session is None:
        session = requests.Session()

    for cand_url in candidates:
        verified = verify_candidate_website(cand_url, employer.get("name", ""), employer.get("city", "Eskişehir"), session)
        if verified:
            return verified

    return None

def discover_and_extract_website_contacts(
    employer: Dict[str, Any],
    session: Optional[requests.Session] = None
) -> Dict[str, Any]:
    """
    İşletme için çok kaynaklı web sitesi araştırması yapar, kimliği doğrular ve
    çok sayfalı taramayla tüm telefon, e-posta ve form kanallarını kanıtlarıyla çıkarır.
    """
    result = {
        "website": "",
        "website_source_url": "",
        "website_verification_status": "unverified",
        "career_url": "",
        "contact_form_url": "",
        "appointment_form_url": "",
        "contacts": [],
        "research_notes": "",
        "attempted_sources": []
    }

    if session is None:
        session = requests.Session()

    candidate_pool: List[str] = []

    # 1. Mevcut veya OSM'den gelen web sitesi bağlantısı varsa ilk sıraya koy
    existing_web = (employer.get("website") or "").strip()
    if existing_web:
        candidate_pool.append(existing_web)

    # 2. Üretilen adayları havuza ekle
    generated = generate_domain_candidates(employer.get("name", ""), employer.get("employer_type", ""))
    for u in generated:
        if u not in candidate_pool:
            candidate_pool.append(u)

    if not candidate_pool:
        result["research_notes"] = "Web: Uygun alan adı adayı üretilemedi."
        return result

    result["attempted_sources"].append("Web Keşif Motoru")
    verified_candidate = None
    verification_evidence = ""
    match_data = None

    for cand_url in candidate_pool:
        try:
            resp = session.get(cand_url, headers=HEADERS, timeout=5, allow_redirects=True)
            if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", "").lower():
                # Kimlik ve Kanıt Denetimi
                match_res = match_website_identity(employer, resp.text, resp.url)
                if match_res["is_match"]:
                    verified_candidate = resp.url.rstrip("/")
                    verification_evidence = match_res["evidence_snippet"]
                    match_data = match_res
                    break
        except Exception:
            pass

    if not verified_candidate or not match_data:
        result["research_notes"] = f"Web: {len(candidate_pool)} aday adres denendi, kimlik doğrulaması sağlanamadı."
        return result

    # Web Sitesi Doğrulandı!
    result["website"] = verified_candidate
    result["website_source_url"] = verified_candidate
    result["website_verification_status"] = match_data["status"]
    
    # Web sitesi kontak kaydı
    result["contacts"].append({
        "contact_type": "website",
        "contact_value": verified_candidate,
        "contact_category": "corporate",
        "source_url": verified_candidate,
        "source_type": "website_scrape",
        "discovery_method": "identity_matcher",
        "evidence_text": f"Puan: {match_data['match_score']} | {verification_evidence}",
        "confidence_category": match_data["confidence_category"],
        "verification_status": match_data["status"]
    })

    # 3. Çok Sayfalı Saygılı Tarama (Crawler)
    crawl_res = crawl_business_website(verified_candidate, session=session, max_pages=5)
    
    if crawl_res.get("contact_form_url"):
        result["contact_form_url"] = crawl_res["contact_form_url"]
        result["contacts"].append({
            "contact_type": "contact_form",
            "contact_value": crawl_res["contact_form_url"],
            "contact_category": "contact_form",
            "source_url": crawl_res["contact_form_url"],
            "source_type": "website_scrape",
            "discovery_method": "form_action",
            "evidence_text": crawl_res.get("contact_form_evidence", "İletişim Formu"),
            "confidence_category": "kaynakli",
            "verification_status": "verified"
        })

    if crawl_res.get("appointment_form_url"):
        result["appointment_form_url"] = crawl_res["appointment_form_url"]

    if crawl_res.get("career_page_urls"):
        career_page = crawl_res["career_page_urls"][0]
        result["career_url"] = career_page
        result["contacts"].append({
            "contact_type": "career_page",
            "contact_value": career_page,
            "contact_category": "career",
            "source_url": career_page,
            "source_type": "website_scrape",
            "discovery_method": "internal_link",
            "evidence_text": f"Kariyer Sayfası Linki: {career_page}",
            "confidence_category": "kaynakli",
            "verification_status": "verified"
        })

    # 4. Taranan Tüm Sayfalardan E-posta ve Telefonları Çıkar
    seen_contacts = {c["contact_value"] for c in result["contacts"]}

    for page in crawl_res.get("pages", []):
        page_url = page["url"]
        html_text = page["html"]
        soup = page.get("soup")

        # E-postalar
        page_emails = extract_emails_from_html(html_text, page_url, soup=soup)
        for pe in page_emails:
            if pe["contact_value"] not in seen_contacts:
                seen_contacts.add(pe["contact_value"])
                result["contacts"].append(pe)

        # Telefonlar
        page_phones = extract_phones_from_html(html_text, page_url, soup=soup)
        for pp in page_phones:
            if pp["contact_value"] not in seen_contacts:
                seen_contacts.add(pp["contact_value"])
                result["contacts"].append(pp)

    result["research_notes"] = f"Web: {verified_candidate} doğrulandı ({match_data['match_score']} puan), {len(crawl_res.get('pages', []))} sayfa tarandı."
    return result
