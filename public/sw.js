const sw = self;

sw.addEventListener("install", () => {
    sw.skipWaiting();
});

sw.addEventListener("activate", (event) => {
    event.waitUntil(sw.clients.claim());
});

sw.addEventListener("fetch", (event) => {
    if (event.request.method !== "GET") {
        return;
    }

    event.respondWith(fetch(event.request));
});

sw.addEventListener("push", (event) => {
    let data = {};
    if (event.data) {
        try {
            data = event.data.json();
        } catch {
            data = {};
        }
    }

    const title = data.title || "Truth X - Analysis Complete";
    const options = {
        body: data.body || "Your content has been analyzed.",
        icon: "/icon-192.png",
        badge: "/icon-192.png",
        tag: data.tag || "analysis-result",
        data: data.url || "/shared",
        vibrate: [200, 100, 200],
        actions: [
            { action: "view", title: "View Results" },
            { action: "dismiss", title: "Dismiss" },
        ],
    };

    event.waitUntil(sw.registration.showNotification(title, options));
});

sw.addEventListener("notificationclick", (event) => {
    event.notification.close();
    const url = event.notification.data || "/shared";

    event.waitUntil(
        sw.clients.matchAll({ type: "window" }).then((clientList) => {
            for (const client of clientList) {
                if (client.url.includes(url) && "focus" in client) {
                    return client.focus();
                }
            }
            return sw.clients.openWindow(url);
        })
    );
});

sw.addEventListener("sync", (event) => {
    if (event.tag === "share-analysis") {
        console.info("[SW] Background sync triggered for share-analysis");
    }
});
