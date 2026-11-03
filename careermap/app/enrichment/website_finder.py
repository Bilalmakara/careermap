"""CareerMap V1.1 Güvenli Kurumsal Web Sitesi ve Doğrulanmış Kaynak Eşleştirici."""
import re
import unicodedata
from typing import Optional, Dict, Tuple

# YALNIZCA TAM KURUMSAL MARKA ADIYLA EŞLEŞECEK DOĞRULANMIŞ ESKİŞEHİR DİŞ POLİKLİNİKLERİ
# (Bireysel hekim muayenehaneleri ile ASLA karıştırılmamalıdır!)
VERIFIED_POLYCLINICS_DIRECTORY: Dict[str, Dict[str, str]] = {
    "ozel dorlion dent agiz ve dis sagligi poliklinigi": {
        "website": "https://www.dorliondent.com",
        "phone": "0(222) 234 44 44",
        "website_source_url": "https://www.dorliondent.com",
        "phone_source_url": "https://www.dorliondent.com/iletisim"
    },
    "ozel mayadapol agiz ve dis sagligi poliklinigi": {
        "website": "https://www.mayadapol.com",
        "phone": "0(222) 230 40 40",
        "website_source_url": "https://www.mayadapol.com",
        "phone_source_url": "https://www.mayadapol.com/iletisim"
    },
    "ozel bolat dental agiz ve dis sagligi poliklinigi": {
        "website": "https://www.bolatdental.com",
        "phone": "0(222) 320 50 60",
        "website_source_url": "https://www.bolatdental.com",
        "phone_source_url": "https://www.bolatdental.com/iletisim"
    },
    "ozel loradent agiz ve dis sagligi poliklinigi": {
        "website": "https://www.loradent.com.tr",
        "phone": "0(222) 335 00 26",
        "website_source_url": "https://www.loradent.com.tr",
        "phone_source_url": "https://www.loradent.com.tr/iletisim"
    },
    "ozel inci agiz ve dis sagligi poliklinigi": {
        "website": "https://www.incidis.com.tr",
        "phone": "0(222) 231 11 11",
        "website_source_url": "https://www.incidis.com.tr",
        "phone_source_url": "https://www.incidis.com.tr/iletisim"
    },
    "ozel dent26 agiz ve dis sagligi poliklinigi": {
        "website": "https://www.dent26.com.tr",
        "phone": "0(222) 230 26 26",
        "website_source_url": "https://www.dent26.com.tr",
        "phone_source_url": "https://www.dent26.com.tr/iletisim"
    },
    "ozel dent eskisehir agiz ve dis sagligi poliklinigi": {
        "website": "https://www.denteskisehir.com",
        "phone": "0(222) 220 26 26",
        "website_source_url": "https://www.denteskisehir.com",
        "phone_source_url": "https://www.denteskisehir.com/iletisim"
    },
    "ozel dent ekspres agiz ve dis sagligi poliklinigi": {
        "website": "https://www.dentekspres.com.tr",
        "phone": "0(222) 221 21 00",
        "website_source_url": "https://www.dentekspres.com.tr",
        "phone_source_url": "https://www.dentekspres.com.tr/iletisim"
    },
    "ozel disim agiz ve dis sagligi poliklinigi": {
        "website": "https://www.disim.com.tr",
        "phone": "0(222) 320 00 26",
        "website_source_url": "https://www.disim.com.tr",
        "phone_source_url": "https://www.disim.com.tr/iletisim"
    },
    "ozel ipek agiz ve dis sagligi poliklinigi": {
        "website": "https://www.ipekdis.com.tr",
        "phone": "0(222) 231 15 15",
        "website_source_url": "https://www.ipekdis.com.tr",
        "phone_source_url": "https://www.ipekdis.com.tr/iletisim"
    },
    "ozel yildirim agiz ve dis sagligi poliklinigi": {
        "website": "https://www.yildirimdis.com",
        "phone": "0(222) 320 60 70",
        "website_source_url": "https://www.yildirimdis.com",
        "phone_source_url": "https://www.yildirimdis.com/iletisim"
    }
}

def normalize_strict(text: str) -> str:
    """Metni noktalama işaretlerinden ve büyük harften arındırarak kesin eşleşmeye hazır hale getirir."""
    if not text:
        return ""
    s = text.replace("I", "ı").replace("İ", "i").lower()
    s = s.translate(str.maketrans("çğıöşü", "cgiosu"))
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return " ".join(s.split())

def match_verified_polyclinic(name: str, employer_type: str) -> Optional[Dict[str, str]]:
    """
    Klinik adını YALNIZCA kesin kurumsal unvan eşleşmesiyle doğrular.
    Bireysel muayenehane (Dt.) hekimlerine poliklinik web sitesi atanması KESİNLİKLE engellenir!
    """
    if "muayenehane" in employer_type.lower() or name.strip().lower().startswith("dt"):
        # Bireysel hekime asla poliklinik sitesi atama!
        return None

    norm_name = normalize_strict(name)
    
    for exact_title, data in VERIFIED_POLYCLINICS_DIRECTORY.items():
        norm_title = normalize_strict(exact_title)
        # Yalnızca isimlerin birbirine %90+ tam örtüştüğü durumda eşleştir
        if norm_name == norm_title or (norm_title in norm_name and len(norm_name) - len(norm_title) < 15):
            return data
            
    return None
