"""CareerMap V2.4 Türkiye 30 Büyükşehir Pazar Karşılaştırma Tabanı (Market Benchmarks) Test Paketi."""
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.discovery.benchmarks import (
    load_benchmarks,
    get_city_benchmark,
    calculate_coverage_metrics,
    normalize_tr_text
)
from app.discovery.discovery_engine import DiscoveryEngine
from app.database.db import get_connection


class TestCareerMapV24MarketBenchmarks(unittest.TestCase):

    def test_01_thirty_metropolitan_benchmark_file_complete(self):
        """30 büyükşehrin tamamı benchmark veri setinde yer almalı ve toplam 14.996 kaydı doğrulamalıdır."""
        data = load_benchmarks()
        self.assertEqual(data["metadata"]["metropolitan_count"], 30)
        self.assertEqual(data["metadata"]["emsalo_30_metro_total"], 14996)

        provinces = data["provinces"]
        self.assertEqual(len(provinces), 30)

        # 30 ilin toplamını doğrula
        total_emsalo = sum(p.get("emsalo_record_count", 0) for p in provinces.values())
        self.assertEqual(total_emsalo, 14996)

    def test_02_national_tdb_category_breakdown(self):
        """TDB 2025 resmî envanterindeki 23.685 kuruluş ve 4 temel kategori doğrulanmalıdır."""
        data = load_benchmarks()
        meta = data["metadata"]
        self.assertEqual(meta["national_tdb_2025_total"], 23685)

        cats = meta["national_tdb_2025_categories"]
        self.assertEqual(cats["muayenehane"], 14458)
        self.assertEqual(cats["poliklinik"], 7178)
        self.assertEqual(cats["musterek_muayenehane"], 1728)
        self.assertEqual(cats["adsm_merkez"], 321)
        self.assertEqual(sum(cats.values()), 23685)

    def test_03_three_tier_accounting_metrics(self):
        """Üç katmanlı sayım modeli (Resmî referans, Keşfedilen, Başvuruya uygun) ve kapsama oranı hesaplanmalıdır."""
        # Eskişehir: 220 keşfedilen / 233 referans = %94.4
        esk = calculate_coverage_metrics("Eskişehir", discovered_count=220, application_ready_count=220)
        self.assertTrue(esk["has_benchmark"])
        self.assertEqual(esk["official_reference_count"], 233)
        self.assertEqual(esk["discovered_count"], 220)
        self.assertEqual(esk["application_ready_count"], 220)
        self.assertEqual(esk["coverage_ratio_percent"], 94.4)
        self.assertIn("Çok Yüksek", esk["coverage_level"])

        # İstanbul: 403 keşfedilen / 4633 resmî referans = %8.7
        ist = calculate_coverage_metrics("İstanbul", discovered_count=403, application_ready_count=350)
        self.assertEqual(ist["official_reference_count"], 4633)
        self.assertEqual(ist["discovered_count"], 403)
        self.assertEqual(ist["application_ready_count"], 350)
        self.assertEqual(ist["coverage_ratio_percent"], 8.7)
        self.assertIn("Genişletilmeli", ist["coverage_level"])

    def test_04_discovery_engine_includes_coverage_metrics(self):
        """DiscoveryEngine tarama sonucunda audit_funnel ve coverage_metrics metriklerini eksiksiz üretmelidir."""
        conn = get_connection()
        summary = DiscoveryEngine.discover_employers(
            profession_id="dentist",
            city="Eskişehir",
            districts=[],
            conn=conn
        )
        self.assertIn("coverage_metrics", summary)
        metrics = summary["coverage_metrics"]
        self.assertTrue(metrics["has_benchmark"])
        self.assertEqual(metrics["official_reference_count"], 233)
        self.assertGreaterEqual(metrics["discovered_count"], 220)
        self.assertGreaterEqual(metrics["coverage_ratio_percent"], 94.0)
        conn.close()

    def test_05_turkish_normalization_in_benchmark_lookup(self):
        """Türkçe karakterli veya karaktersiz il sorguları aynı referans kaydını getirmelidir."""
        b1 = get_city_benchmark("İstanbul")
        b2 = get_city_benchmark("Istanbul")
        self.assertIsNotNone(b1)
        self.assertEqual(b1, b2)

        b3 = get_city_benchmark("İzmir")
        b4 = get_city_benchmark("Izmir")
        self.assertIsNotNone(b3)
        self.assertEqual(b3, b4)


if __name__ == "__main__":
    unittest.main()
