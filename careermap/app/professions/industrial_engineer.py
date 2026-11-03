"""Endüstri Mühendisi mesleği için genişletilebilir şablon."""
from typing import List, Dict, Any
from .base import BaseProfession

class IndustrialEngineerProfession(BaseProfession):
    id = "industrial_engineer"
    name = "Endüstri Mühendisi"
    description = "Organize Sanayi Bölgesi (EOSB) firmaları, üretim tesisleri, otomotiv ve lojistik şirketleri"
    icon = "bi-gear-wide-connected"
    
    supported_cities = {
        "Eskişehir": ["Odunpazarı (EOSB)", "Tepebaşı", "Sivrihisar", "Çifteler"],
        "Bursa": ["Nilüfer (NOSAB)", "Osmangazi", "İnegöl"]
    }
    
    employer_types = [
        {"id": "all", "label": "Tüm Sanayi ve Üretim Kuruluşları"},
        {"id": "factory", "label": "Fabrikalar ve Üretim Şirketleri"},
        {"id": "logistics", "label": "Lojistik Firmaları & Tedarik Zinciri"},
        {"id": "rd_center", "label": "Ar-Ge ve Tasarım Merkezleri"}
    ]
    
    osm_tags = [
        {"key": "industrial", "value": "factory"},
        {"key": "man_made", "value": "works"},
        {"key": "office", "value": "company"}
    ]

    def get_official_sources(self, city: str) -> List[Dict[str, Any]]:
        return [
            {
                "type": "osb",
                "label": "Eskişehir Sanayi Odası / Organize Sanayi Bölgesi Rehberi",
                "url": "https://www.eosb.org.tr/firmalar"
            }
        ]

    def parse_official_records(self, soup_dict: Dict[str, Any], city: str) -> List[Dict[str, Any]]:
        return []

