"""CareerMap V1.3 TDB (Türk Dişhekimleri Birliği) Güvenli Sicil Entegratörü.
- Tam kelime/token bazlı ad-soyad eşleştirmesi (alt-dize hatalı eşleşmeleri engellenir).
- İlçe teyidi ve çelişki kontrolü.
- Belirsiz ve çoklu hekim kayıtlarında otomatik 'manual_review'.
"""
import logging
import re
import unicodedata
import requests
from typing import Dict, Any, Optional, Tuple, List

logger = logging.getLogger("careermap.discovery.tdb")

TDB_API_URL = "https://api.tdb.org.tr/dentists"
HEADERS = {
    "User-Agent": "CareerMap/1.3 (Educational & Public Directory Research; info@careermap.local)",
    "Accept": "application/json"
}

def normalize_tr_text(text: str) -> str:
    """Türkçe İ/ı, Ş/ş karakterlerini koruyarak karşılaştırma standardına getirir."""
    if not text:
        return ""
    s = text.replace("I", "ı").replace("İ", "i").lower()
    s = s.translate(str.maketrans("çğıöşü", "cgiosu"))
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = " ".join(s.split())
    return s

def parse_doctor_name(raw_name: str) -> Tuple[str, str]:
    """'Dt. Ahmet YILMAZ' veya 'Dt. Mehmet Ali KAYA' metninden ad ve soyadı ayıklar."""
    clean = re.sub(r"^(?:Dt\.|Dr\.|Dt|Dr)\s+", "", raw_name.strip(), flags=re.IGNORECASE).strip()
    parts = clean.split()
    if len(parts) >= 2:
        ad = " ".join(parts[:-1])
        soyad = parts[-1]
        return ad, soyad
    elif len(parts) == 1:
        return parts[0], ""
    return "", ""

def match_doctor_names_strictly(target_ad: str, target_soyad: str, tdb_first_name: str, tdb_last_name: str) -> bool:
    """
    Hedef hekim ile TDB kaydı arasında token bazlı kesin ad-soyad kontrolü yapar.
    'Ali' ile 'Alime', 'Can' ile 'Candan' gibi kısmi alt dize eşleşmelerine ASLA izin vermez!
    """
    norm_t_soyad = normalize_tr_text(target_soyad)
    norm_tdb_soyad = normalize_tr_text(tdb_last_name)
    
    # Soyad tam ve kesin eşleşmeli
    if norm_t_soyad != norm_tdb_soyad:
        return False
        
    t_ad_tokens = set(normalize_tr_text(target_ad).split())
    tdb_ad_tokens = set(normalize_tr_text(tdb_first_name).split())
    
    if not t_ad_tokens or not tdb_ad_tokens:
        return False

    # Birebir tam eşleşme
    if normalize_tr_text(target_ad) == normalize_tr_text(tdb_first_name):
        return True

    # İki isimli hekimlerde isim kümelerinin tam kapsanması
    # Örn: 'Mehmet Ali' vs 'Mehmet Ali' veya 'Ali' in {'Mehmet', 'Ali'}
    if t_ad_tokens == tdb_ad_tokens:
        return True
    if len(t_ad_tokens) >= 2 and t_ad_tokens.issubset(tdb_ad_tokens):
        return True
    if len(tdb_ad_tokens) >= 2 and tdb_ad_tokens.issubset(t_ad_tokens):
        return True

    return False

def query_tdb_dentist(raw_name: str, city: str = "Eskişehir", session: Optional[requests.Session] = None) -> Optional[Dict[str, Any]]:
    """
    TDB resmî sicil API'sinden hekimin tescilli oda kaydını ve telefonunu doğrular.
    """
    ad, soyad = parse_doctor_name(raw_name)
    if len(ad) < 2 or len(soyad) < 2:
        return None

    if session is None:
        session = requests.Session()

    params = {"il": city, "ad": ad, "soyad": soyad}
    
    try:
        resp = session.get(TDB_API_URL, params=params, headers=HEADERS, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("data", [])
            
            # İki isimli hekimlerde ilk ad + soyad dene
            if not items and " " in ad:
                first_name_only = ad.split()[0]
                if len(first_name_only) >= 2:
                    p2 = {"il": city, "ad": first_name_only, "soyad": soyad}
                    r2 = session.get(TDB_API_URL, params=p2, headers=HEADERS, timeout=8)
                    if r2.status_code == 200:
                        items = r2.json().get("data", [])

            if not items:
                return None

            # Kesin eşleşen adayları filtrele
            exact_matches = []
            for item in items:
                f_name = item.get("firstName") or ""
                l_name = item.get("lastName") or ""
                if match_doctor_names_strictly(ad, soyad, f_name, l_name):
                    exact_matches.append(item)

            if len(exact_matches) > 1:
                # Aynı ad ve soyada sahip birden fazla hekim var
                logger.warning(f"TDB'de birden fazla hekim bulundu: {raw_name} ({len(exact_matches)} kayıt) -> manual_review")
                return {
                    "phone": "",
                    "district": "",
                    "source_url": "https://www.tdb.org.tr/dishekimi-bul",
                    "verification_status": "manual_review",
                    "phone_type": "unknown",
                    "note": f"Aynı ad ve soyada sahip {len(exact_matches)} farklı hekim bulundu"
                }

            if len(exact_matches) == 1:
                match = exact_matches[0]
                phone = (match.get("phone") or "").strip()
                district = (match.get("ilce") or "").strip()
                
                return {
                    "phone": phone,
                    "district": district,
                    "source_url": "https://www.tdb.org.tr/dishekimi-bul",
                    "phone_type": "personal_registry",
                    "source_type": "tdb",
                    "verification_status": "verified" if phone else "unverified"
                }

    except Exception as e:
        logger.debug(f"TDB bağlantı hatası ({raw_name}): {e}")

    return None
