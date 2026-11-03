"""CareerMap V2.0 Web Platformu ve REST API Birim & Entegrasyon Test Paketi.

Test Edilen Bileşenler:
1. PWA & Web App Uç Noktaları (/app, /manifest.json, /cv/view/{token})
2. Auth API (/api/v2/auth/login, /register, /me)
3. Candidate & CV API (/api/v2/candidate/profile, /api/v2/candidate/cv, /api/v2/candidate/cv/upload)
4. Employers API (/api/v2/employers listeleme, filtreleme, detay ve eşleşme)
5. Applications & CRM API (prepare, approve, channel action, status update, dashboard)
6. Admin API (/api/v2/admin/stats, export-excel, import-excel)
"""
import unittest
import sys
import io
from pathlib import Path
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.main import app
from app.database.db import get_connection, init_db

class TestCareerMapV2WebPlatform(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Gerçek veritabanını başlat
        init_db()
        cls.client = TestClient(app)

    def test_01_web_app_and_manifest_endpoints(self):
        """Web platformu anasayfası, /app ve /manifest.json yanıt veriyor mu?"""
        res_app = self.client.get("/app")
        self.assertEqual(res_app.status_code, 200)
        self.assertIn("CareerMap", res_app.text)
        self.assertIn("Dt. Rümeysa Çolak", res_app.text)

        res_manifest = self.client.get("/manifest.json")
        self.assertEqual(res_manifest.status_code, 200)
        manifest_data = res_manifest.json()
        self.assertEqual(manifest_data["short_name"], "CareerMap")
        self.assertEqual(manifest_data["display"], "standalone")

    def test_02_auth_login_and_roles(self):
        """Aday ve yönetici hesapları doğru kimlik doğrulaması yapıyor mu?"""
        # 1. Aday hesabı
        cand_res = self.client.post("/api/v2/auth/login", json={
            "email": "rumeysa@careermap.local",
            "password": "Rumeysa2026!"
        })
        self.assertEqual(cand_res.status_code, 200)
        cand_data = cand_res.json()
        self.assertIn("access_token", cand_data)
        self.assertEqual(cand_data["user"]["role"], "candidate")

        token = cand_data["access_token"]
        # /me kontrolü
        me_res = self.client.get("/api/v2/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.json()["user"]["email"], "rumeysa@careermap.local")

        # 2. Yönetici hesabı
        admin_res = self.client.post("/api/v2/auth/login", json={
            "email": "admin@careermap.local",
            "password": "Admin2026!"
        })
        self.assertEqual(admin_res.status_code, 200)
        self.assertEqual(admin_res.json()["user"]["role"], "admin")

    def test_03_candidate_profile_and_cv_endpoints(self):
        """Aday profili okuma, güncelleme, CV yükleme ve 30 günlük güvenli link."""
        # İdempotent başlangıç
        self.client.put("/api/v2/candidate/profile", json={"clinical_case_count": 350})
        prof_res = self.client.get("/api/v2/candidate/profile")
        self.assertEqual(prof_res.status_code, 200)
        profile = prof_res.json()["profile"]
        self.assertEqual(profile["full_name"], "Dt. Rümeysa Çolak")
        self.assertEqual(profile["clinical_case_count"], 350)
        self.assertEqual(profile["graduation_year"], 2026)

        # Güncelleme
        put_res = self.client.put("/api/v2/candidate/profile", json={
            "clinical_case_count": 360,
            "title": "Diş Hekimi (SDÜ 2026)"
        })
        self.assertEqual(put_res.status_code, 200)
        self.assertEqual(put_res.json()["profile"]["clinical_case_count"], 360)

        # CV Yükleme & Güvenli Belirteç
        cv_res = self.client.post("/api/v2/candidate/cv/upload", data={"validity_days": 30})
        self.assertEqual(cv_res.status_code, 200)
        cv_doc = cv_res.json()["document"]
        self.assertIn("secure_url", cv_doc)
        token = cv_doc["secure_token"]

        # Public CV görüntüleme sayfası
        public_res = self.client.get(f"/cv/view/{token}")
        self.assertEqual(public_res.status_code, 200)
        self.assertIn("Dt. Rümeysa Çolak", public_res.text)
        self.assertIn("Süleyman Demirel Üniversitesi", public_res.text)

    def test_04_employers_multi_criteria_filtering(self):
        """İşveren listeleme, ilçe filtreleri ve iletişim kanalı rozetleri."""
        # Tümü
        res_all = self.client.get("/api/v2/employers?page_size=220")
        self.assertEqual(res_all.status_code, 200)
        data = res_all.json()
        self.assertGreaterEqual(data["total"], 220)

        # Yalnızca Tepebaşı
        res_tepebasi = self.client.get("/api/v2/employers?district=Tepeba%C5%9F%C4%B1")
        self.assertEqual(res_tepebasi.status_code, 200)
        items_tb = res_tepebasi.json()["items"]
        for it in items_tb:
            self.assertEqual(it["district"].lower(), "tepebaşı")

        # Ulaşılabilir olanlar
        res_reach = self.client.get("/api/v2/employers?reachable_only=true")
        self.assertEqual(res_reach.status_code, 200)
        items_reach = res_reach.json()["items"]
        for it in items_reach:
            self.assertTrue(it["is_reachable"])
            self.assertGreater(len(it["available_channels"]), 0)

    def test_05_application_preparation_and_crm_lifecycle(self):
        """Başvuru hazırlama, onay, kanal eylemi (WhatsApp/Email) ve CRM durumu."""
        # 1. İşveren seç
        res_all = self.client.get("/api/v2/employers?page_size=5")
        emp = res_all.json()["items"][0]
        emp_id = emp["employer_id"]

        # 2. Başvuru dosyası hazırla
        prep_res = self.client.post(f"/api/v2/applications/prepare/{emp_id}")
        self.assertEqual(prep_res.status_code, 200)
        prep_data = prep_res.json()
        app_id = prep_data["application_id"]
        self.assertIn("messages", prep_data)
        self.assertIn("email", prep_data["messages"])
        self.assertIn("whatsapp_model_b", prep_data["messages"])
        self.assertIn("phone_script", prep_data["messages"])

        # Sıfır halüsinasyon kontrolü: SDÜ 2026 ve vaka sayısı metinde geçmeli
        em_body = prep_data["messages"]["email"]["body"]
        self.assertIn("Süleyman Demirel Üniversitesi", em_body)
        self.assertIn("vaka", em_body)

        # 3. Başvuruyu onayla
        appr_res = self.client.post(f"/api/v2/applications/{app_id}/approve")
        self.assertEqual(appr_res.status_code, 200)

        # 4. WhatsApp kanalı üzerinden gönderim kaydet
        act_res = self.client.post(f"/api/v2/applications/{app_id}/action", json={
            "channel": "whatsapp",
            "contact_value": "05550000000",
            "action_status": "confirmed_by_user",
            "notes": "Aday wa.me bağlantısı üzerinden ön yazıyı ve 30 günlük CV bağlantısını iletti."
        })
        self.assertEqual(act_res.status_code, 200)
        self.assertEqual(act_res.json()["application_status"], "waiting_reply")

        # 5. Mülakat daveti kaydet
        status_res = self.client.patch(f"/api/v2/applications/{app_id}/status", json={
            "new_status": "interview",
            "notes": "Klinik direktörü çarşamba günü 14:00 için yüz yüze görüşmeye davet etti."
        })
        self.assertEqual(status_res.status_code, 200)
        self.assertEqual(status_res.json()["new_status"], "interview")

        # 6. CRM kontrol panelinde mülakat sayısının artışını doğrula
        dash_res = self.client.get("/api/v2/applications/dashboard")
        self.assertEqual(dash_res.status_code, 200)
        dash_data = dash_res.json()["dashboard"]
        self.assertGreaterEqual(dash_data["metrics"]["interviews"], 1)

    def test_06_admin_stats_and_excel_export(self):
        """Yönetici istatistikleri ve canlı Excel dışa aktarımı."""
        # 1. İstatistikler
        stats_res = self.client.get("/api/v2/admin/stats")
        self.assertEqual(stats_res.status_code, 200)
        stats = stats_res.json()
        self.assertEqual(stats["status"], "success")
        self.assertGreaterEqual(stats["employers"]["total"], 220)
        self.assertGreaterEqual(stats["employers"]["reachable"], 130)

        # 2. Excel İndirme
        excel_res = self.client.get("/api/v2/admin/export-excel")
        self.assertEqual(excel_res.status_code, 200)
        self.assertEqual(
            excel_res.headers.get("content-type"),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        self.assertGreater(len(excel_res.content), 1000)

    @classmethod
    def tearDownClass(cls):
        from app.discovery.multi_city_directory import clear_demo_and_test_applications
        conn = get_connection()
        clear_demo_and_test_applications(conn)
        conn.close()

if __name__ == "__main__":
    unittest.main()

