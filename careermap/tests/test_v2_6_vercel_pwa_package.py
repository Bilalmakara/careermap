"""CareerMap V2.6 — Vercel PWA Dağıtım Paketi Bütünlük ve Güvenlik Testleri.

Bu test paketi:
1. Vercel dağıtım klasörünün (frontend_vercel) eksiksizliğini,
2. manifest.json ve vercel.json yapılandırmasının doğruluğunu,
3. Service Worker'ın aday CV'lerini ve API yanıtlarını kesinlikle çevrimdışı önbelleğe ALMADIĞINI (gizlilik kuralı),
4. Arayüzün dinamik API bağlantı seçicisine ve Vercel ters vekiline uygunluğunu,
5. iPhone Retina simgelerinin fiziki mevcudiyetini doğrular.
"""
import unittest
import json
from pathlib import Path
from PIL import Image

class TestCareerMapVercelPWAPackage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_dir = Path(__file__).resolve().parent.parent
        cls.vercel_dir = cls.base_dir / "frontend_vercel"
        cls.icons_dir = cls.vercel_dir / "icons"

    def test_01_vercel_directory_structure(self):
        """Vercel paketinin tüm zorunlu dosyaları barındırdığı test edilir."""
        required_files = [
            "index.html",
            "manifest.json",
            "service-worker.js",
            "offline.html",
            "vercel.json",
            "package.json",
            "README.md"
        ]
        for f in required_files:
            file_path = self.vercel_dir / f
            self.assertTrue(file_path.exists(), f"Eksik dosya: {f}")
            self.assertGreater(file_path.stat().st_size, 0, f"Boş dosya: {f}")

    def test_02_manifest_json_validity(self):
        """Vercel manifest.json dosyasının standartlara uygunluğu doğrulanır."""
        manifest_path = self.vercel_dir / "manifest.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        self.assertEqual(data.get("short_name"), "CareerMap")
        self.assertEqual(data.get("display"), "standalone")
        self.assertEqual(data.get("start_url"), "/")
        self.assertEqual(data.get("background_color"), "#0f172a")
        
        icons = data.get("icons", [])
        self.assertGreaterEqual(len(icons), 3)
        srcs = [i.get("src") for i in icons]
        self.assertIn("/icons/icon-192.png", srcs)
        self.assertIn("/icons/icon-512.png", srcs)
        self.assertIn("/icons/apple-touch-icon-180x180.png", srcs)

    def test_03_vercel_json_rewrites_and_headers(self):
        """vercel.json ters vekili ve PWA önbellek başlıkları test edilir."""
        v_path = self.vercel_dir / "vercel.json"
        with open(v_path, "r", encoding="utf-8") as f:
            v_data = json.load(f)
        
        self.assertTrue(v_data.get("cleanUrls"))
        headers = v_data.get("headers", [])
        sw_header = next((h for h in headers if h.get("source") == "/service-worker.js"), None)
        self.assertIsNotNone(sw_header)
        
        rewrites = v_data.get("rewrites", [])
        self.assertTrue(any(r.get("source") == "/api/:path*" for r in rewrites))

    def test_04_service_worker_privacy_enforcement(self):
        """Kritik Gizlilik Testi: Service Worker'ın CV ve canlı API'yi çevrimdışı önbelleğe almadığı doğrulanır."""
        sw_path = self.vercel_dir / "service-worker.js"
        with open(sw_path, "r", encoding="utf-8") as f:
            sw_text = f.read()
        
        # /api/ ve /cv/ yollarının engellendiği kontrol edilir
        self.assertIn("url.pathname.startsWith('/api/')", sw_text)
        self.assertIn("url.pathname.startsWith('/cv/')", sw_text)
        self.assertIn("caches.open", sw_text)
        self.assertIn("İnternet bağlantısı yok", sw_text)

    def test_05_index_html_features(self):
        """index.html dosyasında iOS meta etiketleri, mobil tab bar ve API interceptor doğrulanır."""
        html_path = self.vercel_dir / "index.html"
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
        
        self.assertIn('apple-mobile-web-app-capable" content="yes"', html)
        self.assertIn('viewport-fit=cover', html)
        self.assertIn('CAREERMAP_API_URL', html)
        self.assertIn('class="mobile-bottom-nav"', html)
        self.assertIn('id="api-settings-modal"', html)
        self.assertIn('openApiSettingsModal', html)

    def test_06_icons_physical_existence_and_sizes(self):
        """Tüm PWA simgelerinin diskte var olduğu ve çözünürlükleri doğrulanır."""
        expected_icons = {
            "icon-192.png": (192, 192),
            "icon-512.png": (512, 512),
            "apple-touch-icon-180x180.png": (180, 180),
            "favicon.png": (32, 32)
        }
        for name, expected_size in expected_icons.items():
            icon_file = self.icons_dir / name
            self.assertTrue(icon_file.exists(), f"{name} simgesi eksik")
            with Image.open(icon_file) as img:
                self.assertEqual(img.size, expected_size, f"{name} boyutu hatalı: {img.size}")

if __name__ == "__main__":
    unittest.main()

