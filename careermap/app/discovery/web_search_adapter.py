"""CareerMap V2.5 Canlı Web Arama Kaynak Adaptörü (Web Search Adapter).
- FreeSerp (freeserp.ai) ve SearchRouter üzerinden il ve ilçe bazlı web aramaları gerçekleştirir.
- Dizin sitelerini (DoktorTakvimi, Kariyer.net vb.) kurum kaydı olarak almaz; yalnızca müstakil klinik sitelerini ayıklar.
- Arama sonucundaki URL, başlık, bağlam ve kaynak kanıtlarını employer_source_records'a uygun formatta döner.
- Servis çalışamazsa gerçek hata durumu raporlar; boş sonuçla sahte completed dönmez.
"""
import re
import logging
from urllib.parse import urlparse
from typing import List, Dict, Any, Optional, Tuple

from ..enrichment.search_adapters import FreeSerpAdapter
from ..enrichment.web_search_discovery import DIRECTORY_DOMAINS

logger = logging.getLogger("careermap.discovery.web_search")


class WebSearchAdapter:
    """Arama motorları üzerinden dinamik kurum ve web sitesi keşif adaptörü."""

    SOURCE_ID = "web_search_freeserp"
    SOURCE_NAME = "FreeSerp Canlı Web İndeksi Arama Adaptörü"
    SOURCE_TYPE = "web_search"
    RELIABILITY_TIER = "fallback_search"

    @classmethod
    def discover(
        cls,
        city: str,
        districts: Optional[List[str]] = None,
        employer_types: Optional[List[str]] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Web araması üzerinden hedef il ve ilçelerdeki bağımsız diş kliniklerini araştırır.
        """
        adapter = FreeSerpAdapter(timeout=6)
        found_records = []
        queries = []

        dist_str = districts[0] if (districts and len(districts) > 0 and districts[0].lower() not in ("all", "tüm ilçeler")) else ""
        if dist_str:
            queries.append(f"{city} {dist_str} diş polikliniği")
            queries.append(f"{city} {dist_str} özel diş kliniği")
        else:
            queries.append(f"{city} diş poliklinikleri")
            queries.append(f"{city} özel diş klinikleri")

        errors = []
        for q in queries:
            try:
                results = adapter.search(q, max_results=8)
                for r in results:
                    domain = r.domain.lower().replace("www.", "")
                    # Üçüncü taraf rehber veya haber sitelerini atla
                    if any(dir_dom in domain for dir_dom in DIRECTORY_DOMAINS) or any(k in domain for k in ["haber", "sondakika", "onedio", "bilmece", "blog", "gazete"]):
                        continue

                    # Başlıkta diş hekimliği sinyali ara
                    title_lower = r.title.lower()
                    if not any(k in title_lower for k in ["diş", "dis", "dent", "dental", "poliklinik"]):
                        continue

                    # Kurum adını başlıktan temizle
                    raw_name = r.title.split("|")[0].split("-")[0].split("—")[0].strip()
                    if len(raw_name) < 4 or len(raw_name) > 80:
                        continue

                    found_records.append({
                        "name": raw_name,
                        "employer_type": "Özel poliklinik",
                        "city": city,
                        "district": dist_str or city,
                        "address": f"{city} / {dist_str}" if dist_str else city,
                        "phone": "",
                        "phone_type": "unknown",
                        "phone_source_url": "",
                        "phone_verification_status": "unverified",
                        "email": "",
                        "email_type": "unknown",
                        "email_source_url": "",
                        "email_verification_status": "unverified",
                        "website": r.url,
                        "website_source_url": r.url,
                        "website_verification_status": "observed_on_search",
                        "whatsapp_url": "",
                        "source_urls": r.url,
                        "source_type": "Web Arama (FreeSerp)",
                        "source_id": cls.SOURCE_ID,
                        "source_object_id": domain,
                        "business_status": "active",
                        "research_status": "completed",
                        "confidence_score": 75,
                        "confidence_level": "Orta"
                    })
            except Exception as e:
                logger.warning(f"Web arama hatası ({q}): {e}")
                errors.append(str(e))

        status = "completed" if found_records else ("failed" if errors else "not_configured")
        err_msg = "; ".join(errors) if errors else ""

        report = {
            "source_id": cls.SOURCE_ID,
            "source_name": cls.SOURCE_NAME,
            "status": status,
            "city": city,
            "items_found": len(found_records),
            "error_message": err_msg
        }
        return found_records, report
