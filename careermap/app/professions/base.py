"""Meslek taban sınıfı ve soyutlama sözleşmesi."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import unicodedata
import re

def turkish_lower(s: str) -> str:
    """Türkçe I/ı ve İ/i harflerini doğru küçülten yardımcı fonksiyon."""
    if not s:
        return ""
    return s.replace("I", "ı").replace("İ", "i").lower()

class BaseProfession(ABC):
    """Herhangi bir meslek için türetilecek soyut sınıf."""
    id: str = "base"
    name: str = "Genel Meslek"
    description: str = "Tüm meslekler için temel şablon"
    icon: str = "bi-briefcase"  # Bootstrap icon
    
    # Desteklenen şehirler ve ilçeleri: { "Eskişehir": ["Tepebaşı", "Odunpazarı", ...] }
    supported_cities: Dict[str, List[str]] = {}
    
    # İşveren türleri: [{"id": "all", "label": "Tüm Uygun İşverenler"}, ...]
    employer_types: List[Dict[str, str]] = []
    
    # OpenStreetMap sorgusu için etiketler: [("amenity", "dentist"), ...]
    osm_tags: List[Dict[str, str]] = []

    @abstractmethod
    def get_official_sources(self, city: str) -> List[Dict[str, Any]]:
        """Resmî kurum listeleri veya rehberlerin URL ve yapılandırmalarını döner."""
        pass

    @abstractmethod
    def parse_official_records(self, soup_dict: Dict[str, Any], city: str) -> List[Dict[str, Any]]:
        """Çekilen HTML sayfalarını işveren kayıtlarına dönüştürür."""
        pass

    def clean_text(self, s: Optional[str]) -> str:
        if not s:
            return ""
        return " ".join(str(s).split()).strip()

    def normalize_for_comparison(self, s: str) -> str:
        """İsimleri fuzzy karşılaştırma için standardize eder."""
        s = self.clean_text(s).lower()
        s = s.translate(str.maketrans("çğıöşü", "cgiosu"))
        s = unicodedata.normalize("NFKD", s)
        # Mesleğe özgü unvanları ve genel kelimeleri temizleme
        s = re.sub(r"[^a-z0-9]", "", s)
        return s

    def detect_district(self, text: str, city: str) -> str:
        """Adres veya metinden ilçeyi tespit eder."""
        t = turkish_lower(self.clean_text(text))
        city_districts = self.supported_cities.get(city, [])
        for d in city_districts:
            d_lower = turkish_lower(d)
            if d_lower in t:
                return d
        return ""

    def calculate_confidence(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """İşveren kaydı için güven puanı ve doğrulama durumu hesaplar."""
        score = 30  # Temel puan
        
        # Resmî kurum kaydı varsa
        source_type = record.get("source_type", "")
        if "İl Sağlık" in source_type or "Resmî" in source_type or "Oda" in source_type:
            score += 35
        if "OpenStreetMap" in source_type or "OSM" in source_type:
            score += 15
        if "+" in source_type: # Birden çok kaynakta bulunduysa büyük artı!
            score += 15
            
        # İletişim verisi doluluğu
        if record.get("phone"):
            score += 10
        if record.get("website"):
            score += 15
        if record.get("email"):
            score += 15
        if record.get("address") and len(record["address"]) > 10:
            score += 5
            
        score = min(score, 100)
        
        if score >= 80:
            level = "Yüksek"
            status = "Doğrulandı"
        elif score >= 55:
            level = "Orta"
            status = "Kontrol Edilmeli"
        else:
            level = "Düşük"
            status = "Eksik Bilgi"
            
        return {
            "confidence_score": score,
            "confidence_level": level,
            "verification_status": status
        }

