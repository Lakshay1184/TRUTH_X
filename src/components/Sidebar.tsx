"use client";

import { useState, useEffect } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  Home,
  Shield,
  Clock,
  Video,
  Info,
  LogOut,
  ChevronLeft,
  ChevronRight,
  User,
  Settings,
  Download,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";

export default function Sidebar() {
  const pathname = usePathname();
  const [isCollapsed, setIsCollapsed] = useState(true);
  const { user, logout, isAuthenticated } = useAuth();
  const [mounted, setMounted] = useState(false);
  const { showToast } = useToast();
  const [deferredPrompt, setDeferredPrompt] = useState<any>(null);
  const [isInstalled, setIsInstalled] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

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
    };

    const installedHandler = () => {
      setIsInstalled(true);
      setDeferredPrompt(null);
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
      const isSecure = window.isSecureContext;
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
    if (outcome === "accepted") {
      setIsInstalled(true);
    }
    setDeferredPrompt(null);
  };

  // Don't render anything until client-side hydration is complete
  if (!mounted) return null;

  // Don't render sidebar if not authenticated
  if (!isAuthenticated) return null;

  const links = [
    { href: "/", label: "Home", icon: Home },
    { href: "/analyze", label: "Analyze", icon: Shield },
    { href: "/intel", label: "Source Check", icon: Video },
    { href: "/history", label: "History", icon: Clock },
    { href: "/live", label: "Live", icon: Info },
  ];

  return (
    <motion.aside
      initial={{ width: 280, x: 20, opacity: 0 }}
      animate={{
        width: isCollapsed ? 88 : 280,
        x: 0,
        opacity: 1
      }}
      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      className="fixed right-6 top-6 bottom-6 z-50 flex flex-col"
    >
      <div className="flex-1 glass-card rounded-[32px] flex flex-col overflow-hidden border border-white/10 shadow-[0_0_50px_-12px_rgba(0,0,0,0.5)] backdrop-blur-3xl bg-black/40 relative">

        {/* Logo / Toggle Area */}
        <div className="p-6 flex items-center gap-4 relative">
          <button 
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="w-12 h-12 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center shrink-0 shadow-[0_0_20px_-5px_rgba(34,211,238,0.4)] hover:bg-cyan-500/20 hover:border-cyan-500/40 transition-all duration-500 group/logo"
          >
            <Shield className="w-6 h-6 text-cyan-400 group-hover/logo:scale-110 transition-transform duration-500" />
            <div className="absolute inset-0 bg-cyan-400/10 blur-xl opacity-50 rounded-2xl" />
          </button>

          <AnimatePresence mode="wait">
            {!isCollapsed && (
              <motion.div
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                className="flex flex-col pointer-events-none"
              >
                <span className="font-black text-xl text-white tracking-tighter">TRUTH <span className="text-cyan-400">X</span></span>
                <span className="text-[10px] text-cyan-500/60 font-mono tracking-widest uppercase font-bold">AI Defense</span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Navigation */}
        <AnimatePresence>
          {!isCollapsed && (
            <motion.nav 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex-1 px-4 py-6 space-y-2 overflow-y-auto custom-scrollbar"
            >
              {links.map((link) => {
                const Icon = link.icon;
                const isActive = pathname === link.href;

                return (
                  <Link key={link.href} href={link.href}>
                    <div className="relative group">
                      {/* Active Glow Background */}
                      {isActive && (
                        <motion.div
                          layoutId="activeTab"
                          className="absolute inset-0 bg-cyan-500/10 rounded-2xl border border-cyan-500/20"
                        />
                      )}

                      <div
                        className={`relative flex items-center gap-4 px-5 py-4 rounded-2xl transition-all duration-300 ${isActive ? "text-white" : "text-slate-500 hover:text-white hover:bg-white/5"
                          }`}
                      >
                        <Icon
                          className={`w-5 h-5 shrink-0 transition-colors duration-300 ${isActive ? "text-cyan-400" : "group-hover:text-cyan-400/80"
                            }`}
                        />

                        <span className="font-bold text-sm uppercase tracking-widest whitespace-nowrap">
                          {link.label}
                        </span>

                        {/* Active Indicator Dot */}
                        {isActive && (
                          <motion.div
                            initial={{ scale: 0 }}
                            animate={{ scale: 1 }}
                            className="absolute right-4 w-1.5 h-1.5 rounded-full bg-cyan-400 shadow-[0_0_8px_0_rgba(34,211,238,0.8)]"
                          />
                        )}
                      </div>
                    </div>
                  </Link>
                );
              })}
            </motion.nav>
          )}
        </AnimatePresence>

        {/* User Profile & Footer */}
        <AnimatePresence>
          {!isCollapsed && (
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 20 }}
              className="p-4 mt-auto border-t border-white/5 bg-black/20 space-y-3"
            >
              <div className="flex items-center gap-3 p-3 rounded-2xl bg-white/5 border border-white/5">
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-slate-700 to-slate-800 flex items-center justify-center shrink-0 border border-white/10 shadow-inner">
                  <User className="w-5 h-5 text-slate-300" />
                </div>

                <div className="flex-1 min-w-0">
                  <p className="text-xs font-bold text-white truncate">{user?.user_metadata?.full_name || user?.email || "Agent"}</p>
                  <div className="flex items-center gap-1.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse" />
                    <span className="text-[10px] text-cyan-500/80 font-bold uppercase tracking-tighter">Authorized</span>
                  </div>
                </div>

                <button
                  onClick={logout}
                  className="p-2 rounded-xl hover:bg-red-500/20 text-slate-500 hover:text-red-400 transition-all border border-transparent hover:border-red-500/20"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>

              {/* Install App Button */}
              {!isInstalled && (deferredPrompt || window.isSecureContext) && (
                <button
                  onClick={handleInstallClick}
                  className="w-full flex items-center gap-3 px-4 py-3 rounded-2xl bg-gradient-to-r from-cyan-500/10 to-blue-500/10 border border-cyan-500/20 hover:border-cyan-500/40 text-cyan-400 hover:text-cyan-300 font-bold uppercase tracking-widest text-[10px] transition-all"
                >
                  <Download className="w-4 h-4" />
                  <span>Offline Terminal</span>
                </button>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Minimal Tooltip when collapsed */}
        {isCollapsed && (
          <div className="flex-1 flex flex-col items-center justify-center gap-6 py-10">
            {links.map((link) => (
               <Link key={link.href} href={link.href} className={`p-3 rounded-2xl transition-all ${pathname === link.href ? "bg-cyan-400/10 text-cyan-400 border border-cyan-400/20 shadow-[0_0_15px_-5px_rgba(34,211,238,0.4)]" : "text-slate-600 hover:text-slate-300"}`}>
                 <link.icon className="w-6 h-6" />
               </Link>
            ))}
          </div>
        )}
      </div>
    </motion.aside>
  );
}
