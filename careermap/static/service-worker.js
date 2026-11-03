// CareerMap V2.6 Service Worker
// Enables offline shell, instant loading, and PWA capabilities on iOS Safari & Modern Browsers

const CACHE_NAME = 'careermap-v2-6-cache';
const PRECACHE_URLS = [
  '/',
  '/app',
  '/manifest.json',
  '/static/offline.html',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/apple-touch-icon.png',
  '/static/icons/favicon.png'
];

// Install: Cache critical shell assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
      .catch((err) => console.warn('[CareerMap SW] Pre-caching warning:', err))
  );
});

// Activate: Clean up older cache versions
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((name) => {
          if (name !== CACHE_NAME) {
            console.log('[CareerMap SW] Purging old cache:', name);
            return caches.delete(name);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch: Strategy based on request type
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Skip non-GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  // API calls & Dynamic Searches: Network-First (always fresh data)
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/search')) {
    event.respondWith(
      fetch(event.request)
        .catch(() => {
          return new Response(
            JSON.stringify({ error: 'offline', message: 'Çevrimdışısınız. Lütfen internet bağlantınızı kontrol edin.' }),
            { headers: { 'Content-Type': 'application/json' }, status: 503 }
          );
        })
    );
    return;
  }

  // Static Assets (icons, css, images): Cache-first with network fallback
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(event.request).then((cachedResponse) => {
        if (cachedResponse) return cachedResponse;
        return fetch(event.request).then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const responseClone = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, responseClone));
          }
          return networkResponse;
        });
      })
    );
    return;
  }

  // HTML Page Navigations: Network-first, cache fallback, offline fallback
  if (event.request.mode === 'navigate' || event.request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response && response.status === 200) {
            const responseClone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, responseClone));
          }
          return response;
        })
        .catch(async () => {
          const cached = await caches.match(event.request);
          if (cached) return cached;
          const offlinePage = await caches.match('/static/offline.html');
          if (offlinePage) return offlinePage;
          return new Response('Çevrimdışı moddasınız.', {
            headers: { 'Content-Type': 'text/plain; charset=utf-8' },
            status: 503
          });
        })
    );
    return;
  }

  // Default fallback
  event.respondWith(
    caches.match(event.request).then((response) => response || fetch(event.request))
  );
});

