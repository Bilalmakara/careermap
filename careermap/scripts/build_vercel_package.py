"""CareerMap V2.6 Vercel Frontend Package Builder.
Extracts and optimizes the client single-page application for instant Vercel deployment.
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
VERCEL_DIR = BASE_DIR / "frontend_vercel"

def build_vercel_index():
    source_html = TEMPLATES_DIR / "v2_app.html"
    target_html = VERCEL_DIR / "index.html"

    with open(source_html, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Update static asset paths to root-relative
    content = content.replace("/static/icons/", "/icons/")
    content = content.replace("/static/manifest.json", "/manifest.json")
    content = content.replace("/static/service-worker.js", "/service-worker.js")

    # 2. Add dynamic API URL Interceptor in <head>
    interceptor_code = """
  <!-- CareerMap Vercel API Interceptor -->
  <script>
    (function() {
      const originalFetch = window.fetch;
      window.fetch = function(url, options) {
        if (typeof url === 'string' && url.startsWith('/api/')) {
          const customApiBase = localStorage.getItem('CAREERMAP_API_URL');
          if (customApiBase && customApiBase.trim() !== '') {
            url = customApiBase.trim().replace(/\\/+$/, '') + url;
          }
        }
        return originalFetch.call(this, url, options);
      };
    })();
  </script>
"""
    content = content.replace("<head>", "<head>" + interceptor_code, 1)

    # 3. Add API Settings button in navbar user area
    old_nav_user = '<div class="nav-user">'
    new_nav_user = """<div class="nav-user">
      <button class="btn btn-outline btn-sm" style="color:#38bdf8; border-color:#0284c7; padding: 6px 10px;" onclick="openApiSettingsModal()">🌐 API Sunucusu</button>"""
    content = content.replace(old_nav_user, new_nav_user, 1)

    # 4. Add API Settings Modal and handlers before </body>
    modal_code = """
  <!-- API Sunucu Ayarları Modalı (Vercel -> Remote Backend) -->
  <div id="api-settings-modal" class="modal-backdrop">
    <div class="modal-box" style="max-width: 500px; padding: 24px;">
      <div style="font-size: 32px; margin-bottom: 8px;">⚙️</div>
      <h3 style="font-size: 19px; font-weight: 700; color: #0f172a; margin-bottom: 6px;">FastAPI Sunucu Bağlantısı</h3>
      <p style="font-size: 13.5px; color: #64748b; line-height: 1.5; margin-bottom: 18px;">
        Vercel üzerinde barındırılan CareerMap'in kurum araştırmalarını ve CV işlemlerini yürüteceği Python backend adresini belirleyin.
      </p>

      <div style="margin-bottom: 16px; text-align: left;">
        <label style="font-size: 13px; font-weight: 600; color: #334155; display: block; margin-bottom: 6px;">Arka Uç (Backend) URL</label>
        <input type="url" id="custom-api-input" placeholder="https://careermap-api.onrender.com veya tünel linki" 
               style="width: 100%; padding: 10px 14px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; box-sizing: border-box;">
        <span style="font-size: 11.5px; color: #94a3b8; display: block; margin-top: 4px;">Boş bırakırsanız Vercel ters vekili (proxy) kullanılır.</span>
      </div>

      <div id="api-connection-status" style="display:none; padding: 10px; border-radius: 8px; font-size: 13px; margin-bottom: 16px;"></div>

      <div style="display: flex; gap: 10px; justify-content: flex-end;">
        <button class="btn btn-outline btn-sm" onclick="testBackendConnection()">Bağlantıyı Sına</button>
        <button class="btn btn-outline btn-sm" onclick="closeApiSettingsModal()">Kapat</button>
        <button class="btn btn-primary btn-sm" onclick="saveApiSettings()">Kaydet</button>
      </div>
    </div>
  </div>

  <script>
    function openApiSettingsModal() {
      const input = document.getElementById('custom-api-input');
      if (input) input.value = localStorage.getItem('CAREERMAP_API_URL') || '';
      const modal = document.getElementById('api-settings-modal');
      if (modal) modal.classList.add('open');
    }

    function closeApiSettingsModal() {
      const modal = document.getElementById('api-settings-modal');
      if (modal) modal.classList.remove('open');
    }

    function saveApiSettings() {
      const input = document.getElementById('custom-api-input');
      const val = input.value.trim();
      if (val) {
        localStorage.setItem('CAREERMAP_API_URL', val);
        showToast('✓ Arka uç adresi kaydedildi: ' + val);
      } else {
        localStorage.removeItem('CAREERMAP_API_URL');
        showToast('✓ Varsayılan Vercel vekili seçildi.');
      }
      closeApiSettingsModal();
      setTimeout(() => window.location.reload(), 500);
    }

    async function testBackendConnection() {
      const input = document.getElementById('custom-api-input');
      const statusDiv = document.getElementById('api-connection-status');
      statusDiv.style.display = 'block';
      statusDiv.style.background = '#e0f2fe';
      statusDiv.style.color = '#0369a1';
      statusDiv.innerText = '⏳ Sunucu test ediliyor...';

      let targetUrl = input.value.trim().replace(/\\/+$/, '');
      const testEndpoint = (targetUrl ? targetUrl : '') + '/api/v2/research/professions';

      try {
        const res = await fetch(testEndpoint);
        if (res.ok) {
          statusDiv.style.background = '#dcfce7';
          statusDiv.style.color = '#15803d';
          statusDiv.innerText = '✓ Bağlantı başarılı! FastAPI sunucusuna erişildi.';
        } else {
          statusDiv.style.background = '#fee2e2';
          statusDiv.style.color = '#b91c1c';
          statusDiv.innerText = `⚠️ Sunucu yanıt verdi ancak HTTP kodu: ${res.status}`;
        }
      } catch (err) {
        statusDiv.style.background = '#fee2e2';
        statusDiv.style.color = '#b91c1c';
        statusDiv.innerText = `✗ Sunucuya ulaşılamadı (${err.message}). CORS veya URL kontrol ediniz.`;
      }
    }
  </script>
"""
    content = content.replace("</body>", modal_code + "</body>", 1)

    with open(target_html, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[OK] Generated {target_html} ({target_html.stat().st_size} bytes)")

if __name__ == "__main__":
    build_vercel_index()

