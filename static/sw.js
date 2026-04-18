const CACHE_NAME = 'private-universe-v3';
const STATIC_ASSETS = [
  '/',
  '/login',
  '/static/css/style.css',
  '/static/js/main.js',
  '/static/manifest.json',
  '/static/icon-192.png',
  '/static/icon-512.png',
];

const CDN_ASSETS = [
  'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=Playfair+Display:ital,wght@0,600;1,600&display=swap',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
];

// ─── Install: pre-cache static assets ───────────────────────────
self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      // Cache static assets (ignore failures for CDN)
      return cache.addAll(STATIC_ASSETS)
        .then(() => cache.addAll(CDN_ASSETS).catch(() => {}));
    })
  );
});

// ─── Activate: clear old caches ─────────────────────────────────
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// ─── Fetch: Network-first for API, Cache-first for assets ───────
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Skip non-GET and WebSocket upgrades
  if (event.request.method !== 'GET') return;
  if (url.pathname.startsWith('/socket.io')) return;

  // Static assets (CSS, JS, images, fonts) → Cache first, then network
  if (
    url.pathname.startsWith('/static/') ||
    url.hostname.includes('googleapis.com') ||
    url.hostname.includes('cloudflare.com') ||
    url.hostname.includes('jsdelivr.net') ||
    url.hostname.includes('fonts.gstatic.com')
  ) {
    event.respondWith(
      caches.match(event.request).then(cached => {
        if (cached) return cached;
        return fetch(event.request).then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          }
          return response;
        });
      })
    );
    return;
  }

  // Dynamic pages → Network first, offline fallback
  event.respondWith(
    fetch(event.request)
      .then(response => {
        // Cache successful page loads
        if (response.ok && response.type === 'basic') {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() => {
        // Offline: try cache
        return caches.match(event.request).then(cached => {
          if (cached) return cached;
          // Last resort: show offline page (the login page)
          return caches.match('/login');
        });
      })
  );
});

// ─── Push Notifications ─────────────────────────────────────────
self.addEventListener('push', event => {
  let data = {title: 'Private Universe', body: 'You have a new message 💌', icon: '/static/icon-192.png'};
  try { data = event.data.json(); } catch(e) {}

  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: data.icon || '/static/icon-192.png',
      badge: '/static/icon-96.png',
      vibrate: [200, 100, 200],
      tag: 'us-notification',
      renotify: true,
      data: {url: data.url || '/'}
    })
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({type: 'window'}).then(clientList => {
      const url = event.notification.data.url;
      for (const client of clientList) {
        if (client.url === url && 'focus' in client) return client.focus();
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});
