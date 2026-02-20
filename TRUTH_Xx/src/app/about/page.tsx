"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import {
  Shield,
  Zap,
  Eye,
  Users,
  Globe,
  Lock,
  AlertTriangle,
  CheckCircle,
  Phone,
  Newspaper,
  Baby,
  ArrowRight,
  Cpu,
  Database,
  Network,
} from "lucide-react";

const techStack = [
  { name: "FaceForensics++ Neural Net", role: "Video deepfake detection", icon: Cpu, color: "#00d4ff" },
  { name: "WavLM Voice Classifier", role: "Synthetic audio detection", icon: Network, color: "#00ff9d" },
  { name: "GPT-Origin Detector", role: "AI text identification", icon: Database, color: "#a855f7" },
  { name: "ELA & GAN Fingerprinting", role: "Image manipulation detection", icon: Eye, color: "#ffd700" },
  { name: "Temporal Graph Analysis", role: "Content lifecycle tracking", icon: Globe, color: "#ff6b35" },
  { name: "Metadata Forensics Engine", role: "File header & EXIF analysis", icon: Lock, color: "#00d4ff" },
];

const howItWorks = [
  {
    step: "01",
    title: "Upload or Input Content",
    desc: "Drop a video, audio clip, image, paste text, or enter a URL. TRUTH X accepts all major formats.",
    color: "#00d4ff",
  },
  {
    step: "02",
    title: "AI Analysis Runs Instantly",
    desc: "Multiple specialized AI models simultaneously analyze your content for synthetic patterns, GAN artifacts, and manipulation signals.",
    color: "#00ff9d",
  },
  {
    step: "03",
    title: "Authenticity Score Generated",
    desc: "You receive a clear percentage score showing how authentic the content is, with a risk level (Low/Medium/High) badge.",
    color: "#a855f7",
  },
  {
    step: "04",
    title: "Detailed Explanation Provided",
    desc: "TRUTH X explains exactly why content was flagged — in plain English. No technical jargon. You understand what's wrong and why.",
    color: "#ffd700",
  },
  {
    step: "05",
    title: "Lifecycle Timeline Shown",
    desc: "See the content's history: when it was created, edited, and redistributed — and where manipulation likely occurred.",
    color: "#ff6b35",
  },
];

export default function AboutPage() {
  return (
    <div className="min-h-screen">
      <div className="pt-24 pb-16">
        {/* Hero */}
        <section className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center mb-20">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[#00d4ff]/10 border border-[#00d4ff]/20 mb-8">
              <Shield className="w-4 h-4 text-[#00d4ff]" />
              <span className="text-[#00d4ff] text-sm font-medium">About TRUTH X</span>
            </div>
            <h1 className="text-5xl font-black text-white mb-6 leading-tight">
              Fighting AI Deception<br />
              <span className="text-gradient-cyan">For Everyone</span>
            </h1>
            <p className="text-[#b0b0b0] text-lg leading-relaxed max-w-2xl mx-auto">
              TRUTH X was built to give every person — regardless of technical skill — the ability to detect
              AI manipulation, deepfake fraud, and misinformation before it causes harm.
            </p>
          </motion.div>
        </section>

        {/* Mission */}
        <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 mb-20">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              {
                icon: AlertTriangle,
                title: "The Problem",
                color: "#ff4444",
                points: [
                  "AI deepfake videos now indistinguishable to the human eye",
                  "Voice cloning used in billion-dollar phone scams",
                  "AI-generated misinformation spreads 6x faster than truth",
                  "60% of viral content contains manipulated or false claims",
                ],
              },
              {
                icon: Shield,
                title: "Our Mission",
                color: "#00d4ff",
                points: [
                  "Make AI detection accessible to non-technical users",
                  "Protect families from phone scams and deepfake fraud",
                  "Help journalists verify media before publishing",
                  "Restore trust in digital communication",
                ],
              },
              {
                icon: CheckCircle,
                title: "Our Approach",
                color: "#00ff9d",
                points: [
                  "Multiple specialized AI models working in parallel",
                  "Explainable results in plain, simple language",
                  "No data stored — privacy-first architecture",
                  "Continuous model updates against new threats",
                ],
              },
            ].map((card, i) => {
              const Icon = card.icon;
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 30 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.1 }}
                  className="glass rounded-xl p-6"
                >
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center mb-4"
                    style={{ background: `${card.color}15`, border: `1px solid ${card.color}30` }}
                  >
                    <Icon className="w-5 h-5" style={{ color: card.color }} />
                  </div>
                  <h3 className="text-white font-bold text-lg mb-4">{card.title}</h3>
                  <ul className="space-y-2">
                    {card.points.map((point, j) => (
                      <li key={j} className="flex items-start gap-2 text-[#b0b0b0] text-sm">
                        <span className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0" style={{ background: card.color }} />
                        {point}
                      </li>
                    ))}
                  </ul>
                </motion.div>
              );
            })}
          </div>
        </section>

        {/* Who uses it */}
        <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 mb-20">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-black text-white mb-3">Who Uses TRUTH X</h2>
            <p className="text-[#777777]">Designed for real-world users facing real threats</p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            {[
              {
                icon: Baby,
                title: "Parents & Families",
                color: "#00ff9d",
                desc: "Parents can check if that viral WhatsApp video is real, whether a voice call claiming to be their child is genuine, or if a social media post is AI-generated misinformation before believing or sharing it.",
                use: "Most common use: Scam call verification",
              },
              {
                icon: Newspaper,
                title: "Journalists & Researchers",
                color: "#00d4ff",
                desc: "Fact-checkers and reporters can verify photos, video footage, and articles before publishing. TRUTH X provides detailed forensic evidence that can be cited in investigations.",
                use: "Most common use: Media authenticity verification",
              },
              {
                icon: Phone,
                title: "Scam Victims & At-Risk Users",
                color: "#a855f7",
                desc: "Anyone receiving suspicious calls, emails, or videos — especially the elderly — can use TRUTH X to instantly check if a voice, face, or claim is AI-generated as part of a fraud attempt.",
                use: "Most common use: Voice cloning scam detection",
              },
            ].map((user, i) => {
              const Icon = user.icon;
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 30 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.1 }}
                  className="glass rounded-xl p-6"
                >
                  <div
                    className="w-12 h-12 rounded-xl flex items-center justify-center mb-4"
                    style={{ background: `${user.color}15`, border: `1px solid ${user.color}30` }}
                  >
                    <Icon className="w-6 h-6" style={{ color: user.color }} />
                  </div>
                  <h3 className="text-white font-bold text-lg mb-3">{user.title}</h3>
                  <p className="text-[#777777] text-sm leading-relaxed mb-4">{user.desc}</p>
                  <div
                    className="text-xs px-3 py-1.5 rounded-full border"
                    style={{ color: user.color, background: `${user.color}10`, borderColor: `${user.color}30` }}
                  >
                    {user.use}
                  </div>
                </motion.div>
              );
            })}
          </div>
        </section>

        {/* How it works */}
        <section className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 mb-20">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-black text-white mb-3">How TRUTH X Works</h2>
            <p className="text-[#777777]">From upload to verified result in under 5 seconds</p>
          </div>
          <div className="space-y-4">
            {howItWorks.map((step, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="flex gap-6 glass rounded-xl p-5"
              >
                <div
                  className="text-3xl font-black shrink-0 w-12 h-12 rounded-xl flex items-center justify-center"
                  style={{ color: step.color, background: `${step.color}10`, border: `1px solid ${step.color}20` }}
                >
                  <span className="text-sm">{step.step}</span>
                </div>
                <div>
                  <h3 className="text-white font-bold mb-1">{step.title}</h3>
                  <p className="text-[#777777] text-sm leading-relaxed">{step.desc}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </section>

        {/* Tech stack */}
        <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 mb-20">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-black text-white mb-3">Detection Technology</h2>
            <p className="text-[#777777]">Six specialized AI models running simultaneously on every analysis</p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {techStack.map((tech, i) => {
              const Icon = tech.icon;
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.07 }}
                  className="glass rounded-xl p-5 flex items-start gap-4"
                >
                  <div
                    className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
                    style={{ background: `${tech.color}15`, border: `1px solid ${tech.color}30` }}
                  >
                    <Icon className="w-5 h-5" style={{ color: tech.color }} />
                  </div>
                  <div>
                    <p className="text-white font-medium text-sm">{tech.name}</p>
                    <p className="text-[#777777] text-xs mt-0.5">{tech.role}</p>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </section>

        {/* Privacy */}
        <section className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 mb-20">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="glass rounded-2xl p-8 border border-[#00d4ff]/10"
          >
            <div className="flex items-center gap-3 mb-6">
              <Lock className="w-6 h-6 text-[#00d4ff]" />
              <h2 className="text-2xl font-black text-white">Privacy & Security</h2>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {[
                { text: "All uploaded content is deleted immediately after analysis — nothing is stored", ok: true },
                { text: "No user accounts or personal data required to use TRUTH X", ok: true },
                { text: "Analysis runs in isolated sandboxed environments", ok: true },
                { text: "No content is shared with advertisers or third parties", ok: true },
                { text: "End-to-end encrypted transmission for all uploads", ok: true },
                { text: "Open audit logs available for security researchers", ok: true },
              ].map((item, i) => (
                <div key={i} className="flex items-start gap-3">
                  <CheckCircle className="w-4 h-4 text-[#00ff9d] mt-0.5 shrink-0" />
                  <p className="text-[#b0b0b0] text-sm">{item.text}</p>
                </div>
              ))}
            </div>
          </motion.div>
        </section>

        {/* CTA */}
        <section className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-3xl font-black text-white mb-4">
              Ready to Verify the Truth?
            </h2>
            <p className="text-[#777777] mb-8">
              No signup. No cost. Just upload and see the truth.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link
                href="/analyze"
                className="group flex items-center justify-center gap-3 px-8 py-4 rounded-xl bg-[#00d4ff] text-[#000000] font-bold text-lg hover:bg-[#00d4ff]/90 transition-all glow-cyan"
              >
                <Shield className="w-5 h-5" />
                Start Free Analysis
                <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </Link>
              <Link
                href="/live"
                className="flex items-center justify-center gap-3 px-8 py-4 rounded-xl border border-[#222222] text-[#b0b0b0] font-bold text-lg hover:border-[#00d4ff]/30 hover:text-white transition-all"
              >
                <Zap className="w-5 h-5" />
                Try Live Detection
              </Link>
            </div>
          </motion.div>
        </section>
      </div>

      {/* Footer */}
      <footer className="border-t border-[#222222] py-8 mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-[#00d4ff]" />
            <span className="text-white font-bold">TRUTH X</span>
            <span className="text-[#777777] text-sm">— AI Deepfake & Misinformation Detection</span>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-[#777777] text-sm">v2.4.1</span>
            <span className="text-[#222222]">|</span>
            <span className="text-[#777777] text-sm">Frontend demonstration</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
