// Service worker de NotisNotis (servido en /sw.js → scope raíz). Caché offline + Web Push.
const CACHE = "notisnotis-v1";
const AUDIO = "nn-audio";   // episodios descargados para escuchar sin conexión
const SHELL = [
  "/static/css/app.css",
  "/static/js/app.js",
  "/static/js/htmx.min.js",
  "/static/manifest.webmanifest",
  "/static/icons/icon.svg",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((k) => k !== CACHE && k !== AUDIO).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// Descargas offline: la página pide cachear/borrar el audio de un episodio.
self.addEventListener("message", (e) => {
  const m = e.data || {};
  if (m.type === "cache-audio" && m.url) {
    e.waitUntil(caches.open(AUDIO)
      .then((c) => c.add(new Request(m.url, { mode: "no-cors" })))
      .then(() => reply(e, { ok: true, url: m.url }))
      .catch(() => reply(e, { ok: false, url: m.url })));
  } else if (m.type === "uncache-audio" && m.url) {
    e.waitUntil(caches.open(AUDIO).then((c) => c.delete(new Request(m.url, { mode: "no-cors" })))
      .then((ok) => reply(e, { ok: ok, url: m.url, removed: true })));
  }
});
function reply(e, data) {
  if (e.source && e.source.postMessage) e.source.postMessage(data);
}

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  // Episodio descargado: servir desde la caché de audio (también cross-origin/opaque).
  if (req.destination === "audio" || /\.(mp3|m4a|ogg|aac|opus|wav)(\?|$)/i.test(url.pathname)) {
    e.respondWith(caches.open(AUDIO).then((c) => c.match(req, { ignoreVary: true }))
      .then((hit) => hit || fetch(req)));
    return;
  }
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/static/")) {
    // estáticos: cache-first
    e.respondWith(caches.match(req).then((hit) => hit || fetch(req).then((res) => {
      const copy = res.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); return res;
    })));
  } else {
    // páginas: network-first con fallback a caché
    e.respondWith(
      fetch(req).then((res) => { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); return res; })
        .catch(() => caches.match(req).then((hit) => hit || caches.match("/")))
    );
  }
});

// --- Web Push ---
self.addEventListener("push", (e) => {
  let data = {};
  try { data = e.data ? e.data.json() : {}; } catch (err) { data = {}; }
  e.waitUntil(self.registration.showNotification(data.title || "NotisNotis", {
    body: data.body || "", data: { url: data.url || "/" }, icon: "/static/icons/icon.svg",
  }));
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || "/";
  e.waitUntil(clients.openWindow(url));
});
