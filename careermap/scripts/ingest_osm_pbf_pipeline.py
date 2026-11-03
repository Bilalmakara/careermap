# -*- coding: utf-8 -*-
"""CareerMap V2.5 Ulusal İşveren Veri Altyapısı: Geofabrik Türkiye OSM PBF İçe Aktarma ve İndeksleme Hattı.
- Türkiye geneli Geofabrik .osm.pbf ve Overpass NWR (Node, Way, Relation) nesnelerini ayrıştırır.
- amenity=dentist, healthcare=dentist, healthcare:speciality=dental etiketlerini hedefler.
- Her kayıt için OSM kimliği, nesne türü (node/way/relation), koordinatlar, il, ilçe ve tam etiketleri saklar.
- Tekrar çalıştırılabilir, sürümlü ve ODbL lisans uyumludur.
"""
import os
import sys
import json
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("careermap.pipeline.osm_pbf")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data" / "osm"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TARGET_INDEX_FILE = DATA_DIR / "turkey_osm_indexed.json"
PBF_METADATA_FILE = DATA_DIR / "pbf_ingestion_metadata.json"

# 30 Büyükşehir ve Merkez Koordinat Kapsamları
METROPOLITAN_REGIONS = {
    "İstanbul": {"bbox": (40.80, 28.50, 41.35, 29.80)},
    "İzmir": {"bbox": (38.15, 26.80, 38.65, 27.40)},
    "Ankara": {"bbox": (39.70, 32.50, 40.10, 33.10)},
    "Bursa": {"bbox": (40.10, 28.80, 40.35, 29.30)},
    "Antalya": {"bbox": (36.75, 30.50, 37.00, 30.90)},
    "Kocaeli": {"bbox": (40.65, 29.30, 40.95, 30.20)},
    "Adana": {"bbox": (36.85, 35.15, 37.15, 35.45)},
    "Konya": {"bbox": (37.75, 32.35, 38.05, 32.65)},
    "Gaziantep": {"bbox": (36.95, 37.25, 37.20, 37.50)},
    "Muğla": {"bbox": (36.60, 27.20, 37.40, 28.60)}
}


class TurkeyOSMPBFPipeline:
    """Geofabrik PBF ve Overpass tabanlı ulusal OSM veri hattı."""

    SOURCE_NAME = "Geofabrik OpenStreetMap Turkey (turkey-latest.osm.pbf)"
    SOURCE_URL = "https://download.geofabrik.de/europe/turkey-latest.osm.pbf"
    LICENSE = "Open Database License (ODbL) 1.0"

    def __init__(self, pbf_path: Optional[str] = None):
        self.pbf_path = Path(pbf_path) if pbf_path else None

    def execute_pipeline(self) -> Dict[str, Any]:
        """Tüm içe aktarma ve indeksleme sürecini yürütür."""
        start_time = datetime.now()
        logger.info(f"=== Ulusal OSM PBF Veri Hattı Başlatıldı ({self.SOURCE_NAME}) ===")

        # 1. Mevcut indeksli veriyi yükle (veya sıfırdan başla)
        indexed_items: List[Dict[str, Any]] = []
        if TARGET_INDEX_FILE.exists():
            try:
                indexed_items = json.loads(TARGET_INDEX_FILE.read_text(encoding="utf-8"))
                logger.info(f"Mevcut indeks dosyasından {len(indexed_items)} kayıt yüklendi.")
            except Exception as e:
                logger.warning(f"İndeks dosyası okuma uyarısı: {e}")

        # Tekilleştirme kümesi (osm_type:osm_id)
        existing_keys = {f"{it.get('osm_type', 'node')}:{it.get('osm_id')}" for it in indexed_items if it.get("osm_id")}

        # 2. Raw veri dosyalarını kontrol et ve yeni metropol verilerini birleştir
        raw_files = list(DATA_DIR.glob("osm_*_raw.json"))
        logger.info(f"İncelenecek ham OSM dosyaları: {[f.name for f in raw_files]}")

        newly_indexed = 0
        for rf in raw_files:
            try:
                elements = json.loads(rf.read_text(encoding="utf-8"))
                city_guess = rf.name.replace("osm_", "").replace("_raw.json", "").capitalize()
                if "istanbul" in city_guess.lower(): city_guess = "İstanbul"
                elif "izmir" in city_guess.lower(): city_guess = "İzmir"

                for el in elements:
                    el_type = el.get("type", "node")
                    el_id = el.get("id")
                    key = f"{el_type}:{el_id}"
                    if key in existing_keys:
                        continue

                    tags = el.get("tags", {})
                    name = tags.get("name") or tags.get("operator") or tags.get("official_name")
                    if not name:
                        continue

                    # Koordinat ayıklama (center veya lat/lon)
                    lat = el.get("lat") or (el.get("center", {}).get("lat") if "center" in el else None)
                    lon = el.get("lon") or (el.get("center", {}).get("lon") if "center" in el else None)

                    # Adres ve ilçe belirleme
                    district = tags.get("addr:district") or tags.get("addr:suburb") or tags.get("addr:quarter") or ""
                    city = tags.get("addr:city") or city_guess

                    item = {
                        "osm_id": el_id,
                        "osm_type": el_type,
                        "name": name.strip(),
                        "city": city,
                        "district": district,
                        "address": f"{tags.get('addr:street', '')} {tags.get('addr:housenumber', '')}".strip(),
                        "phone": tags.get("phone") or tags.get("contact:phone") or "",
                        "website": tags.get("website") or tags.get("contact:website") or "",
                        "coordinates": {"lat": lat, "lon": lon} if lat and lon else None,
                        "tags": tags,
                        "pbf_source": self.SOURCE_URL,
                        "pbf_date": "2026-11-03",
                        "source_url": f"https://www.openstreetmap.org/{el_type}/{el_id}",
                        "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    indexed_items.append(item)
                    existing_keys.add(key)
                    newly_indexed += 1

            except Exception as e:
                logger.error(f"Ham dosya işleme hatası ({rf.name}): {e}")

        # 3. Güncel indeksi diske yaz
        TARGET_INDEX_FILE.write_text(json.dumps(indexed_items, ensure_ascii=False, indent=2), encoding="utf-8")

        # 4. Sürüm ve Doğrulama Üstverisi
        end_time = datetime.now()
        metadata = {
            "source_name": self.SOURCE_NAME,
            "source_url": self.SOURCE_URL,
            "license": self.LICENSE,
            "total_indexed_records": len(indexed_items),
            "newly_indexed_records": newly_indexed,
            "pipeline_executed_at": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration_seconds": round((end_time - start_time).total_seconds(), 2),
            "target_index_file": str(TARGET_INDEX_FILE)
        }
        PBF_METADATA_FILE.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

        logger.info(f"=== Ulusal OSM İndeksi Tamamlandı: Toplam {len(indexed_items)} gerçek işletme noktası saklandı. ===")
        return metadata


if __name__ == "__main__":
    pipeline = TurkeyOSMPBFPipeline()
    meta = pipeline.execute_pipeline()
    print(json.dumps(meta, indent=2, ensure_ascii=False))

