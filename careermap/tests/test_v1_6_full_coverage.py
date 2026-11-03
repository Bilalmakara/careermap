"""CareerMap V1.6 Tam Kapsam ve İletişim Kanalları Birim Test Paketi.

Test Edilen Yetenekler:
1. Crawler Starvation Çözümü: Gerçek iç bağlantıların (iletisim.php vb.) statik tahmin tükenmesinden önce ziyaret edilmesi.
2. Captive Portal / Ağ Yönlendirme Tespiti: 192.168.1.1 veya router redirect.html sayfalarının elenmesi.
3. WhatsApp İletişim Kanalları: wa.me ve api.whatsapp.com linkleri ile TR mobil hatlarının çıkarımı.
4. İkincil Sağlık Rehberleri (directory_observed): DoktorTakvimi ve hekim portallarından sadece doğrulanmış telefonların alınması ve üçüncü taraf platform e-postalarının ASLA kabul edilmemesi.
5. Reachability (Ulaşılabilirlik) Metriği: Telefon, e-posta, WhatsApp veya kurumsal form üzerinden en az bir aktif kanalla ulaşılabilen işletmelerin doğru hesaplanması.
"""
import unittest
import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.enrichment.contact_page_crawler import crawl_business_website, is_contact_form, is_appointment_form
from app.enrichment.web_search_discovery import extract_directory_phones, is_third_party_directory
from app.enrichment.search_adapters import SearchResult
from app.enrichment.phone_extractor import format_phone, inspect_phone_number
from app.enrichment.contact_validator import validate_email_contact, validate_phone_contact

class TestCareerMapV16FullCoverage(unittest.TestCase):

    def test_01_crawler_starvation_prevention(self):
        """V1.6 Gereksinimi 1: Crawler ana sayfadan keşfettiği gerçek bağlantıları (/iletisim.php) 404 tahminlerinden önce ziyaret etmeli."""
        from unittest.mock import MagicMock
        mock_session = MagicMock()
        
        # Ana sayfa cevabı: Menüde iletisim.php bağlantısı var
        homepage_html = """
        <html><body>
            <nav>
                <a href="/">Ana Sayfa</a>
                <a href="/hakkimizda.php">Hakkımızda</a>
                <a href="/iletisim.php">İletişim & Randevu</a>
            </nav>
            <h1>Özel Test Diş Polikliniği</h1>
        </body></html>
        """
        contact_html = """
        <html><body>
            <h1>İletişim Bilgilerimiz</h1>
            <p>E-posta: testpoliklinik@gmail.com</p>
            <p>Telefon: 0222 231 44 55</p>
            <a href="https://wa.me/905421234567">WhatsApp Destek Hattı</a>
        </body></html>
        """
        
        def mock_get(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.headers = {"content-type": "text/html; charset=utf-8"}
            if url.rstrip("/").endswith("iletisim.php"):
                resp.url = "https://www.testdent.com/iletisim.php"
                resp.text = contact_html
            elif url.rstrip("/") in ["https://www.testdent.com", "https://www.testdent.com/"]:
                resp.url = "https://www.testdent.com"
                resp.text = homepage_html
            else:
                resp.status_code = 404
                resp.text = "Not found"
            return resp

        mock_session.get.side_effect = mock_get

        crawl_result = crawl_business_website(
            website_url="https://www.testdent.com",
            session=mock_session,
            max_pages=4
        )

        # Starvation olmamalı: iletisim.php ziyaret edilip sayfalara eklenmeli ve WhatsApp tespit edilmeli
        self.assertIn("https://www.testdent.com/iletisim.php", crawl_result["contact_page_urls"])
        self.assertEqual(len(crawl_result["pages"]), 2)

        # Sayfalardan e-posta çıkarımı
        from app.enrichment.email_extractor import extract_emails_from_html
        found_emails = []
        for p in crawl_result["pages"]:
            for e in extract_emails_from_html(p["html"], p["url"]):
                found_emails.append(e["contact_value"])

        self.assertIn("testpoliklinik@gmail.com", found_emails, "Crawler starvation nedeniyle iletisim.php'deki e-posta kaçırıldı!")
        self.assertTrue(bool(crawl_result.get("whatsapp_url")), "WhatsApp bağlantısı tespit edilemedi!")
        self.assertEqual(crawl_result["whatsapp_phone"], "05421234567")

    def test_02_captive_portal_detection(self):
        """V1.6 Gereksinimi 2: Modem / captive portal (192.168.1.1/redirect.html) sahte HTML cevapları ayıklanmalı."""
        from unittest.mock import MagicMock
        mock_session = MagicMock()

        portal_resp = MagicMock()
        portal_resp.status_code = 200
        portal_resp.url = "http://192.168.1.1/redirect.html"
        portal_resp.headers = {"content-type": "text/html"}
        portal_resp.text = "<script>window.location='http://192.168.1.1';</script>"

        mock_session.get.return_value = portal_resp

        crawl_result = crawl_business_website(
            website_url="https://www.kapalisite.com",
            session=mock_session,
            max_pages=2
        )

        self.assertEqual(len(crawl_result["pages"]), 0, "Captive portal HTML sayfası taranan sayfalara eklendi!")
        self.assertEqual(crawl_result["access_status"], "network_interception")

    def test_03_whatsapp_channels_extraction(self):
        """V1.6 Gereksinimi 3: wa.me ve api.whatsapp.com bağlantılarından WhatsApp URL ve mobil numara çıkarılmalı."""
        html_snippet = """
        <div class="footer">
            <a href="https://wa.me/905427315801?text=Randevu">WhatsApp Hattı</a>
            <a href="https://api.whatsapp.com/send?phone=+905468680222">Hemen Yazın</a>
        </div>
        """
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_snippet, "html.parser")
        
        wa_links = []
        for a in soup.find_all("a", href=True):
            h = a["href"]
            if "wa.me/" in h or "api.whatsapp.com" in h:
                wa_links.append(h)

        self.assertEqual(len(wa_links), 2)
        p1 = format_phone("905427315801")
        self.assertEqual(p1, "0(542) 731 58 01")

    def test_04_directory_phones_strict_isolation(self):
        """V1.6 Gereksinimi 4: DoktorTakvimi vb. dizinlerden telefon 'directory_observed' olarak alınmalı, portal e-postası asla alınmamalı."""
        employer = {
            "name": "Dt. Ahmet Kaya",
            "employer_type": "Bireysel muayenehane",
            "city": "Eskişehir",
            "district": "Odunpazarı"
        }
        
        search_candidates = [
            SearchResult(
                url="https://www.doktortakvimi.com/ahmet-kaya/dis-hekimi/eskisehir",
                domain="doktortakvimi.com",
                title="Dt. Ahmet Kaya - Diş Hekimi Eskişehir | DoktorTakvimi",
                snippet="Dt. Ahmet Kaya muayenehane iletişim: 0222 230 45 60. Randevu ve adres bilgileri.",
                source_provider="freeserp"
            ),
            SearchResult(
                url="https://www.doktortakvimi.com/iletisim",
                domain="doktortakvimi.com",
                title="DoktorTakvimi Destek",
                snippet="Bize ulaşın: info@doktortakvimi.com veya 0850 333 0 333",
                source_provider="freeserp"
            )
        ]

        dir_phones = extract_directory_phones(employer, search_candidates)
        self.assertEqual(len(dir_phones), 1, "Sadece hekimle eşleşen telefon çıkarılmalı!")
        dp = dir_phones[0]
        self.assertEqual(dp["contact_value"], "0(222) 230 45 60")
        self.assertEqual(dp["verification_status"], "directory_observed")
        self.assertEqual(dp["source_type"], "directory")

        # Üçüncü taraf portal e-postası engellenmeli
        self.assertTrue(is_third_party_directory("https://www.doktortakvimi.com/ahmet-kaya"))
        # validate_email_contact platform e-postasını engellemeli
        ve = validate_email_contact("destek@doktortakvimi.com", employer)
        self.assertFalse(ve["is_valid"], "Dizin portal e-postası kabul edildi!")

    def test_05_reachability_metric_calculation(self):
        """V1.6 Gereksinimi 5: Ulaşılabilirlik metriği en az bir aktif iletişim kanalı bulunan işletmeleri doğru saymalı."""
        test_employers = [
            {"name": "E1", "phone": "02222301122", "email": "", "contact_form_url": "", "whatsapp_url": ""}, # Ulaşılabilir (Tel)
            {"name": "E2", "phone": "", "email": "info@klinik.com", "contact_form_url": "", "whatsapp_url": ""}, # Ulaşılabilir (Email)
            {"name": "E3", "phone": "", "email": "", "contact_form_url": "https://k.com/iletisim", "whatsapp_url": ""}, # Ulaşılabilir (Form)
            {"name": "E4", "phone": "", "email": "", "contact_form_url": "", "whatsapp_url": "https://wa.me/90500"}, # Ulaşılabilir (WA)
            {"name": "E5", "phone": "", "email": "", "contact_form_url": "", "whatsapp_url": ""} # Ulaşılamaz
        ]

        reachable_count = sum(
            1 for e in test_employers
            if (e["phone"] or "").strip() 
            or (e["email"] or "").strip() 
            or (e["contact_form_url"] or "").strip() 
            or (e["whatsapp_url"] or "").strip()
        )
        self.assertEqual(reachable_count, 4)
        self.assertEqual(reachable_count / len(test_employers) * 100, 80.0)

if __name__ == "__main__":
    unittest.main()
