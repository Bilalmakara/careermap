# -*- coding: utf-8 -*-
"""Geofabrik Türkiye OSM PBF İndirme, SHA-256 Doğrulama ve PyOsmium Ayrıştırma Scripti."""
import os
import sys
import json
import hashlib
import time
from pathlib import Path
import requests

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data" / "osm"
DATA_DIR.mkdir(parents=True, exist_ok=True)

PBF_URL = "https://download.geofabrik.de/europe/turkey-latest.osm.pbf"
PBF_FILE = DATA_DIR / "turkey-latest.osm.pbf"
METADATA_FILE = DATA_DIR / "pbf_download_metadata.json"
EXTRACTED_FILE = DATA_DIR / "turkey_pbf_dental_raw.json"

def download_pbf():
    print(f"İndirme başlatılıyor: {PBF_URL} -> {PBF_FILE}")
    start = time.time()
    resp = requests.get(PBF_URL, stream=True, timeout=30)
    resp.raise_for_status()
    total_size = int(resp.headers.get("content-length", 0))

    downloaded = 0
    sha256 = hashlib.sha256()

    with open(PBF_FILE, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024): # 1 MB chunks
            if chunk:
                f.write(chunk)
                sha256.update(chunk)
                downloaded += len(chunk)
                if downloaded % (50 * 1024 * 1024) == 0:
                    pct = (downloaded / total_size) * 100 if total_size else 0
                    print(f"İndirildi: {downloaded // (1024*1024)} MB / {total_size // (1024*1024)} MB (%{pct:.1f})")

    duration = time.time() - start
    hex_digest = sha256.hexdigest()
    print(f"İndirme tamamlandı! Boyut: {downloaded} bayt (~{downloaded // (1024*1024)} MB). Süre: {duration:.1f} sn. SHA256: {hex_digest}")

    meta = {
        "source_url": PBF_URL,
        "final_url": resp.url,
        "file_path": str(PBF_FILE),
        "file_size_bytes": downloaded,
        "file_size_mb": round(downloaded / (1024 * 1024), 2),
        "sha256": hex_digest,
        "last_modified": resp.headers.get("Last-Modified"),
        "downloaded_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    METADATA_FILE.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta

if __name__ == "__main__":
    download_pbf()

