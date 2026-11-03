"""CareerMap V1.1 Kapsamlı Kalite ve Güvenilirlik Otomatik Testleri (8 Senaryo)."""
import unittest
import sys
from pathlib import Path

# Paket kök dizinini Python yoluna ekle
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.professions.dentist import DentistProfession
from app.professions.base import turkish_lower
from app.matching.deduplicator import is_same_employer, merge_two_records, deduplicate_records
from app.matching.confidence import assess_records_quality
from app.discovery.osm_source import fetch_osm_records
from app.enrichment.website_finder import match_verified_polyclinic

class TestCareerMapV11Quality(unittest.TestCase):
    def setUp(self):
        self.prof = DentistProfession()

    def test_01_same_employer_different_spellings(self):
        """Senaryo 1: Aynı işletmenin farklı yazılışları başarıyla birleştirilmeli."""
        rec_a = {
            "name": "Özel Dorlion Dent Ağız ve Diş Sağlığı Polikliniği",
            "district": "Odunpazarı",
            "address": "Atatürk Bulvarı No:10 Odunpazarı",
            "phone": "0222 234 44 44"
        }
        rec_b = {
            "name": "Dorlion Dent Diş Polikliniği",
            "district": "Odunpazarı",
            "address": "Atatürk Bulv. No:10",
            "phone": ""
        }
        self.assertTrue(is_same_employer(rec_a, rec_b, self.prof), "Farklı yazılan aynı klinik birleştirilemedi!")

    def test_02_same_brand_different_branches_preserved(self):
        """Senaryo 2: Aynı markanın farklı şubeleri ASLA birleştirilmemeli, bağımsız korunmalı."""
        branch_camlica = {
            "name": "Özel Modapol Ağız ve Diş Sağlığı Polikliniği Çamlıca Şubesi",
            "district": "Tepebaşı",
            "address": "Çamlıca Mah. Tepebaşı",
            "phone": "0222 111 00 01"
        }
        branch_emek = {
            "name": "Özel Modapol Emek Ağız ve Diş Sağlığı Polikliniği",
            "district": "Odunpazarı",
            "address": "Emek Mah. Odunpazarı",
            "phone": "0222 111 00 02"
        }
        self.assertFalse(is_same_employer(branch_camlica, branch_emek, self.prof), "Farklı şubeler yanlışlıkla birleştirildi!")

    def test_03_same_surname_different_dentists_preserved(self):
        """Senaryo 3: Aynı soyadını taşıyan farklı hekimler ASLA birleştirilmemeli ve poliklinikle karışmamalı."""
        doc_a = {
            "name": "Dt. Abdülkadir ÖZYILDIRIM",
            "employer_type": "Bireysel muayenehane",
            "district": "Tepebaşı",
            "phone": "0222 231 02 22"
        }
        doc_b = {
            "name": "Dt. Ahmet ÖZYILDIRIM",
            "employer_type": "Bireysel muayenehane",
            "district": "Tepebaşı",
            "phone": ""
        }
        polyclinic = {
            "name": "Özel Yıldırım Ağız ve Diş Sağlığı Polikliniği",
            "employer_type": "Özel poliklinik",
            "district": "Tepebaşı",
            "phone": "0222 320 60 70"
        }
        # Farklı hekimler birleştirilmemeli
        self.assertFalse(is_same_employer(doc_a, doc_b, self.prof), "Aynı soyadlı farklı hekimler yanlışlıkla birleştirildi!")
        # Hekim ile benzer isimli poliklinik birleştirilmemeli
        self.assertFalse(is_same_employer(doc_a, polyclinic, self.prof), "Hekim muayenehanesi poliklinikle birleştirildi!")
        # Hekime poliklinik sitesi atanmamalı
        self.assertIsNone(match_verified_polyclinic(doc_a["name"], doc_a["employer_type"]), "Hekime poliklinik sitesi atandı!")

    def test_04_conflicting_phones_flagged_as_conflict(self):
        """Senaryo 4: Farklı kaynaklardan gelen çelişkili telefonlar 'conflict' durumuna alınmalı."""
        base_rec = {
            "name": "Örnek Test Kliniği",
            "district": "Tepebaşı",
            "phone": "0(222) 230 11 11",
            "phone_source_url": "https://source-a.com"
        }
        incoming_rec = {
            "name": "Örnek Test Kliniği",
            "district": "Tepebaşı",
            "phone": "0(222) 555 99 99",
            "phone_source_url": "https://source-b.com"
        }
        merged = merge_two_records(base_rec, incoming_rec)
        self.assertEqual(merged.get("verification_status"), "conflict", "Çelişkili telefonlar conflict olarak işaretlenmedi!")

    def test_05_failed_overpass_connection_handling(self):
        """Senaryo 5: Overpass bağlantısı çöktüğünde sistem hata raporlamalı, sessizce başarılı saymamalı."""
        recs, report = fetch_osm_records(self.prof, "Eskişehir")
        self.assertIn("status", report)
        self.assertIn("failed_attempts", report)
        if report["status"] == "failed":
            self.assertEqual(len(recs), 0)
            self.assertTrue(len(report["failed_attempts"]) > 0, "Başarısız Overpass denemeleri loglanmadı!")

    def test_06_clinic_without_website_handled_safely(self):
        """Senaryo 6: Web sitesi bulunamayan klinik güvenle işlenmeli, tahminî site atanmamalı."""
        res = match_verified_polyclinic("Özel Bilinmeyen Yeni Diş Kliniği", "Özel poliklinik")
        self.assertIsNone(res, "Bilinmeyen kliniğe tahminî/yanlış site atandı!")

    def test_07_unverified_email_not_marked_as_verified(self):
        """Senaryo 7: E-posta kaynağı veya kanıtı yoksa kayıt ASLA verified yapılmamalı."""
        test_records = [{
            "name": "Test Muayenehane",
            "employer_type": "Bireysel muayenehane",
            "email": "test@unverified.com",
            "email_source_url": "",  # Kaynak yok!
            "verification_method": "unverified"
        }]
        assessed = assess_records_quality(test_records, self.prof)
        self.assertNotEqual(assessed[0]["verification_status"], "verified", "Kaynaksız e-posta verified olarak işaretlendi!")

    def test_08_turkish_character_and_district_matching(self):
        """Senaryo 8: Türkçe İ/ı, Ş/ş büyük-küçük harf dönüşümleri ve ilçe eşleşmeleri kusursuz çalışmalı."""
        raw_upper_district = "TEPEBAŞI"
        detected = self.prof.detect_district(raw_upper_district, "Eskişehir")
        self.assertEqual(detected, "Tepebaşı", f"Büyük harf TEPEBAŞI Tepebaşı olarak eşleşmedi: {detected}")
        
        odunpazari = self.prof.detect_district("ODUNPAZARI", "Eskişehir")
        self.assertEqual(odunpazari, "Odunpazarı", f"Büyük harf ODUNPAZARI eşleşmedi: {odunpazari}")

if __name__ == "__main__":
    unittest.main()

