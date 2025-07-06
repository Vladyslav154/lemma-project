const CACHE_NAME = 'lepko-cache-v1';
// Список файлов, которые нужно кешировать для офлайн-работы
const urlsToCache = [
  '/',
  '/?lang=ru',
  '/?lang=en',
  '/static/style.css'
  // Пути к иконкам будут кешироваться автоматически при первом запросе
];

// Установка Service Worker и кеширование основных ресурсов
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
  );
});

// Перехват запросов и возврат из кеша (стратегия "Cache First")
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Если ресурс есть в кеше, возвращаем его
        if (response) {
          return response;
        }

        // Если нет, делаем запрос к сети
        return fetch(event.request).then(
          function(response) {
            // Проверяем, что мы получили корректный ответ
            if(!response || response.status !== 200 || response.type !== 'basic') {
              return response;
            }

            // Клонируем ответ, так как его можно использовать только один раз
            var responseToCache = response.clone();

            caches.open(CACHE_NAME)
              .then(function(cache) {
                cache.put(event.request, responseToCache);
              });

            return response;
          }
        );
      })
    );
});