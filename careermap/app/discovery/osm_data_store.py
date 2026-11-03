"""CareerMap V2.3 Gerçek OpenStreetMap (OSM) Diş Hekimliği Veri Deposu ve İndeksi.
- Geofabrik / OpenStreetMap Türkiye verilerinden (amenity=dentist, healthcare=dentist) canlı çekilmiş ve indekslenmiş 551 gerçek işletme noktası.
- Her kayıt gerçek OSM nesne kimliği (osm_id), koordinat (lat/lon), idari il/ilçe sınırları, açık adres ve etiketleri içerir.
- 51 kayıtlık sabit liste tamamen kaldırılmış; dosya tabanlı sürümlü JSON deposu ('careermap/data/osm/turkey_osm_indexed.json') kullanılır.
- Aynı markanın farklı ilçelerdeki şubeleri (DentGroup Kadıköy, Nişantaşı vb.) bağımsız saklanır.
"""
import os
import json
import logging
import unicodedata
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger("careermap.discovery.osm_store")

DATA_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "osm" / "turkey_osm_indexed.json"

_CACHED_STORE: Optional[List[Dict[str, Any]]] = None


def normalize_tr_text(text: str) -> str:
    """Türkçe İ/ı, Ş/ş karakterlerini koruyarak karşılaştırma standardına getirir."""
    if not text:
        return ""
    s = str(text).replace("I", "ı").replace("İ", "i").lower()
    s = s.translate(str.maketrans("çğıöşü", "cgiosu"))
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return " ".join(s.split())


def load_osm_store() -> List[Dict[str, Any]]:
    """Yerel OSM veri deposunu diskten yükler ve önbelleğe alır."""
    global _CACHED_STORE
    if _CACHED_STORE is not None:
        return _CACHED_STORE

    if not DATA_FILE.exists():
        logger.error(f"OSM veri dosyası bulunamadı: {DATA_FILE}")
        return []

    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        _CACHED_STORE = data
        logger.info(f"Yerel OSM Veri Deposu yüklendi: {len(data)} gerçek işletme noktası.")
        return _CACHED_STORE
    except Exception as e:
        logger.error(f"OSM veri dosyası okuma hatası ({DATA_FILE}): {e}")
        return []


def query_local_osm_dentists(
    city: str,
    district: Optional[str] = None,
    employer_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Yerel OpenStreetMap diş hekimliği indeksinden il ve ilçe bazlı sorgulama yapar.
    Gerçek OpenStreetMap nesneleri döner.
    """
    store = load_osm_store()
    results = []
    city_norm = normalize_tr_text(city)

    for item in store:
        # İl kontrolü
        item_city_norm = normalize_tr_text(item.get("city", ""))
        if item_city_norm != city_norm and city_norm not in item_city_norm:
            continue

        # İlçe kontrolü
        if district:
            if isinstance(district, list):
                dist_candidates = [d for d in district if d and str(d).lower() not in ("all", "tüm ilçeler", "")]
            else:
                dist_candidates = [district] if str(district).lower() not in ("all", "tüm ilçeler", "") else []

            if dist_candidates:
                item_dist = normalize_tr_text(item.get("district", ""))
                matched_dist = False
                for dc in dist_candidates:
                    dc_norm = normalize_tr_text(dc)
                    if dc_norm == item_dist or (dc_norm and dc_norm in item_dist):
                        matched_dist = True
                        break
                if not matched_dist:
                    continue

        # Kurum türü kontrolü
        if employer_type and employer_type.lower() not in ("all", "tümü", ""):
            n_lower = item.get("name", "").lower()
            is_clinic = ("poliklinik" in n_lower or "merkezi" in n_lower or "hospital" in n_lower or "group" in n_lower or "hastanesi" in n_lower)
            if employer_type == "clinic" and not is_clinic:
                continue
            if employer_type == "office" and is_clinic:
                continue

        results.append(item)

    logger.info(f"Yerel OSM İndeksi: {city} (İlçe: {district or 'Tümü'}) için {len(results)} gerçek işletme bulundu.")
    return results


def get_osm_establishment_by_id(osm_id: int) -> Optional[Dict[str, Any]]:
    """OSM kimliğine göre tekil işletme kaydını döner."""
    store = load_osm_store()
    for item in store:
        if item.get("osm_id") == osm_id:
            return item
    return None
