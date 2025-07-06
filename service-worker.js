const CACHE_NAME = 'lepko-cache-v2'; // Увеличили версию кэша, чтобы обновить все файлы
const urlsToCache = [
  '/?lang=ru',
  '/?lang=en',
  '/static/style.css',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png'
];

// Этап установки: кешируем основные ресурсы
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Opened cache and caching basic assets');
        return cache.addAll(urlsToCache);
      })
  );
});

// Этап активации: удаляем старые кэши
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.filter(name => name !== CACHE_NAME)
          .map(name => caches.delete(name))
      );
    })
  );
});


// Этап Fetch: обрабатываем запросы
self.addEventListener('fetch', event => {
  const { request } = event;

  // Игнорируем все, что не является GET-запросом (например, WebSocket)
  if (request.method !== 'GET') {
    return;
  }

  // Для HTML-страниц (навигационных запросов) используем "Network First"
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then(response => {
          // Если получили ответ из сети, кешируем его и возвращаем
          const responseToCache = response.clone();
          caches.open(CACHE_NAME).then(cache => {
            cache.put(request, responseToCache);
          });
          return response;
        })
        .catch(() => {
          // Если сети нет, ищем ответ в кеше
          return caches.match(request);
        })
    );
    return;
  }

  // Для остальных ресурсов (CSS, JS, иконки) используем "Cache First"
  event.respondWith(
    caches.match(request)
      .then(cachedResponse => {
        // Если ресурс есть в кеше, возвращаем его
        if (cachedResponse) {
          return cachedResponse;
        }
        // Если нет, идем в сеть, получаем, кешируем и возвращаем
        return fetch(request).then(networkResponse => {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then(cache => {
            cache.put(request, responseToCache);
          });
          return networkResponse;
        });
      })
  );
});