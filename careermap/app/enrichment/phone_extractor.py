"""CareerMap V1.4.1 Telefon Çıkarma, E.164 Normalizasyon ve Doğrulama Modülü.
- Google `phonenumbers` kütüphanesi ile Türkiye (TR) numaralandırma planı doğrulaması.
- E.164 (+90...) ve Ulusal Standart 0(XXX) XXX XX XX formatlaması.
- Sabit hat (0222 Eskişehir), mobil (05XX) ve kurumsal santral tespiti.
- 7 basamaklı yerel numaraların (örn: 2214603) 0222 Eskişehir alan kodu ile normalizasyonu.
- Yabancı (TR dışı) numaraların tespiti ve reddi.
- Her telefon için kaynak URL, keşif yöntemi ve kanıt metni üretimi.
"""
import re
import json
import logging
from typing import List, Dict, Any, Optional, Set
import phonenumbers
from phonenumbers import PhoneNumberType, PhoneNumberFormat

logger = logging.getLogger("careermap.enrichment.phone")

PHONE_HREF_RE = re.compile(r'tel:([+0-9\s()./-]+)')
TR_PHONE_TEXT_RE = re.compile(
    r'(?:(?:\+90|0090|0)\s*)?(?:\(?([2-5]\d{2})\)?[\s.-]*)(\d{3})[\s.-]*(\d{2})[\s.-]*(\d{2})'
)

def format_phone(phone_str: str) -> str:
    """Telefon numarasını standart okunabilir 0(XXX) XXX XX XX formatına getirir."""
    if not phone_str:
        return ""
    
    clean = re.sub(r"[^\d+]", "", phone_str)

    # 7 haneli yerel Eskişehir sabit hattı ise (örn. 2214603 -> 02222214603)
    if len(clean) == 7 and clean.startswith(("2", "3")):
        clean = "0222" + clean
    elif len(clean) == 10 and clean.startswith("222"):
        clean = "0" + clean
    
    try:
        num = phonenumbers.parse(clean, "TR")
        if phonenumbers.is_possible_number(num):
            nat = phonenumbers.format_number(num, PhoneNumberFormat.NATIONAL)
            digits = re.sub(r"\D", "", nat)
            if len(digits) == 11 and digits.startswith("0"):
                return f"0({digits[1:4]}) {digits[4:7]} {digits[7:9]} {digits[9:11]}"
            elif len(digits) == 10:
                return f"0({digits[:3]}) {digits[3:6]} {digits[6:8]} {digits[8:10]}"
            return nat
    except Exception:
        pass

    # Regex yedeği
    m = TR_PHONE_TEXT_RE.search(phone_str)
    if m:
        area, part1, part2, part3 = m.groups()
        return f"0({area}) {part1} {part2} {part3}"

    return phone_str.strip()

def format_e164(phone_str: str) -> str:
    """Telefon numarasını standart uluslararası E.164 (+90...) formatına getirir."""
    if not phone_str:
        return ""
    clean = re.sub(r"[^\d+]", "", phone_str)
    if len(clean) == 7 and clean.startswith(("2", "3")):
        clean = "0222" + clean
    try:
        num = phonenumbers.parse(clean, "TR")
        if phonenumbers.is_possible_number(num):
            return phonenumbers.format_number(num, PhoneNumberFormat.E164)
    except Exception:
        pass
    return ""

def inspect_phone_number(raw_phone: str) -> Dict[str, Any]:
    """
    Telefon numarasını phonenumbers ile derinlemesine inceler:
    Geçerlilik, E.164 formatı, hat türü (sabit, mobil, kurumsal) ve alan kodu tespiti.
    """
    res = {
        "raw": raw_phone,
        "formatted": "",
        "e164": "",
        "is_valid": False,
        "line_type": "unknown",  # fixed_line, mobile, toll_free, unknown
        "is_eskisehir": False,
        "is_foreign": False,
        "area_code": ""
    }
    if not raw_phone:
        return res

    clean = re.sub(r"[^\d+]", "", raw_phone)
    if len(clean) == 7 and clean.startswith(("2", "3")):
        clean = "0222" + clean

    try:
        parsed = phonenumbers.parse(clean, "TR")
        
        # Yabancı numara kontrolü
        if parsed.country_code != 90:
            res["is_foreign"] = True
            res["is_valid"] = False
            return res

        if phonenumbers.is_possible_number(parsed):
            res["is_valid"] = phonenumbers.is_valid_number(parsed)
            res["formatted"] = format_phone(clean)
            res["e164"] = phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
            
            # Hat türü tespiti
            ntype = phonenumbers.number_type(parsed)
            if ntype in [PhoneNumberType.FIXED_LINE, PhoneNumberType.FIXED_LINE_OR_MOBILE]:
                res["line_type"] = "fixed_line"
            elif ntype == PhoneNumberType.MOBILE:
                res["line_type"] = "mobile"
            elif ntype in [PhoneNumberType.TOLL_FREE, PhoneNumberType.VOIP]:
                res["line_type"] = "toll_free"
            else:
                res["line_type"] = "corporate"

            # Alan kodu kontrolü
            digits = re.sub(r"\D", "", res["formatted"])
            if len(digits) == 11 and digits.startswith("0"):
                res["area_code"] = digits[1:4]
                res["is_eskisehir"] = (digits[1:4] == "222")
            elif len(digits) == 10:
                res["area_code"] = digits[:3]
                res["is_eskisehir"] = (digits[:3] == "222")

    except Exception:
        # Regex tabanlı alternatif deneme
        formatted = format_phone(raw_phone)
        if formatted:
            res["formatted"] = formatted
            res["is_valid"] = True
            if "0(222)" in formatted:
                res["is_eskisehir"] = True
                res["line_type"] = "fixed_line"
                res["area_code"] = "222"
            elif any(formatted.startswith(f"0({p})") for p in ["53", "54", "55", "50"]):
                res["line_type"] = "mobile"

    return res

def parse_json_ld_phones(
    item: Any,
    target_url: str,
    found_phones: List[Dict[str, Any]],
    seen_formatted: Set[str]
):
    """JSON-LD yapılandırılmış verilerinden telefonları özyinelemeli çıkarır."""
    if isinstance(item, list):
        for sub in item:
            parse_json_ld_phones(sub, target_url, found_phones, seen_formatted)
        return

    if not isinstance(item, dict):
        return

    # @graph dizisi
    if "@graph" in item and isinstance(item["@graph"], list):
        for g_item in item["@graph"]:
            parse_json_ld_phones(g_item, target_url, found_phones, seen_formatted)

    # Doğrudan telephone alanı
    raw_tel = item.get("telephone")
    if raw_tel:
        t_list = raw_tel if isinstance(raw_tel, list) else [raw_tel]
        for t in t_list:
            if isinstance(t, str):
                info = inspect_phone_number(t)
                if info["formatted"] and info["formatted"] not in seen_formatted and not info["is_foreign"]:
                    seen_formatted.add(info["formatted"])
                    category = "corporate" if info["line_type"] == "fixed_line" else ("personal_registry" if info["line_type"] == "mobile" else "unknown")
                    found_phones.append({
                        "contact_type": "phone",
                        "contact_value": info["formatted"],
                        "contact_category": category,
                        "source_url": target_url,
                        "source_type": "website_scrape",
                        "discovery_method": "json_ld",
                        "evidence_text": f'JSON-LD ({item.get("@type", "Schema")}): {t}',
                        "confidence_category": "kaynakli",
                        "verification_status": "observed_on_source" if info["is_valid"] else "needs_review",
                        "is_eskisehir": info["is_eskisehir"],
                        "e164": info["e164"]
                    })

    # ContactPoint
    cp = item.get("contactPoint")
    if cp:
        parse_json_ld_phones(cp, target_url, found_phones, seen_formatted)

def extract_phones_from_html(
    html_text: str,
    source_url: str,
    soup: Optional[Any] = None
) -> List[Dict[str, Any]]:
    """
    HTML içeriğinden tel: linkleri, JSON-LD, microdata ve metin regex taramasıyla
    telefonları kanıt izleriyle birlikte çıkarır.
    """
    import json
    found_phones: List[Dict[str, Any]] = []
    seen_formatted: Set[str] = set()

    if not html_text:
        return found_phones

    from bs4 import BeautifulSoup
    if soup is None:
        soup = BeautifulSoup(html_text, "html.parser")

    # 1. JSON-LD Çıkarma (@graph ve contactPoint dahil)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            content = script.string or script.get_text()
            if not content:
                continue
            data = json.loads(content)
            parse_json_ld_phones(data, source_url, found_phones, seen_formatted)
        except Exception:
            pass

    # 2. tel: bağlantıları (En güvenilir kanıt)
    for a in soup.select('a[href^="tel:"]'):
        href = a.get("href", "")
        m = PHONE_HREF_RE.search(href)
        if m:
            raw_val = m.group(1).strip()
            info = inspect_phone_number(raw_val)
            if info["formatted"] and info["formatted"] not in seen_formatted and not info["is_foreign"]:
                seen_formatted.add(info["formatted"])
                snippet = str(a)[:150]
                category = "corporate" if info["line_type"] == "fixed_line" else ("personal_registry" if info["line_type"] == "mobile" else "unknown")
                found_phones.append({
                    "contact_type": "phone",
                    "contact_value": info["formatted"],
                    "contact_category": category,
                    "source_url": source_url,
                    "source_type": "website_scrape",
                    "discovery_method": "tel_link",
                    "evidence_text": f"tel:{raw_val} ({snippet})",
                    "confidence_category": "kaynakli",
                    "verification_status": "observed_on_source" if info["is_valid"] else "needs_review",
                    "is_eskisehir": info["is_eskisehir"],
                    "e164": info["e164"]
                })

    # 3. microdata itemprop="telephone"
    for el in soup.find_all(attrs={"itemprop": "telephone"}):
        text_val = el.get_text(" ", strip=True) or el.get("content", "")
        if text_val:
            info = inspect_phone_number(text_val)
            if info["formatted"] and info["formatted"] not in seen_formatted and not info["is_foreign"]:
                seen_formatted.add(info["formatted"])
                found_phones.append({
                    "contact_type": "phone",
                    "contact_value": info["formatted"],
                    "contact_category": "corporate",
                    "source_url": source_url,
                    "source_type": "website_scrape",
                    "discovery_method": "microdata",
                    "evidence_text": f'itemprop="telephone": {text_val[:100]}',
                    "confidence_category": "kaynakli",
                    "verification_status": "observed_on_source" if info["is_valid"] else "needs_review",
                    "is_eskisehir": info["is_eskisehir"],
                    "e164": info["e164"]
                })

    # 4. phonenumbers PhoneNumberMatcher ile sayfa metni taraması (Script ve style etiketleri hariç)
    clean_soup = BeautifulSoup(html_text, "html.parser")
    for t in clean_soup(["script", "style", "noscript", "iframe", "svg"]):
        t.decompose()
        
    page_text = clean_soup.get_text(" ", strip=True)
    for match in phonenumbers.PhoneNumberMatcher(page_text, "TR"):
        raw_val = match.raw_string
        info = inspect_phone_number(raw_val)
        if info["formatted"] and info["formatted"] not in seen_formatted and info["is_valid"] and not info["is_foreign"]:
            seen_formatted.add(info["formatted"])
            start = max(0, match.start - 30)
            end = min(len(page_text), match.end + 30)
            context = page_text[start:end].strip()
            
            category = "corporate" if info["line_type"] == "fixed_line" else ("mobile" if info["line_type"] == "mobile" else "unknown")
            found_phones.append({
                "contact_type": "phone",
                "contact_value": info["formatted"],
                "contact_category": category,
                "source_url": source_url,
                "source_type": "website_scrape",
                "discovery_method": "regex_phonenumbers",
                "evidence_text": f"Metin bağlamı: '...{context}...'",
                "confidence_category": "kaynakli",
                "verification_status": "observed_on_source",
                "is_eskisehir": info["is_eskisehir"],
                "e164": info["e164"]
            })

    return found_phones
