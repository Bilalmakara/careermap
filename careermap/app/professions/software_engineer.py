"""Yazılım Geliştirici mesleği için genişletilebilir şablon."""
from typing import List, Dict, Any
from .base import BaseProfession

class SoftwareEngineerProfession(BaseProfession):
    id = "software_engineer"
    name = "Yazılım Geliştirici"
    description = "Teknopark firmaları, bilişim şirketleri, Ar-Ge merkezleri ve teknoloji girişimleri"
    icon = "bi-code-slash"
    
    supported_cities = {
        "Eskişehir": ["Tepebaşı", "Odunpazarı"],
        "Ankara": ["Çankaya", "Yenimahalle", "Gölbaşı", "ODTÜ Teknokent", "Bilkent Cyberpark"],
        "Bursa": ["Nilüfer", "Osmangazi"]
    }
    
    employer_types = [
        {"id": "all", "label": "Tüm Teknoloji İşverenleri"},
        {"id": "software_company", "label": "Yazılım Şirketleri & Bilişim Firmaları"},
        {"id": "technopark", "label": "Teknopark Firmaları (ATAP, ODTÜ, Cyberpark)"},
        {"id": "startup", "label": "Teknoloji Girişimleri (Startuplar)"},
        {"id": "rd_center", "label": "Ar-Ge ve İnovasyon Merkezleri"}
    ]
    
    osm_tags = [
        {"key": "office", "value": "it"},
        {"key": "office", "value": "telecommunication"},
        {"key": "office", "value": "company"}
    ]

    def get_official_sources(self, city: str) -> List[Dict[str, Any]]:
        # Gelecekte ATAP (Anadolu Teknoloji Araştırma Parkı) rehberi, vb.
        return [
            {
                "type": "technopark",
                "label": "ATAP Eskişehir Teknoloji Geliştirme Bölgesi",
                "url": "https://atap.com.tr/firmalarimiz"
            }
        ]

    def parse_official_records(self, soup_dict: Dict[str, Any], city: str) -> List[Dict[str, Any]]:
        return []

