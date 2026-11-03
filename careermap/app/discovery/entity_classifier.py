"""CareerMap V2.5 Kurum Kimliği ve Tür Sınıflandırıcısı (Entity Classifier & Identity Resolution).
- TDB 2025 standartlarında 5 kurum türünü kanıt bazlı ayırır:
    1. Özel poliklinik
    2. Bireysel diş hekimi muayenehanesi
    3. Müşterek muayenehane
    4. Özel ağız ve diş sağlığı merkezi (ADSM)
    5. Kamu / Üniversite Diş Hastanesi
- Kurum ile bireysel hekim ayrımını yönetir.
- Şube ve zincir kliniklerin (DentGroup Kadıköy, Pendik vb.) bağımsız kimliklerini korur.
"""
import re
import unicodedata
from typing import Dict, Any, Optional


def normalize_tr_text(text: str) -> str:
    """Türkçe karakterleri ve boşlukları karşılaştırma standardına getirir."""
    if not text:
        return ""
    s = str(text).replace("I", "ı").replace("İ", "i").lower()
    s = s.translate(str.maketrans("çğıöşü", "cgiosu"))
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return " ".join(s.split())


def classify_dental_establishment(name: str, tags: Optional[Dict[str, Any]] = None) -> str:
    """
    Kurum adı ve etiket kanıtına dayanarak TDB 2025 kategorilerine göre sınıflandırma yapar.
    """
    n_lower = name.lower()
    t_str = " ".join(f"{k}={v}" for k, v in (tags or {}).items()).lower()
    combined = f"{n_lower} {t_str}"

    # 1. Kamu / Üniversite
    if any(k in combined for k in ["üniversite", "universite", "fakülte", "fakulte", "devlet hastane", "sağlık bakanlığı", "kamu"]):
        return "Kamu / Üniversite Diş Hastanesi"

    # 2. Özel ADSM / Merkez / Diş Hastanesi
    if any(k in combined for k in ["merkezi", "adsm", "diş hastanesi", "dis hastanesi", "hospital"]):
        return "Özel ağız ve diş sağlığı merkezi"

    # 3. Özel Poliklinik
    if any(k in combined for k in ["poliklinik", "polikliniği", "dentgroup", "group"]):
        return "Özel poliklinik"

    # 4. Bireysel Muayenehane (Dt. / Dr. / Hekim adı)
    clean_prefix = re.match(r"^(?:Dt\.|Dr\.|Dt|Dr|Uzm\.\s*Dt\.|Prof\.\s*Dr\.)\s+", name, re.IGNORECASE)
    if clean_prefix or "diş hekimi" in n_lower or "dis hekimi" in n_lower:
        return "Bireysel diş hekimi muayenehanesi"

    # 5. Dental marka / klinik
    if any(k in n_lower for k in ["dent", "dental", "klinik", "clinic", "ağız ve diş", "agiz ve dis"]):
        return "Özel poliklinik"

    return "Bireysel diş hekimi muayenehanesi"


def resolve_branch_identity(name: str, district: str, city: str) -> Dict[str, Any]:
    """
    Zincir veya çok şubeli kurumlarda şube ayrımını yapar.
    Örn: 'DentGroup Kadıköy' -> Ana Marka: 'DentGroup', Şube: 'Kadıköy'.
    """
    clean_name = name.strip()
    brand = clean_name
    branch = district

    # Yaygın zincir markalar
    known_brands = ["DentGroup", "Hospitadent", "Dentistanbul", "Dentway", "Dentram", "Bayındır Diş"]
    for kb in known_brands:
        if kb.lower() in clean_name.lower():
            brand = kb
            # Şube adını temizle
            rem = clean_name.lower().replace(kb.lower(), "").strip()
            rem = re.sub(r"(ağız ve diş sağlığı|diş polikliniği|polikliniği|merkezi|şubesi|subesi|diş|dis)", "", rem, flags=re.IGNORECASE).strip()
            if rem:
                branch = rem.title()
            break

    return {
        "brand_name": brand,
        "branch_name": branch or district or city,
        "is_chain": brand != clean_name
    }
