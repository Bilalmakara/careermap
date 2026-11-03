"""CareerMap V2.3 Yerel ve Canlı OpenStreetMap Kaynak Adaptörü (Local OSM Adapter).
- P1 & P2: Türkiye'deki diş hekimliği ve poliklinik noktalarını gerçek OSM veri havuzundan nesne kimlikleri ve koordinatlarıyla çeker.
- Yapay limitler (out 30/40) kaldırılmıştır; tüm idari ilçeleri kapsar.
- Her kayıt gerçek nesne URL'si (https://www.openstreetmap.org/node/123456) ve koordinat taşır.
- Markaların farklı ilçelerdeki şubeleri (DentGroup Kadıköy, Nişantaşı vb.) korunur.
- V2.3 Doğrulama Kuralı: OSM etiketindeki telefon ve e-posta doğrudan 'verified' yapılmaz; 'observed_on_source' olarak işaretlenir.
- P4 kuralı: Telefon bulunması otomatik WhatsApp sayılmaz.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from .osm_data_store import query_local_osm_dentists
from .entity_classifier import classify_dental_establishment
from ..enrichment.phone_extractor import format_phone

logger = logging.getLogger("careermap.discovery.local_osm")


class LocalOSMAdapter:
    """Yerel OpenStreetMap indeksi ve harita kaynak adaptörü."""

    SOURCE_ID = "osm_turkey_local"
    SOURCE_NAME = "OpenStreetMap Türkiye Diş Hekimliği İndeksi"
    SOURCE_TYPE = "osm"
    RELIABILITY_TIER = "geographical_osm"

    @classmethod
    def discover(
        cls,
        city: str,
        districts: Optional[List[str]] = None,
        employer_types: Optional[List[str]] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Belirtilen il ve ilçeler için OSM indeksinden gerçek işletme noktalarını keşfeder.
        Dönüş: (kurum_listesi, çalışma_raporu)
        """
        all_found = []
        target_districts = districts if (districts and len(districts) > 0 and districts[0].lower() not in ("all", "tüm ilçeler")) else [None]

        # Kurum tipi filtreleme
        emp_type_filter = None
        if employer_types and "all" not in employer_types:
            if "clinic" in employer_types and "office" not in employer_types:
                emp_type_filter = "clinic"
            elif "office" in employer_types and "clinic" not in employer_types:
                emp_type_filter = "office"

        for dist in target_districts:
            items = query_local_osm_dentists(city=city, district=dist, employer_type=emp_type_filter)
            for it in items:
                raw_phone = it.get("phone", "")
                norm_phone = format_phone(raw_phone) if raw_phone else ""
                osm_type = it.get("osm_type", "node")
                osm_id = it.get("osm_id")
                source_url = it.get("source_url") or f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
                
                name = it.get("name", "").strip()
                tags = it.get("tags") or {}
                emp_type = it.get("employer_type") or classify_dental_establishment(name, tags)

                email = it.get("email", "").strip()
                website = it.get("website", "").strip()
                coords = f"{it.get('lat', 0.0)},{it.get('lon', 0.0)}"

                # V2.3 Kalibre Doğrulama: Kaynaktan okunan etiket 'observed_on_source' olarak kaydedilir
                all_found.append({
                    "name": name,
                    "employer_type": emp_type,
                    "city": it.get("city", city),
                    "district": it.get("district", ""),
                    "address": it.get("address", ""),
                    "phone": norm_phone,
                    "phone_type": "corporate" if norm_phone else "unknown",
                    "phone_source_url": source_url if norm_phone else "",
                    "phone_verification_status": "observed_on_source" if norm_phone else "unverified",
                    "email": email,
                    "email_type": "corporate" if email else "unknown",
                    "email_source_url": source_url if email else "",
                    "email_verification_status": "observed_on_source" if email else "unverified",
                    "website": website,
                    "website_source_url": source_url if website else "",
                    "website_verification_status": "observed_on_source" if website else "unverified",
                    "whatsapp_url": "", # P4: Telefon bulunması otomatik WhatsApp sayılmaz
                    "career_url": "",
                    "contact_form_url": "",
                    "source_type": "OpenStreetMap",
                    "source_urls": source_url,
                    "source_id": cls.SOURCE_ID,
                    "source_object_id": f"{osm_type}/{osm_id}",
                    "coordinates": coords,
                    "business_status": "active",
                    "research_status": "observed_on_source" if (norm_phone or email or website) else "pending_enrichment",
                    "confidence_score": 80,
                    "confidence_level": "Yüksek",
                    "osm_snapshot_date": it.get("osm_snapshot_date", "2026-11-03")
                })

        report = {
            "source_id": cls.SOURCE_ID,
            "source_name": cls.SOURCE_NAME,
            "status": "completed",
            "city": city,
            "items_found": len(all_found),
            "error_message": ""
        }

        return all_found, report
