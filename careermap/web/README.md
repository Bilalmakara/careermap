# CareerMap V2.0 — Web & Mobil Uyumlu Frontend Mimarisi

Bu dizin, CareerMap V2.0 REST API'si üzerine inşa edilen Next.js web platformu ve React Native / Expo mobil uygulaması için paylaşılan TypeScript tiplerini ve API istemcisini barındırır.

## Mimari Yaklaşım: "Önce Web, Sonra Mobil"
1. **Tek Doğruluk Kaynağı (FastAPI Backend):** Tüm eşleştirme algoritmaları, sıfır halüsinasyonlu mesaj üretim şablonları, CRM durum makineleri ve 30 günlük güvenli CV bağlantı yönetimi FastAPI backend'inde çalışır.
2. **Ortak TypeScript Tipleri (`src/types/careermap.ts`):** Web (Next.js) ve Mobil (Expo) aynı veri yapılarını tüketir.
3. **Taşınabilir API İstemcisi (`src/services/apiClient.ts`):** Hem web tarayıcılarında hem de iOS / Android React Native ortamında harici kütüphane bağımlılığı olmadan yerel `fetch` ile çalışır.

## Sayfalar & Ekranlar
1. **Giriş & Hesap Seçici (`/login`):** Dt. Rümeysa Çolak ve Admin rolleri arasında geçiş.
2. **Kontrol Paneli (`/dashboard`):** 220 hedef kurum, 135 ulaşılabilir klinik, aktif yanıt bekleyenler ve mülakat davetleri.
3. **İşveren Keşfi (`/employers`):** Tepebaşı / Odunpazarı, poliklinik/muayenehane filtreleri, WhatsApp & E-posta kanalı rozetleri.
4. **Başvuru Hazırlama & Mesaj Motoru:** Kişiselleştirilmiş kurumsal e-posta, WhatsApp Model B (`wa.me` güvenli link) ve Model C (PDF ekleme), telefon konuşma senaryosu.
5. **Aday Profili & CV Yönetimi (`/profile`):** SDÜ 2026 mezuniyeti, 350+ vaka deneyimi, 30 günlük süreli bağlantı kopyalama ve PDF yükleme.
6. **Başvuru Takip CRM (`/crm`):** Tekil işveren başvuru kartları, zaman çizelgesi hareketleri ve mülakat daveti kaydı.
7. **Yönetici Paneli (`/admin`):** Kapsama oranları ve canlı 7 sekmeli Excel içe/dışa aktarımı.

