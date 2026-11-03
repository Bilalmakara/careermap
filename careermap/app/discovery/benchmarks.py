"""CareerMap V2.4 Türkiye 30 Büyükşehir Resmî ve Sektörel Karşılaştırma Tabanı (Market Benchmarks).
- TDB 2025 resmî istatistikleri (23.685 özel kuruluş).
- Emsalo Ekim 2026 30 büyükşehir dizin verileri (14.996 kuruluş).
- İl Sağlık Müdürlükleri ve TBMM/AFAD tutanaklarına dayalı kesin referanslar.
- Üç katmanlı sayım modeli:
    1. Resmî referans sayısı (official_reference)
    2. Keşfedilmiş benzersiz kurum sayısı (discovered_count)
    3. Başvuruya uygun kurum sayısı (application_ready_count)
- Kapsama oranı (coverage_ratio) hesaplayıcı.
"""
import json
import logging
import unicodedata
import re
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("careermap.discovery.benchmarks")

BENCHMARK_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "benchmarks" / "turkey_30_metropolitan_benchmarks.json"

_CACHED_BENCHMARKS: Optional[Dict[str, Any]] = None


def normalize_tr_text(text: str) -> str:
    """Türkçe karakterleri ve boşlukları karşılaştırma standardına getirir."""
    if not text:
        return ""
    s = str(text).replace("I", "ı").replace("İ", "i").lower()
    s = s.translate(str.maketrans("çğıöşü", "cgiosu"))
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return " ".join(s.split())


def load_benchmarks() -> Dict[str, Any]:
    """30 büyükşehir pazar referans verisini yükler."""
    global _CACHED_BENCHMARKS
    if _CACHED_BENCHMARKS is not None:
        return _CACHED_BENCHMARKS

    if not BENCHMARK_FILE.exists():
        logger.warning(f"Benchmark dosyası bulunamadı: {BENCHMARK_FILE}")
        return {"metadata": {}, "provinces": {}}

    try:
        data = json.loads(BENCHMARK_FILE.read_text(encoding="utf-8"))
        _CACHED_BENCHMARKS = data
        return _CACHED_BENCHMARKS
    except Exception as e:
        logger.error(f"Benchmark verisi okunamadı: {e}")
        return {"metadata": {}, "provinces": {}}


def get_city_benchmark(city: str) -> Optional[Dict[str, Any]]:
    """Belirli bir il için pazar referans ve karşılaştırma verilerini döner."""
    data = load_benchmarks()
    provinces = data.get("provinces", {})

    target_norm = normalize_tr_text(city)
    for prov_name, prov_data in provinces.items():
        if normalize_tr_text(prov_name) == target_norm:
            return prov_data

    return None


def calculate_coverage_metrics(
    city: str,
    discovered_count: int,
    application_ready_count: int = 0
) -> Dict[str, Any]:
    """
    Kullanıcının belirlediği 3 katmanlı sayım modeline göre kapsama metriklerini hesaplar:
    1. Resmî referans sayısı
    2. Keşfedilmiş benzersiz kurum sayısı
    3. Başvuruya uygun kurum sayısı
    """
    bench = get_city_benchmark(city)
    if not bench:
        return {
            "city": city,
            "has_benchmark": False,
            "official_reference_count": None,
            "discovered_count": discovered_count,
            "application_ready_count": application_ready_count,
            "coverage_ratio_percent": None,
            "coverage_level": "Bilinmiyor (Büyükşehir Dışı)",
            "benchmark_source": None
        }

    ref_count = bench.get("official_reference_count") or bench.get("emsalo_record_count") or 1
    coverage_ratio = round((discovered_count / ref_count) * 100, 1)

    if coverage_ratio >= 80:
        level = "Çok Yüksek (Tam Envanter)"
    elif coverage_ratio >= 40:
        level = "Geniş Kapsam"
    elif coverage_ratio >= 15:
        level = "Orta Kapsam"
    else:
        level = "Başlangıç / Kısmi Keşif (Genişletilmeli)"

    return {
        "city": bench.get("city", city),
        "has_benchmark": True,
        "official_reference_count": ref_count,
        "discovered_count": discovered_count,
        "application_ready_count": application_ready_count,
        "coverage_ratio_percent": coverage_ratio,
        "coverage_level": level,
        "official_breakdown": bench.get("official_breakdown"),
        "benchmark_source": bench.get("official_reference_source") or bench.get("official_reference_source")
    }

