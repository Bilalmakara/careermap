"""CareerMap V1.2 Çok Kaynaklı İletişim Keşif Motoru Kapsamlı Test Paketi (12 Senaryo)."""
import unittest
import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.professions.dentist import DentistProfession
from app.professions.base import turkish_lower
from app.matching.deduplicator import is_same_employer, merge_two_records
from app.matching.confidence import assess_records_quality
from app.discovery.osm_source import fetch_osm_records
from app.discovery.tdb_source import normalize_tr_text, parse_doctor_name
from app.enrichment.website_discovery import generate_domain_candidates
from app.enrichment.email_extractor import classify_email, clean_email
from app.database.db import canonical_id, get_connection

class TestCareerMapV12Comprehensive(unittest.TestCase):
    def setUp(self):
        self.prof = DentistProfession()

    def test_01_same_person_different_spellings(self):
        """Senaryo 1: Aynı kişinin/işletmenin farklı yazılışları tekilleştirilmeli."""
        rec_a = {"name": "Özel Dorlion Dent Ağız ve Diş Sağlığı Polikliniği", "district": "Odunpazarı", "address": "Atatürk Bulvarı"}
        rec_b = {"name": "Dorlion Dent Diş Polikliniği", "district": "Odunpazarı", "address": "Atatürk Bulv."}
        self.assertTrue(is_same_employer(rec_a, rec_b, self.prof))

    def test_02_same_name_different_dentists(self):
        """Senaryo 2: Aynı soyadlı veya ada sahip farklı hekimler birleştirilmemeli."""
        doc_a = {"name": "Dt. Abdülkadir ÖZYILDIRIM", "employer_type": "Bireysel muayenehane", "district": "Tepebaşı"}
        doc_b = {"name": "Dt. Ahmet ÖZYILDIRIM", "employer_type": "Bireysel muayenehane", "district": "Tepebaşı"}
        self.assertFalse(is_same_employer(doc_a, doc_b, self.prof))

    def test_03_same_brand_different_branches_preserved(self):
        """Senaryo 3: Aynı markanın farklı şubeleri bağımsız işletme olarak korunmalı."""
        branch_camlica = {"name": "Özel Modapol Ağız ve Diş Sağlığı Polikliniği Çamlıca Şubesi", "district": "Tepebaşı"}
        branch_emek = {"name": "Özel Modapol Emek Ağız ve Diş Sağlığı Polikliniği", "district": "Odunpazarı"}
        self.assertFalse(is_same_employer(branch_camlica, branch_emek, self.prof))
        
        # Deterministik ID'leri de farklı olmalı
        id_camlica = canonical_id(branch_camlica["name"], "Tepebaşı", "Özel poliklinik")
        id_emek = canonical_id(branch_emek["name"], "Odunpazarı", "Özel poliklinik")
        self.assertNotEqual(id_camlica, id_emek)

    def test_04_tdb_strict_name_matching(self):
        """Senaryo 4: TDB'de yalnızca soyadı içerme kabul edilmemeli, tam ad-soyad normalizasyonu yapılmalı."""
        raw = "Dt. Mehmet Ali KAYA"
        ad, soyad = parse_doctor_name(raw)
        self.assertEqual(ad, "Mehmet Ali")
        self.assertEqual(soyad, "KAYA")
        self.assertEqual(normalize_tr_text("ÖZYILDIRIM"), "ozyildirim")
        self.assertEqual(normalize_tr_text("İPEK"), "ipek")

    def test_05_clinic_without_website(self):
        """Senaryo 5: Web sitesi aramasında muayenehane hekimine poliklinik domaini üretilmemeli, hekime özel alan adı üretilmeli."""
        cands = generate_domain_candidates("Dt. Ali Veli", "Bireysel muayenehane")
        self.assertTrue(len(cands) > 0, "V1.3 gereği hekime özel alan adı adayları üretilmeli!")
        self.assertFalse(any("poliklinik" in c for c in cands), "Hekime poliklinik domaini üretilmemeli!")
        self.assertTrue(any("dtaliveli" in c for c in cands), "Hekim unvanlı domain adayı bulunamadı!")

    def test_06_website_without_email(self):
        """Senaryo 6: Web sitesi olan ama e-postası olmayan klinik için sahte e-posta üretilmemeli."""
        rec = [{"name": "Örnek Klinik", "website": "https://ornek.com", "website_source_url": "https://ornek.com", "email": ""}]
        assessed = assess_records_quality(rec, self.prof)
        self.assertEqual(assessed[0]["email"], "")
        self.assertEqual(assessed[0]["email_verification_status"], "unverified")

    def test_07_multiple_emails_career_priority(self):
        """Senaryo 7: Kariyer e-postası (ik@ / kariyer@) genel e-postaya (info@) tercih edilmeli."""
        self.assertEqual(classify_email("ik@klinik.com"), "career")
        self.assertEqual(classify_email("info@klinik.com"), "general")
        self.assertIn(classify_email("randevu@klinik.com"), ["other", "randevu"])

    def test_08_conflicting_phones(self):
        """Senaryo 8: İki kaynaktan gelen çelişkili telefonlar 'conflict' olarak işaretlenmeli."""
        base = {"name": "Test Kliniği", "phone": "0(222) 230 11 11"}
        inc = {"name": "Test Kliniği", "phone": "0(222) 555 99 99"}
        merged = merge_two_records(base, inc)
        self.assertEqual(merged.get("verification_status"), "conflict")

    def test_09_osm_timeout_and_error_handling(self):
        """Senaryo 9: OSM bağlantı hataları gizlenmemeli, status ve failed_attempts içinde açıkça raporlanmalı."""
        recs, report = fetch_osm_records(self.prof, "Eskişehir")
        self.assertIn("status", report)
        self.assertIn("failed_attempts", report)

    def test_10_db_migration_single_records(self):
        """Senaryo 10: SQLite veritabanında 439 mükerrer kayıt onarılmış ve 220 tekil Eskişehir resmî işvereni korunmuş olmalı."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM employers WHERE city = 'Eskişehir' AND source_type LIKE '%Sağlık Müdürlüğü%'")
        count = cursor.fetchone()[0]
        conn.close()
        self.assertEqual(count, 220, f"Eskişehir için 220 tekil resmî kayıt bekleniyordu, bulunan: {count}")

    def test_11_no_duplicate_on_rescan(self):
        """Senaryo 11: Aynı işveren tekrar kaydedildiğinde yeni satır eklenmemeli (UPSERT doğrulaması)."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM employers WHERE employer_id = 'dentist-eskisehir-clinic-odunpazari-dorliondent'")
        dorlion_cnt = cursor.fetchone()[0]
        conn.close()
        self.assertEqual(dorlion_cnt, 1, "Aynı employer_id için birden fazla kayıt mevcut!")

    def test_12_unverified_contact_without_source(self):
        """Senaryo 12: Kaynak URL'si olmayan telefon veya e-posta 'verified' yapılmamalı."""
        rec = [{"name": "Test Hekim", "phone": "0532 000 00 00", "phone_source_url": ""}]
        assessed = assess_records_quality(rec, self.prof)
        self.assertEqual(assessed[0]["phone_verification_status"], "manual_review")

if __name__ == "__main__":
    unittest.main()

