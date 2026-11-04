// CareerMap V2.6 PWA Service Worker (Vercel & Standalone Production)
// Provides instant offline shell while ensuring candidate CVs & sensitive API data are never cached offline.

const CACHE_NAME = 'careermap-pwa-v2-6';
const STATIC_PRECACHE = [
  '/',
  '/index.html',
  '/manifest.json',
  '/offline.html',
  '/canonical_datasets.js',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  '/icons/apple-touch-icon.png',
  '/icons/favicon.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(STATIC_PRECACHE))
      .then(() => self.skipWaiting())
      .catch((err) => console.warn('[CareerMap PWA SW] Pre-cache warning:', err))
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((k) => {
          if (k !== CACHE_NAME) {
            console.log('[CareerMap PWA SW] Clearing old cache:', k);
            return caches.delete(k);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // 1. Never cache non-GET methods (POST, PUT, DELETE, PATCH)
  if (req.method !== 'GET') {
    return;
  }

  // 2. CRITICAL PRIVACY RULE: Never cache candidate CVs, uploads, or live API responses offline
  if (url.pathname.startsWith('/api/') || 
      url.pathname.startsWith('/cv/') || 
      url.pathname.includes('/uploads/') ||
      url.searchParams.has('token')) {
    // Pure network request with offline JSON error fallback
    event.respondWith(
      fetch(req).catch(() => {
        return new Response(
          JSON.stringify({ 
            status: 'error', 
            code: 'offline', 
            detail: 'İnternet bağlantısı yok. Güvenlik nedeniyle CV ve başvuru verileri çevrimdışı saklanmaz.' 
          }),
          { headers: { 'Content-Type': 'application/json' }, status: 503 }
        );
      })
    );
    return;
  }

  // 3. Static Assets (icons, images): Cache-first
  if (url.pathname.startsWith('/icons/') || url.pathname.endsWith('.png') || url.pathname.endsWith('.ico')) {
    event.respondWith(
      caches.match(req).then((cached) => {
        if (cached) return cached;
        return fetch(req).then((res) => {
          if (res && res.status === 200) {
            const clone = res.clone();
            caches.open(CACHE_NAME).then((c) => c.put(req, clone));
          }
          return res;
        });
      })
    );
    return;
  }

  // 4. HTML Navigation: Stale-while-revalidate or Network-first with offline.html fallback
  if (req.mode === 'navigate' || req.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res && res.status === 200) {
            const clone = res.clone();
            caches.open(CACHE_NAME).then((c) => c.put(req, clone));
          }
          return res;
        })
        .catch(async () => {
          const cached = await caches.match(req);
          if (cached) return cached;
          const offline = await caches.match('/offline.html');
          if (offline) return offline;
          return new Response('CareerMap çevrimdışı.', { status: 503, headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
        })
    );
    return;
  }

  // Default fallback
  event.respondWith(
    caches.match(req).then((cached) => cached || fetch(req))
  );
});

