"""CareerMap V2.1 Arama Odaklı İş Bulma ve Başvuru Platformu Birim & Entegrasyon Test Paketi.

Test Edilen Senaryolar:
1. Meslek Kataloğu & Dinamik Kurum Türleri (/api/v2/research/professions)
2. Dinamik Araştırma Görevi Oluşturma & İlerleme Takibi (POST & GET /api/v2/research/jobs)
3. Desteklenmeyen Meslek / Konum için Sahte Veri Üretmeme İlkesi (Endüstri mühendisi vb.)
4. Araştırma Sonuçları Listeleme, Filtreleme ve Seçim (/api/v2/research/jobs/{id}/results)
5. Çoklu Seçilen Kurumlara Toplu Başvuru Hazırlama (/api/v2/applications/batch-prepare)
6. Başvuru CRM Yaşam Döngüsü & Aşamalar (approved, whatsapp_opened, whatsapp_confirmed_sent, replied, interview)
7. Ankara / Çankaya Senaryosu (Gerçek kaynak adaptörü ile taranabilir arama)
"""
import unittest
import sys
import time
from pathlib import Path
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.main import app
from app.database.db import init_db
from app.research.research_engine import ResearchJobService

class TestCareerMapV21SearchFirstPlatform(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def test_01_professions_and_dynamic_employer_types(self):
        """Kullanıcının mesleğine göre kurum türleri dinamik ayrışıyor mu?"""
        res = self.client.get("/api/v2/research/professions")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")

        prof_ids = [p["id"] for p in data["professions"]]
        self.assertIn("dentist", prof_ids)
        self.assertIn("industrial_engineer", prof_ids)
        self.assertIn("software_engineer", prof_ids)
        self.assertIn("veterinarian", prof_ids)
        self.assertIn("lawyer", prof_ids)

        # Diş hekimi kurum tipleri
        dentist = next(p for p in data["professions"] if p["id"] == "dentist")
        d_type_ids = [et["id"] for et in dentist["employer_types"]]
        self.assertIn("clinic", d_type_ids)
        self.assertIn("office", d_type_ids)

        # Endüstri mühendisi kurum tipleri
        ie = next(p for p in data["professions"] if p["id"] == "industrial_engineer")
        ie_type_ids = [et["id"] for et in ie["employer_types"]]
        self.assertIn("factory", ie_type_ids)
        self.assertIn("logistics", ie_type_ids)

    def test_02_dynamic_research_job_creation_and_execution(self):
        """Kullanıcı araştırma başlattığında görev yürütülüp sonuçlar kademeli toplanıyor mu?"""
        # 1. Eskişehir Diş Hekimi Araştırması Başlat
        post_res = self.client.post("/api/v2/research/jobs", json={
            "profession_id": "dentist",
            "city": "Eskişehir",
            "districts": ["Tepebaşı"],
            "employer_types": ["clinic"],
            "keywords": ""
        })
        self.assertEqual(post_res.status_code, 200)
        job_data = post_res.json()
        self.assertEqual(job_data["status"], "success")
        job_id = job_data["job_id"]

        # 2. Görevin yürütülmesini bekle (senkron veya kısa sleep)
        ResearchJobService.execute_job_sync(job_id)

        # 3. Görev durumunu sorgula
        status_res = self.client.get(f"/api/v2/research/jobs/{job_id}")
        self.assertEqual(status_res.status_code, 200)
        j = status_res.json()["job"]
        self.assertEqual(j["status"], "completed")
        self.assertEqual(j["progress_percent"], 100)
        self.assertGreater(j["total_found"], 0)
        self.assertGreater(j["contacts_found"], 0)

        # 4. Sonuçları çek
        results_res = self.client.get(f"/api/v2/research/jobs/{job_id}/results")
        self.assertEqual(results_res.status_code, 200)
        res_list = results_res.json()["items"]
        self.assertGreater(len(res_list), 0)

        # Tüm sonuçların Tepebaşı olduğunu doğrula
        for r in res_list:
            self.assertEqual(r["district"].lower(), "tepebaşı")
            self.assertIn("poliklinik", r["employer_type"].lower())

    def test_03_zero_hallucination_for_unsupported_profession(self):
        """Henüz adaptörü hazır olmayan mesleklerde sahte veri üretilmiyor, şeffaf bilgi veriliyor mu?"""
        post_res = self.client.post("/api/v2/research/jobs", json={
            "profession_id": "industrial_engineer",
            "city": "Eskişehir",
            "districts": [],
            "employer_types": ["factory"]
        })
        self.assertEqual(post_res.status_code, 200)
        job_id = post_res.json()["job_id"]

        ResearchJobService.execute_job_sync(job_id)

        status_res = self.client.get(f"/api/v2/research/jobs/{job_id}")
        j = status_res.json()["job"]
        self.assertEqual(j["status"], "completed")
        self.assertEqual(j["total_found"], 0)
        self.assertIn("geliştirme aşamasındadır", j["progress_stage"])
        self.assertIn("sahte sonuç üretilmemektedir", j["progress_stage"])

    def test_04_batch_application_preparation_and_crm_lifecycle(self):
        """Kullanıcının seçtiği kurumlara toplu başvuru hazırlanıp CRM'e kaydediliyor mu?"""
        # 1. Örnek bir araştırma çalıştır
        post_res = self.client.post("/api/v2/research/jobs", json={
            "profession_id": "dentist",
            "city": "Eskişehir",
            "districts": ["Odunpazarı"],
            "employer_types": ["all"]
        })
        job_id = post_res.json()["job_id"]
        ResearchJobService.execute_job_sync(job_id)

        # 2. Sonuçlardan 2 klinik seç
        results_res = self.client.get(f"/api/v2/research/jobs/{job_id}/results")
        items = results_res.json()["items"][:2]
        selected_ids = [it["employer_id"] for it in items]
        self.assertEqual(len(selected_ids), 2)

        # 3. Toplu başvuru hazırla
        batch_res = self.client.post("/api/v2/applications/batch-prepare", json={
            "employer_ids": selected_ids,
            "position_title": "Diş Hekimi"
        })
        self.assertEqual(batch_res.status_code, 200)
        batch_data = batch_res.json()
        self.assertEqual(batch_data["prepared_count"], 2)
        self.assertEqual(len(batch_data["packages"]), 2)

        first_pkg = batch_data["packages"][0]
        app_id = first_pkg["application_id"]

        # Taslak metin doğrulaması (Sıfır halüsinasyon: SDÜ ve 350 vaka)
        em_body = first_pkg["messages"]["email"]["body"]
        self.assertIn("Süleyman Demirel Üniversitesi", em_body)
        self.assertIn("vaka", em_body)

        # 4. WhatsApp Sohbeti Açıldı durumuna güncelle
        patch_res = self.client.patch(f"/api/v2/applications/{app_id}/status", json={
            "new_status": "whatsapp_opened",
            "notes": "Aday wa.me bağlantısına tıkladı."
        })
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.json()["new_status"], "whatsapp_opened")

        # 5. WhatsApp Gönderildi olarak onayla
        action_res = self.client.post(f"/api/v2/applications/{app_id}/action", json={
            "channel": "whatsapp",
            "contact_value": "05550000000",
            "action_status": "confirmed_by_user",
            "notes": "Aday WhatsApp mesajını ve güvenli CV linkini gönderdiğini teyit etti."
        })
        self.assertEqual(action_res.status_code, 200)
        self.assertEqual(action_res.json()["application_status"], "waiting_reply")

        # 6. Yanıt Alındı olarak işaretle
        reply_res = self.client.patch(f"/api/v2/applications/{app_id}/status", json={
            "new_status": "replied",
            "notes": "Klinik Direktörü WhatsApp üzerinden geri dönüş yaptı."
        })
        self.assertEqual(reply_res.status_code, 200)
        self.assertEqual(reply_res.json()["new_status"], "replied")

        # 7. Mülakat Daveti olarak güncelle
        int_res = self.client.patch(f"/api/v2/applications/{app_id}/status", json={
            "new_status": "interview",
            "notes": "Perşembe saat 11:00 mülakat randevusu verildi."
        })
        self.assertEqual(int_res.status_code, 200)
        self.assertEqual(int_res.json()["new_status"], "interview")

    def test_05_ankara_cankaya_research_scenario(self):
        """Kullanıcının talimatındaki Diş Hekimi -> Ankara -> Çankaya uçtan uca senaryosu."""
        post_res = self.client.post("/api/v2/research/jobs", json={
            "profession_id": "dentist",
            "city": "Ankara",
            "districts": ["Çankaya"],
            "employer_types": ["clinic", "office"],
            "keywords": ""
        })
        self.assertEqual(post_res.status_code, 200)
        job_id = post_res.json()["job_id"]

        # Görevi yürüt
        ResearchJobService.execute_job_sync(job_id)

        status_res = self.client.get(f"/api/v2/research/jobs/{job_id}")
        self.assertEqual(status_res.status_code, 200)
        j = status_res.json()["job"]
        self.assertIn(j["status"], ("completed", "partial"))
        self.assertEqual(j["city"], "Ankara")
        self.assertIn("Çankaya", j["districts"])

        results_res = self.client.get(f"/api/v2/research/jobs/{job_id}/results")
        self.assertEqual(results_res.status_code, 200)
        results = results_res.json()["items"]
        self.assertGreater(len(results), 0)
        # Tüm sonuçların Ankara ve Çankaya olduğunu doğrula
        for r in results:
            self.assertEqual(r["city"], "Ankara")
            self.assertEqual(r["district"], "Çankaya")

    @classmethod
    def tearDownClass(cls):
        from app.database.db import get_connection
        from app.discovery.multi_city_directory import clear_demo_and_test_applications
        conn = get_connection()
        clear_demo_and_test_applications(conn)
        conn.close()

if __name__ == "__main__":
    unittest.main()

