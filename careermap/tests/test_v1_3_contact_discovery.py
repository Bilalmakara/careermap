"""CareerMap V1.3 İletişim Bilgisi Bulma Motoru Birim ve Entegrasyon Testleri.
- Bireysel hekim ve poliklinik web sitesi aday üretimi.
- İç içe JSON-LD (@graph, ContactPoint) çözme.
- İletişim formu (<form>) tespiti.
- employer_contacts çoklu iletişim tablosu CRUD ve indeksleme.
- TDB token bazlı kesin ad-soyad eşleştirme güvenliği.
- 7 sekmeli Excel raporunda iletişim formları ve çoklu kanallar.
"""
import unittest
import sqlite3
import sys
from pathlib import Path
import openpyxl
from unittest.mock import patch, MagicMock

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.enrichment.website_discovery import generate_domain_candidates, verify_candidate_website
from app.enrichment.email_extractor import extract_contact_from_website, clean_email, classify_email
from app.discovery.tdb_source import match_doctor_names_strictly, parse_doctor_name
from app.database.db import get_connection, upsert_contact, get_employer_contacts, canonical_id, upsert_employer, init_db
from app.exports.excel_exporter import generate_careermap_excel

class TestCareerMapV13ContactDiscovery(unittest.TestCase):

    def test_01_dentist_domain_candidates_not_empty(self):
        """V1.3 Gereksinimi 1: Bireysel diş hekimleri (Dt.) için web sitesi adayları boş dönmemeli."""
        candidates = generate_domain_candidates("Dt. Ahmet KAYA", "Bireysel muayenehane")
        self.assertTrue(len(candidates) > 0, "Bireysel hekim için web sitesi adayları üretilmedi!")
        self.assertTrue(any("dtahmetkaya" in c for c in candidates), "dtahmetkaya adayı eksik!")
        self.assertTrue(any(".com.tr" in c for c in candidates), "com.tr adayı eksik!")

    def test_02_polyclinic_domain_candidates_expanded(self):
        """V1.3 Gereksinimi 2: Poliklinik domain adayları şehir ve ağız-diş varyasyonlarını içermeli."""
        candidates = generate_domain_candidates("Özel Anadolu Ağız ve Diş Sağlığı Polikliniği", "Özel poliklinik")
        self.assertTrue(len(candidates) >= 5, "Poliklinik için yeterli aday üretilmedi!")
        self.assertTrue(any("anadolu" in c for c in candidates), "Temel marka adayı eksik!")

    def test_03_nested_json_ld_and_contact_point(self):
        """V1.3 Gereksinimi 3: İç içe JSON-LD (@graph ve ContactPoint) yapıları başarıyla çözülmeli."""
        sample_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Özel Test Diş Polikliniği Eskişehir</title>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@graph": [
                    {
                        "@type": "Dentist",
                        "name": "Özel Test Diş Polikliniği",
                        "telephone": "0222 230 40 50",
                        "contactPoint": {
                            "@type": "ContactPoint",
                            "telephone": "0222 230 40 51",
                            "email": "kariyer@testdis.com",
                            "contactType": "human resources"
                        }
                    }
                ]
            }
            </script>
        </head>
        <body>
            <p>Eskişehir Tepebaşı kliniğimize hoş geldiniz.</p>
        </body>
        </html>
        """
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "text/html; charset=utf-8"}
        mock_resp.text = sample_html
        mock_resp.url = "https://www.testdis.com"

        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp

        result = extract_contact_from_website("https://www.testdis.com", session=mock_session)
        self.assertEqual(result["email"], "kariyer@testdis.com")
        self.assertEqual(result["email_type"], "career")
        self.assertTrue(any("0(222) 230 40 50" in p["contact_value"] or "0(222) 230 40 51" in p["contact_value"] for p in result["contacts"] if p["contact_type"] == "phone"))

    def test_04_contact_form_detection(self):
        """V1.3 Gereksinimi 4: Sayfa içerisindeki iletişim / randevu formu tespit edilmeli."""
        sample_html = """
        <!DOCTYPE html>
        <html>
        <head><title>İletişim - Özel Klinik</title></head>
        <body>
            <form action="/iletisim-gonder" method="POST">
                <input type="text" name="ad_soyad" placeholder="Adınız Soyadınız">
                <input type="email" name="email" placeholder="E-posta">
                <input type="tel" name="telefon" placeholder="Telefon">
                <textarea name="mesaj"></textarea>
                <button type="submit">Gönder</button>
            </form>
        </body>
        </html>
        """
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "text/html; charset=utf-8"}
        mock_resp.text = sample_html
        mock_resp.url = "https://www.testklinik.com/iletisim"

        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp

        result = extract_contact_from_website("https://www.testklinik.com/iletisim", session=mock_session)
        self.assertTrue(bool(result["contact_form_url"]), "İletişim formu tespit edilemedi!")
        self.assertTrue(any(c["contact_type"] == "contact_form" for c in result["contacts"]), "contact_form tipi contacts listesinde yok!")

    def test_05_employer_contacts_table_crud(self):
        """V1.3 Gereksinimi 5: employer_contacts tablosuna çoklu iletişim bilgileri kaydedilebilmeli (İzole Bellek DB)."""
        conn = get_connection(":memory:")
        init_db(conn)
        cursor = conn.cursor()
        
        test_emp_id = "dentist-eskisehir-test-sample-01"
        
        # Test işvereni ekle
        cursor.execute("""
        INSERT INTO employers (employer_id, profession_id, city, district, name, employer_type)
        VALUES (?, 'dentist', 'Eskişehir', 'Tepebaşı', 'Örnek Test Diş', 'Özel poliklinik')
        """, (test_emp_id,))
        
        # Birden fazla telefon ve e-posta ekle
        upsert_contact(cursor, test_emp_id, "phone", "0(222) 231 11 11", "corporate", "https://site.com", "osm", "verified")
        upsert_contact(cursor, test_emp_id, "phone", "0(222) 231 22 22", "corporate", "https://site.com/contact", "website_scrape", "verified")
        upsert_contact(cursor, test_emp_id, "email", "ik@site.com", "career", "https://site.com/kariyer", "website_scrape", "verified")
        upsert_contact(cursor, test_emp_id, "email", "info@site.com", "general", "https://site.com", "website_scrape", "verified")
        upsert_contact(cursor, test_emp_id, "contact_form", "https://site.com/iletisim", "contact_form", "https://site.com/iletisim", "website_scrape", "verified")
        
        conn.commit()

        contacts = get_employer_contacts(test_emp_id, conn=conn)
        self.assertEqual(len(contacts), 5, "5 adet iletişim kaydı listelenemedi!")
        phone_vals = [c["contact_value"] for c in contacts if c["contact_type"] == "phone"]
        self.assertIn("0(222) 231 11 11", phone_vals)
        self.assertIn("0(222) 231 22 22", phone_vals)
        
        conn.close()

    def test_06_tdb_token_strict_matching_security(self):
        """V1.3 Gereksinimi 6: TDB ad-soyad kontrolü alt-dize hatalarını kesinlikle engellemeli."""
        # Doğru kesin eşleşmeler
        self.assertTrue(match_doctor_names_strictly("Ahmet", "KAYA", "Ahmet", "KAYA"))
        self.assertTrue(match_doctor_names_strictly("Mehmet Ali", "ÖZTÜRK", "Mehmet Ali", "ÖZTÜRK"))

        # Farklı ad veya alt-dize eşleşmeleri ASLA kabul edilmemeli!
        self.assertFalse(match_doctor_names_strictly("Ali", "KAYA", "Mehmet Ali", "KAYA"), "Tek isim 'Ali' ile çift isim 'Mehmet Ali' eşleşmemeli!")
        self.assertFalse(match_doctor_names_strictly("Ali", "KAYA", "Alime", "KAYA"), "'Ali' adı 'Alime' ile yanlış eşleşti!")
        self.assertFalse(match_doctor_names_strictly("Can", "YILDIRIM", "Candan", "YILDIRIM"), "'Can' adı 'Candan' ile yanlış eşleşti!")
        self.assertFalse(match_doctor_names_strictly("Ece", "DEMİR", "Ecem", "DEMİR"), "'Ece' adı 'Ecem' ile yanlış eşleşti!")
        self.assertFalse(match_doctor_names_strictly("Ahmet", "KAYA", "Ahmet", "KAYALI"), "Farklı soyadı yanlış eşleşti!")

    def test_07_excel_v1_3_contact_form_column(self):
        """V1.3 Gereksinimi 7: Excel çıktısında İletişim Formu sütunu ve 7 sekme eksiksiz bulunmalı."""
        test_records = [{
            "name": "Özel Test Diş Polikliniği",
            "employer_type": "Özel poliklinik",
            "district": "Tepebaşı",
            "address": "İki Eylül Cd. No:10 Eskişehir",
            "phone": "0(222) 230 40 50",
            "phone_type": "corporate",
            "phone_source_url": "https://test.com",
            "phone_verification_status": "verified",
            "email": "info@test.com",
            "email_type": "general",
            "email_source_url": "https://test.com/iletisim",
            "email_verification_status": "verified",
            "website": "https://test.com",
            "website_source_url": "https://test.com",
            "website_verification_status": "verified",
            "career_url": "https://test.com/kariyer",
            "contact_form_url": "https://test.com/bize-ulasin",
            "source_type": "Eskişehir İl Sağlık Müdürlüğü",
            "source_last_checked": "2026-11-02",
            "contact_last_verified": "2026-11-02",
            "research_status": "completed"
        }]

        excel_buf = generate_careermap_excel(test_records, "Diş Hekimi", "Eskişehir")
        wb = openpyxl.load_workbook(excel_buf)
        
        self.assertEqual(len(wb.sheetnames), 7, "7 sekme bulunamadı!")
        ws_all = wb["Tüm İşverenler"]
        headers = [ws_all.cell(row=1, column=col).value for col in range(1, ws_all.max_column + 1)]
        self.assertIn("İletişim Formu", headers, "İletişim Formu sütunu Tüm İşverenler sayfasında yok!")
        
        # Satır verisi kontrolü
        row_vals = [ws_all.cell(row=2, column=col).value for col in range(1, ws_all.max_column + 1)]
        self.assertIn("https://test.com/bize-ulasin", row_vals, "İletişim formu linki Excel hücresine yazılmadı!")

if __name__ == "__main__":
    unittest.main()
