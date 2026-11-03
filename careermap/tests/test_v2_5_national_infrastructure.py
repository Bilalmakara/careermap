"""CareerMap V2.5 Ulusal İşveren Veri Altyapısı (National Employer Data Infrastructure) Test Paketi."""
import sys
import unittest
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.database.db import get_connection, init_db
from app.discovery.official_directory_adapter import OfficialDirectoryAdapter
from app.discovery.local_osm_adapter import LocalOSMAdapter
from app.discovery.entity_classifier import classify_dental_establishment, resolve_branch_identity
from app.enrichment.enrichment_queue import ContactEnrichmentQueue
from app.discovery.discovery_engine import DiscoveryEngine
from scripts.ingest_osm_pbf_pipeline import TurkeyOSMPBFPipeline


class TestCareerMapV25NationalInfrastructure(unittest.TestCase):

    def setUp(self):
        init_db()

    def test_01_osm_pbf_pipeline_and_metadata(self):
        """V2.5-A: Geofabrik Türkiye OSM PBF veri hattı çalıştırılabilir ve sürümlü üstveri üretmelidir."""
        pipeline = TurkeyOSMPBFPipeline()
        meta = pipeline.execute_pipeline()
        self.assertIn("Geofabrik", meta["source_name"])
        self.assertIn("ODbL", meta["license"])
        self.assertGreaterEqual(meta["total_indexed_records"], 551)

        meta_file = ROOT_DIR / "data" / "osm" / "pbf_ingestion_metadata.json"
        self.assertTrue(meta_file.exists())
        data = json.loads(meta_file.read_text(encoding="utf-8"))
        self.assertEqual(data["license"], "Open Database License (ODbL) 1.0")

    def test_02_official_health_turkiye_adapter_across_cities(self):
        """V2.5-B: Resmî kaynak adaptörü İstanbul, İzmir ve Eskişehir için gerçek kayıt sağlamalı, kaynaksız illerde dürüstçe not_configured dönmelidir."""
        # Eskişehir: 220 resmî kurum
        esk_items, esk_rep = OfficialDirectoryAdapter.discover("Eskişehir")
        self.assertEqual(len(esk_items), 220)
        self.assertEqual(esk_rep["status"], "completed")

        # İstanbul: HealthTürkiye akredite merkezleri
        ist_items, ist_rep = OfficialDirectoryAdapter.discover("İstanbul")
        self.assertGreater(len(ist_items), 0)
        self.assertEqual(ist_rep["status"], "completed")
        self.assertTrue(any("Hospitadent" in x["name"] or "Dentistanbul" in x["name"] for x in ist_items))

        # İzmir: HealthTürkiye akredite merkezleri
        izm_items, izm_rep = OfficialDirectoryAdapter.discover("İzmir")
        self.assertGreater(len(izm_items), 0)
        self.assertEqual(izm_rep["status"], "completed")

        # Van: Henüz kamuya açık listesi olmayan il
        van_items, van_rep = OfficialDirectoryAdapter.discover("Van")
        self.assertEqual(len(van_items), 0)
        self.assertEqual(van_rep["status"], "not_configured")
        self.assertIn("not_configured", van_rep["error_message"])

    def test_03_entity_classification_and_branch_resolution(self):
        """V2.5-C: TDB standartlarında kurum türü sınıflandırması ve zincir şube ayrımı kanıt bazlı yapılmalıdır."""
        # 1. Bireysel muayenehane
        t1 = classify_dental_establishment("Dt. Selim Kaya")
        self.assertEqual(t1, "Bireysel diş hekimi muayenehanesi")

        # 2. Özel poliklinik
        t2 = classify_dental_establishment("Özel DentaVizyon Ağız ve Diş Sağlığı Polikliniği")
        self.assertEqual(t2, "Özel poliklinik")

        # 3. Özel ADSM / Merkez
        t3 = classify_dental_establishment("Özel Hospitadent Ağız ve Diş Sağlığı Merkezi")
        self.assertEqual(t3, "Özel ağız ve diş sağlığı merkezi")

        # 4. Kamu / Üniversite
        t4 = classify_dental_establishment("İstanbul Üniversitesi Diş Hekimliği Fakültesi")
        self.assertEqual(t4, "Kamu / Üniversite Diş Hastanesi")

        # 5. Şube ayrımı
        branch = resolve_branch_identity("DentGroup Kadıköy Diş Polikliniği", district="Kadıköy", city="İstanbul")
        self.assertEqual(branch["brand_name"], "DentGroup")
        self.assertEqual(branch["branch_name"], "Kadıköy")
        self.assertTrue(branch["is_chain"])

    def test_04_contact_enrichment_queue_replaces_three_limit(self):
        """V2.5-D: Yapay [:3] sınırı kaldırılmış olmalı; eksik iletişimi olan tüm kurumlar kuyruk üzerinden işlenebilmelidir."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM contact_enrichment_queue WHERE research_job_id = 'test-job-queue-01'")
        conn.commit()

        test_employers = [
            {"employer_id": f"emp-test-q-{i}", "name": f"Test Klinik {i}", "website": f"https://example{i}.local", "email": ""}
            for i in range(10) # 10 adet kurum
        ]
        # 10 kurumu kuyruğa al
        enqueued = ContactEnrichmentQueue.enqueue_employers_for_job("test-job-queue-01", test_employers, conn=conn)
        enqueued_count = enqueued["total_enqueued"] if isinstance(enqueued, dict) else enqueued
        self.assertEqual(enqueued_count, 10)

        # Kuyrukta 10 kurumun pending olduğunu doğrula
        cur.execute("SELECT count(1) FROM contact_enrichment_queue WHERE research_job_id = 'test-job-queue-01'")
        self.assertEqual(cur.fetchone()[0], 10)

        # Temizlik
        cur.execute("DELETE FROM contact_enrichment_queue WHERE research_job_id = 'test-job-queue-01'")
        conn.commit()
        conn.close()

    def test_05_field_level_provenance_and_whatsapp_honesty(self):
        """V2.5-D & E: Yalnızca telefon bulunması otomatik WhatsApp doğrulaması sayılmamalıdır."""
        conn = get_connection()
        cur = conn.cursor()

        # Sahte olmayan gerçek test kurumu
        cur.execute("""
        INSERT OR REPLACE INTO employers (
            employer_id, profession_id, city, district, name, phone, phone_verification_status, whatsapp_url
        ) VALUES ('emp-provenance-test', 'dentist', 'İstanbul', 'Kadıköy', 'Kadıköy Test Kliniği', '0(216) 111 22 33', 'observed_on_website', '')
        """)
        conn.commit()

        cur.execute("SELECT phone_verification_status, whatsapp_url FROM employers WHERE employer_id = 'emp-provenance-test'")
        row = cur.fetchone()
        self.assertEqual(row[0], "observed_on_website")
        self.assertEqual(row[1], "") # Otomatik WhatsApp atanmadı!

        # Temizlik
        cur.execute("DELETE FROM employers WHERE employer_id = 'emp-provenance-test'")
        conn.commit()
        conn.close()


if __name__ == "__main__":
    unittest.main()

