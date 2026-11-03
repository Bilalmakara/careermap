"""CareerMap V1.4.1 E-posta Çıkarma, Doğrulama ve Sınıflandırma Motoru.
- Sahte ve yanlış pozitif filtreleri: Yazılım paketleri (bootstrap@5.3.3 vb.), semver versiyonlama engeli.
- TLD geçerliliği: Harf tabanlı geçerli alan adı son ekleri ([a-zA-Z]{2,24}) zorunlu, sayısal TLD'ler geçersiz.
- Web ajansı ve geliştirici altbilgi (footer) tespiti: Ajans e-postaları kurumsal e-posta olarak kabul edilmez.
- Script ve Style arındırma: HTML metin taraması öncesinde <script>, <style>, <link> etiketleri temizlenir.
- Öncelik sıralaması: mailto: > microdata / JSON-LD > gövde metni.
"""
import re
import json
import logging
from urllib.parse import urlparse
from typing import Optional, List, Dict, Any, Set
from bs4 import BeautifulSoup

logger = logging.getLogger("careermap.enrichment.email")

# Kesin e-posta regex kalıbı (TLD en az 2 harf olmalı, sayı veya semver kabul edilmez)
STRICT_EMAIL_RE = re.compile(
    r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,24}$'
)

# Metin içi genel arama regex'i (öncesinde ve sonrasında kelime sınırı)
EMAIL_RE = re.compile(
    r'(?<![\w.+-])([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,24})(?![\w.-])'
)

MAILTO_RE = re.compile(
    r'mailto:([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,24})',
    re.IGNORECASE
)

# Obfuskasyon regex kalıpları (Örn: info [at] domain [dot] com veya info [at] domain.com.tr)
# Bare '@' içermez; normal e-postalar EMAIL_RE tarafından işlenir.
OBFUSCATED_RE = re.compile(
    r'(?<![\w.+-])([a-zA-Z0-9_.+-]+)\s*(?:\[at\]|\(at\)|\[@\])\s*([a-zA-Z0-9-]+(?:\s*(?:\[dot\]|\(dot\)|\.)\s*[a-zA-Z0-9-]+)*\s*(?:\[dot\]|\(dot\)|\.)\s*[a-zA-Z]{2,12})',
    re.IGNORECASE
)

# Bilinen yazılım paketleri, CDN ve kütüphane adları (Asla e-posta olamaz)
SOFTWARE_PACKAGES = {
    "bootstrap", "jquery", "react", "vue", "angular", "wordpress", "elementor",
    "fontawesome", "font-awesome", "swiper", "popper", "webpack", "npm", "yarn",
    "cdn", "jsdelivr", "cdnjs", "cloudflare", "github", "gitlab", "google", "apple",
    "microsoft", "twitter", "facebook", "instagram", "youtube", "linkedin", "tiktok",
    "whatsapp", "telegram", "android", "ios", "adobe", "figma", "canva", "slick",
    "owlcarousel", "lightbox", "fancybox", "modernizr", "lodash", "moment"
}

# Web ajansı, tasarım ve bilişim anahtar kelimeleri (Sağlık kurumu e-postası değildir)
AGENCY_DOMAINS = {
    "siradisidigitial.com", "siradisidigital.com", "ajans.com", "pixelajans.com",
    "webajans.com", "grafiktasarim.com", "creativestudio.com", "medyapanel.com"
}

AGENCY_KEYWORDS = [
    "siradisi", "ajans", "tasarim", "yazilim", "digital", "medya",
    "pixel", "creatif", "creative", "webajans", "bilisim", "developer", "seo"
]

EXCLUDED_DOMAINS = {
    "example.com", "sentry.io", "wixpress.com", "cloudflare.com",
    "schema.org", "wordpress.org", "google.com", "facebook.com",
    "instagram.com", "twitter.com", "github.com", "w3.org", "domain.com",
    "themeforest.net", "envato.com", "yandex.com", "site-domain.com", "bootstrap.com",
    "sitem.com", "dentisarea.com", "dishek.org", "isigmeclisi.org", "eskisehirhaber26.com",
    "2eylul.com.tr", "doktortakvimi.com", "doktorsitesi.com"
}

IGNORED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".css", ".js", ".webp", ".pdf", ".ico", ".map"}

def is_agency_email(email: str) -> bool:
    """E-postanın sağlık kuruluşuna değil, web tasarım/yazılım ajansına ait olup olmadığını tespit eder."""
    if "@" not in email:
        return False
    domain = email.split("@")[1].lower()
    if domain in AGENCY_DOMAINS:
        return True
    # Alan adında açıkça tasarım/ajans geçen durumlar (sağlık/diş hekimi olmayan)
    for kw in AGENCY_KEYWORDS:
        if kw in domain and not any(med in domain for med in ["dis", "dent", "klinik", "saglik", "hekim"]):
            return True
    return False

def clean_email(email: str) -> Optional[str]:
    """
    E-postayı temizler ve sıkı geçerlilik denetiminden geçirir:
    - Boşluk ve noktalama temizliği
    - TLD'nin harf olması ([a-zA-Z]{2,})
    - Semver versiyon numaralarının (örn. bootstrap@5.3.3) kesin reddi
    - Yazılım paket isimlerinin reddi
    """
    if not email:
        return None
    email = email.lower().strip(".,;:()<>[]'\" \t\n\r")
    if "@" not in email:
        return None

    parts = email.split("@")
    if len(parts) != 2:
        return None

    local, domain = parts[0], parts[1]

    # 1. Yazılım paketi veya kütüphane veya şablon yer tutucu kontrolü
    if local in SOFTWARE_PACKAGES or local in ["ornek", "example", "deneme", "test", "demo", "sample"]:
        return None

    # 2. Domain içinde sayısal semver kontrolü (Örn: 5.3.3 veya 4.0.0)
    # Eğer domain parçaları sadece sayılardan oluşuyorsa geçersizdir
    domain_parts = domain.split(".")
    if len(domain_parts) >= 2 and all(p.isdigit() for p in domain_parts):
        return None

    # TLD'nin sadece sayılardan oluşması kesinlikle geçersizdir
    tld = domain_parts[-1]
    if not tld.isalpha() or len(tld) < 2:
        return None

    # 3. Kesin regex kontrolü
    if not STRICT_EMAIL_RE.match(email):
        return None

    # 4. Hariç tutulan alan adları
    if domain in EXCLUDED_DOMAINS or any(domain.endswith("." + d) for d in EXCLUDED_DOMAINS):
        return None

    # 5. Dosya uzantısı kontrolü
    if any(email.endswith(ext) for ext in IGNORED_EXTENSIONS):
        return None

    if len(local) < 2 or len(domain) < 3:
        return None

    return email

def classify_email(email: str) -> str:
    """E-postanın başvuru ve iletişim türünü belirler."""
    e = email.lower()
    if is_agency_email(e):
        return "agency"
    elif any(e.startswith(p) for p in ["ik@", "kariyer@", "hr@", "insankaynaklari@", "basvuru@", "isealim@"]):
        return "career"
    elif any(e.startswith(p) for p in ["randevu@", "online@", "erandevu@"]):
        return "randevu"
    elif any(e.startswith(p) for p in ["info@", "iletisim@", "contact@", "merhaba@", "bilgi@", "muayenehane@"]):
        return "general"
    return "other"

def parse_json_ld_emails(item: Any, target_url: str, found_emails: List[Dict[str, Any]]):
    """JSON-LD yapılandırılmış verilerinden e-postaları özyinelemeli çıkarır."""
    if isinstance(item, list):
        for sub in item:
            parse_json_ld_emails(sub, target_url, found_emails)
        return

    if not isinstance(item, dict):
        return

    # @graph dizisi
    if "@graph" in item and isinstance(item["@graph"], list):
        for g_item in item["@graph"]:
            parse_json_ld_emails(g_item, target_url, found_emails)

    # Doğrudan email alanı
    raw_email = item.get("email")
    if raw_email:
        e_list = raw_email if isinstance(raw_email, list) else [raw_email]
        for e in e_list:
            if isinstance(e, str):
                cleaned = clean_email(e)
                if cleaned and not any(f["contact_value"] == cleaned for f in found_emails):
                    cat = classify_email(cleaned)
                    found_emails.append({
                        "contact_type": "email",
                        "contact_value": cleaned,
                        "contact_category": cat,
                        "source_url": target_url,
                        "source_type": "website_scrape",
                        "discovery_method": "json_ld",
                        "evidence_text": f'JSON-LD ({item.get("@type", "Schema")}): {cleaned}',
                        "confidence_category": "kaynakli",
                        "verification_status": "observed_on_source" if cat != "agency" else "needs_review"
                    })

    # ContactPoint
    cp = item.get("contactPoint")
    if cp:
        parse_json_ld_emails(cp, target_url, found_emails)

def extract_emails_from_html(
    html_text: str,
    source_url: str,
    soup: Optional[Any] = None
) -> List[Dict[str, Any]]:
    """
    HTML sayfasından tüm e-postaları yöntem ve kanıt bilgisiyle çıkarır.
    Script ve style etiketleri metin aramasından kesinlikle ayıklanır.
    """
    found_emails: List[Dict[str, Any]] = []
    seen_values: Set[str] = set()

    if not html_text:
        return found_emails

    from bs4 import BeautifulSoup
    if soup is None:
        soup = BeautifulSoup(html_text, "html.parser")

    # 1. mailto: Linkleri (En güçlü doğrudan kanıt)
    for a in soup.select('a[href^="mailto:"]'):
        href = a.get("href", "")
        m = MAILTO_RE.search(href)
        if m:
            cleaned = clean_email(m.group(1))
            if cleaned and cleaned not in seen_values:
                seen_values.add(cleaned)
                cat = classify_email(cleaned)
                snippet = str(a)[:120]
                status = "observed_on_source" if cat != "agency" else "needs_review"
                found_emails.append({
                    "contact_type": "email",
                    "contact_value": cleaned,
                    "contact_category": cat,
                    "source_url": source_url,
                    "source_type": "website_scrape",
                    "discovery_method": "mailto",
                    "evidence_text": f"mailto linki: {snippet}",
                    "confidence_category": "kaynakli",
                    "verification_status": status
                })

    # 2. JSON-LD Çıkarma (@graph dahil)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            content = script.string or script.get_text() or ""
            if content.strip():
                js = json.loads(content)
                parse_json_ld_emails(js, source_url, found_emails)
                for f in found_emails:
                    seen_values.add(f["contact_value"])
        except Exception:
            pass

    # 3. microdata itemprop="email"
    for el in soup.find_all(attrs={"itemprop": "email"}):
        text_val = el.get_text(" ", strip=True) or el.get("content", "")
        cleaned = clean_email(text_val)
        if cleaned and cleaned not in seen_values:
            seen_values.add(cleaned)
            cat = classify_email(cleaned)
            status = "observed_on_source" if cat != "agency" else "needs_review"
            found_emails.append({
                "contact_type": "email",
                "contact_value": cleaned,
                "contact_category": cat,
                "source_url": source_url,
                "source_type": "website_scrape",
                "discovery_method": "microdata",
                "evidence_text": f'itemprop="email": {text_val[:80]}',
                "confidence_category": "kaynakli",
                "verification_status": status
            })

    # 4. Obfuskasyon Çözümleme (Örn: info [at] domain [dot] com veya merhaba [at] testdental.com.tr)
    for m in OBFUSCATED_RE.finditer(html_text):
        local, raw_domain = m.groups()
        clean_domain = re.sub(r'\s*(?:\[dot\]|\(dot\))\s*', '.', raw_domain).replace(' ', '')
        reassembled = f"{local}@{clean_domain}"
        cleaned = clean_email(reassembled)
        if cleaned and cleaned not in seen_values:
            seen_values.add(cleaned)
            cat = classify_email(cleaned)
            status = "observed_on_source" if cat != "agency" else "needs_review"
            found_emails.append({
                "contact_type": "email",
                "contact_value": cleaned,
                "contact_category": cat,
                "source_url": source_url,
                "source_type": "website_scrape",
                "discovery_method": "obfuscated",
                "evidence_text": f"Çözülmüş metin: '{m.group(0)[:60]}'",
                "confidence_category": "kaynakli",
                "verification_status": status
            })

    # 5. Sayfa Metni Regex Taraması (Script, Style, Meta ve Link etiketleri tamamen arındırılır)
    clean_soup = BeautifulSoup(html_text, "html.parser")
    for tag in clean_soup(["script", "style", "noscript", "iframe", "svg", "link", "meta"]):
        tag.decompose()

    page_text = clean_soup.get_text(" ", strip=True)
    for m in EMAIL_RE.finditer(page_text):
        raw_val = m.group(1)
        cleaned = clean_email(raw_val)
        if cleaned and cleaned not in seen_values:
            seen_values.add(cleaned)
            cat = classify_email(cleaned)
            start = max(0, m.start() - 25)
            end = min(len(page_text), m.end() + 25)
            context = page_text[start:end].strip()
            status = "observed_on_source" if cat != "agency" else "needs_review"
            found_emails.append({
                "contact_type": "email",
                "contact_value": cleaned,
                "contact_category": cat,
                "source_url": source_url,
                "source_type": "website_scrape",
                "discovery_method": "text_regex",
                "evidence_text": f"Metin bağlamı: '...{context}...'",
                "confidence_category": "kaynakli",
                "verification_status": status
            })

    return found_emails

def extract_contact_from_website(
    website_url: str,
    session: Optional[Any] = None
) -> Dict[str, Any]:
    """Web sitesini ve sayfalarını tarayarak iletişim bilgilerini ve formları çıkarır (V1.3/V1.4 uyumluluk köprüsü)."""
    from .contact_page_crawler import crawl_business_website
    from .phone_extractor import extract_phones_from_html

    crawl_data = crawl_business_website(website_url, session=session, max_pages=3)
    contacts: List[Dict[str, Any]] = []
    seen_contacts = set()

    primary_email = ""
    primary_email_type = ""

    for page in crawl_data.get("pages", []):
        html_str = page.get("html", "")
        p_soup = page.get("soup")
        p_url = page.get("url", website_url)

        emails = extract_emails_from_html(html_str, p_url, soup=p_soup)
        for em in emails:
            key = (em["contact_type"], em["contact_value"])
            if key not in seen_contacts:
                seen_contacts.add(key)
                contacts.append(em)
                
                # Ajans e-postaları birincil sağlık e-postası seçilmez
                if em.get("contact_category") != "agency":
                    if not primary_email:
                        primary_email = em["contact_value"]
                        primary_email_type = em["contact_category"]
                    elif primary_email_type != "career" and em["contact_category"] == "career":
                        primary_email = em["contact_value"]
                        primary_email_type = "career"

        phones = extract_phones_from_html(html_str, p_url, soup=p_soup)
        for ph in phones:
            key = (ph["contact_type"], ph["contact_value"])
            if key not in seen_contacts:
                seen_contacts.add(key)
                contacts.append(ph)

    if crawl_data.get("contact_form_url"):
        form_entry = {
            "contact_type": "contact_form",
            "contact_value": crawl_data["contact_form_url"],
            "contact_category": "corporate_form",
            "source_url": crawl_data["contact_form_url"],
            "source_type": "website_scrape",
            "discovery_method": "form_detection",
            "evidence_text": crawl_data.get("contact_form_evidence", "İletişim Formu"),
            "confidence_category": "kaynakli",
            "verification_status": "observed_on_source"
        }
        contacts.append(form_entry)

    return {
        "email": primary_email,
        "email_type": primary_email_type,
        "contact_form_url": crawl_data.get("contact_form_url", ""),
        "appointment_form_url": crawl_data.get("appointment_form_url", ""),
        "contacts": contacts,
        "pages_crawled": len(crawl_data.get("pages", []))
    }
