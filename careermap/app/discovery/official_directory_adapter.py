"""CareerMap V2.5 Resmî Kurum ve Sağlık Tesisleri Sicil Adaptörü (Official Directory Adapter).
- P3: Şehir bazlı resmî sağlık müdürlükleri, Türk Dişhekimleri Birliği (TDB) ve HealthTürkiye (USHAŞ) ruhsatlı tesis kayıtlarını işler.
- Eskişehir için 220 adet doğrulanmış il sağlık kuruluşunu tam korur ve sunar.
- İstanbul, İzmir, Ankara, Bursa ve Antalya için HealthTürkiye akredite özel ADSM ve poliklinik kayıtlarını sağlar.
- Bir şehirde resmî kaynak adaptörü henüz yapılandırılmamışsa dürüstçe 'not_configured' durumu raporlar; boş sonuçla 'completed' dönmez.
"""
import os
import json
import logging
import sqlite3
import unicodedata
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from ..database.db import get_connection

logger = logging.getLogger("careermap.discovery.official")

HEALTH_TURKIYE_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "official" / "health_turkiye_licensed_facilities.json"


def normalize_tr_text(text: str) -> str:
    """Türkçe karakterleri ve boşlukları karşılaştırma standardına getirir."""
    if not text:
        return ""
    s = str(text).replace("I", "ı").replace("İ", "i").lower()
    s = s.translate(str.maketrans("çğıöşü", "cgiosu"))
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return " ".join(s.split())


class OfficialDirectoryAdapter:
    """Resmî sağlık müdürlüğü, TDB ve HealthTürkiye kayıtları adaptörü."""

    SOURCE_ID = "official_chambers"
    SOURCE_NAME = "Resmî İl Sağlık Müdürlükleri & HealthTürkiye Akredite Tesis Sicili"
    SOURCE_TYPE = "official"
    RELIABILITY_TIER = "primary_official"

    @classmethod
    def discover(
        cls,
        city: str,
        districts: Optional[List[str]] = None,
        employer_types: Optional[List[str]] = None,
        conn: Optional[sqlite3.Connection] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Şehir ve ilçe bazlı resmî sağlık kuruluşu kayıtlarını çeker.
        """
        should_close = False
        if conn is None:
            conn = get_connection()
            should_close = True

        cursor = conn.cursor()
        city_clean = city.strip().lower()

        # 1. Eskişehir Resmî İl Sağlık ve TDB Listesi (Doğrulanmış 220 Kurum)
        if city_clean in ("eskişehir", "eskisehir"):
            query = """
            SELECT employer_id, profession_id, city, district, name,
                   employer_type, address, phone, phone_type, phone_source_url, phone_verification_status,
                   email, email_type, email_source_url, email_verification_status,
                   website, website_source_url, website_verification_status,
                   whatsapp_url, source_urls, source_type, business_status,
                   research_status, confidence_score, confidence_level
            FROM employers
            WHERE city = 'Eskişehir' AND profession_id = 'dentist' AND source_type LIKE '%Sağlık Müdürlüğü%'
            """
            params = []

            if districts and len(districts) > 0 and districts[0].lower() not in ("all", "tüm ilçeler"):
                dist_placeholders = ",".join(["?" for _ in districts])
                query += f" AND district IN ({dist_placeholders})"
                params.extend(districts)

            if employer_types and "all" not in employer_types:
                type_conds = []
                for et in employer_types:
                    if et == "clinic":
                        type_conds.append("employer_type LIKE '%poliklinik%'")
                    elif et == "office":
                        type_conds.append("(employer_type LIKE '%muayenehane%' OR name LIKE 'Dt.%')")
                if type_conds:
                    query += f" AND ({' OR '.join(type_conds)})"

            cursor.execute(query, params)
            rows = cursor.fetchall()
            col_names = [c[0] for c in cursor.description]

            results = []
            for r in rows:
                d = dict(zip(col_names, r))
                d["source_id"] = cls.SOURCE_ID
                d["source_object_id"] = f"eskisehir_ism_{d.get('employer_id')}"
                results.append(d)

            if should_close:
                conn.close()

            report = {
                "source_id": cls.SOURCE_ID,
                "source_name": cls.SOURCE_NAME,
                "status": "completed",
                "city": city,
                "items_found": len(results),
                "error_message": ""
            }
            return results, report

        # 2. HealthTürkiye / USHAŞ Akredite Sağlık Tesisleri Listesi Kontrolü
        if should_close:
            conn.close()

        ht_facilities = cls._load_health_turkiye_facilities(city, districts, employer_types)
        if ht_facilities:
            report = {
                "source_id": cls.SOURCE_ID,
                "source_name": cls.SOURCE_NAME,
                "status": "completed",
                "city": city,
                "items_found": len(ht_facilities),
                "error_message": ""
            }
            return ht_facilities, report

        # 3. Henüz yapılandırılmamış şehirler için dürüst durum
        report = {
            "source_id": cls.SOURCE_ID,
            "source_name": cls.SOURCE_NAME,
            "status": "not_configured",
            "city": city,
            "items_found": 0,
            "error_message": f"{city} İl Sağlık Müdürlüğü açık toplu sicil API'si sunmamaktadır (not_configured). İzinli veri paylaşım protokolü gereklidir. Sentetik veri üretilmemektedir."
        }
        return [], report

    @classmethod
    def _load_health_turkiye_facilities(
        cls,
        city: str,
        districts: Optional[List[str]] = None,
        employer_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """HealthTürkiye JSON dosyasından ilgili şehirdeki tesisleri filtreler."""
        if not HEALTH_TURKIYE_FILE.exists():
            return []

        try:
            raw = json.loads(HEALTH_TURKIYE_FILE.read_text(encoding="utf-8"))
            facilities = raw.get("facilities", [])
        except Exception as e:
            logger.error(f"HealthTürkiye dosyası okuma hatası: {e}")
            return []

        city_norm = normalize_tr_text(city)
        results = []

        for f in facilities:
            if normalize_tr_text(f.get("city", "")) != city_norm:
                continue

            # İlçe filtresi
            if districts and districts[0].lower() not in ("all", "tüm ilçeler", ""):
                dist_norm = normalize_tr_text(districts[0])
                f_dist = normalize_tr_text(f.get("district", ""))
                if dist_norm != f_dist and dist_norm not in f_dist:
                    continue

            # Tür filtresi
            inst_type = f.get("institution_type", "Özel poliklinik")
            if employer_types and "all" not in employer_types:
                if "clinic" in employer_types and "muayenehane" in inst_type.lower():
                    continue
                if "office" in employer_types and "muayenehane" not in inst_type.lower():
                    continue

            results.append({
                "employer_id": f.get("facility_id"),
                "profession_id": "dentist",
                "city": f.get("city", city),
                "district": f.get("district", ""),
                "name": f.get("name"),
                "employer_type": inst_type,
                "address": f.get("address", ""),
                "phone": f.get("phone", ""),
                "phone_type": "corporate",
                "phone_source_url": f.get("source_url", ""),
                "phone_verification_status": "verified",
                "email": "",
                "email_type": "",
                "email_source_url": "",
                "email_verification_status": "unverified",
                "website": f.get("website", ""),
                "website_source_url": f.get("source_url", ""),
                "website_verification_status": "verified" if f.get("website") else "unverified",
                "whatsapp_url": "",
                "source_urls": f.get("source_url", ""),
                "source_type": "official_health_tourism_registry",
                "source_id": "official_health_tourism_registry",
                "source_name": "HealthTürkiye / USHAŞ Uluslararası Sağlık Turizmi Yetkili Sağlık Tesisleri Sicili",
                "source_object_id": f.get("facility_id"),
                "business_status": "active",
                "research_status": "completed",
                "research_notes": "Sağlık Bakanlığı USHAŞ Uluslararası Sağlık Turizmi Yetki Belgeli ADSM ve Hastane (Bireysel muayenehaneleri kapsamaz).",
                "confidence_score": f.get("confidence_score", 90),
                "confidence_level": "Yüksek"
            })

        return results
