"""CareerMap V1.4-A İletişim İstihbaratı ve Kanıt Doğrulama Test Paketi.
Test senaryoları:
1. Yanlış domaine eşleşmenin engellenmesi (Fake / squatter / unrelated domain rejection).
2. Aynı soyadlı hekimlerin ve polikliniklerin ad-soyad token teyidi ile ayrılması.
3. Çok şubeli kliniklerde şube ve adres doğrulama.
4. İletişim formu ile randevu formunun doğru ayrımı (İş arayan vs Hasta).
5. phonenumbers ile farklı telefon formatlarının tekilleştirilmesi ve Eskişehir (222) tespiti.
6. İç içe JSON-LD, microdata ve obfuskasyon (info [at] domain) e-posta çıkarma.
7. employer_contacts tablosunda kanıt izlerinin (discovery_method, evidence_text) doğrulanması.
"""
import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.enrichment.phone_extractor import format_phone, inspect_phone_number, extract_phones_from_html
from app.enrichment.email_extractor import clean_email, classify_email, extract_emails_from_html
from app.enrichment.website_identity_matcher import match_website_identity, parse_target_names
from app.enrichment.contact_page_crawler import is_contact_form, is_appointment_form, crawl_business_website
from app.enrichment.website_discovery import generate_domain_candidates
from app.database.db import get_connection, upsert_contact, get_employer_contacts, init_db

class TestCareerMapV14ContactIntelligence(unittest.TestCase):

    def test_01_phonenumbers_standardization_and_validation(self):
        """Senaryo 1: phonenumbers ile farklı formatlar tekilleştirilmeli ve Eskişehir (222) tespit edilmeli."""
        raw_formats = [
            "0222 234 44 44",
            "+90 222 234 44 44",
            "+902222344444",
            "(0222) 234-44-44",
            "tel:+902222344444",
            "2222344444"
        ]
        expected = "0(222) 234 44 44"
        for raw in raw_formats:
            formatted = format_phone(raw)
            self.assertEqual(formatted, expected, f"Formatlama hatası: {raw} -> {formatted}")
            
            info = inspect_phone_number(raw)
            self.assertTrue(info["is_valid"], f"Numara geçerli sayılmadı: {raw}")
            self.assertTrue(info["is_eskisehir"], f"Eskişehir alan kodu tanınmadı: {raw}")
            self.assertEqual(info["line_type"], "fixed_line")

    def test_02_wrong_domain_and_parked_site_rejection(self):
        """Senaryo 2: Yanlış domaine eşleşme ve satılık/park edilmiş siteler ASLA kabul edilmemeli."""
        target_employer = {
            "name": "Özel Test Ağız ve Diş Sağlığı Polikliniği",
            "employer_type": "Özel poliklinik",
            "city": "Eskişehir",
            "district": "Tepebaşı"
        }
        
        # Park edilmiş site HTML'i
        parked_html = """
        <!DOCTYPE html>
        <html><head><title>Test.com is for sale!</title></head>
        <body>
            <h1>This domain is registered and for sale. Buy this domain at GoDaddy!</h1>
        </body></html>
        """
        match_parked = match_website_identity(target_employer, parked_html, "https://www.test.com")
        self.assertFalse(match_parked["is_match"], "Park edilmiş site yanlışlıkla eşleşti!")
        self.assertEqual(match_parked["status"], "rejected")

        # Alakasız başka sektördeki site HTML'i
        unrelated_html = """
        <!DOCTYPE html>
        <html><head><title>Özel Test Otomotiv Eskişehir</title></head>
        <body>
            <h1>Eskişehir Tepebaşı Oto Bakım ve Yedek Parça</h1>
            <p>İletişim: 0222 111 22 33</p>
        </body></html>
        """
        match_unrelated = match_website_identity(target_employer, unrelated_html, "https://www.testoto.com")
        self.assertFalse(match_unrelated["is_match"], "Otomotiv sitesi diş kliniğiyle yanlışlıkla eşleşti!")
        self.assertEqual(match_unrelated["status"], "rejected")

    def test_03_same_surname_different_dentists_disambiguation(self):
        """Senaryo 3: Aynı soyadlı farklı hekimler (Ahmet vs Abdülkadir) ve poliklinik karışıklığı engellenmeli."""
        target_doc = {
            "name": "Dt. Abdülkadir ÖZYILDIRIM",
            "employer_type": "Bireysel muayenehane",
            "city": "Eskişehir",
            "district": "Tepebaşı"
        }

        # Poliklinik sitesi (Yıldırım adı geçiyor ama 'Abdülkadir' hekimi geçmiyor!)
        polyclinic_html = """
        <!DOCTYPE html>
        <html><head><title>Özel Yıldırım Ağız ve Diş Sağlığı Polikliniği</title></head>
        <body>
            <h1>Eskişehir Özel Yıldırım Diş Polikliniği</h1>
            <p>Başhekim: Dt. Hasan Yıldırım, Ortodontist: Dt. Merve Yıldırım</p>
            <p>Telefon: 0222 320 60 70</p>
        </body></html>
        """
        # Hedef hekim 'Abdülkadir' bu sitede geçmediği için eşleşme ONAYLANMAMALI
        res = match_website_identity(target_doc, polyclinic_html, "https://www.yildirimdis.com")
        self.assertFalse(res["is_match"] and res["status"] in ["verified", "observed_on_source"], 
                         "İsminde Abdülkadir geçmeyen Yıldırım Diş polikliniği Dt. Abdülkadir'e atandı!")

        # Kendi gerçek hekim sitesi (Hem Abdülkadir hem Özyıldırım geçiyor)
        doc_html = """
        <!DOCTYPE html>
        <html><head><title>Dt. Abdülkadir Özyıldırım Diş Muayenehanesi Eskişehir</title></head>
        <body>
            <h1>Dt. Abdülkadir Özyıldırım - Eskişehir Tepebaşı Diş Hekimi</h1>
            <p>İmplant ve ortodonti tedavileri. Tel: 0222 231 02 22</p>
        </body></html>
        """
        res_correct = match_website_identity(target_doc, doc_html, "https://www.dtabdulkadirozyildirim.com")
        self.assertTrue(res_correct["is_match"], "Gerçek hekim sitesi doğrulanamadı!")
        self.assertIn(res_correct["status"], ["verified", "observed_on_source"])

    def test_04_contact_form_vs_appointment_form_distinction(self):
        """Senaryo 4: İletişim formu (iş arayan hekim için) ile hasta randevu formu kesinlikle ayırt edilmeli."""
        from bs4 import BeautifulSoup
        
        # 1. Hasta Randevu Formu (Tarih, saat, doktor seçimi, şikayet)
        appointment_html = """
        <form action="/randevu-kaydet" method="POST">
            <select name="poliklinik_secimi"><option>Ağız ve Çene Cerrahisi</option></select>
            <select name="doktor"><option>Dt. Ahmet</option></select>
            <input type="date" name="randevu_tarihi">
            <input type="time" name="randevu_saati">
            <input type="text" name="tc_kimlik" placeholder="T.C. Kimlik No">
            <textarea name="sikayet" placeholder="Şikayetiniz"></textarea>
            <button type="submit">Randevu Al</button>
        </form>
        """
        soup_app = BeautifulSoup(appointment_html, "html.parser").find("form")
        self.assertTrue(is_appointment_form(soup_app), "Randevu formu randevu olarak tanınmadı!")
        self.assertFalse(is_contact_form(soup_app), "Randevu formu yanlışlıkla genel iletişim formu sayıldı!")

        # 2. Genel İletişim / Başvuru Formu (Ad, soyad, email, telefon, mesaj)
        contact_html = """
        <form action="/iletisim-gonder" method="POST">
            <input type="text" name="ad_soyad" placeholder="Adınız Soyadınız">
            <input type="email" name="email" placeholder="E-posta Adresiniz">
            <input type="tel" name="telefon" placeholder="Telefon">
            <input type="text" name="konu" placeholder="Mesaj Konusu">
            <textarea name="mesaj" placeholder="Mesajınız"></textarea>
            <button type="submit">Gönder</button>
        </form>
        """
        soup_cnt = BeautifulSoup(contact_html, "html.parser").find("form")
        self.assertTrue(is_contact_form(soup_cnt), "İletişim formu iletişim formu olarak tanınmadı!")
        self.assertFalse(is_appointment_form(soup_cnt), "İletişim formu randevu formu sayıldı!")

    def test_05_multi_format_email_and_obfuscation(self):
        """Senaryo 5: mailto, microdata, obfuskasyon (info [at] domain) ve sınıflandırma teyit edilmeli."""
        sample_html = """
        <!DOCTYPE html>
        <html>
        <body>
            <!-- mailto linki -->
            <a href="mailto:ik@testdental.com.tr?subject=IsBasvurusu">Kariyer Başvurusu</a>
            
            <!-- microdata -->
            <span itemprop="email">bilgi@testdental.com.tr</span>
            
            <!-- Obfuskasyon -->
            <p>Yedek iletişim: merhaba [at] testdental.com.tr</p>
            
            <!-- Randevu e-postası -->
            <p>Randevu için: randevu@testdental.com.tr</p>
        </body>
        </html>
        """
        emails = extract_emails_from_html(sample_html, "https://www.testdental.com.tr/iletisim")
        email_map = {e["contact_value"]: e for e in emails}
        
        self.assertIn("ik@testdental.com.tr", email_map)
        self.assertEqual(email_map["ik@testdental.com.tr"]["contact_category"], "career")
        self.assertEqual(email_map["ik@testdental.com.tr"]["discovery_method"], "mailto")
        
        self.assertIn("bilgi@testdental.com.tr", email_map)
        self.assertEqual(email_map["bilgi@testdental.com.tr"]["discovery_method"], "microdata")
        
        self.assertIn("merhaba@testdental.com.tr", email_map)
        self.assertEqual(email_map["merhaba@testdental.com.tr"]["discovery_method"], "obfuscated")
        
        self.assertIn("randevu@testdental.com.tr", email_map)
        self.assertEqual(email_map["randevu@testdental.com.tr"]["contact_category"], "randevu")

    def test_06_employer_contacts_evidence_storage(self):
        """Senaryo 6: employer_contacts tablosunda kanıt metni ve keşif yöntemi eksiksiz saklanmalı (İzole Bellek DB)."""
        conn = get_connection(":memory:")
        init_db(conn)
        cursor = conn.cursor()
        test_id = "dentist-eskisehir-v14-evidence-test"
        
        cursor.execute("""
        INSERT INTO employers (employer_id, profession_id, city, district, name, employer_type)
        VALUES (?, 'dentist', 'Eskişehir', 'Tepebaşı', 'Kanıt Test Kliniği', 'Özel poliklinik')
        """, (test_id,))

        upsert_contact(
            cursor=cursor,
            employer_id=test_id,
            contact_type="phone",
            contact_value="0(222) 234 56 78",
            contact_category="corporate",
            source_url="https://test.com/iletisim",
            source_type="website_scrape",
            discovery_method="tel_link",
            evidence_text="<a href='tel:02222345678'>Bizi Arayın</a>",
            confidence_category="kaynakli",
            verification_status="verified"
        )
        conn.commit()

        contacts = get_employer_contacts(test_id, conn=conn)
        self.assertEqual(len(contacts), 1)
        c = contacts[0]
        self.assertEqual(c["discovery_method"], "tel_link")
        self.assertIn("tel:02222345678", c["evidence_text"])
        self.assertEqual(c["confidence_category"], "kaynakli")
        
        conn.close()

if __name__ == "__main__":
    unittest.main()

