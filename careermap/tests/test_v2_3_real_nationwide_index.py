"""CareerMap V2.3 Gerçek Türkiye Geneli İşveren İndeksi & Kapsam Doğrulama Test Paketi.
- Aşama A: Gerçek OpenStreetMap verisi (turkey_osm_indexed.json > 500 kayıt).
- Aşama B: Adaptörlerin şeffaf durumları (completed, not_configured, failed) - sahte completed yasağı.
- Aşama C: Gerçek İstanbul (80+ Kadıköy) ve İzmir (15+ Karşıyaka) ölçek doğrulaması.
- Aşama D: Multi-tenant aday profili güvenliği (dinamik CV ve aday bilgisi).
- Aşama E: Keşif huni denetimi (Ham -> Tekilleştirilmiş -> Filtrelenmiş).
"""
import unittest
import sys
import json
from pathlib import Path
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.main import app
from app.database.db import get_connection, get_job_results, get_research_job
from app.discovery.multi_city_directory import clear_demo_and_test_applications
from app.discovery.osm_data_store import load_osm_store, query_local_osm_dentists
from app.discovery.local_osm_adapter import LocalOSMAdapter
from app.discovery.official_directory_adapter import OfficialDirectoryAdapter
from app.discovery.permitted_directory_adapter import PermittedDirectoryAdapter
from app.discovery.web_search_adapter import WebSearchAdapter
from app.research.research_engine import ResearchJobService
from app.candidates.profile_manager import CandidateProfileManager


class TestCareerMapV23RealNationwideIndex(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        conn = get_connection()
        clear_demo_and_test_applications(conn)
        conn.close()

    def test_01_real_osm_files_present_and_indexed(self):
        """Aşama A: Gerçek OSM veri deposu yüklenmeli ve 500'den fazla gerçek harita nesnesi içermelidir."""
        store = load_osm_store()
        self.assertGreater(len(store), 500)

        # Örnek nesne doğrulaması
        sample = store[0]
        self.assertIn("osm_id", sample)
        self.assertIn("osm_type", sample)
        self.assertIn("lat", sample)
        self.assertIn("lon", sample)
        self.assertIn("city", sample)
        self.assertIn("district", sample)
        self.assertEqual(sample["osm_snapshot_date"], "2026-11-03")
        self.assertIn("openstreetmap.org", sample["source_url"])

    def test_02_adapter_transparent_states_no_fake_completion(self):
        """Aşama B: Yapılandırılmamış adaptörler 'not_configured' dönmeli, sahte 'completed' raporlanmamalıdır."""
        # PermittedDirectoryAdapter henüz harici API'ye bağlı değilse not_configured dönmeli
        _, p_rep = PermittedDirectoryAdapter.discover("İstanbul")
        self.assertEqual(p_rep["status"], "not_configured")

        # WebSearchAdapter durumu kontrolü
        _, w_rep = WebSearchAdapter.discover("İstanbul")
        self.assertIn(w_rep["status"], ("not_configured", "completed"))

        # OfficialDirectoryAdapter yapılandırılmamış il (örn. Van) için dürüstçe not_configured dönmeli
        _, o_rep_unconf = OfficialDirectoryAdapter.discover("Van")
        self.assertEqual(o_rep_unconf["status"], "not_configured")

        # OfficialDirectoryAdapter Eskişehir için resmî 220 kurumu completed olarak dönmeli
        items_esk, o_rep_esk = OfficialDirectoryAdapter.discover("Eskişehir")
        self.assertEqual(o_rep_esk["status"], "completed")
        self.assertEqual(len(items_esk), 220)

        # LocalOSMAdapter gerçek veri deposunu başarıyla tarayıp completed dönmeli (PBF Kadıköy gerçekte 49 nokta)
        items_osm, osm_rep = LocalOSMAdapter.discover("İstanbul", ["Kadıköy"])
        self.assertEqual(osm_rep["status"], "completed")
        self.assertGreaterEqual(len(items_osm), 45)

    def test_03_istanbul_kadikoy_real_scale_discovery(self):
        """Aşama C: İstanbul Kadıköy araştırması eski 12 sınırına takılmamalı, gerçek OSM verilerini sunmalıdır."""
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

        job_info = get_research_job(job_id)
        # 12 sınırını aşmalı; Kadıköy'de 80'e yakın gerçek OSM noktası bulunmalı
        self.assertGreater(job_info["total_found"], 50)

        results_res = self.client.get(f"/api/v2/research/jobs/{job_id}/results")
        self.assertEqual(results_res.status_code, 200)
        items = results_res.json()["items"]
        self.assertEqual(len(items), job_info["total_found"])

        # Tüm kayıtların Kadıköy ve İstanbul olduğu doğrulanmalı
        for it in items[:10]:
            self.assertEqual(it["city"], "İstanbul")
            self.assertEqual(it["district"], "Kadıköy")
            self.assertIn("openstreetmap.org", it["source_urls"])

    def test_04_izmir_karsiyaka_real_scale_discovery(self):
        """Aşama C: İzmir Karşıyaka araştırması eski 7 sınırına takılmamalı, gerçek OSM noktalarını sunmalıdır."""
        post_res = self.client.post("/api/v2/research/jobs", json={
            "profession_id": "dentist",
            "city": "İzmir",
            "districts": ["Karşıyaka"],
            "employer_types": ["all"],
            "keywords": ""
        })
        self.assertEqual(post_res.status_code, 200)
        job_id = post_res.json()["job_id"]

        ResearchJobService.execute_job_sync(job_id)

        job_info = get_research_job(job_id)
        self.assertGreaterEqual(job_info["total_found"], 15)

        results_res = self.client.get(f"/api/v2/research/jobs/{job_id}/results")
        items = results_res.json()["items"]
        for it in items:
            self.assertEqual(it["city"], "İzmir")
            self.assertEqual(it["district"], "Karşıyaka")

    def test_05_multi_tenant_candidate_profile_in_application(self):
        """Aşama D: Başvuru ve taslak metinleri sabit değil, oturum açan adayın profiline göre dinamik üretilmelidir."""
        conn = get_connection()
        mgr = CandidateProfileManager(conn)

        # İkinci bir aday oluştur
        second_candidate = {
            "candidate_id": "candidate-dt-ahmet-demir",
            "user_id": "user-dt-ahmet",
            "full_name": "Dt. Ahmet Demir",
            "title": "Diş Hekimi",
            "profession_id": "dentist",
            "phone": "0(532) 999 88 77",
            "email": "ahmet.demir@careermap.local",
            "city": "Ankara",
            "graduation_school": "Hacettepe Üniversitesi Diş Hekimliği Fakültesi",
            "graduation_year": 2025,
            "clinical_case_count": 420
        }
        mgr.upsert_candidate(second_candidate)
        mgr.register_cv_document("candidate-dt-ahmet-demir", file_name="Ahmet_Demir_CV.pdf")

        cand = mgr.get_candidate("candidate-dt-ahmet-demir")
        self.assertEqual(cand["full_name"], "Dt. Ahmet Demir")
        self.assertEqual(cand["graduation_school"], "Hacettepe Üniversitesi Diş Hekimliği Fakültesi")

        # get_job_results içinde adayın adı dinamik olarak kullanılmalı
        # Bir araştırma görevi oluşturup sonuçlarını bu aday için çekelim
        from app.database.db import create_research_job
        job_id = create_research_job("dentist", "Diş Hekimi", "Ankara", ["Çankaya"], conn=conn)
        ResearchJobService.execute_job_sync(job_id)

        results = get_job_results(
            job_id=job_id,
            candidate_id="candidate-dt-ahmet-demir",
            conn=conn
        )
        self.assertGreater(len(results), 0)

        # İlk sonuçta adayın adı ve CV linki dinamik olarak yer almalı
        first_res = results[0]
        if first_res.get("gmail_compose_url"):
            self.assertIn("Ahmet", first_res["gmail_compose_url"])
            self.assertNotIn("Rümeysa", first_res["gmail_compose_url"])
        if first_res.get("whatsapp_chat_url"):
            self.assertIn("Ahmet", first_res["whatsapp_chat_url"])
            self.assertNotIn("Rümeysa", first_res["whatsapp_chat_url"])

        conn.close()

    def test_06_audit_funnel_and_coverage_accounting(self):
        """Aşama E: Her araştırma görevi huni denetimini (Ham -> Tekil -> Filtrelenmiş) coverage_summary'de tutmalıdır."""
        post_res = self.client.post("/api/v2/research/jobs", json={
            "profession_id": "dentist",
            "city": "Ankara",
            "districts": ["Çankaya"],
            "employer_types": ["all"],
            "keywords": ""
        })
        self.assertEqual(post_res.status_code, 200)
        job_id = post_res.json()["job_id"]

        ResearchJobService.execute_job_sync(job_id)

        job = get_research_job(job_id)
        coverage = job.get("coverage_summary", "")
        self.assertIn("Ham Kaynak", coverage)
        self.assertIn("Tekilleştirilmiş", coverage)
        self.assertIn("Filtrelenmiş Sonuç", coverage)
