const CACHE = "downnepa-shell-v1";
const SHELL = ["/", "/manifest.webmanifest", "/favicon.svg"];
self.addEventListener("install", event => event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL))));
self.addEventListener("activate", event => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", event => {
  if (event.request.method !== "GET" || new URL(event.request.url).pathname.startsWith("/api/")) return;
  event.respondWith(fetch(event.request).then(response => {
    const copy = response.clone();
    caches.open(CACHE).then(cache => cache.put(event.request, copy));
    return response;
  }).catch(async () => {
    const hit = await caches.match(event.request);
    if (hit) return hit;
    if (event.request.mode === "navigate") return caches.match("/");
    return Response.error();
  }));
});
