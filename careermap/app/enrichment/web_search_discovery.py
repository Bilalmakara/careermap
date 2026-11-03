"""CareerMap V1.5 Gerçek Web Arama Keşif ve Derin İletişim Zenginleştirme Motoru (Web Search Discovery).
- SearchRouter aracılığıyla FreeSerp ve alternatif arama motorlarını sorgular.
- Hedefli 2-3 arama sorgusu çalıştırır, sonuçları yerel SQLite önbelleğinde saklar.
- Aday web sitelerini V1.5 Çok Faktörlü Kimlik Eşleyicisi (website_identity_matcher) ile denetler.
- Doğrulanan sitelerde Deep Crawler ile çok sayfalı tarama (HTML, Form, JSON-LD, PDF) yapar.
- Tüm kontakları contact_validator ile tekil kalite denetiminden geçirir.
- Hekim vs. Poliklinik (Associated Clinic) ilişkilerini doğru modeller.
"""
import re
import logging
from typing import Optional, Dict, Any, List, Set
import requests

from .search_adapters import SearchRouter, FreeSerpAdapter, SearchResult
from .website_identity_matcher import match_website_identity, normalize_tr_text
from .contact_page_crawler import crawl_business_website
from .email_extractor import extract_emails_from_html
from .phone_extractor import extract_phones_from_html, inspect_phone_number, TR_PHONE_TEXT_RE, format_phone
from .contact_validator import validate_email_contact, validate_phone_contact, validate_associated_clinic
from .website_discovery import generate_domain_candidates

logger = logging.getLogger("careermap.enrichment.web_search_discovery")

HEADERS = {
    "User-Agent": "CareerMap/1.5 (Healthcare Website Verification; info@careermap.local)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

# Dizin, rehber, haber, ilan ve kamu portalları (İşletmenin kendi resmî sitesi değildir)
DIRECTORY_DOMAINS = {
    # Hekim & Sağlık Dizinleri
    "doktortakvimi.com", "doktorsitesi.com", "eniyihekim.com", "dentisarea.com",
    "dishek.org", "hekimler.net", "doktorburada.com", "turkiyeklinikleri.com",
    "kolayrandevu.com", "randevual.com", "sagliktaguven.com", "whatclinic.com",
    "drtarif.com", "doktorbul.com", "hekimport.com", "dishekimleri.net",
    "hekimhane.com.tr", "istebudoktor.com.tr", "doktorlar.net", "hekimce.com",
    # Sosyal Medya & İş Platformları
    "instagram.com", "facebook.com", "linkedin.com", "twitter.com", "x.com",
    "youtube.com", "tiktok.com", "pinterest.com",
    # Firma Rehberleri & İlan Siteleri
    "yellowpages.com.tr", "bulurum.com", "firmarehberi.com", "firmalar.gen.tr",
    "firmaportal.com", "ilandan.com", "eskisehirfirma.com", "esrehber.com",
    "sahibinden.com", "kariyer.net", "eleman.net", "yenibiris.com", "secretcv.com", "ilan.eskisehir.net.tr",
    # Haber & Medya & Forum Siteleri
    "haberler.com", "cumhuriyet.com.tr", "ntv.com.tr", "haberturk.com",
    "sozcu.com.tr", "hurriyet.com.tr", "milliyet.com.tr", "sabah.com.tr",
    "2eylul.com.tr", "eskisehirhaber26.com", "eskisehirekspres.net", "eskisehir.net", "eskisehir.net.tr",
    "anadolugazetesi.net", "sonhaber.com.tr", "isigmeclisi.org", "donanimhaber.com",
    "journo.com.tr", "meleklermekani.com", "kirmizisemsiye.org", "zoomeskisehir.com",
    # Üniversite, Hastane ve Kamu Kurumları
    "saglik.gov.tr", "baskent.edu.tr", "anadolu.edu.tr", "ogu.edu.tr",
    "kecioren.bel.tr", "tkd.org.tr", "eskisehir.bel.tr", "tepebasi.bel.tr", "odunpazari.bel.tr",
    # Perakende / Genel / Diğer
    "vodafone.com.tr", "turkcell.com.tr", "turktelekom.com.tr", "beko.com.tr",
    "trendyol.com", "hepsiburada.com", "amazon.com.tr", "idealmimarlik.com",
    "yaziatolyesi.com", "turkcenindirilisi.com", "garantibakici.com"
}

def is_third_party_directory(url: str) -> bool:
    """URL'in kurumun kendi müstakil web sitesi mi yoksa üçüncü taraf dizin/rehber/haber mi olduğunu tespit eder."""
    try:
        from urllib.parse import urlparse
        p = urlparse(url)
        netloc = p.netloc.lower().replace("www.", "")
        path = p.path.lower()
        query = p.query.lower()

        # 1. Bilinen liste eşleşmesi
        if any(d in netloc for d in DIRECTORY_DOMAINS):
            return True

        # 2. Kamu, belediye, üniversite alan adı uzantıları
        if netloc.endswith((".gov.tr", ".edu.tr", ".bel.tr", ".org.tr", ".k12.tr")):
            return True

        # 3. Alan adı içinde haber/rehber/ilan/medya kalıpları
        media_keywords = ["haber", "gazete", "ajans", "medya", "basin", "dergi", "rehber", "sozluk", "sözlük", "forum"]
        if any(mk in netloc for mk in media_keywords):
            return True

        # 4. URL path içinde haber/makale/dizin parametreleri
        article_paths = [
            "/haber/", "/haberler/", "/article/", "/makale/", "/clinics/", "/doktor-bul",
            "/threads/", "/sizin-sayfaniz", "/duyuru/", "/kategori/", "/firma-rehberi/",
            "/search/", "/klinikler", "/dis-hekimi/", "/hekimler/", "/doktorlar/"
        ]
        if any(ap in path for ap in article_paths):
            return True

        # 5. Dizin sorgu parametreleri (örn: ?ulke=TR&il=...)
        if "doktor-bul" in path or ("ulke=" in query and "il=" in query):
            return True

        return False
    except Exception:
        return False

def extract_directory_phones(
    employer: Dict[str, Any],
    search_candidates: List[SearchResult]
) -> List[Dict[str, Any]]:
    """
    İkincil sağlık rehberleri ve dizinlerinden (DoktorTakvimi, DentisArea vb.)
    işletmeye ait doğrulanabilir telefon numaralarını çıkarır.
    Statü: 'directory_observed'.
    Asla platform e-postası veya üçüncü taraf portal e-postası çıkarılmaz.
    """
    discovered_phones: List[Dict[str, Any]] = []
    seen_phones = set()

    raw_name = employer.get("name", "").strip()
    clean_name = re.sub(
        r"^(?:prof\.\s*dr\.|doç\.\s*dr\.|doc\.\s*dr\.|dr\.\s*dt\.|dt\.|dr\.|dt|dr)\s+",
        "", raw_name, flags=re.IGNORECASE
    ).strip()
    norm_name = normalize_tr_text(clean_name)
    name_tokens = [t for t in norm_name.split() if len(t) > 2]

    for cand in search_candidates:
        if not is_third_party_directory(cand.url):
            continue

        # Sadece rehber/dizin veya yerel dizinler (sosyal medya ve genel haberleri ele)
        non_directory_domains = {"instagram.com", "facebook.com", "linkedin.com", "twitter.com", "x.com", "youtube.com", "tiktok.com"}
        if any(nd in cand.domain for nd in non_directory_domains):
            continue

        text_to_search = f"{cand.title} {cand.snippet}"
        norm_text = normalize_tr_text(text_to_search)

        # İsim eşleşmesi kontrolü: en az iki isim parçasının metinde geçmesi
        name_match = False
        if len(name_tokens) >= 2:
            if all(tok in norm_text for tok in name_tokens):
                name_match = True
        elif len(name_tokens) == 1:
            if name_tokens[0] in norm_text:
                name_match = True

        if not name_match:
            continue

        # TR telefon regexi ile ara
        matches = TR_PHONE_TEXT_RE.finditer(text_to_search)
        for m in matches:
            full_raw = m.group(0)
            area_code = m.group(1)
            # Çağrı merkezlerini (0850, 444) atla
            if area_code.startswith("850") or full_raw.startswith(("444", "0850", "+90850")):
                continue

            phone_info = inspect_phone_number(full_raw)
            if phone_info.get("is_valid") and not phone_info.get("is_foreign"):
                formatted = phone_info.get("formatted")
                if formatted and formatted not in seen_phones:
                    seen_phones.add(formatted)
                    cat = "mobile" if phone_info.get("line_type") == "mobile" else "corporate"
                    discovered_phones.append({
                        "contact_type": "phone",
                        "contact_value": formatted,
                        "contact_category": cat,
                        "source_url": cand.url,
                        "source_type": "directory",
                        "discovery_method": "directory_listing",
                        "evidence_text": f"Sağlık Rehberi Gözlemi ({cand.domain}): {cand.title}",
                        "confidence_category": "kaynakli",
                        "verification_status": "directory_observed"
                    })

    return discovered_phones

def discover_employer_via_web_search(
    employer: Dict[str, Any],
    session: Optional[requests.Session] = None,
    search_router: Optional[SearchRouter] = None,
    max_crawl_pages: int = 5
) -> Dict[str, Any]:
    """
    İşletme için gerçek web araması (FreeSerp vb.) yapar, aday siteleri doğrular
    ve derin iletişim çıkarma sürecini yürütür.
    """
    result = {
        "website": "",
        "website_source_url": "",
        "website_verification_status": "unverified",
        "career_url": "",
        "contact_form_url": "",
        "appointment_form_url": "",
        "whatsapp_url": "",
        "associated_clinic": None,
        "contacts": [],
        "research_notes": "",
        "attempted_sources": [],
        "search_status": "pending",
        "search_provider": "freeserp"
    }

    if session is None:
        session = requests.Session()

    if search_router is None:
        search_router = SearchRouter()

    # 1. GERÇEK WEB ARAMASI ÇALIŞTIR
    result["attempted_sources"].append("FreeSerp Web Arama")
    search_res = search_router.search_for_employer(employer, max_results_per_query=5)
    result["search_status"] = search_res.get("status", "unknown")
    result["search_provider"] = search_res.get("provider_used", "freeserp")

    search_candidates: List[SearchResult] = search_res.get("candidates", [])
    queries_run = search_res.get("queries_executed", [])

    # İkincil Sağlık Rehberi Telefon Tespiti (directory_observed)
    directory_phones = extract_directory_phones(employer, search_candidates)
    if directory_phones:
        result["attempted_sources"].append("Sağlık Rehberi İncelemesi")
        for dp in directory_phones:
            result["contacts"].append(dp)

    # Aday Havuzunu Oluştur (Öncelik: Arama Sonuçları -> Mevcut Site -> Dizin Snippet Alan Adları -> Alan Adı Tahminleri)
    candidate_urls: List[str] = []
    seen_urls = set()

    # A. Arama motorundan gelen bağımsız web siteleri (Dizinler hariç)
    for c in search_candidates:
        c_url = c.url.rstrip("/")
        if c_url not in seen_urls and not is_third_party_directory(c_url):
            seen_urls.add(c_url)
            candidate_urls.append(c_url)
        elif is_third_party_directory(c_url):
            # Dizin snippet'i içinde geçen olası bağımsız site alan adlarını çek
            found_domains = re.findall(r'(?:https?://)?([a-zA-Z0-9-]+\.(?:com\.tr|com|org\.tr|net\.tr|net))', c.snippet)
            for fd in found_domains:
                fd_clean = fd.lower().strip()
                if not any(d in fd_clean for d in DIRECTORY_DOMAINS):
                    full_cand = f"https://{fd_clean}"
                    if full_cand not in seen_urls:
                        seen_urls.add(full_cand)
                        candidate_urls.append(full_cand)

    # B. İşletmede zaten kayıtlı bir site adayı varsa ekle
    existing_web = (employer.get("website") or "").strip()
    if existing_web and existing_web not in seen_urls:
        seen_urls.add(existing_web)
        candidate_urls.insert(0, existing_web)

    # C. Düşük Öncelikli Alan Adı Tahmini (Yalnızca arama sonucu yetersizse fallback olarak)
    if len(candidate_urls) < 2:
        result["attempted_sources"].append("Alan Adı Heuristic Fallback")
        heuristics = generate_domain_candidates(employer.get("name", ""), employer.get("employer_type", ""))
        for h in heuristics[:8]:  # İlk 8 en muhtemel aday
            if h not in seen_urls:
                seen_urls.add(h)
                candidate_urls.append(h)

    if not candidate_urls:
        if directory_phones:
            result["research_notes"] = f"Web Araması ({result['search_provider']}): Bağımsız site bulunamadı; ikincil sağlık rehberi üzerinden telefon tespit edildi."
        else:
            result["research_notes"] = f"Web Araması ({result['search_provider']}): {len(queries_run)} hedefli sorgu çalıştırıldı, uygun aday bulunamadı."
        return result

    # 2. ADAY WEB SİTELERİNİ KİMLİK EŞLEME İLE DENETLE
    # Tüm adayları puanla; en yüksek puan alan ve kesin 'observed_on_source' olan adayı seç
    best_candidate = None
    best_verification_evidence = ""
    best_match_data = None
    best_score = -1

    for cand_url in candidate_urls:
        if is_third_party_directory(cand_url):
            continue
        try:
            resp = session.get(cand_url, headers=HEADERS, timeout=3.5, allow_redirects=True)
            # Yerel ağ / captive portal tespiti
            if "192.168.1.1" in resp.url or "redirect.html" in resp.url:
                logger.warning(f"Ağ yönlendirme (captive portal) tespit edildi: {resp.url}")
                continue
            if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", "").lower():
                if is_third_party_directory(resp.url):
                    continue
                m_res = match_website_identity(employer, resp.text, resp.url)
                if m_res["is_match"] and m_res["status"] == "observed_on_source" and m_res["match_score"] > best_score:
                    best_candidate = resp.url.rstrip("/")
                    best_verification_evidence = m_res["evidence_snippet"]
                    best_match_data = m_res
                    best_score = m_res["match_score"]
        except requests.exceptions.SSLError as ssl_err:
            logger.warning(f"SSL Doğrulama Hatası ({cand_url}): {ssl_err}")
            # SSL doğrulaması asla kapatılmaz (verify=True zorunludur)
        except requests.exceptions.Timeout:
            logger.debug(f"Zaman aşımı: {cand_url}")
        except requests.exceptions.RequestException as req_err:
            logger.debug(f"Ağ isteği hatası ({cand_url}): {req_err}")
        except Exception as e:
            logger.debug(f"Beklenmeyen hata ({cand_url}): {e}")

    if not best_candidate or not best_match_data:
        if directory_phones:
            result["research_notes"] = f"Web Araması ({result['search_provider']}): Bağımsız site doğrulanamadı; ikincil sağlık rehberi üzerinden telefon tespit edildi ({len(directory_phones)} numara)."
        else:
            result["research_notes"] = f"Web Araması ({result['search_provider']}): {len(candidate_urls)} aday adres incelendi; kimlik eşleşmesi doğrulanamadı."
        return result

    verified_candidate = best_candidate
    verification_evidence = best_verification_evidence
    match_data = best_match_data

    # 3. WEB SİTESİ DOĞRULANDI!
    result["website"] = verified_candidate
    result["website_source_url"] = verified_candidate
    result["website_verification_status"] = match_data["status"]

    # Web sitesi temas noktası kaydı
    result["contacts"].append({
        "contact_type": "website",
        "contact_value": verified_candidate,
        "contact_category": "corporate",
        "source_url": verified_candidate,
        "source_type": "website_scrape",
        "discovery_method": "web_search_identity_match",
        "evidence_text": f"Puan: {match_data['match_score']} | {verification_evidence}",
        "confidence_category": match_data["confidence_category"],
        "verification_status": match_data["status"]
    })

    # Associated Clinic Tespiti (Hekim poliklinik kadrosunda bulunduysa)
    if match_data.get("is_associated_clinic") and match_data.get("associated_clinic"):
        assoc = match_data["associated_clinic"]
        result["associated_clinic"] = assoc
        result["contacts"].append({
            "contact_type": "associated_clinic",
            "contact_value": assoc.get("clinic_name", ""),
            "contact_category": "associated_clinic",
            "source_url": assoc.get("clinic_url", ""),
            "source_type": "website_scrape",
            "discovery_method": "staff_roster_match",
            "evidence_text": assoc.get("evidence_text", ""),
            "confidence_category": "kaynakli",
            "verification_status": "observed_on_source"
        })

    # 4. ÇOK SAYFALI DERİN TARAMA (Deep Crawler)
    crawl_res = crawl_business_website(
        website_url=verified_candidate,
        session=session,
        max_pages=max_crawl_pages,
        enable_js_fallback=False,
        enable_pdf_extraction=True
    )

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
            "verification_status": "observed_on_source"
        })

    if crawl_res.get("appointment_form_url"):
        result["appointment_form_url"] = crawl_res["appointment_form_url"]

    if crawl_res.get("whatsapp_url"):
        result["whatsapp_url"] = crawl_res["whatsapp_url"]
        result["contacts"].append({
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
            v_phone = validate_phone_contact(crawl_res["whatsapp_phone"], employer, source_url=crawl_res["whatsapp_url"])
            if v_phone["is_valid"]:
                result["contacts"].append({
                    "contact_type": "phone",
                    "contact_value": v_phone["formatted_phone"],
                    "contact_category": "mobile",
                    "source_url": crawl_res["whatsapp_url"],
                    "source_type": "website_scrape",
                    "discovery_method": "whatsapp_number",
                    "evidence_text": f"WhatsApp Mobil Hattı: {v_phone['formatted_phone']}",
                    "confidence_category": "kaynakli",
                    "verification_status": "observed_on_source"
                })

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
            "evidence_text": f"Kariyer Sayfası: {career_page}",
            "confidence_category": "kaynakli",
            "verification_status": "observed_on_source"
        })

    # 5. TARANAN TÜM SAYFALARDAN VE PDF DOKÜMANLARINDAN İLETİŞİM ÇIKARMA
    seen_contacts = {c["contact_value"] for c in result["contacts"]}

    for page in crawl_res.get("pages", []):
        page_url = page["url"]
        html_text = page["html"]
        soup = page.get("soup")

        # E-postalar
        page_emails = extract_emails_from_html(html_text, page_url, soup=soup)
        for pe in page_emails:
            v_email = validate_email_contact(pe["contact_value"], employer, source_url=page_url)
            if v_email["is_valid"] and v_email["cleaned_email"] not in seen_contacts:
                seen_contacts.add(v_email["cleaned_email"])
                pe["contact_value"] = v_email["cleaned_email"]
                pe["verification_status"] = v_email["verification_status"]
                pe["contact_category"] = v_email["email_type"]
                result["contacts"].append(pe)

        # Telefonlar
        page_phones = extract_phones_from_html(html_text, page_url, soup=soup)
        for pp in page_phones:
            v_phone = validate_phone_contact(pp["contact_value"], employer, source_url=page_url)
            if v_phone["is_valid"] and v_phone["formatted_phone"] not in seen_contacts:
                seen_contacts.add(v_phone["formatted_phone"])
                pp["contact_value"] = v_phone["formatted_phone"]
                pp["verification_status"] = v_phone["verification_status"]
                pp["contact_category"] = v_phone["phone_type"]
                result["contacts"].append(pp)

    # PDF Doküman Metinleri Taraması
    for pdf_item in crawl_res.get("pdf_texts", []):
        pdf_url = pdf_item["url"]
        pdf_text = pdf_item["text"]
        
        pdf_emails = extract_emails_from_html(pdf_text, pdf_url)
        for pe in pdf_emails:
            v_email = validate_email_contact(pe["contact_value"], employer, source_url=pdf_url)
            if v_email["is_valid"] and v_email["cleaned_email"] not in seen_contacts:
                seen_contacts.add(v_email["cleaned_email"])
                pe["discovery_method"] = "pdf_text_extraction"
                result["contacts"].append(pe)

    result["research_notes"] = f"Web Araması ({result['search_provider']}): {verified_candidate} doğrulandı ({match_data['match_score']} puan), {len(crawl_res.get('pages', []))} sayfa tarandı."
    return result
