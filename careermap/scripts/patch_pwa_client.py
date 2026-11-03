"""CareerMap PWA Client Enhancer.
Adds default fallback catalog, friendly backend connection errors,
and prevents raw 404s when opening PWA or running research before backend is connected.
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"
FRONTEND_DIR = BASE_DIR / "frontend_vercel"

DEFAULT_CATALOG_JS = """    // Yerleşik Varsayılan Katalog (Arka uç henüz bağlı olmasa bile arayüzü tam çalıştırır)
    const DEFAULT_CATALOG = [
      {
        id: "dentist",
        name: "Diş Hekimi",
        adapter_status: "ready",
        employer_types: [
          { id: "all", label: "Tüm Diş Klinikleri ve Muayenehaneler" },
          { id: "clinic", label: "Özel Ağız ve Diş Sağlığı Poliklinikleri" },
          { id: "practice", label: "Bireysel Diş Hekimi Muayenehaneleri" }
        ],
        supported_cities: {
          "Bursa": ["Nilüfer", "Osmangazi", "Yıldırım", "İnegöl", "Mudanya"],
          "İstanbul": ["Kadıköy", "Beşiktaş", "Şişli", "Üsküdar", "Bakırköy", "Ataşehir", "Maltepe", "Fatih", "Pendik", "Kartal", "Beyoğlu"],
          "İzmir": ["Konak", "Karşıyaka", "Bornova", "Buca", "Çiğli", "Bayraklı", "Balçova"],
          "Ankara": ["Çankaya", "Keçiören", "Yenimahalle", "Mamak", "Etimesgut"],
          "Eskişehir": ["Tepebaşı", "Odunpazarı"],
          "Antalya": ["Muratpaşa", "Kepez", "Konyaaltı", "Alanya"]
        }
      }
    ];

    let professionsCatalog = DEFAULT_CATALOG;"""

def patch_html_file(file_path: Path):
    with open(file_path, "r", encoding="utf-8") as f:
        html = f.read()

    # 1. Replace empty catalog declaration with DEFAULT_CATALOG
    if "let professionsCatalog = [];" in html:
        html = html.replace("let professionsCatalog = [];", DEFAULT_CATALOG_JS)

    # 2. Populate UI immediately on DOMContentLoaded
    old_init = """    // Başlangıç Yüklemesi
    document.addEventListener('DOMContentLoaded', async () => {
      await loadProfessions();"""
    new_init = """    // Başlangıç Yüklemesi
    document.addEventListener('DOMContentLoaded', async () => {
      populateProfessionUI(); // Anında arayüzü doldur, asla boş kalmasın
      await loadProfessions();"""
    if old_init in html:
        html = html.replace(old_init, new_init)

    # 3. Patch loadProfessions with graceful fallback
    old_load_prof = """    // 1. Meslek Kataloğunu Çek
    async function loadProfessions() {
      try {
        const res = await fetch('/api/v2/research/professions');
        const data = await res.json();
        if (data.status === 'success') {
          professionsCatalog = data.professions;
          populateProfessionUI();
        }
      } catch (e) {
        console.error('Meslekler yüklenirken hata:', e);
      }
    }"""

    new_load_prof = """    // 1. Meslek Kataloğunu Çek
    async function loadProfessions() {
      try {
        const res = await fetch('/api/v2/research/professions');
        if (!res.ok) {
          console.warn('Arka uç henüz bağlı değil (HTTP ' + res.status + '). Yerleşik katalog kullanılıyor.');
          return;
        }
        const data = await res.json();
        if (data.status === 'success' && data.professions) {
          professionsCatalog = data.professions;
          populateProfessionUI();
        }
      } catch (e) {
        console.warn('Arka uç henüz bağlı değil. Yerleşik meslek kataloğu devrede.');
      }
    }"""
    if old_load_prof in html:
        html = html.replace(old_load_prof, new_load_prof)

    # 4. Patch startNewResearchJob to give friendly feedback on 404 instead of raw "Hata: Not Found"
    old_start_job = """      try {
        showToast('Araştırma görevi başlatılıyor...');
        const res = await fetch('/api/v2/research/jobs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.status === 'success') {
          currentJobId = data.job_id;
          displayLiveProgressBanner(data.job);
          startJobPolling(data.job_id);
        } else {
          showToast('Hata: ' + (data.detail || 'Araştırma başlatılamadı.'));
        }
      } catch (e) {
        console.error('Araştırma hatası:', e);
        showToast('Sunucu bağlantı hatası.');
      }"""

    new_start_job = """      try {
        showToast('Araştırma görevi başlatılıyor...');
        const res = await fetch('/api/v2/research/jobs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (!res.ok) {
          if (res.status === 404 || res.status === 502 || res.status === 503) {
            showToast('⚠️ Python arka ucu bağlı değil. Canlı araştırma için sağ üstteki 🌐 API Sunucusu butonundan backend adresinizi bağlayın.');
            openApiSettingsModal();
            return;
          }
          const errData = await res.json().catch(() => ({}));
          showToast('Hata: ' + (errData.detail || errData.message || `Sunucu hatası (${res.status})`));
          return;
        }

        const data = await res.json();
        if (data.status === 'success') {
          currentJobId = data.job_id;
          displayLiveProgressBanner(data.job);
          startJobPolling(data.job_id);
        } else {
          showToast('Hata: ' + (data.detail || 'Araştırma başlatılamadı.'));
        }
      } catch (e) {
        console.error('Araştırma hatası:', e);
        showToast('⚠️ Arka uç sunucusuna ulaşılamadı. Sağ üstteki 🌐 API Sunucusu butonundan bağlantıyı kontrol ediniz.');
        openApiSettingsModal();
      }"""
    if old_start_job in html:
        html = html.replace(old_start_job, new_start_job)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  [OK] Patched {file_path}")

def main():
    target_files = [
        WEB_DIR / "index.html",
        WEB_DIR / "app.html",
        WEB_DIR / "app" / "index.html",
        FRONTEND_DIR / "index.html",
        FRONTEND_DIR / "app.html",
        FRONTEND_DIR / "app" / "index.html",
        BASE_DIR / "templates" / "v2_app.html"
    ]
    print("Patching CareerMap PWA HTML files...")
    for tf in target_files:
        if tf.exists():
            patch_html_file(tf)
    print("All PWA client files patched successfully!")

if __name__ == "__main__":
    main()

