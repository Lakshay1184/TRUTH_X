"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Shield, Zap, History, Info, Menu, X, ChevronRight } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";

const navLinks = [
    { name: "Live Detection", href: "/live", icon: Zap, color: "#ff4444" },
    { name: "History", href: "/history", icon: History, color: "#00d4ff" },
    { name: "Technology", href: "/about", icon: Info, color: "#a855f7" },
];

export default function Navbar() {
    const pathname = usePathname();
    const { user, logout } = useAuth();
    const [isOpen, setIsOpen] = useState(false);
    const [hidden, setHidden] = useState(false);
    const lastScrollY = useRef(0);

    useEffect(() => {
        const onScroll = () => {
            const y = window.scrollY;
            // Hide when scrolling down past 60px, show when scrolling up
            if (y > lastScrollY.current && y > 60) {
                setHidden(true);
                setIsOpen(false); // close mobile menu too
            } else {
                setHidden(false);
            }
            lastScrollY.current = y;
        };
        window.addEventListener("scroll", onScroll, { passive: true });
        return () => window.removeEventListener("scroll", onScroll);
    }, []);

    // Hide navbar on auth pages
    if (pathname === "/login" || pathname === "/signup") return null;

    return (
        <>
            <motion.nav
                initial={{ y: -100, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                className={`fixed top-0 left-0 right-0 z-50 px-4 py-4 md:px-6 transition-transform duration-300 ${hidden ? "-translate-y-full" : "translate-y-0"}`}
            >
                <div className="max-w-7xl mx-auto flex items-center justify-between p-4 rounded-2xl glass-panel relative overflow-hidden">
                    {/* Animated Glow Line */}
                    <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-cyan-500/50 to-transparent" />

                    {/* Logo */}
                    <Link href="/" className="flex items-center gap-2 group relative z-10">
                        <div className="relative w-10 h-10 flex items-center justify-center bg-cyan-500/10 rounded-xl group-hover:bg-cyan-500/20 transition-all duration-300 group-hover:scale-110">
                            <Shield className="w-6 h-6 text-cyan-400 group-hover:rotate-12 transition-transform duration-300" />
                            <div className="absolute inset-0 bg-cyan-400/20 blur-md opacity-0 group-hover:opacity-100 transition-opacity" />
                        </div>
                        <div className="flex flex-col">
                            <span className="text-xl font-black tracking-tight text-white leading-none">
                                TRUTH <span className="text-cyan-400">X</span>
                            </span>
                            <span className="text-[10px] font-bold text-cyan-500/60 tracking-widest uppercase">AI Defense System</span>
                        </div>
                    </Link>

                    {/* Desktop Nav */}
                    <div className="hidden md:flex items-center gap-2 bg-black/20 rounded-full p-1 border border-white/5 backdrop-blur-md">
                        {navLinks.map((link) => {
                            const Icon = link.icon;
                            const isActive = pathname === link.href;
                            return (
                                <Link
                                    key={link.href}
                                    href={link.href}
                                    className="relative px-6 py-2.5 rounded-full text-sm font-bold transition-all duration-300 group overflow-hidden"
                                >
                                    {isActive && (
                                        <motion.div
                                            layoutId="nav-pill"
                                            className="absolute inset-0 bg-white/10"
                                            style={{ borderRadius: 9999 }}
                                            transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                                        />
                                    )}
                                    <span className={`relative z-10 flex items-center gap-2 ${isActive ? "text-white" : "text-slate-400 group-hover:text-white"}`}>
                                        <Icon className={`w-4 h-4 transition-colors ${isActive ? "text-cyan-400" : "text-slate-500 group-hover:text-cyan-400"}`} />
                                        {link.name}
                                    </span>
                                    {/* Hover Glow */}
                                    <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                                        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-700" />
                                    </div>
                                </Link>
                            );
                        })}
                    </div>

                    {/* Auth & Mobile Toggle */}
                    <div className="flex items-center gap-4">
                        {user ? (
                            <div className="flex items-center gap-4">
                                <div className="hidden sm:flex flex-col items-end">
                                    <span className="text-xs text-slate-400 font-medium">Logged in as</span>
                                    <span className="text-sm text-cyan-400 font-bold">{user.email.split('@')[0]}</span>
                                </div>
                                <button
                                    onClick={logout}
                                    className="px-5 py-2.5 rounded-xl bg-white/5 hover:bg-red-500/20 text-white text-sm font-bold transition-all border border-white/10 hover:border-red-500/50 hover:text-red-400"
                                >
                                    Sign Out
                                </button>
                            </div>
                        ) : (
                            <Link
                                href="/login"
                                className="group relative px-6 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-black text-sm font-black transition-all shadow-[0_0_20px_-5px_rgba(6,182,212,0.5)] hover:shadow-[0_0_30px_-5px_rgba(6,182,212,0.7)] active:scale-95 overflow-hidden"
                            >
                                <div className="absolute inset-0 bg-white/40 translate-y-full group-hover:translate-y-0 transition-transform duration-300" />
                                <span className="relative flex items-center gap-2">
                                    LOGIN
                                    <ChevronRight className="w-4 h-4" />
                                </span>
                            </Link>
                        )}

                        {/* Mobile Menu Toggle */}
                        <button
                            className="md:hidden p-2 text-slate-400 hover:text-white"
                            onClick={() => setIsOpen(!isOpen)}
                        >
                            {isOpen ? <X /> : <Menu />}
                        </button>
                    </div>
                </div>
            </motion.nav>

            {/* Mobile Menu Overlay */}
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        className="fixed top-24 left-4 right-4 z-40 md:hidden glass-panel rounded-2xl overflow-hidden border border-white/10"
                    >
                        <div className="p-4 flex flex-col gap-2">
                            {navLinks.map((link) => (
                                <Link
                                    key={link.href}
                                    href={link.href}
                                    onClick={() => setIsOpen(false)}
                                    className="flex items-center gap-3 p-4 rounded-xl hover:bg-white/5 text-slate-300 hover:text-white transition-all"
                                >
                                    <link.icon className="w-5 h-5 text-cyan-500" />
                                    <span className="font-bold">{link.name}</span>
                                </Link>
                            ))}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </>
    );
}
