"""CareerMap V2.2 Kapsamlı Keşif Motoru ve Veri Güvenliği Test Paketi.
- P0: Sentetik kayıtların engellenmesi, karantina politikası ve güvenli olmayan kurumlara başvuru yasağı.
- P1 & P2: Gerçek OSM indeksi, koordinatlı işletme noktaları ve nesne kimlikleri.
- P7: 220 Eskişehir kaydının eksiksiz korunması.
- P8: İstanbul ve İzmir gerçek araştırma senaryoları; sabit liste limitlerinin olmaması.
"""
import unittest
import sys
from pathlib import Path
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.main import app
from app.database.db import get_connection
from app.discovery.multi_city_directory import generate_synthetic_province_clinics, clear_demo_and_test_applications
from app.discovery.quarantine_manager import execute_v2_2_quarantine, is_employer_allowed_for_application
from app.discovery.discovery_engine import DiscoveryEngine
from app.research.research_engine import ResearchJobService


class TestCareerMapV22DiscoveryIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        conn = get_connection()
        execute_v2_2_quarantine(conn)
        conn.close()

    @classmethod
    def tearDownClass(cls):
        conn = get_connection()
        clear_demo_and_test_applications(conn)
        conn.close()

    def test_01_synthetic_generator_disabled_in_production(self):
        """P0: Üretim keşfinde sentetik veya uydurma kurum kesinlikle üretilmemelidir."""
        res_konya = generate_synthetic_province_clinics("Konya")
        self.assertEqual(res_konya, [])
        res_trabzon = generate_synthetic_province_clinics("Trabzon")
        self.assertEqual(res_trabzon, [])

    def test_02_quarantine_policy_and_application_blocking(self):
        """P0: Karantinadaki kurumlara başvuru hazırlanması ve mesaj gönderimi engellenmelidir."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT employer_id, name, research_status FROM employers WHERE research_status = 'quarantined' LIMIT 1")
        row = cursor.fetchone()
        conn.close()

        if row:
            quarantined_emp_id = row[0]
            # Başvuru hazırlama isteği at
            resp = self.client.post(f"/api/v2/applications/prepare/{quarantined_emp_id}")
            self.assertEqual(resp.status_code, 400)
            self.assertIn("karantinaya alınmıştır", resp.json()["detail"])

            # Toplu başvuru hazırlamada atlanmalı
            batch_resp = self.client.post("/api/v2/applications/batch-prepare", json={
                "employer_ids": [quarantined_emp_id],
                "position_title": "Diş Hekimi"
            })
            self.assertEqual(batch_resp.status_code, 200)
            self.assertEqual(batch_resp.json()["prepared_count"], 0)

    def test_03_eskisehir_records_integrity_preserved(self):
        """P7: 220 kanonik Eskişehir resmî kaydı korunmalı, karantinaya alınmamalı ve yeni gerçek kayıtlar silinmemelidir."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT count(1) FROM employers WHERE city = 'Eskişehir' AND source_type LIKE '%Sağlık Müdürlüğü%'")
        official_eski = cursor.fetchone()[0]
        self.assertEqual(official_eski, 220)

        cursor.execute("SELECT count(1) FROM employers WHERE city = 'Eskişehir'")
        total_eski = cursor.fetchone()[0]
        self.assertGreaterEqual(total_eski, 220)

        cursor.execute("SELECT count(1) FROM employers WHERE city = 'Eskişehir' AND research_status = 'quarantined'")
        quarantined_eski = cursor.fetchone()[0]
        self.assertEqual(quarantined_eski, 0)
        conn.close()

    def test_04_istanbul_kadikoy_real_osm_discovery(self):
        """P1 & P2: İstanbul Kadıköy için gerçek OSM nesne kimlikleri ve koordinatları keşfedilmelidir."""
        post_res = self.client.post("/api/v2/research/jobs", json={
            "profession_id": "dentist",
            "city": "İstanbul",
            "districts": ["Kadıköy"],
            "employer_types": ["all"],
            "keywords": ""
        })
        self.assertEqual(post_res.status_code, 200)
        job_id = post_res.json()["job_id"]

        ResearchJobService.execute_job_sync(job_id)

        # Sonuçları incele
        results_res = self.client.get(f"/api/v2/research/jobs/{job_id}/results")
        self.assertEqual(results_res.status_code, 200)
        data = results_res.json()
        self.assertGreater(data["total"], 0)

        first_item = data["items"][0]
        self.assertEqual(first_item["city"], "İstanbul")
        self.assertEqual(first_item["district"], "Kadıköy")
        # Gerçek OSM kaynak URL'si
        self.assertIn("openstreetmap.org", first_item["source_urls"])
        self.assertTrue(first_item["can_apply"])

    def test_05_izmir_konak_real_osm_discovery(self):
        """P1 & P2: İzmir Konak için gerçek işletme noktaları bulunmalıdır."""
        post_res = self.client.post("/api/v2/research/jobs", json={
            "profession_id": "dentist",
            "city": "İzmir",
            "districts": ["Konak"],
            "employer_types": ["all"],
            "keywords": ""
        })
        self.assertEqual(post_res.status_code, 200)
        job_id = post_res.json()["job_id"]

        ResearchJobService.execute_job_sync(job_id)

        results_res = self.client.get(f"/api/v2/research/jobs/{job_id}/results")
        self.assertEqual(results_res.status_code, 200)
        data = results_res.json()
        self.assertGreater(data["total"], 0)
        for it in data["items"]:
            self.assertEqual(it["city"], "İzmir")
            self.assertEqual(it["district"], "Konak")

    def test_06_multi_branch_preservation(self):
        """P2 & P7: Aynı markanın farklı şubeleri (Kadıköy, Nişantaşı, Nilüfer) tekilleştirmede kaybolmamalıdır."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT employer_id, name, district, city FROM employers WHERE name LIKE '%DentGroup%'")
        dg_branches = cursor.fetchall()
        conn.close()

        # En az 3 farklı DentGroup şubesi bağımsız saklanmalı
        self.assertGreaterEqual(len(dg_branches), 3)
        districts_seen = set(row[2] for row in dg_branches)
        self.assertGreaterEqual(len(districts_seen), 3)

    def test_07_evidence_and_run_tables_logged(self):
        """P5: Keşif koşuları ve ham kaynak kayıtları ilgili tablolara yazılmalıdır."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT count(1) FROM discovery_runs")
        run_count = cursor.fetchone()[0]
        self.assertGreater(run_count, 0)

        cursor.execute("SELECT count(1) FROM employer_source_records")
        evidence_count = cursor.fetchone()[0]
        self.assertGreater(evidence_count, 0)
        conn.close()
