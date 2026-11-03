# CareerMap V2.6 — Vercel PWA Frontend Dağıtım Paketi

Bu klasör, CareerMap platformunun **Vercel üzerinde barındırılmaya hazır, tam donanımlı PWA (Progressive Web App)** ön yüzünü içerir.

Bu mimari sayesinde:
1. **$0 Ek Maliyet:** Apple Developer ($99/yıl) veya pahalı sunucu maliyeti olmadan iPhone'a ana ekran uygulaması kurulur.
2. **Otomatik Küresel HTTPS:** Vercel'in sağladığı ücretsiz SSL sertifikası sayesinde iPhone Safari'nin PWA gereksinimleri doğrudan karşılanır.
3. **Akıllı Ayrık Mimari (Decoupled):** Ağır Python / OSM PBF / araştırma motoru Vercel'in sunucusuz limitlerine takılmaz; ayrı bir Python sunucusunda çalışırken Vercel sadece hızlı arayüz ve PWA kabuğunu sunar.

---

## 📁 Paket İçeriği

- `index.html`: 7 ekranlı Search-First işveren keşfi, CV yönetimi, WhatsApp/Gmail başvuru merkezi ve CRM takip arayüzü.
- `manifest.json`: iOS ve Android için `standalone` mod, tema renkleri ve Retina simgeler.
- `service-worker.js`: Statik kabuk önbellekleme ve **gizlilik korumalı** çevrimdışı filtre (Aday CV'leri ve canlı API verileri telefonda çevrimdışı saklanmaz).
- `offline.html`: İnternet bağlantısı kesildiğinde açılan şık bildirim sayfası.
- `vercel.json`: PWA önbellek başlıkları ve `/api/:path*` ters vekili (reverse proxy).
- `icons/`: 180x180 Retina iPhone simgeleri, 192px/512px Android simgeleri ve favicon.

---

## 🚀 2 Dakikada Vercel'e Nasıl Dağıtılır?

### Yöntem A: Vercel CLI ile Doğrudan Terminalden
```bash
cd careermap/frontend_vercel
npx vercel
```
Gelen sorulara:
- `Set up and deploy?` -> **y**
- `Which scope?` -> Hesabınızı seçin
- `Link to existing project?` -> **n**
- `What's your project's name?` -> **careermap**
- `In which directory is your code located?` -> **./**
Birkaç saniye içinde `https://careermap-xxx.vercel.app` canlı HTTPS adresiniz hazır!

### Yöntem B: GitHub ile Bağlama
1. Bu klasörü veya projenizi GitHub reponuza yükleyin.
2. [vercel.com](https://vercel.com) adresine girin -> **Add New...** -> **Project**.
3. GitHub reponuzu seçin, Root Directory olarak `careermap/frontend_vercel` belirleyin ve **Deploy** butonuna basın.

---

## 🔗 Python FastAPI Arka Ucunu Bağlama

Vercel frontend'inin gerçek Türkiye geneli klinik verilerini çekmesi için iki kolay yönteminiz vardır:

### 1. Arayüz Üzerinden (Sıfır Yeniden Derleme)
Canlı Vercel adresinizi açtıktan sonra sağ üstteki **"🌐 API Sunucusu"** butonuna tıklayın:
- Geliştirme/Test aşamasında yerel tünel adresinizi (Örn: `https://xxx.trycloudflare.com`) yazın.
- Canlı sunucuya geçtiğinizde Render / Railway adresinizi (Örn: `https://careermap-api.onrender.com`) yazıp **Kaydet** deyin.

### 2. `vercel.json` Üzerinden Otomatik Vekil (Önerilen)
`vercel.json` dosyasındaki hedef adresi güncelleyin:
```json
{
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://careermap-backend.onrender.com/api/:path*"
    }
  ]
}
```
Böylece tarayıcı doğrudan Vercel adresi üzerinden konuşur; **CORS sorunu tamamen ortadan kalkar**.

---

## 📲 iPhone Safari'ye Kurulum (PWA)

1. iPhone Safari'de Vercel adresinizi (`https://careermap.vercel.app`) açın.
2. Safari'nin altındaki **Paylaş (⎋)** simgesine dokunun.
3. Menüde aşağı kaydırıp **"Ana Ekrana Ekle"** seçeneğini seçin.
4. Sağ üstteki **"Ekle"** butonuna basın.

Ana ekrandaki CareerMap simgesine dokunduğunuzda uygulama Safari adres çubuğu olmadan tam ekran bir iPhone uygulaması olarak çalışır!

