// Damascus Transit PWA - Service Worker
// Provides offline support via cache-first strategy for the app shell,
// stale-while-revalidate for stops/routes/schedules API data,
// and tile caching for offline map usage.

const CACHE_NAME = 'damascus-transit-v2';
const APP_SHELL = [
  '/passenger/',
  '/passenger/index.html',
  '/passenger/manifest.json',
  'https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@300;400;500;600;700&display=swap',
  'https://unpkg.com/maplibre-gl@4.1.2/dist/maplibre-gl.css',
  'https://unpkg.com/maplibre-gl@4.1.2/dist/maplibre-gl.js',
];

// Map tile pattern — cache tiles as they're fetched
const TILE_CACHE = 'damascus-transit-tiles-v2';
const TILE_HOSTS = ['basemaps.cartocdn.com'];

// Static data API — stale-while-revalidate (stops/routes/schedules)
const STATIC_DATA_CACHE = 'damascus-transit-data-v2';
const STATIC_DATA_PATTERNS = ['/api/stops', '/api/routes', '/api/schedules'];

// API endpoints — network-only (live data must be fresh)
const LIVE_API_PATTERNS = ['/api/vehicles', '/api/stream'];

// ─── Install: pre-cache app shell ───
self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return Promise.allSettled(
        APP_SHELL.map(url => cache.add(url).catch(() => {}))
      );
    })
  );
});

// ─── Activate: clear old caches ───
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(k => k !== CACHE_NAME && k !== TILE_CACHE && k !== STATIC_DATA_CACHE)
          .map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// ─── Fetch: routing strategy ───
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET and SSE (streaming)
  if (request.method !== 'GET') return;
  if (request.headers.get('Accept') === 'text/event-stream') return;

  // Map tiles — cache-first (tiles don't change)
  if (TILE_HOSTS.some(h => url.hostname.includes(h))) {
    event.respondWith(tileStrategy(request));
    return;
  }

  // Live API calls — network-only (vehicle positions must be fresh)
  if (LIVE_API_PATTERNS.some(p => url.pathname.includes(p))) {
    return;
  }

  // Static data API — stale-while-revalidate (serve cached, refresh in background)
  if (STATIC_DATA_PATTERNS.some(p => url.pathname.includes(p))) {
    event.respondWith(staleWhileRevalidate(request, STATIC_DATA_CACHE));
    return;
  }

  // ETA API — stale-while-revalidate
  if (url.pathname.includes('/api/eta') ||
      (url.pathname.includes('/api/stops/') && url.pathname.includes('/arrivals'))) {
    event.respondWith(staleWhileRevalidate(request, STATIC_DATA_CACHE));
    return;
  }

  // App shell — cache-first, fallback to network, fallback to cached index.html
  event.respondWith(appShellStrategy(request));
});

async function appShellStrategy(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const fallback = await caches.match('/passenger/index.html') ||
                     await caches.match('/passenger/');
    if (fallback) return fallback;
    return new Response('غير متصل — يرجى الاتصال بالإنترنت لاستخدام DamascusTransit', {
      status: 503,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' },
    });
  }
}

async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);

  // Fetch fresh copy in background regardless
  const fetchPromise = fetch(request).then(response => {
    if (response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  }).catch(() => null);

  // Return cached immediately if available; otherwise wait for network
  if (cached) return cached;

  const fresh = await fetchPromise;
  if (fresh) return fresh;

  return new Response(JSON.stringify([]), {
    status: 200,
    headers: { 'Content-Type': 'application/json', 'X-Offline': 'true' },
  });
}

async function tileStrategy(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(TILE_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response('', { status: 503 });
  }
}

// ─── Web Push: receive notification ───
self.addEventListener('push', event => {
  let payload = { title: 'Damascus Transit', body: '', data: {} };
  if (event.data) {
    try { Object.assign(payload, JSON.parse(event.data.text())); } catch {}
  }
  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      icon: '/passenger/icons/icon-192.png',
      badge: '/passenger/icons/badge-72.png',
      data: payload.data,
      dir: 'auto',
      lang: 'ar',
    })
  );
});

// ─── Web Push: notification click ───
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/passenger/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(windowClients => {
      for (const client of windowClients) {
        if (client.url.includes('/passenger/') && 'focus' in client) {
          if (event.notification.data && event.notification.data.stopId) {
            client.postMessage({ type: 'FOCUS_STOP', stopId: event.notification.data.stopId });
          }
          return client.focus();
        }
      }
      return clients.openWindow(url);
    })
  );
});
