"""CareerMap V1.5 Saygılı, Çok Sayfalı ve Derin İletişim & Doküman Tarayıcısı (Deep Crawler).
- Çok sayfalı hedefli tarama: Ana sayfa, iletişim, hakkımızda, kariyer, hekim kadrosu/ekibimiz, şubeler.
- İletişim formu ile hasta randevu formunu kesin parametrelerle ayırt eder.
- İlgili ve izinli kurumsal PDF dokümanlarından (iletişim, bilgilendirme, kvkk) iletişim çıkarma desteği.
- JavaScript ile dinamik render edilen sayfalar için Playwright tabanlı hafif fallback.
- Nazik tarama kurallarına uyar (maksimum sayfa limiti, kısa zaman aşımı, domain içi kalma).
"""
import io
import re
import logging
from urllib.parse import urlparse, urljoin
from typing import Dict, Any, List, Optional, Set
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("careermap.enrichment.crawler")

HEADERS = {
    "User-Agent": "CareerMap/1.5 (Polite Healthcare Contact & Career Research; info@careermap.local)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

def is_appointment_form(form_tag: Any) -> bool:
    """Formun hasta randevu formu olup olmadığını denetler."""
    text = form_tag.get_text(" ", strip=True).lower()
    action = form_tag.get("action", "").lower()
    
    inputs = [
        (inp.get("name", "") + " " + inp.get("id", "") + " " + inp.get("placeholder", "")).lower()
        for inp in form_tag.find_all(["input", "select", "textarea", "button"])
    ]
    inputs_str = " ".join(inputs)

    appointment_signals = [
        "randevu", "tarih", "saat", "doktor", "hekim", "brans", "klinik",
        "sikayet", "tc_kimlik", "tc", "poliklinik_secimi", "appointment"
    ]
    matches = sum(1 for s in appointment_signals if s in inputs_str or s in text[:300] or s in action)
    return matches >= 2

def is_contact_form(form_tag: Any) -> bool:
    """Formun kurumsal iletişim veya başvuru formu olup olmadığını denetler."""
    if is_appointment_form(form_tag):
        return False
        
    text = form_tag.get_text(" ", strip=True).lower()
    action = form_tag.get("action", "").lower()
    
    inputs = [
        (inp.get("name", "") + " " + inp.get("id", "") + " " + inp.get("placeholder", "")).lower()
        for inp in form_tag.find_all(["input", "select", "textarea", "button"])
    ]
    inputs_str = " ".join(inputs)

    contact_signals = ["mesaj", "message", "email", "eposta", "telefon", "phone", "ad", "soyad", "konu", "subject"]
    matches = sum(1 for s in contact_signals if s in inputs_str or s in text[:300] or s in action)
    return matches >= 2

def extract_text_from_pdf_stream(pdf_bytes: bytes) -> str:
    """PDF içeriğinden metin çıkarır (pdfplumber veya pypdf ile)."""
    if not pdf_bytes or len(pdf_bytes) < 50:
        return ""
    text = ""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages[:5]:  # İlk 5 sayfa yeterli
                page_text = page.extract_text()
                if page_text:
                    text += " " + page_text
        return text.strip()
    except Exception:
        pass

    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages[:5]:
            t = page.extract_text()
            if t:
                text += " " + t
        return text.strip()
    except Exception:
        pass

    return ""

def fetch_page_with_js_fallback(url: str, timeout_sec: int = 6) -> Optional[str]:
    """
    HTTP isteğinin yetersiz kaldığı (boş JS iskeleti döndüğü) durumlarda
    Playwright headless tarayıcı ile sayfayı render eder.
    """
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=HEADERS["User-Agent"])
            page.goto(url, timeout=timeout_sec * 1000, wait_until="domcontentloaded")
            content = page.content()
            browser.close()
            return content
    except Exception as e:
        logger.debug(f"Playwright JS fallback çağrısı başarısız ({url}): {e}")
        return None

def normalize_link_text(text: str) -> str:
    """Türkçe karakterleri normalize ederek link metinlerini eşleştirir."""
    if not text:
        return ""
    s = text.replace("I", "ı").replace("İ", "i").lower()
    return s.translate(str.maketrans("çğıöşü", "cgiosu"))

def crawl_business_website(
    website_url: str,
    session: Optional[requests.Session] = None,
    max_pages: int = 6,
    enable_js_fallback: bool = False,
    enable_pdf_extraction: bool = True
) -> Dict[str, Any]:
    """
    Hedef web sitesinin ana sayfasını ve ilgili kurumsal alt sayfalarını saygılı biçimde tarar;
    HTML içeriklerini, WhatsApp bağlantılarını, form bağlantılarını ve PDF metinlerini toplar.
    """
    result = {
        "homepage_url": website_url,
        "contact_page_urls": [],
        "career_page_urls": [],
        "team_page_urls": [],
        "appointment_page_urls": [],
        "pdf_document_urls": [],
        "whatsapp_url": "",
        "whatsapp_phone": "",
        "contact_form_url": "",
        "contact_form_evidence": "",
        "appointment_form_url": "",
        "access_status": "ok",
        "access_error": "",
        "pages": [],  # List of dicts: {"url": ..., "html": ..., "page_type": ..., "soup": ...}
        "pdf_texts": []  # List of dicts: {"url": ..., "text": ...}
    }

    if not website_url or not website_url.startswith(("http://", "https://")):
        return result

    if session is None:
        session = requests.Session()

    parsed_base = urlparse(website_url)
    base_domain = parsed_base.netloc.lower().replace("www.", "")

    visited_urls: Set[str] = set()
    candidate_queue: List[Dict[str, str]] = [
        {"url": website_url, "type": "homepage"}
    ]

    successful_pages = 0
    total_attempts = 0
    max_attempts = max_pages * 3
    found_contact_page_in_html = False

    while candidate_queue and successful_pages < max_pages and total_attempts < max_attempts:
        total_attempts += 1
        item = candidate_queue.pop(0)
        target_url = item["url"]

        if target_url in visited_urls:
            continue
        visited_urls.add(target_url)

        try:
            resp = session.get(target_url, headers=HEADERS, timeout=6, allow_redirects=True)
            final_page_url = resp.url
            content_type = resp.headers.get("content-type", "").lower()

            # Captive portal / yerel ağ yönlendirmesi denetimi (192.168.1.1 / router interception)
            raw_text_peek = resp.text[:1200]
            if "192.168.1.1" in raw_text_peek or ("top.location.href" in raw_text_peek and "redirect.html" in raw_text_peek):
                result["access_status"] = "network_interception"
                result["access_error"] = "Yerel ağ geçidi / captive portal yönlendirmesi tespit edildi (192.168.1.1)."
                logger.warning(f"Yerel ağ yönlendirmesi tespit edildi: {target_url}")
                continue

            # PDF Dokümanı Kontrolü
            if "application/pdf" in content_type or target_url.lower().endswith(".pdf"):
                if enable_pdf_extraction and len(resp.content) < 3 * 1024 * 1024:  # < 3MB
                    pdf_text = extract_text_from_pdf_stream(resp.content)
                    if pdf_text:
                        result["pdf_document_urls"].append(final_page_url)
                        result["pdf_texts"].append({
                            "url": final_page_url,
                            "text": pdf_text
                        })
                successful_pages += 1
                continue

            if resp.status_code != 200 or "text/html" not in content_type:
                continue

            html_text = resp.text

            # JS İskelet Kontrolü
            if enable_js_fallback and len(html_text.strip()) < 300 and ("<div id=\"root\">" in html_text or "<div id=\"app\">" in html_text):
                rendered = fetch_page_with_js_fallback(final_page_url)
                if rendered and len(rendered) > len(html_text):
                    html_text = rendered

            soup = BeautifulSoup(html_text, "html.parser")
            successful_pages += 1

            # Sayfa türü tespiti
            url_lower = final_page_url.lower()
            page_type = item["type"]
            if any(k in url_lower for k in ["kariyer", "career", "is-basvuru", "insan-kaynaklari"]):
                page_type = "career"
                if final_page_url not in result["career_page_urls"]:
                    result["career_page_urls"].append(final_page_url)
            elif any(k in url_lower for k in ["iletisim", "bize-ulasin", "contact", "adres"]):
                page_type = "contact"
                found_contact_page_in_html = True
                if final_page_url not in result["contact_page_urls"]:
                    result["contact_page_urls"].append(final_page_url)
            elif any(k in url_lower for k in ["ekibimiz", "hekimlerimiz", "kadromuz", "doktorlarimiz", "hekimler"]):
                page_type = "team"
                if final_page_url not in result["team_page_urls"]:
                    result["team_page_urls"].append(final_page_url)
            elif any(k in url_lower for k in ["randevu", "appointment"]):
                page_type = "appointment"
                if final_page_url not in result["appointment_page_urls"]:
                    result["appointment_page_urls"].append(final_page_url)

            # WhatsApp Bağlantısı Tespiti
            for a in soup.find_all("a", href=True):
                href_str = a["href"].strip()
                if any(wa in href_str.lower() for wa in ["wa.me/", "api.whatsapp.com", "whatsapp.com/send", "whatsapp:"]):
                    if not result["whatsapp_url"]:
                        result["whatsapp_url"] = href_str
                        # Numarayı ayıkla
                        num_m = re.search(r'(?:phone=|\.me/|\+?)(\d{10,13})', href_str)
                        if num_m:
                            num_raw = num_m.group(1)
                            if num_raw.startswith("90") and len(num_raw) == 12:
                                num_raw = "0" + num_raw[2:]
                            elif len(num_raw) == 10:
                                num_raw = "0" + num_raw
                            result["whatsapp_phone"] = num_raw

            # Form Denetimi
            forms = soup.find_all("form")
            for f in forms:
                if is_contact_form(f) and not result["contact_form_url"]:
                    result["contact_form_url"] = final_page_url
                    result["contact_form_evidence"] = f"İletişim Formu: {str(f)[:120]}"
                elif is_appointment_form(f) and not result["appointment_form_url"]:
                    result["appointment_form_url"] = final_page_url

            result["pages"].append({
                "url": final_page_url,
                "html": html_text,
                "soup": soup,
                "page_type": page_type
            })

            # Ana sayfadan veya menülerden yeni bağlantıları keşfet
            if page_type in ["homepage", "standard_guess"]:
                discovered_links: List[Dict[str, str]] = []
                for a in soup.find_all("a", href=True):
                    href = a["href"].strip()
                    if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                        continue
                    abs_url = urljoin(final_page_url, href)
                    p_abs = urlparse(abs_url)

                    # Aynı domain altında kal
                    if p_abs.netloc.lower().replace("www.", "") == base_domain:
                        l_href = normalize_link_text(href)
                        l_text = normalize_link_text(a.get_text(" ", strip=True))

                        if any(k in l_href or k in l_text for k in ["kariyer", "career", "is basvurusu", "is-basvuru", "insan kaynaklari"]):
                            if abs_url not in visited_urls:
                                discovered_links.append({"url": abs_url, "type": "career"})
                                if abs_url not in result["career_page_urls"]:
                                    result["career_page_urls"].append(abs_url)

                        elif any(k in l_href or k in l_text for k in ["iletisim", "bize ulasin", "bize-ulasin", "contact", "adres"]):
                            if abs_url not in visited_urls:
                                found_contact_page_in_html = True
                                discovered_links.append({"url": abs_url, "type": "contact"})
                                if abs_url not in result["contact_page_urls"]:
                                    result["contact_page_urls"].append(abs_url)

                        elif any(k in l_href or k in l_text for k in ["ekibimiz", "hekimlerimiz", "kadromuz", "doktorlarimiz"]):
                            if abs_url not in visited_urls:
                                discovered_links.append({"url": abs_url, "type": "team"})
                                if abs_url not in result["team_page_urls"]:
                                    result["team_page_urls"].append(abs_url)

                        elif any(k in l_href or k in l_text for k in ["randevu", "e-randevu"]):
                            if abs_url not in visited_urls:
                                if abs_url not in result["appointment_page_urls"]:
                                    result["appointment_page_urls"].append(abs_url)

                        elif abs_url.lower().endswith(".pdf") and any(k in l_href for k in ["iletisim", "kvkk", "bilgilendirme"]):
                            if abs_url not in visited_urls:
                                discovered_links.append({"url": abs_url, "type": "pdf"})

                # Sayfada açıkça bulunan bağlantıları kuyruğun en önüne al
                for d_link in reversed(discovered_links):
                    if d_link["url"] not in visited_urls and d_link not in candidate_queue:
                        candidate_queue.insert(0, d_link)

                # Eğer ana sayfada hiçbir iletişim linki bulunamadıysa, standart tahminleri kuyruğun sonuna ekle
                if not found_contact_page_in_html and not any(q["type"] == "contact" for q in candidate_queue):
                    for p in ["iletisim.php", "iletisim", "iletisim.html", "contact.php", "contact", "bize-ulasin"]:
                        g_url = urljoin(website_url.rstrip("/") + "/", p)
                        if g_url not in visited_urls:
                            candidate_queue.append({"url": g_url, "type": "standard_guess"})

        except requests.exceptions.SSLError as ssl_err:
            result["access_status"] = "ssl_error"
            result["access_error"] = f"SSL Sertifika Hatası: {ssl_err}"
            logger.warning(f"SSL hatası ({target_url}): {ssl_err}")
        except requests.exceptions.RequestException as req_err:
            logger.debug(f"Sayfa getirme hatası ({target_url}): {req_err}")
        except Exception as e:
            logger.debug(f"Beklenmeyen tarama hatası ({target_url}): {e}")

    return result
