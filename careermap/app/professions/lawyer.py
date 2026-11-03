"""Avukat mesleği için şablon ve kural tanımları."""
from typing import List, Dict, Any
from .base import BaseProfession

class LawyerProfession(BaseProfession):
    id = "lawyer"
    name = "Avukat"
    description = "Hukuk büroları, avukatlık ortaklıkları ve şirket hukuk müşavirlikleri"
    icon = "bi-journal-check"

    supported_cities = {
        "Eskişehir": ["Tepebaşı", "Odunpazarı"],
        "Ankara": ["Çankaya", "Sıhhiye", "Yenimahalle", "Gölbaşı"],
        "İstanbul": ["Şişli", "Çağlayan", "Bakırköy", "Kartal", "Kadıköy"],
        "İzmir": ["Bayraklı", "Konak", "Alsancak"]
    }

    employer_types = [
        {"id": "all", "label": "Tüm Hukuk Büroları ve Departmanlar"},
        {"id": "law_firm", "label": "Bağımsız Hukuk Büroları ve Ortaklıkları"},
        {"id": "corporate_legal", "label": "Şirket Hukuk ve Uyum Müşavirlikleri"}
    ]

    osm_tags = [
        {"key": "office", "value": "lawyer"}
    ]

    def get_official_sources(self, city: str) -> List[Dict[str, Any]]:
        return []

    def parse_official_records(self, soup_dict: Dict[str, Any], city: str) -> List[Dict[str, Any]]:
        return []

