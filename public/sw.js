/// <reference lib="webworker" />

const sw = self as unknown as ServiceWorkerGlobalScope;

// ── Install & Activate ──────────────────────────────────────────────────
sw.addEventListener("install", () => sw.skipWaiting());
sw.addEventListener("activate", (e) => e.waitUntil(sw.clients.claim()));

// ── Fetch Handler (Required for PWA Installability) ─────────────────────
sw.addEventListener("fetch", (event) => {
    // ⚠️ CRITICAL: Do NOT intercept POST requests (Share Target).
    // Allowing the SW to handle POST with large bodies often fails (stream error / null is unreachable).
    if (event.request.method === "POST") {
        return;
    }

    // Simple network-only strategy for GET
    event.respondWith(fetch(event.request));
});

// ── Push Notification (for future server-sent pushes) ───────────────────
sw.addEventListener("push", (event) => {
    const data = event.data?.json() ?? {};
    const title = data.title || "Truth X — Analysis Complete";
    const options: NotificationOptions = {
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

// ── Notification Click ──────────────────────────────────────────────────
sw.addEventListener("notificationclick", (event) => {
    event.notification.close();
    const url = event.notification.data || "/shared";

    event.waitUntil(
        sw.clients.matchAll({ type: "window" }).then((clientList) => {
            // Focus existing window if open
            for (const client of clientList) {
                if (client.url.includes(url) && "focus" in client) {
                    return client.focus();
                }
            }
            // Otherwise open new window
            return sw.clients.openWindow(url);
        })
    );
});

// ── Background Sync (for offline shares) ────────────────────────────────
sw.addEventListener("sync", (event) => {
    if ((event as any).tag === "share-analysis") {
        // Future: retry failed share-target uploads when back online
        console.log("[SW] Background sync triggered for share-analysis");
    }
});
