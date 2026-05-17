"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { ArrowRight, Globe, CheckCircle2, Lock, Cpu } from "lucide-react";

export default function Home() {
  return (
    <main className="relative min-h-screen overflow-hidden">
      <div className="relative z-10 pt-44 pb-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
        {/* Hero Section */}
        <div className="text-center max-w-4xl mx-auto mb-20 pointer-events-none"> {/* pointer-events-none lets clicks pass to 3D agents */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="pointer-events-auto"
          >
            <h1 className="text-6xl md:text-8xl font-black tracking-tighter mb-6 leading-tight text-transparent bg-clip-text bg-gradient-to-b from-white via-white to-white/50 drop-shadow-2xl">
              TRUTH <span className="text-cyan-400">X</span>
            </h1>

            <p className="text-xl md:text-2xl text-slate-400 mb-10 max-w-2xl mx-auto leading-relaxed">
              Advanced <span className="text-white font-bold">AI Media Verification</span> & Source Intelligence.
              Grounded OSINT analysis for the age of misinformation.
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/analyze"
                className="group relative px-8 py-4 bg-cyan-500 hover:bg-cyan-400 text-black font-black text-lg rounded-xl transition-all shadow-[0_0_40px_-10px_rgba(6,182,212,0.5)] hover:shadow-[0_0_60px_-10px_rgba(6,182,212,0.7)] overflow-hidden"
              >
                <div className="absolute inset-0 bg-white/20 translate-y-full group-hover:translate-y-0 transition-transform duration-300" />
                <span className="relative flex items-center gap-2">
                  START ANALYSIS <ArrowRight className="w-5 h-5" />
                </span>
              </Link>

              <Link
                href="/intel"
                className="px-8 py-4 bg-white/5 hover:bg-white/10 text-white font-bold text-lg rounded-xl border border-white/10 hover:border-white/30 transition-all backdrop-blur-md"
              >
                Source Check
              </Link>
            </div>
          </motion.div>
        </div>

        {/* BENTO GRID Features */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 auto-rows-[240px] pointer-events-auto">
          {/* Card 1: Large - Core Tech */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            className="md:col-span-2 glass-card rounded-3xl p-8 relative overflow-hidden group"
          >
            <div className="absolute top-0 right-0 w-64 h-64 bg-cyan-500/20 rounded-full blur-[80px] -translate-y-1/2 translate-x-1/2 group-hover:bg-cyan-500/30 transition-colors" />
            <div className="relative z-10 h-full flex flex-col justify-between">
              <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center mb-4">
                <Cpu className="w-6 h-6 text-cyan-400" />
              </div>
              <div>
                <h3 className="text-2xl font-bold text-white mb-2">Neural Intelligence Core</h3>
                <p className="text-slate-400 max-w-md">Multi-model architecture utilizing Whisper transcription and Mistral reasoning to detect cross-modal inconsistencies.</p>
              </div>
            </div>
          </motion.div>

          {/* Card 2: Vertical - Privacy */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
            className="md:row-span-2 glass-card rounded-3xl p-8 relative overflow-hidden group border-l-4 border-l-purple-500"
          >
            <div className="absolute bottom-0 left-0 w-full h-1/2 bg-gradient-to-t from-purple-900/40 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
            <div className="relative z-10 h-full flex flex-col">
              <div className="w-12 h-12 rounded-2xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center mb-auto">
                <Lock className="w-6 h-6 text-purple-400" />
              </div>
              <h3 className="text-2xl font-bold text-white mb-2 mt-4">Forensic Privacy</h3>
              <p className="text-slate-400 mb-6">Content is processed in isolated environments and never stored. Intelligence is ephemeral and secure.</p>
              <div className="mt-auto">
                <div className="flex items-center gap-2 text-sm text-purple-300 font-mono">
                  <CheckCircle2 className="w-4 h-4" /> Secure Transmission
                </div>
                <div className="flex items-center gap-2 text-sm text-purple-300 font-mono mt-2">
                  <CheckCircle2 className="w-4 h-4" /> Automated Cleanup
                </div>
              </div>
            </div>
          </motion.div>

          {/* Card 3: Small - Live */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ delay: 0.2 }}
            className="glass-card rounded-3xl p-8 relative overflow-hidden group bg-gradient-to-br from-white/5 to-transparent"
          >
            <div className="relative z-10">
              <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mb-4">
                <Globe className="w-6 h-6 text-emerald-400" />
              </div>
              <h3 className="text-xl font-bold text-white mb-1">OSINT Retrieval</h3>
              <p className="text-slate-400 text-sm">Real-time source contradiction analysis via Tavily search.</p>
            </div>
          </motion.div>

          {/* Card 4: Wide - Stats */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ delay: 0.3 }}
            className="md:col-span-2 glass-card rounded-3xl p-8 relative overflow-hidden flex items-center justify-between"
          >
            <div>
              <h3 className="text-4xl font-black text-white mb-1">1.42K+</h3>
              <p className="text-cyan-400 font-bold tracking-wide text-sm">THREATS ANALYZED</p>
            </div>
            <div className="w-16 h-16 rounded-full border-4 border-cyan-500/20 border-t-cyan-400 animate-spin" />
          </motion.div>
        </div>
      </div>
    </main>
  );
}
