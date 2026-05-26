// Damascus Transit Driver PWA - Service Worker
// Provides offline support, GPS position queue background sync,
// and Web Push notifications for driver app.

const CACHE_NAME = 'damascus-driver-v2';
const APP_SHELL = [
  '/driver/',
  '/driver/index.html',
  '/driver/manifest.json',
];

// Static data — stale-while-revalidate (trip manifests, routes)
const STATIC_DATA_CACHE = 'damascus-driver-data-v2';
const STATIC_DATA_PATTERNS = ['/api/routes', '/api/stops'];

// Map tile cache
const TILE_CACHE = 'damascus-driver-tiles-v2';
const TILE_HOSTS = ['basemaps.cartocdn.com'];

// IndexedDB for GPS position queue (accessed from SW context)
const IDB_NAME = 'damascus-driver-sw';
const IDB_VERSION = 1;
const GPS_STORE = 'gps-queue';

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
          .filter(k => k !== CACHE_NAME && k !== STATIC_DATA_CACHE && k !== TILE_CACHE)
          .map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// ─── Fetch: routing strategy ───
self.addEventListener('fetch', event => {
  const { request } = event;
  if (request.method !== 'GET') return;
  if (request.headers.get('Accept') === 'text/event-stream') return;

  const url = new URL(request.url);

  // Map tiles — cache-first
  if (TILE_HOSTS.some(h => url.hostname.includes(h))) {
    event.respondWith(tileStrategy(request));
    return;
  }

  // Static data — stale-while-revalidate
  if (STATIC_DATA_PATTERNS.some(p => url.pathname.includes(p))) {
    event.respondWith(staleWhileRevalidate(request, STATIC_DATA_CACHE));
    return;
  }

  // Driver API calls — network-only (position, trip endpoints)
  if (url.pathname.includes('/api/driver/') || url.pathname.includes('/api/auth/')) return;

  // App shell
  event.respondWith(
    caches.match(request).then(cached => {
      if (cached) return cached;
      return fetch(request).then(response => {
        if (response.ok) {
          caches.open(CACHE_NAME).then(cache => cache.put(request, response.clone()));
        }
        return response;
      }).catch(async () => {
        const fallback = await caches.match('/driver/index.html') || await caches.match('/driver/');
        return fallback || new Response('Offline', { status: 503 });
      });
    })
  );
});

async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);

  const fetchPromise = fetch(request).then(response => {
    if (response.ok) cache.put(request, response.clone());
    return response;
  }).catch(() => null);

  if (cached) return cached;
  const fresh = await fetchPromise;
  return fresh || new Response(JSON.stringify([]), {
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

// ─── IndexedDB helpers (SW context) ───
function openSwIDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(IDB_NAME, IDB_VERSION);
    req.onupgradeneeded = e => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(GPS_STORE)) {
        db.createObjectStore(GPS_STORE, { keyPath: 'id', autoIncrement: true });
      }
    };
    req.onsuccess = e => resolve(e.target.result);
    req.onerror = () => reject(req.error);
  });
}

function getAllQueued(db) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(GPS_STORE, 'readonly');
    const req = tx.objectStore(GPS_STORE).getAll();
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function deleteQueued(db, id) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(GPS_STORE, 'readwrite');
    tx.objectStore(GPS_STORE).delete(id);
    tx.oncomplete = resolve;
    tx.onerror = () => reject(tx.error);
  });
}

// ─── Background Sync: flush GPS queue ───
self.addEventListener('sync', event => {
  if (event.tag === 'gps-sync') {
    event.waitUntil(flushGpsQueue());
  }
});

async function flushGpsQueue() {
  let db;
  try { db = await openSwIDB(); } catch { return; }

  const positions = await getAllQueued(db);
  if (!positions.length) return;

  // Get auth token from clients
  const clientList = await self.clients.matchAll({ type: 'window' });
  let authToken = null;
  for (const client of clientList) {
    // Request token via postMessage
    const tokenPromise = new Promise(resolve => {
      const channel = new MessageChannel();
      channel.port1.onmessage = e => resolve(e.data && e.data.authToken);
      client.postMessage({ type: 'REQUEST_AUTH_TOKEN' }, [channel.port2]);
      setTimeout(() => resolve(null), 2000);
    });
    authToken = await tokenPromise;
    if (authToken) break;
  }

  const apiBase = self.location.hostname === 'localhost' || self.location.hostname === '127.0.0.1'
    ? `http://${self.location.hostname}:8080`
    : self.location.origin;

  const headers = {
    'Content-Type': 'application/json',
    ...(authToken ? { 'Authorization': `Bearer ${authToken}` } : {}),
  };

  for (const pos of positions) {
    try {
      const res = await fetch(`${apiBase}/api/driver/position`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          latitude: pos.latitude,
          longitude: pos.longitude,
          speed_kmh: pos.speed_kmh,
          heading: pos.heading || 0,
          timestamp: pos.timestamp,
        }),
      });
      if (res.ok || res.status === 401) {
        // Remove from queue if sent (or if auth failed — stale token)
        await deleteQueued(db, pos.id);
      }
    } catch {
      // Still offline — leave in queue, sync will retry
      break;
    }
  }

  // Notify app of sync completion
  for (const client of clientList) {
    client.postMessage({ type: 'GPS_SYNC_DONE' });
  }
}

// ─── Message handler: queue a GPS position from app ───
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'QUEUE_GPS_POSITION') {
    event.waitUntil(
      openSwIDB().then(db => {
        return new Promise((resolve, reject) => {
          const tx = db.transaction(GPS_STORE, 'readwrite');
          tx.objectStore(GPS_STORE).add({
            latitude: event.data.latitude,
            longitude: event.data.longitude,
            speed_kmh: event.data.speed_kmh,
            heading: event.data.heading || 0,
            timestamp: event.data.timestamp || Date.now(),
          });
          tx.oncomplete = resolve;
          tx.onerror = () => reject(tx.error);
        });
      })
    );
  }
});

// ─── Web Push: receive notification ───
self.addEventListener('push', event => {
  let payload = { title: 'Damascus Transit', body: '', data: {} };
  if (event.data) {
    try { Object.assign(payload, JSON.parse(event.data.text())); } catch {}
  }
  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      icon: '/driver/icons/icon-192.png',
      badge: '/driver/icons/badge-72.png',
      data: payload.data,
      dir: 'auto',
      lang: 'ar',
      requireInteraction: true,
    })
  );
});

// ─── Web Push: notification click ───
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/driver/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(windowClients => {
      for (const client of windowClients) {
        if (client.url.includes('/driver/') && 'focus' in client) {
          if (event.notification.data) {
            client.postMessage({ type: 'PUSH_DATA', data: event.notification.data });
          }
          return client.focus();
        }
      }
      return clients.openWindow(url);
    })
  );
});
