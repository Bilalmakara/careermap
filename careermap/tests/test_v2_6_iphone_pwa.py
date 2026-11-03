"""CareerMap V2.6 — iPhone PWA (Progressive Web App) Doğrulama Testleri.

Bu test modülü, CareerMap'in iPhone Safari ve modern mobil tarayıcılarda:
1. PWA Manifest geçerliliğini ve standartlara uygunluğunu,
2. iOS Safari özel meta etiketlerini (apple-mobile-web-app-capable, apple-touch-icon vb.),
3. Service Worker ve çevrimdışı önbellekleme yeteneğini,
4. Ana ekrana ekleme (Add to Home Screen) altyapısını ve simgelerini,
5. Mobil uyumlu tab bar ve dokunma alanı (touch targets >= 44px) kurallarını
eksiksiz olarak doğrular.
"""
import unittest
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
from app.main import app

class TestCareerMapV26IPhonePWA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.base_dir = Path(__file__).resolve().parent.parent
        cls.static_dir = cls.base_dir / "static"

    def test_01_manifest_json_structure_and_fields(self):
        """Manifest dosyasının PWA standartlarına ve standalone moduna uygunluğu test edilir."""
        resp = self.client.get("/manifest.json")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/manifest+json", resp.headers.get("content-type", ""))
        
        manifest = resp.json()
        self.assertEqual(manifest.get("short_name"), "CareerMap")
        self.assertIn("CareerMap", manifest.get("name"))
        self.assertEqual(manifest.get("display"), "standalone")
        self.assertEqual(manifest.get("start_url"), "/app")
        self.assertEqual(manifest.get("background_color"), "#0f172a")
        
        # Simgelerin varlığı ve boyutları
        icons = manifest.get("icons", [])
        self.assertGreaterEqual(len(icons), 3)
        sizes = [icon.get("sizes") for icon in icons]
        self.assertIn("192x192", sizes)
        self.assertIn("512x512", sizes)
        self.assertIn("180x180", sizes)

    def test_02_service_worker_served_with_correct_mime(self):
        """Service Worker dosyasının root adresinden ve JS MIME tipiyle sunulduğu test edilir."""
        resp = self.client.get("/service-worker.js")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/javascript", resp.headers.get("content-type", ""))
        content = resp.text
        self.assertIn("caches.open", content)
        self.assertIn("careermap-v2-6-cache", content)
        self.assertIn("fetch", content)

    def test_03_offline_page_served(self):
        """İnternetsiz mod için çevrimdışı fallback sayfasının hazır olduğu test edilir."""
        resp = self.client.get("/offline.html")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/html", resp.headers.get("content-type", ""))
        self.assertIn("Çevrimdışı", resp.text)

    def test_04_ios_apple_touch_icons_served(self):
        """iPhone Safari'nin ana ekran simgesi (apple-touch-icon) için PNG dosyaları doğrulanır."""
        for path in ["/apple-touch-icon.png", "/apple-touch-icon-180x180.png"]:
            resp = self.client.get(path)
            self.assertEqual(resp.status_code, 200, f"{path} bulunamadı")
            self.assertIn("image/png", resp.headers.get("content-type", ""))
            self.assertGreater(len(resp.content), 500)

    def test_05_favicon_served(self):
        """Tarayıcı favicon dosyasının sunulduğu test edilir."""
        resp = self.client.get("/favicon.ico")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("image/png", resp.headers.get("content-type", ""))

    def test_06_v2_app_html_ios_pwa_meta_tags(self):
        """Uygulama arayüzünün iPhone Safari PWA gereksinimlerini karşıladığı test edilir."""
        resp = self.client.get("/app")
        self.assertEqual(resp.status_code, 200)
        html = resp.text
        
        # Standalone ve tam ekran meta etiketleri
        self.assertIn('name="apple-mobile-web-app-capable" content="yes"', html)
        self.assertIn('name="apple-mobile-web-app-status-bar-style" content="black-translucent"', html)
        self.assertIn('name="apple-mobile-web-app-title" content="CareerMap"', html)
        self.assertIn('rel="apple-touch-icon"', html)
        self.assertIn('rel="manifest" href="/manifest.json"', html)
        
        # Viewport safe area ve iOS fit
        self.assertIn('viewport-fit=cover', html)
        
        # PWA Rehber modalı ve mobil tab bar
        self.assertIn('id="pwa-install-modal"', html)
        self.assertIn('class="mobile-bottom-nav"', html)
        self.assertIn('serviceWorker.register', html)

    def test_07_mobile_responsive_css_and_safe_areas(self):
        """CSS içinde iOS çentik (safe area) ve otomatik zoom engelleme kuralları doğrulanır."""
        resp = self.client.get("/app")
        html = resp.text
        
        # Safe area insets desteği
        self.assertIn('safe-area-inset-top', html)
        self.assertIn('safe-area-inset-bottom', html)
        
        # 16px font-size kuralı (iPhone Safari'de tıklandığında ekranın istem dışı yakınlaşmasını önler)
        self.assertIn('font-size: 16px !important', html)
        
        # Dokunma alanı (min-height: 44px)
        self.assertIn('min-height: 44px', html)

    def test_08_root_index_renders_v2_6_pwa_version(self):
        """Ana sayfanın V2.6 PWA başlığıyla yüklendiği doğrulanır."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("V2.6 PWA", resp.text)
        self.assertIn("CAREERMAP V2.6", resp.text)

if __name__ == "__main__":
    unittest.main()
