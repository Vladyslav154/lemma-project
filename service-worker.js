const CACHE_NAME = 'lepko-cache-v4'; // Снова увеличиваем версию кэша
const urlsToCache = [
  '/?lang=ru',
  '/static/style.css',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.filter(name => name !== CACHE_NAME).map(name => caches.delete(name))
      );
    })
  );
});

self.addEventListener('fetch', event => {
  const { request } = event;

  // Игнорируем запросы, которые не являются GET
  if (request.method !== 'GET' || request.url.includes('/ws/')) {
    return;
  }

  // Для HTML-страниц (навигационных запросов) - "Сначала сеть, потом кэш"
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then(response => {
          const responseToCache = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(request, responseToCache));
          return response;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  // Для остальных ресурсов (CSS, JS, иконки) - "Сначала кэш, потом сеть"
  event.respondWith(
    caches.match(request)
      .then(cachedResponse => {
        return cachedResponse || fetch(request).then(networkResponse => {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(request, responseToCache));
          return networkResponse;
        });
      })
  );
});