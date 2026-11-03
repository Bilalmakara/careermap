# -*- coding: utf-8 -*-
"""CareerMap V2.3 Canlı OpenStreetMap Veri İndirme ve Ayrıştırma Scripti.
- Türkiye'nin büyük metropolleri için gerçek OpenStreetMap (amenity=dentist, healthcare=dentist) noktalarını çeker.
- Her kayıt gerçek OSM ID (node/way), koordinatlar, il, ilçe ve etiketleriyle 'careermap/data/osm/' dizininde saklanır.
"""
import os
import json
import time
from pathlib import Path
import requests

DATA_DIR = Path("careermap/data/osm")
DATA_DIR.mkdir(parents=True, exist_ok=True)

CITIES = {
    "İstanbul": {
        "bbox": (40.80, 28.50, 41.35, 29.80),
        "filename": "osm_istanbul_raw.json"
    },
    "İzmir": {
        "bbox": (38.15, 26.80, 38.65, 27.40),
        "filename": "osm_izmir_raw.json"
    },
    "Ankara": {
        "bbox": (39.70, 32.50, 40.10, 33.10),
        "filename": "osm_ankara_raw.json"
    },
    "Bursa": {
        "bbox": (40.10, 28.80, 40.35, 29.30),
        "filename": "osm_bursa_raw.json"
    },
    "Antalya": {
        "bbox": (36.75, 30.50, 37.00, 30.90),
        "filename": "osm_antalya_raw.json"
    }
}

ENDPOINTS = [
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter"
]

def fetch_city_osm(city_name: str, cfg: dict):
    target_path = DATA_DIR / cfg["filename"]
    bb = cfg["bbox"]
    query = f"""[out:json][timeout:35];
(
  node["amenity"="dentist"]({bb[0]}, {bb[1]}, {bb[2]}, {bb[3]});
  way["amenity"="dentist"]({bb[0]}, {bb[1]}, {bb[2]}, {bb[3]});
  node["healthcare"="dentist"]({bb[0]}, {bb[1]}, {bb[2]}, {bb[3]});
  way["healthcare"="dentist"]({bb[0]}, {bb[1]}, {bb[2]}, {bb[3]});
);
out center tags;
"""
    headers = {"User-Agent": "CareerMap/2.3 (OSM Ingest; Respectful; info@careermap.local)"}

    for ep in ENDPOINTS:
        try:
            print(f"[{city_name}] Sorgulanıyor: {ep} ...")
            resp = requests.post(ep, data={"data": query}, headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                elements = data.get("elements", [])
                if elements:
                    target_path.write_text(json.dumps(elements, ensure_ascii=False, indent=2), encoding="utf-8")
                    print(f"[{city_name}] BAŞARILI: {len(elements)} gerçek OSM nesnesi {target_path} dosyasına kaydedildi.")
                    return len(elements)
                else:
                    print(f"[{city_name}] Sunucu 200 döndü ancak kayıt sayısı 0.")
            else:
                print(f"[{city_name}] HTTP {resp.status_code} on {ep}")
        except Exception as e:
            print(f"[{city_name}] Hata ({ep}): {e}")
        time.sleep(1)

    print(f"[{city_name}] Tüm aynalar başarısız oldu.")
    return 0

if __name__ == "__main__":
    total_elements = 0
    for city, cfg in CITIES.items():
        count = fetch_city_osm(city, cfg)
        total_elements += count
        time.sleep(2)
    print(f"\n--- İŞLEM TAMAMLANDI: Toplam {total_elements} gerçek OSM harita nesnesi indirildi. ---")

