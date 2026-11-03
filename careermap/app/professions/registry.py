"""Meslek Kayıt ve Yönetim Merkezi (Profession Registry)."""
from typing import Dict, List, Optional, Any
from .base import BaseProfession
from .dentist import DentistProfession
from .software_engineer import SoftwareEngineerProfession
from .industrial_engineer import IndustrialEngineerProfession
from .veterinarian import VeterinarianProfession
from .lawyer import LawyerProfession

class ProfessionRegistry:
    _registry: Dict[str, BaseProfession] = {}

    @classmethod
    def register(cls, profession: BaseProfession):
        cls._registry[profession.id] = profession

    @classmethod
    def get(cls, profession_id: str) -> Optional[BaseProfession]:
        return cls._registry.get(profession_id)

    @classmethod
    def list_all(cls) -> List[Dict[str, Any]]:
        return [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "icon": p.icon,
                "supported_cities": p.supported_cities,
                "employer_types": p.employer_types,
                "is_active": (p.id == "dentist"),
                "adapter_status": "ready" if p.id == "dentist" else "planned",
                "adapter_message": "Resmî rehberler, OSM ve çok kaynaklı iletişim keşfi aktif." if p.id == "dentist" else f"{p.name} için veri kaynağı adaptörü geliştirme aşamasındadır."
            }
            for p in cls._registry.values()
        ]

# Başlangıçta meslekleri kaydet
ProfessionRegistry.register(DentistProfession())
ProfessionRegistry.register(IndustrialEngineerProfession())
ProfessionRegistry.register(SoftwareEngineerProfession())
ProfessionRegistry.register(VeterinarianProfession())
ProfessionRegistry.register(LawyerProfession())
