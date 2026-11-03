# -*- coding: utf-8 -*-
"""Geofabrik turkey-latest.osm.pbf Gerçek Diş Hekimliği Ayrıştırıcısı (PyOsmium Stream Handler)."""
import os
import sys
import json
import time
import logging
from pathlib import Path
import osmium

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("careermap.osm.pbf_extractor")

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data" / "osm"
PBF_FILE = DATA_DIR / "turkey-latest.osm.pbf"
OUTPUT_JSON = DATA_DIR / "turkey_pbf_dental_raw.json"

# İl Coğrafi Sınırları (Bounding Boxes) ile İl Eşleştirme
PROVINCE_BOUNDS = {
    "İstanbul": (40.80, 27.95, 41.60, 29.95),
    "Bursa": (39.50, 28.10, 40.60, 30.00),
    "İzmir": (37.75, 26.25, 39.40, 28.50),
    "Ankara": (39.10, 31.40, 40.70, 33.50),
    "Antalya": (36.10, 29.20, 37.50, 32.60),
    "Kocaeli": (40.50, 29.35, 41.25, 30.35),
    "Adana": (36.50, 34.70, 38.00, 36.40),
    "Konya": (36.70, 31.25, 39.30, 34.40),
    "Gaziantep": (36.60, 36.45, 37.40, 37.95),
    "Muğla": (36.30, 27.20, 37.60, 29.70),
    "Eskişehir": (39.10, 29.90, 40.20, 32.10),
    "Trabzon": (40.50, 39.10, 41.15, 40.50),
    "Samsun": (40.85, 35.00, 41.75, 37.15),
    "Kayseri": (37.75, 34.90, 39.25, 36.90),
    "Diyarbakır": (37.50, 39.80, 38.80, 41.20)
}

def determine_province(lat: float, lon: float, tags: dict) -> str:
    """Koordinat veya adres etiketinden ili tespit eder."""
    city_tag = tags.get("addr:city") or tags.get("addr:province")
    if city_tag:
        c_clean = city_tag.strip().title()
        if "Istanbul" in c_clean or "İstanbul" in c_clean: return "İstanbul"
        if "Izmir" in c_clean or "İzmir" in c_clean: return "İzmir"
        if "Bursa" in c_clean: return "Bursa"
        if "Ankara" in c_clean: return "Ankara"
        if "Antalya" in c_clean: return "Antalya"
        if "Eskişehir" in c_clean or "Eskisehir" in c_clean: return "Eskişehir"
        return c_clean

    # Koordinat kutusu kontrolü
    for prov, (min_lat, min_lon, max_lat, max_lon) in PROVINCE_BOUNDS.items():
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            return prov

    return "Türkiye (Diğer)"


class DentalPBFHandler(osmium.SimpleHandler):
    """OSM PBF akışından diş sağlığı nesnelerini süzen PyOsmium sınıfı."""

    def __init__(self):
        super().__init__()
        self.elements = []
        self.stats = {"node": 0, "way": 0, "relation": 0}

    def is_dental(self, tags) -> bool:
        amenity = tags.get("amenity")
        healthcare = tags.get("healthcare")
        speciality = tags.get("healthcare:speciality")
        name = (tags.get("name") or "").lower()

        if amenity == "dentist" or healthcare == "dentist" or speciality == "dental":
            return True
        if "diş" in name or "dis" in name or "dent" in name:
            if any(k in name for k in ["poliklinik", "klinik", "merkezi", "hekim", "muayenehane", "hospital"]):
                return True
        return False

    def node(self, n):
        if not n.location.valid():
            return
        tags = dict(n.tags)
        if self.is_dental(tags):
            lat = n.location.lat
            lon = n.location.lon
            name = tags.get("name") or tags.get("operator") or f"Diş Kliniği #{n.id}"
            prov = determine_province(lat, lon, tags)
            district = tags.get("addr:district") or tags.get("addr:suburb") or ""

            self.elements.append({
                "osm_type": "node",
                "osm_id": n.id,
                "name": name.strip(),
                "city": prov,
                "district": district,
                "lat": lat,
                "lon": lon,
                "phone": tags.get("phone") or tags.get("contact:phone") or "",
                "website": tags.get("website") or tags.get("contact:website") or "",
                "address": f"{tags.get('addr:street', '')} {tags.get('addr:housenumber', '')}".strip(),
                "tags": tags,
                "source_url": f"https://www.openstreetmap.org/node/{n.id}"
            })
            self.stats["node"] += 1

    def way(self, w):
        tags = dict(w.tags)
        if not self.is_dental(tags):
            return

        valid_nodes = [n for n in w.nodes if n.location.valid()]
        if not valid_nodes:
            return

        lat = sum(n.lat for n in valid_nodes) / len(valid_nodes)
        lon = sum(n.lon for n in valid_nodes) / len(valid_nodes)
        name = tags.get("name") or tags.get("operator") or f"Diş Polikliniği #{w.id}"
        prov = determine_province(lat, lon, tags)
        district = tags.get("addr:district") or tags.get("addr:suburb") or ""

        self.elements.append({
            "osm_type": "way",
            "osm_id": w.id,
            "name": name.strip(),
            "city": prov,
            "district": district,
            "lat": lat,
            "lon": lon,
            "phone": tags.get("phone") or tags.get("contact:phone") or "",
            "website": tags.get("website") or tags.get("contact:website") or "",
            "address": f"{tags.get('addr:street', '')} {tags.get('addr:housenumber', '')}".strip(),
            "tags": tags,
            "source_url": f"https://www.openstreetmap.org/way/{w.id}"
        })
        self.stats["way"] += 1

    def relation(self, r):
        tags = dict(r.tags)
        if self.is_dental(tags):
            name = tags.get("name") or tags.get("operator") or f"Diş Sağlığı Merkezi #{r.id}"
            self.elements.append({
                "osm_type": "relation",
                "osm_id": r.id,
                "name": name.strip(),
                "city": tags.get("addr:city") or "İstanbul",
                "district": tags.get("addr:district") or "",
                "lat": 0.0,
                "lon": 0.0,
                "phone": tags.get("phone") or tags.get("contact:phone") or "",
                "website": tags.get("website") or tags.get("contact:website") or "",
                "tags": tags,
                "source_url": f"https://www.openstreetmap.org/relation/{r.id}"
            })
            self.stats["relation"] += 1


def run_extraction():
    if not PBF_FILE.exists():
        print(f"HATA: PBF dosyası bulunamadı ({PBF_FILE}). Lütfen önce download_and_extract_pbf.py çalıştırın.")
        return

    sz = PBF_FILE.stat().st_size
    print(f"PyOsmium ile Türkiye PBF Ayrıştırılıyor: {PBF_FILE} ({sz // (1024*1024)} MB) ...")
    start = time.time()

    handler = DentalPBFHandler()
    handler.apply_file(str(PBF_FILE), locations=True, idx="flex_mem")

    dur = time.time() - start
    print(f"Ayrıştırma tamamlandı! Süre: {dur:.1f} sn.")
    print(f"Bulunan nesneler: Node: {handler.stats['node']}, Way: {handler.stats['way']}, Relation: {handler.stats['relation']}, Toplam: {len(handler.elements)}")

    OUTPUT_JSON.write_text(json.dumps(handler.elements, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Ham kayıtlar diske kaydedildi: {OUTPUT_JSON}")

    # İllere göre dağılım
    from collections import Counter
    c = Counter(el["city"] for el in handler.elements)
    print("\nİllere Göre Dağılım:")
    for city, count in c.most_common(15):
        print(f"  - {city}: {count}")

if __name__ == "__main__":
    run_extraction()

