"""CareerMap V2.3 Kamuya Açık İzinli Rehber Adaptörü (Permitted Directory Adapter).
- P1: Kamuya açık hekim profilleri ve oda rehberlerini çapraz kontrol ve hekim doğrulaması için sorgular.
- V2.3 Kuralı: Yapılandırılmamış veya boş çalışan adaptör 'not_configured' döner; sahte 'completed' durumu raporlanmaz.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger("careermap.discovery.permitted_directory")


class PermittedDirectoryAdapter:
    """Kamuya açık izinli dizin ve oda rehberleri adaptörü."""

    SOURCE_ID = "permitted_directories"
    SOURCE_NAME = "Kamuya Açık Sağlık ve Diş Hekimi Rehberleri"
    SOURCE_TYPE = "directory"
    RELIABILITY_TIER = "secondary_directory"

    @classmethod
    def discover(
        cls,
        city: str,
        districts: Optional[List[str]] = None,
        employer_types: Optional[List[str]] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Kamuya açık rehberlerden ek kurum ve hekim adaylarını araştırır.
        """
        records = []
        report = {
            "source_id": cls.SOURCE_ID,
            "source_name": cls.SOURCE_NAME,
            "status": "not_configured",
            "city": city,
            "items_found": 0,
            "error_message": f"{city} için kamuya açık rehber adaptörü yapılandırma aşamasındadır (not_configured)."
        }
        return records, report
