"""CareerMap V2.0 Akıllı İş Başvuru ve İletişim Yönetim Sistemi Birim Test Paketi.

Test Edilen Yetenekler:
1. CandidateProfileManager: Profil oluşturma, vaka sayısı, güvenli süreli CV bağlantısı tescili.
2. EmployerMatcher: Konum, kapasite, kanal mevcudiyeti ve yetkinlik uyumu ile 0-100 puanlama.
3. ApplicationPlanner: Kanal koordinasyonu, aşamalı takvim, eşzamanlı spam engeli.
4. MessageGenerator: Özelleştirilmiş e-posta, WhatsApp (Model B & C), takip hatırlatması, sıfır halüsinasyon.
5. WhatsAppHandoff: TR numara normalizasyonu (05XX -> 905XX), URL quote, wa.me standardı.
6. ApplicationCRM: 1 işveren = 1 başvuru ilkesi, çoklu kanal denemeleri, olay geçmişi, durum güncellemeleri.
"""
import unittest
import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.database.db import get_connection, init_db
from app.candidates.profile_manager import CandidateProfileManager, get_rumeysa_colak_default_profile
from app.matching.employer_matcher import match_candidate_to_employer
from app.application_engine.application_planner import plan_application_workflow
from app.application_engine.message_generator import generate_application_messages, get_clinic_specific_pitch
from app.channels.whatsapp_handoff import (
    create_whatsapp_link,
    normalize_tr_mobile_for_whatsapp,
    build_whatsapp_application_package
)
from app.tracking.application_crm import ApplicationCRM

class TestCareerMapV2ApplicationEngine(unittest.TestCase):

    def setUp(self):
        # İzole bellek içi test veritabanı
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        init_db(self.conn)
        self.profile_mgr = CandidateProfileManager(self.conn)
        self.crm = ApplicationCRM(self.conn)
        self.candidate = get_rumeysa_colak_default_profile()

    def tearDown(self):
        self.conn.close()

    def test_01_candidate_profile_and_secure_cv_link(self):
        """V2.0 Test 1: Aday profili ve süreli güvenli CV bağlantısı üretimi."""
        cid = self.profile_mgr.upsert_candidate(self.candidate)
        self.assertEqual(cid, "candidate-dt-rumeysa-colak")

        doc = self.profile_mgr.register_cv_document(cid, "Rumeysa_Colak_CV.pdf", validity_days=30)
        self.assertIn("secure_url", doc)
        self.assertTrue(doc["secure_url"].startswith("https://careermap.local/cv/view/"))
        self.assertTrue(len(doc["secure_token"]) >= 16)

        retrieved = self.profile_mgr.get_candidate(cid)
        self.assertEqual(retrieved["full_name"], "Dt. Rümeysa Çolak")
        self.assertEqual(retrieved["clinical_case_count"], 350)
        self.assertIn("Restoratif Diş Tedavisi", retrieved["specialties"])

    def test_02_employer_matching_scoring(self):
        """V2.0 Test 2: Konum, poliklinik türü ve çoklu kanal uyumu üzerinden puanlama."""
        clinic = {
            "employer_id": "emp-test-01",
            "name": "Özel Test Ağız ve Diş Sağlığı Polikliniği",
            "employer_type": "Özel poliklinik",
            "city": "Eskişehir",
            "district": "Tepebaşı",
            "email": "info@testdent.com",
            "whatsapp_url": "https://wa.me/905450000000",
            "contact_form_url": "https://testdent.com/iletisim"
        }
        res = match_candidate_to_employer(self.candidate, clinic)
        self.assertEqual(res["match_score"], 100)
        self.assertEqual(res["primary_channel"], "email")
        self.assertTrue(res["is_recommended"])
        self.assertIn("email", res["planned_channels"])
        self.assertIn("whatsapp", res["planned_channels"])

    def test_03_application_planner_orchestration(self):
        """V2.0 Test 3: Kanalların sıralı koordinasyonu, eşzamanlı gönderim engeli ve takip penceresi."""
        clinic = {
            "employer_id": "emp-test-02",
            "name": "Özel Örnek Dental",
            "email": "iletisim@ornek.com",
            "whatsapp_url": "https://wa.me/905551234567"
        }
        plan = plan_application_workflow(clinic, self.candidate)
        steps = plan["steps"]

        # Adım 1: E-posta olmalı
        self.assertEqual(steps[0]["channel"], "email")
        self.assertEqual(steps[0]["day"], 1)

        # Adım 2: 4-5 gün bekleme penceresi olmalı
        self.assertEqual(steps[1]["action_type"], "wait_and_check")
        self.assertEqual(steps[1]["day"], 4)

        # Adım 3: Yalnızca cevap gelmediyse WhatsApp hatırlatması olmalı
        self.assertEqual(steps[2]["channel"], "whatsapp")
        self.assertEqual(steps[2]["action_type"], "followup_reminder")
        self.assertEqual(steps[2]["day"], 5)

    def test_04_whatsapp_link_generation_and_phone_normalization(self):
        """V2.0 Test 4: TR numara standardizasyonu ve wa.me URL formatı."""
        # 05XX biçiminde numara
        p1 = normalize_tr_mobile_for_whatsapp("0(545) 425 27 19")
        self.assertEqual(p1, "905454252719")

        # 5XX biçiminde numara
        p2 = normalize_tr_mobile_for_whatsapp("536 601 77 26")
        self.assertEqual(p2, "905366017726")

        # wa.me bağlantısı üretimi
        link = create_whatsapp_link("0545 425 27 19", "Merhaba, başvuru yapmak istiyorum.")
        self.assertTrue(link.startswith("https://wa.me/905454252719?text="))
        self.assertIn("Merhaba%2C%20ba%C5%9Fvuru", link)

    def test_05_personalized_message_generator_zero_hallucination(self):
        """V2.0 Test 5: Adayın gerçek verilerine ve doğrulanmış kuruma sadık kişiselleştirilmiş metin üretimi."""
        clinic = {
            "name": "Özel BC Ağız Ve Diş Sağlığı Polikliniği",
            "employer_type": "Özel poliklinik",
            "district": "Tepebaşı",
            "email": "bilgi@bcklinik.com.tr",
            "whatsapp_url": "https://wa.me/905454252719"
        }
        msgs = generate_application_messages(
            employer=clinic,
            candidate=self.candidate,
            secure_cv_url="https://careermap.local/cv/view/test-token",
            cv_file_name="Rumeysa_Colak_CV.pdf"
        )

        email = msgs["email"]
        self.assertIn("Dt. Rümeysa Çolak", email["body"])
        self.assertIn("Süleyman Demirel Üniversitesi Diş Hekimliği Fakültesi", email["body"])
        self.assertIn("350'nin üzerinde klinik vaka", email["body"])
        self.assertIn("restoratif diş tedavisi", email["body"])
        self.assertIn("endodonti (kanal tedavisi)", email["body"])
        self.assertIn("Tepebaşı", email["body"])
        self.assertIn("Ek: Rumeysa_Colak_CV.pdf", email["body"])

        # WhatsApp Model B güvenli bağlantı içermeli
        wa_b = msgs["whatsapp_model_b"]
        self.assertIn("https://careermap.local/cv/view/test-token", wa_b["body"])

        # WhatsApp Followup yalnızca e-posta hatırlatması yapmalı
        wa_followup = msgs["whatsapp_followup"]
        self.assertIn("e-posta yoluyla iletmiştim", wa_followup["body"])

    def test_06_application_crm_lifecycle(self):
        """V2.0 Test 6: CRM tekil başvuru kaydı, durum geçişleri ve olay günlüğü."""
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO employers (
            employer_id, profession_id, city, district, name, employer_type, email, phone, whatsapp_url
        ) VALUES (
            'dentist-test-clinic', 'dentist', 'Eskişehir', 'Tepebaşı', 'Özel Test Kliniği', 'Özel poliklinik', 'info@testclinic.com', '0222 230 00 00', 'https://wa.me/905001234567'
        )
        """)
        self.conn.commit()

        cid = self.profile_mgr.upsert_candidate(self.candidate)
        app_id = self.crm.create_application_record(
            candidate_id=cid,
            employer_id="dentist-test-clinic",
            position_title="Diş Hekimi",
            status="draft"
        )
        self.assertTrue(app_id.startswith("app-"))

        # Onay ver
        self.crm.approve_application(app_id)
        
        # Gönderim kaydet
        att_id = self.crm.record_channel_action(
            application_id=app_id,
            channel="email",
            contact_value="info@testclinic.com",
            action_status="confirmed_by_user",
            notes="CV ekli e-posta gönderildi."
        )
        self.assertTrue(att_id.startswith("att-"))

        # Mülakat daveti geldi
        self.crm.update_application_status(app_id, "interview", "Görüşme daveti alındı.")

        dashboard = self.crm.get_candidate_crm_dashboard(cid)
        metrics = dashboard["metrics"]
        self.assertEqual(metrics["target_employers"], 1)
        self.assertEqual(metrics["interviews"], 1)
        self.assertEqual(len(dashboard["applications"]), 1)
        
        card = dashboard["applications"][0]
        self.assertEqual(card["status"], "interview")
        self.assertEqual(len(card["channel_attempts"]), 1)
        self.assertTrue(len(card["events"]) >= 3)

if __name__ == "__main__":
    unittest.main()
