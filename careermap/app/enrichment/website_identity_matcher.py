"""CareerMap V1.5 Çok Faktörlü Kalibre Edilmiş İşletme ve Web Sitesi Kimlik Doğrulama Motoru (Identity Matcher).
- Ağırlıklı Puanlama Modeli:
  1. Tam İsim ve Marka Uyumu: %35
  2. Açık Adres ve Mahalle Uyumu: %30
  3. İl ve İlçe Uyumu: %15
  4. Bilinen Telefon Uyumu: %15
  5. Diş Hekimliği Faaliyet Uyumu: %5
- Kritik Çelişki Güvenlik Kilidi: Başka büyükşehir (İstanbul, Ankara, İzmir vb.) açıkça geçiyorsa ve Eskişehir yoksa puan ne olursa olsun otomatik eşleşme DURDURULUR.
- Hekim vs. Poliklinik Ayrımı (Associated Clinic):
  Bireysel hekimin adı bir poliklinik sitesinde (ekibimiz/kadromuz) geçiyorsa kliniğin telefonu hekime atanmaz; 'associated_clinic' ilişkisi kurulur.
- Standart Durumlar: 'observed_on_source', 'needs_review', 'rejected'.
"""
import re
import unicodedata
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from bs4 import BeautifulSoup

logger = logging.getLogger("careermap.enrichment.matcher")

PARKED_DOMAIN_PATTERNS = [
    r"\bbuy this domain\b", r"\bdomain satılıktır\b", r"\bdomain for sale\b",
    r"\balan adı satılıktır\b", r"\bgodaddy\b", r"\bsedo\.com\b", r"\bsedoparking\b",
    r"\bdan\.com\b", r"\bhugedomains\b",
    r"\bthis domain is registered\b", r"\bbu alan adı tescil edilmiştir\b",
    r"\bunder construction\b", r"\byapım aşamasında\b", r"\bparked free\b"
]

# Yabancı lokasyon sinyalleri (Eskişehir sağlık kuruluşlarında yabancı adres olamaz)
FOREIGN_LOCATION_PATTERNS = [
    r"\bmilford\b", r"\bmassachusetts\b", r"\bcalifornia\b", r"\bflorida\b",
    r"\bnew york\b", r"\blondon\b", r"\bgermany\b", r"\bfrankfurt\b",
    r"\bunited states\b", r"\busa\b"
]

# Başka şehir çelişki sinyalleri (Eskişehir dışındaki diğer iller)
OTHER_CITIES_PATTERNS = [
    r"\bistanbul\b", r"\bankara\b", r"\bizmir\b", r"\bbursa\b",
    r"\bantalya\b", r"\bkonya\b", r"\badana\b", r"\bkocaeli\b"
]

# Diş hekimliği kesin bağlam terimleri
DENTAL_KEYWORDS = [
    "dis", "dental", "dishekimi", "ortodonti", "implant", "periodontoloji",
    "endodonti", "pedodonti", "protez", "diseti", "agizdis", "dentistry",
    "muayenehane", "poliklinik", "cene", "dolgu", "kanal tedavisi", "gulus tasarimi"
]

# Sağlık ve diş hekimliği dışı sektörler (Müşteri referansı veya alakasız sektör siteleri engellenir)
NON_HEALTHCARE_PATTERNS = [
    r"\bguvenlik\b", r"\bgüvenlik\b", r"\binsaat\b", r"\binşaat\b", r"\bemlak\b",
    r"\bsigorta\b", r"\bhukuk\b", r"\bavukat\b", r"\bmuhasebe\b", r"\bdanismanlik\b",
    r"\btemizlik\b", r"\bmobilya\b", r"\botomotiv\b", r"\btekstil\b", r"\bturizm\b",
    r"\blojistik\b", r"\bkargo\b", r"\bmatbaa\b"
]

def normalize_tr_text(text: str) -> str:
    """Türkçe karakterleri koruyarak karşılaştırma standardına getirir."""
    if not text:
        return ""
    s = text.replace("I", "ı").replace("İ", "i").lower()
    s = s.translate(str.maketrans("çğıöşü", "cgiosu"))
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return " ".join(s.split())

def word_in_text(word: str, text: str) -> bool:
    """Kelimenin metin içinde tekil bir sözcük olarak (word boundary ile) geçip geçmediğini denetler."""
    if not word or not text:
        return False
    w_clean = normalize_tr_text(word)
    if not w_clean:
        return False
    if " " in w_clean:
        return w_clean in text
    pattern = r'(?<![a-z0-9])' + re.escape(w_clean) + r'(?![a-z0-9])'
    return bool(re.search(pattern, text))

def parse_target_names(raw_name: str, employer_type: str) -> Dict[str, Any]:
    """Hekim veya klinik adını karşılaştırma token'larına ayrıştırır."""
    is_office = "muayenehane" in employer_type.lower() or raw_name.strip().lower().startswith("dt")
    clean = re.sub(r"^(?:prof\.\s*dr\.|doç\.\s*dr\.|doc\.\s*dr\.|dr\.\s*dt\.|dt\.|dr\.|dt|dr)\s+", "", raw_name.strip(), flags=re.IGNORECASE).strip()
    norm_clean = normalize_tr_text(clean)
    tokens = norm_clean.split()

    brand_tokens = [
        t for t in tokens 
        if t not in ["ozel", "agiz", "ve", "dis", "sagligi", "poliklinigi", "poliklinik", "klinik", "merkezi", "muayenehanesi", "muayenehane"]
    ]

    result = {
        "is_office": is_office,
        "raw_clean": clean,
        "norm_clean": norm_clean,
        "all_tokens": tokens,
        "brand_tokens": brand_tokens,
        "first_name": "",
        "last_name": ""
    }

    if is_office and len(tokens) >= 2:
        result["first_name"] = " ".join(tokens[:-1])
        result["last_name"] = tokens[-1]
    elif is_office and len(tokens) == 1:
        result["last_name"] = tokens[0]

    return result

def extract_address_tokens(address: str) -> List[str]:
    """Adresten cadde, sokak ve mahalle gibi ayırt edici parçaları ayıklar."""
    if not address:
        return []
    norm = normalize_tr_text(address)
    tokens = norm.split()
    generic_words = {"eskisehir", "tepebasi", "odunpazari", "sivrihisar", "cifteler", "turkiye", "no", "kat", "cad", "caddesi", "sok", "sokak", "mah", "mahallesi"}
    return [t for t in tokens if len(t) >= 4 and t not in generic_words]

def match_website_identity(
    target_employer: Dict[str, Any],
    html_content: str,
    final_url: str
) -> Dict[str, Any]:
    """
    V1.5 Çok Faktörlü Kalibre Edilmiş Web Sitesi Kimlik Doğrulaması.
    Puan Dağılımı:
    - İsim/Marka: max 35 puan
    - Açık Adres/Cadde: max 30 puan
    - İl/İlçe: max 15 puan
    - Bilinen Telefon: max 15 puan
    - Sağlık Faaliyet Alanı: max 5 puan
    Toplam: 100 puan
    """
    res = {
        "is_match": False,
        "status": "rejected",  # observed_on_source, needs_review, rejected
        "confidence_category": "supheli",
        "match_score": 0,
        "score_breakdown": {
            "name_score": 0,
            "address_score": 0,
            "location_score": 0,
            "phone_score": 0,
            "dental_score": 0,
            "total_score": 0
        },
        "is_associated_clinic": False,
        "associated_clinic": None,
        "reasons": [],
        "evidence_snippet": "",
        "final_url": final_url
    }

    if not html_content or len(html_content) < 100:
        res["reasons"].append("Web sayfası boş veya erişilemedi.")
        return res

    text_lower = html_content.lower()

    # 1. Park Edilmiş / Satılık Alan Adı Kontrolü
    for parked in PARKED_DOMAIN_PATTERNS:
        if re.search(parked, text_lower):
            res["reasons"].append(f"Park edilmiş veya satılık alan adı tespit edildi: '{parked}'")
            return res

    # 2. Yabancı / Uluslararası Lokasyon Kontrolü
    for fl in FOREIGN_LOCATION_PATTERNS:
        if re.search(fl, text_lower):
            if "turkey" not in text_lower and "turkiye" not in text_lower and "eskisehir" not in text_lower:
                res["reasons"].append(f"Yabancı lokasyon kalıbı tespit edildi: '{fl}'")
                return res

    # Script ve style etiketlerini temizle
    clean_soup = BeautifulSoup(html_content, "html.parser")
    for t in clean_soup(["script", "style", "noscript", "iframe", "svg"]):
        t.decompose()

    page_text = clean_soup.get_text(" ", strip=True)
    norm_page_text = normalize_tr_text(page_text)
    
    title_text = (clean_soup.title.string.strip() if clean_soup.title and clean_soup.title.string else "")
    norm_title = normalize_tr_text(title_text)

    h1_elements = [el.get_text(" ", strip=True) for el in clean_soup.find_all(["h1", "h2"])]
    norm_headers = normalize_tr_text(" ".join(h1_elements))

    name_info = parse_target_names(
        target_employer.get("name", ""),
        target_employer.get("employer_type", "")
    )

    reasons = []
    evidence_parts = []

    # -------------------------------------------------------------
    # FAKTÖR 1: DİŞ HEKİMLİĞİ VE SAĞLIK FAALİYET ALANI (%5)
    # -------------------------------------------------------------
    # A. Sektör dışı alan adı ve başlık kontrolü (Güvenlik, inşaat, emlak vb.)
    for nh_pat in NON_HEALTHCARE_PATTERNS:
        if re.search(nh_pat, final_url.lower()) or re.search(nh_pat, norm_title):
            res["reasons"].append(f"Sağlık dışı sektör tespit edildi ('{nh_pat}').")
            return res

    # B. Sektörel Belirginlik: Başlık, ana başlıklar veya alan adında mutlaka diş/hekimlik terimi olmalı
    has_dental_prominence = (
        any(k in norm_title or k in norm_headers for k in ["dis", "dental", "agiz", "klinik", "poliklinik", "hekim", "ortodonti", "implant", "dentist"])
        or any(k in final_url.lower() for k in ["dis", "dent", "klinik", "hekim"])
    )
    if not has_dental_prominence:
        res["reasons"].append("Sayfa başlığında veya alan adında diş hekimliği/sağlık belirginliği bulunamadı (Müşteri referansı engellendi).")
        return res

    matched_dental = [k for k in DENTAL_KEYWORDS if word_in_text(k, norm_title) or word_in_text(k, norm_headers) or word_in_text(k, norm_page_text[:4000])]
    has_dental = len(matched_dental) >= 1
    dental_score = 0
    if not has_dental:
        res["reasons"].append("Diş hekimliği veya sağlık faaliyeti bağlamı bulunamadı (Sektör dışı site engellendi).")
        return res
    dental_score = 5
    reasons.append(f"Diş hekimliği faaliyeti teyit edildi ({matched_dental[:2]})")

    # -------------------------------------------------------------
    # FAKTÖR 2: ŞEHİR VE İLÇE UYUMU (%15)
    # -------------------------------------------------------------
    location_score = 0
    has_city = False
    has_district = False
    if word_in_text("eskisehir", norm_page_text) or word_in_text("eskisehir", norm_title) or "0222" in html_content or " 222 " in html_content:
        location_score += 10
        has_city = True
        reasons.append("Eskişehir il/telefon kodu sinyali doğrulandı.")

    target_district = normalize_tr_text(target_employer.get("district", ""))
    if target_district and word_in_text(target_district, norm_page_text):
        location_score += 5
        has_district = True
        reasons.append(f"İlçe '{target_district}' doğrulandı.")

    # Kritik Çelişki Denetimi: Başka büyükşehir adı var ve Eskişehir yoksa DERHAL REDDET
    has_other_city = any(re.search(pat, norm_page_text[:3000]) for pat in OTHER_CITIES_PATTERNS)
    if has_other_city and not has_city:
        res["reasons"].append("Başka bir şehir (İstanbul/Ankara vb.) tespit edildi ve Eskişehir sinyali yok.")
        return res

    # -------------------------------------------------------------
    # FAKTÖR 3: TAM İSİM VE MARKA UYUMU (%35)
    # -------------------------------------------------------------
    name_score = 0
    is_associated_clinic = False

    if name_info["is_office"]:
        f_name = name_info["first_name"]
        l_name = name_info["last_name"]
        
        has_last_name = bool(l_name and (word_in_text(l_name, norm_title) or word_in_text(l_name, norm_headers) or word_in_text(l_name, norm_page_text[:5000])))
        has_first_name = bool(f_name and (word_in_text(f_name, norm_title) or word_in_text(f_name, norm_headers) or word_in_text(f_name, norm_page_text[:5000])))

        if has_last_name and has_first_name:
            name_score = 35
            reasons.append(f"Hekim tam adı ve soyadı bağımsız kelimeler olarak doğrulandı: '{name_info['raw_clean']}'")
            evidence_parts.append(f"Hekim: {name_info['raw_clean']}")

            # Muayenehane hekiminin bir poliklinik sitesinde ekip üyesi olup olmadığını kontrol et
            is_polyclinic_site = any(pk in norm_title or pk in norm_headers for pk in ["poliklinigi", "dental", "agiz ve dis sagligi"])
            is_team_context = any(tc in norm_page_text for tc in ["hekimlerimiz", "kadromuz", "ekibimiz", "doktorlarimiz"])
            if is_polyclinic_site and is_team_context:
                is_associated_clinic = True
                reasons.append("Hekim poliklinik ekibinde/kadrosunda yer alıyor (Associated Clinic tespit edildi).")

        elif has_last_name:
            # Yalnızca soyadı eşleşti (aynı soyadlı başka hekim riski!)
            name_score = 5
            reasons.append(f"Yalnızca soyadı eşleşti ('{l_name}'); tam ad ('{f_name}') bulunamadı.")
        else:
            reasons.append(f"Hekim adı sayfada bulunamadı: '{name_info['raw_clean']}'")

    else:
        # Poliklinik Kurumsal Marka Kontrolü
        brand_tokens = name_info["brand_tokens"]
        if brand_tokens:
            matched_brands = [t for t in brand_tokens if word_in_text(t, norm_title) or word_in_text(t, norm_headers) or word_in_text(t, norm_page_text[:3500])]
            is_generic_or_numeric = len(brand_tokens) == 1 and (brand_tokens[0].isdigit() or len(brand_tokens[0]) <= 3)

            if len(matched_brands) == len(brand_tokens):
                if is_generic_or_numeric and not has_city:
                    name_score = 10
                    reasons.append("Kısa/sayısal marka eşleşti fakat şehir teyidi yetersiz.")
                else:
                    name_score = 35
                    reasons.append(f"Klinik kurumsal markası tam eşleşti: {brand_tokens}")
                    evidence_parts.append(f"Marka: {' '.join(brand_tokens)}")
            elif matched_brands and not is_generic_or_numeric:
                name_score = 15
                reasons.append(f"Klinik marka parçaları kısmen eşleşti: {matched_brands}")

    # -------------------------------------------------------------
    # FAKTÖR 4: AÇIK ADRES VE MAHALLE UYUMU (%30)
    # -------------------------------------------------------------
    address_score = 0
    addr_tokens = extract_address_tokens(target_employer.get("address", ""))
    if addr_tokens:
        matched_addr = [t for t in addr_tokens if word_in_text(t, norm_page_text)]
        if len(matched_addr) >= 2:
            address_score = 30
            reasons.append(f"Açık adres ve cadde/mahalle parçaları kuvvetli doğrulandı: {matched_addr}")
            evidence_parts.append(f"Adres: {' '.join(matched_addr)}")
        elif len(matched_addr) == 1:
            address_score = 15
            reasons.append(f"Adres/mahalle sinyali kısmen doğrulandı: '{matched_addr[0]}'")
    elif has_city and has_district:
        # Önceden kayıtlı açık adresi yoksa ancak il + ilçe tam uyumluysa temel adres puanı ver
        address_score = 15
        reasons.append("Kayıtlı açık adres yoktu; il ve ilçe uyumundan temel adres puanı verildi.")

    # -------------------------------------------------------------
    # FAKTÖR 5: BİLİNEN TELEFON UYUMU (%15)
    # -------------------------------------------------------------
    phone_score = 0
    known_phone = re.sub(r"[^0-9]", "", target_employer.get("phone", ""))
    if known_phone and len(known_phone) >= 7:
        last_7_digits = known_phone[-7:]
        clean_html_digits = re.sub(r"[^0-9]", "", html_content)
        if last_7_digits in clean_html_digits:
            phone_score = 15
            reasons.append(f"Bilinen telefon son 7 hanesi sayfada doğrulandı ({last_7_digits}).")
            evidence_parts.append(f"Tel Teyit: {last_7_digits}")

    # -------------------------------------------------------------
    # TOPLAM PUAN VE KARAR
    # -------------------------------------------------------------
    total_score = min(name_score + address_score + location_score + phone_score + dental_score, 100)
    
    res["score_breakdown"] = {
        "name_score": name_score,
        "address_score": address_score,
        "location_score": location_score,
        "phone_score": phone_score,
        "dental_score": dental_score,
        "total_score": total_score
    }
    res["match_score"] = total_score
    res["reasons"] = reasons

    if norm_title:
        evidence_parts.append(f"Title: {title_text.strip()[:90]}")
    res["evidence_snippet"] = " | ".join(evidence_parts)

    # Karar Eşikleri:
    # 1. 65+ puan ve tam isim/marka + şehir -> observed_on_source
    if total_score >= 65 and name_score >= 30 and has_city:
        res["is_match"] = True
        res["status"] = "observed_on_source"
        res["confidence_category"] = "kaynakli"
        
        # Hekim poliklinik ekibinde bulunduysa
        if is_associated_clinic:
            res["is_associated_clinic"] = True
            res["associated_clinic"] = {
                "clinic_name": title_text.strip()[:60],
                "clinic_url": final_url.rstrip("/"),
                "relation_type": "staff_dentist",
                "evidence_text": f"Hekim '{target_employer.get('name')}' poliklinik hekim kadrosunda listelenmiştir."
            }

    # 2. 45-64 puan -> needs_review (Manuel İnceleme)
    elif total_score >= 45 and name_score >= 15:
        res["is_match"] = True
        res["status"] = "needs_review"
        res["confidence_category"] = "supheli"
    else:
        res["is_match"] = False
        res["status"] = "rejected"
        res["confidence_category"] = "supheli"

    return res
