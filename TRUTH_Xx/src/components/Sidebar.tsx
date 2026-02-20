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
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";

export default function Sidebar() {
  const pathname = usePathname();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const { user, logout, isAuthenticated } = useAuth();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Don't render anything until client-side hydration is complete
  if (!mounted) return null;

  // Don't render sidebar if not authenticated
  if (!isAuthenticated) return null;

  const links = [
    { href: "/", label: "Home", icon: Home },
    { href: "/analyze", label: "Analyze", icon: Shield },
    { href: "/history", label: "History", icon: Clock },
    { href: "/live", label: "Live Detection", icon: Video },
    { href: "/about", label: "About", icon: Info },
  ];

  return (
    <motion.aside
      initial={{ width: 260, x: -20, opacity: 0 }}
      animate={{
        width: isCollapsed ? 90 : 260,
        x: 0,
        opacity: 1
      }}
      transition={{ duration: 0.5, type: "spring", bounce: 0.1 }}
      className="fixed left-6 top-6 bottom-6 z-50 flex flex-col"
    >
      <div className="flex-1 glass-card rounded-3xl flex flex-col overflow-hidden border border-white/10 shadow-2xl backdrop-blur-3xl bg-black/40">

        {/* Logo Area */}
        <div className="p-6 flex items-center gap-4 relative">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-violet-600 to-indigo-600 flex items-center justify-center shrink-0 shadow-lg shadow-violet-500/20">
            <Shield className="w-6 h-6 text-white text-shadow" />
          </div>

          <AnimatePresence mode="wait">
            {!isCollapsed && (
              <motion.div
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                className="flex flex-col"
              >
                <span className="font-bold text-lg text-white tracking-wide">TRUTH X</span>
                <span className="text-[10px] text-cyan-400 font-mono tracking-wider uppercase">AI Verifier</span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-4 py-6 space-y-2 overflow-y-auto custom-scrollbar">
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
                      className="absolute inset-0 bg-white/5 rounded-xl border border-white/5 shadow-[0_0_20px_0_rgba(99,102,241,0.15)]"
                    />
                  )}

                  <div
                    className={`relative flex items-center gap-4 px-4 py-3.5 rounded-xl transition-all duration-300 ${isActive ? "text-white" : "text-slate-400 hover:text-white hover:bg-white/5"
                      }`}
                  >
                    <Icon
                      className={`w-5 h-5 shrink-0 transition-colors duration-300 ${isActive ? "text-cyan-400" : "group-hover:text-cyan-400/80"
                        }`}
                    />

                    <AnimatePresence mode="wait">
                      {!isCollapsed && (
                        <motion.span
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          exit={{ opacity: 0, x: -10 }}
                          className="font-medium whitespace-nowrap"
                        >
                          {link.label}
                        </motion.span>
                      )}
                    </AnimatePresence>

                    {/* Active Indicator Dot */}
                    {isActive && !isCollapsed && (
                      <motion.div
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        className="absolute right-3 w-1.5 h-1.5 rounded-full bg-cyan-400 shadow-[0_0_8px_0_rgba(34,211,238,0.8)]"
                      />
                    )}
                  </div>
                </div>
              </Link>
            );
          })}
        </nav>

        {/* User Profile & Footer */}
        <div className="p-4 mt-auto border-t border-white/5 bg-black/20">
          <div className={`flex items-center gap-3 p-3 rounded-xl transition-all ${!isCollapsed ? "bg-white/5 border border-white/5" : "justify-center"}`}>
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-slate-700 to-slate-800 flex items-center justify-center shrink-0 border border-white/10">
              <User className="w-5 h-5 text-slate-300" />
            </div>

            {!isCollapsed && (
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white truncate">{user?.email || "User"}</p>
                <div className="flex items-center gap-1.5">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  <span className="text-[10px] text-emerald-500 font-medium">Online</span>
                </div>
              </div>
            )}

            {!isCollapsed && (
              <button
                onClick={logout}
                className="p-1.5 rounded-lg hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
              >
                <LogOut className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Collapse Toggle */}
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="w-full mt-4 flex items-center justify-center p-2 rounded-lg hover:bg-white/5 text-slate-500 hover:text-white transition-colors"
          >
            {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </div>
      </div>
    </motion.aside>
  );
}
