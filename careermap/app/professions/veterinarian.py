"""Veteriner Hekim mesleği için şablon ve kural tanımları."""
from typing import List, Dict, Any
from .base import BaseProfession

class VeterinarianProfession(BaseProfession):
    id = "veterinarian"
    name = "Veteriner Hekim"
    description = "Veteriner klinikleri, hayvan hastaneleri ve poliklinikler"
    icon = "bi-bandaid"

    supported_cities = {
        "Eskişehir": ["Tepebaşı", "Odunpazarı", "Sivrihisar"],
        "Ankara": ["Çankaya", "Yenimahalle", "Gölbaşı", "Keçiören"],
        "İstanbul": ["Kadıköy", "Beşiktaş", "Üsküdar", "Sarıyer"],
        "İzmir": ["Bornova", "Karşıyaka", "Konak"]
    }

    employer_types = [
        {"id": "all", "label": "Tüm Veteriner Sağlık Kuruluşları"},
        {"id": "vet_clinic", "label": "Veteriner Klinikleri ve Poliklinikleri"},
        {"id": "animal_hospital", "label": "Hayvan Hastaneleri"}
    ]

    osm_tags = [
        {"key": "amenity", "value": "veterinary"}
    ]

    def get_official_sources(self, city: str) -> List[Dict[str, Any]]:
        return []

    def parse_official_records(self, soup_dict: Dict[str, Any], city: str) -> List[Dict[str, Any]]:
        return []

