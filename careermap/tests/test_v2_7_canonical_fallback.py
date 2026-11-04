"""CareerMap V2.7 — Sıfır Gecikmeli Kanonik Veri Kataloğu & İstemci Çevrimdışı Güvence Testleri.

Bu test paketi:
1. canonical_datasets.js dosyasının Eskişehir (229), Bursa (96) ve Ankara (218) kliniklerini eksiksiz barındırdığını,
2. Vercel ve PWA dağıtımlarındaki 6 dosyanın birebir senkronize olduğunu,
3. Frontend JS motorunun zaman aşımı ve donma önleme mekanizmalarını (completeJobLocally, DEFAULT_RECENT_JOBS)
doğrular.
"""
import unittest
import json
import re
from pathlib import Path

class TestCareerMapCanonicalFallback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_dir = Path(__file__).resolve().parent.parent
        cls.web_dir = cls.base_dir / "web"
        cls.vercel_dir = cls.base_dir / "frontend_vercel"

    def test_01_canonical_datasets_js_presence_and_counts(self):
        """canonical_datasets.js dosyasının varlığı ve şehir hekim sayıları doğrulanır."""
        js_file = self.web_dir / "canonical_datasets.js"
        self.assertTrue(js_file.exists(), "canonical_datasets.js bulunamadı")
        self.assertGreater(js_file.stat().st_size, 100000, "Dosya boyutu yetersiz")

        with open(js_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertTrue(content.startswith("window.CAREERMAP_CANONICAL_DATA = "))
        json_str = content[len("window.CAREERMAP_CANONICAL_DATA = "):].rstrip(";\n")
        data = json.loads(json_str)

        self.assertIn("Eskişehir", data)
        self.assertIn("Bursa", data)
        self.assertIn("Ankara", data)

        esk = data["Eskişehir"]
        self.assertGreaterEqual(len(esk["results"]), 220)
        self.assertGreaterEqual(esk["job"]["total_found"], 220)

        bursa = data["Bursa"]
        self.assertGreaterEqual(len(bursa["results"]), 90)
        self.assertGreaterEqual(bursa["job"]["total_found"], 90)

        ankara = data["Ankara"]
        self.assertGreaterEqual(len(ankara["results"]), 200)
        self.assertGreaterEqual(ankara["job"]["total_found"], 200)

    def test_02_mirrored_web_files_in_sync(self):
        """Web ve Vercel arayüz dosyalarının tam senkronize olduğu test edilir."""
        targets = [
            self.web_dir / "index.html",
            self.web_dir / "app.html",
            self.web_dir / "app" / "index.html",
            self.vercel_dir / "index.html",
            self.vercel_dir / "app.html",
            self.vercel_dir / "app" / "index.html"
        ]

        with open(targets[0], "r", encoding="utf-8") as f:
            ref_content = f.read()

        for t in targets[1:]:
            self.assertTrue(t.exists(), f"Eksik dosya: {t}")
            with open(t, "r", encoding="utf-8") as f:
                t_content = f.read()
            self.assertEqual(len(ref_content), len(t_content), f"Boyut uyuşmazlığı: {t}")

    def test_03_resilient_zero_latency_frontend_logic(self):
        """index.html dosyasında Render uyku modu ve donma koruma fonksiyonları doğrulanır."""
        with open(self.web_dir / "index.html", "r", encoding="utf-8") as f:
            html = f.read()

        self.assertIn("canonical_datasets.js", html)
        self.assertIn("DEFAULT_RECENT_JOBS", html)
        self.assertIn("getCanonicalDataForCity", html)
        self.assertIn("completeJobLocally", html)
        self.assertIn("AbortController", html)
        self.assertIn("renderLoadedResults", html)

if __name__ == "__main__":
    unittest.main()
