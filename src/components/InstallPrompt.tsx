"use client";

import { useEffect, useState } from "react";
import { useToast } from "@/context/ToastContext";
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

    const { showToast } = useToast();

    const handleInstallClick = async () => {
        if (!deferredPrompt) {
            // Check if secure context is the issue
            const isSecure = window.isSecureContext;
            const currentUrl = window.location.href;

            if (!isSecure) {
                showToast("Install blocked: site not served over HTTPS. See console for instructions.", "error");
                console.info(`PWA install note: insecure context. Suggested steps:\n1. Go to chrome://flags\n2. Enable 'Insecure origins treated as secure'\n3. Add origin: ${window.location.origin}\n4. Restart browser.`);
                return;
            }

            showToast("App install is available via browser menu: 'Install App' or 'Add to Home Screen'", "info");
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
