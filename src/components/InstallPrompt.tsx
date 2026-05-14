"use client";

import { useEffect, useState } from "react";
import { Download } from "lucide-react";

export default function InstallPrompt() {
    const [deferredPrompt, setDeferredPrompt] = useState<any>(null);
    const [isInstalled, setIsInstalled] = useState(false);

    useEffect(() => {
        // Check if already running as installed PWA
        if (window.matchMedia("(display-mode: standalone)").matches) {
            setIsInstalled(true);
            return;
        }

        // Capture the install prompt event
        const handler = (e: Event) => {
            e.preventDefault();
            setDeferredPrompt(e);
            console.log("[PWA] Install prompt captured");
        };

        // Listen for successful install
        const installedHandler = () => {
            setIsInstalled(true);
            setDeferredPrompt(null);
            console.log("[PWA] App installed successfully");
        };

        window.addEventListener("beforeinstallprompt", handler);
        window.addEventListener("appinstalled", installedHandler);

        return () => {
            window.removeEventListener("beforeinstallprompt", handler);
            window.removeEventListener("appinstalled", installedHandler);
        };
    }, []);

    const handleInstallClick = async () => {
        if (!deferredPrompt) {
            // Check if secure context is the issue
            const isSecure = window.isSecureContext;
            const currentUrl = window.location.href;

            if (!isSecure) {
                alert(
                    `⚠️ Install Blocked by Browser\n\n` +
                    `Reason: Not Secure (HTTP)\n\n` +
                    `FIX:\n` +
                    `1. Go to chrome://flags\n` +
                    `2. Enable "Insecure origins treated as secure"\n` +
                    `3. Add this URL: ${window.location.origin}\n` +
                    `4. Restart Chrome.\n\n` +
                    `After this, the button will work!`
                );
                return;
            }

            alert(
                "App is ready but browser blocked auto-install.\n\n" +
                "• Tap ⋮ menu -> 'Install App'\n" +
                "• Or 'Add to Home Screen'"
            );
            return;
        }

        deferredPrompt.prompt();

        const { outcome } = await deferredPrompt.userChoice;
        console.log(`[PWA] Install response: ${outcome}`);
        if (outcome === "accepted") {
            setIsInstalled(true);
        }
        setDeferredPrompt(null);
    };

    // Hide completely if already installed
    if (isInstalled) return null;

    return (
        <button
            onClick={handleInstallClick}
            className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-cyan-500/20 to-purple-500/20 
                 border border-cyan-500/50 hover:bg-cyan-500/30 text-cyan-400 font-medium rounded-lg 
                 transition-all hover:scale-105 active:scale-95 shadow-[0_0_15px_rgba(6,182,212,0.15)]"
        >
            <Download className="w-4 h-4" />
            <span>Install App</span>
        </button>
    );
}
