// Nigehban service worker: offline app shell, and web-push notifications.
const CACHE = "nigehban-v1";
const SHELL = ["/", "/manifest.webmanifest", "/icon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

// Pages: network first, cached shell when offline. API calls are never cached (risk must be fresh).
self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET" || new URL(req.url).origin !== self.location.origin) return;
  event.respondWith(
    fetch(req).then((res) => {
      const copy = res.clone();
      caches.open(CACHE).then((c) => c.put(req, copy));
      return res;
    }).catch(() => caches.match(req).then((hit) => hit || caches.match("/"))),
  );
});

self.addEventListener("push", (event) => {
  let data = { title: "Nigehban", body: "" };
  try { data = event.data.json(); } catch (e) { data.body = event.data ? event.data.text() : ""; }
  event.waitUntil(self.registration.showNotification(data.title || "Nigehban", {
    body: data.body, icon: "/icon.svg", badge: "/icon.svg", dir: "auto", tag: "nigehban-alert",
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(self.clients.openWindow("/?tab=alerts"));
});
