"use client";

import { useState, useRef, useCallback } from "react";
import { motion } from "framer-motion";
import { useToast } from "@/context/ToastContext";
import {
  Upload,
  Link as LinkIcon,
  FileText,
  Image,
  AlertCircle,
  Search,
  Video,
} from "lucide-react";

type InputTab = "headline" | "url";

const tabs: { id: InputTab; label: string; icon: any; color: string }[] = [
  { id: "headline", label: "Article/Headline", icon: FileText, color: "#00d4ff" },
  { id: "url", label: "URL", icon: LinkIcon, color: "#00ff9d" },
];

interface VerificationInputProps {
  onSubmit: (data: {
    type: InputTab;
    content: string;
    file?: File;
  }) => void;
  isLoading?: boolean;
}

export default function VerificationInput({ onSubmit, isLoading = false }: VerificationInputProps) {
  const [activeTab, setActiveTab] = useState<InputTab>("headline");
  const [headlineText, setHeadlineText] = useState("");
  const [urlText, setUrlText] = useState("");
  const { showToast } = useToast();

  const handleSubmit = () => {
    let content = "";
    switch (activeTab) {
      case "headline":
        content = headlineText.trim();
        break;
      case "url":
        content = urlText.trim();
        break;
    }

    if (!content) {
      showToast("Please provide content to verify", "error");
      return;
    }

    onSubmit({
      type: activeTab,
      content,
    });
  };

  const isValid = () => {
    switch (activeTab) {
      case "headline":
        return headlineText.trim().length > 10;
      case "url":
        return urlText.trim().length > 0;
    }
  };

  return (
    <div className="space-y-6">
      {/* Tab Navigation */}
      <div className="flex flex-wrap gap-3">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => {
                setActiveTab(tab.id);
              }}
              className={`group relative px-4 py-2 rounded-xl font-semibold transition-all duration-300 ${
                isActive
                  ? "bg-white/15 text-white border border-white/30"
                  : "bg-white/5 text-slate-400 border border-white/10 hover:border-white/20 hover:text-white"
              }`}
            >
              <span className="flex items-center gap-2">
                <Icon className="w-4 h-4" />
                {tab.label}
              </span>
              {isActive && (
                <div
                  className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-cyan-500 via-cyan-400 to-transparent rounded-full"
                  style={{ background: `linear-gradient(90deg, ${tab.color}, transparent)` }}
                />
              )}
            </button>
          );
        })}
      </div>

      {/* Input Area */}
      <motion.div
        key={activeTab}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="space-y-4"
      >
        {activeTab === "headline" && (
          <div className="space-y-3">
            <label className="block text-sm font-medium text-white">
              Article Headline or Claim
            </label>
            <textarea
              value={headlineText}
              onChange={(e) => setHeadlineText(e.target.value)}
              placeholder="Paste an article headline or controversial claim you want to verify..."
              className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 focus:ring-2 focus:ring-cyan-500/20 resize-none"
              rows={4}
            />
            <div className="text-xs text-slate-400">
              {headlineText.length} characters
            </div>
          </div>
        )}

        {activeTab === "url" && (
          <div className="space-y-3">
            <label className="block text-sm font-medium text-white">
              Article or Video URL
            </label>
            <input
              type="url"
              value={urlText}
              onChange={(e) => setUrlText(e.target.value)}
              placeholder="https://example.com/article-or-video"
              className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 focus:ring-2 focus:ring-cyan-500/20"
            />
            <div className="text-xs text-slate-400 flex items-center gap-2">
              <AlertCircle className="w-3 h-3" />
              We'll extract the transcript or text content for investigative intelligence
            </div>
          </div>
        )}
      </motion.div>

      {/* Verification Info */}
      <div className="bg-cyan-500/10 border border-cyan-500/20 rounded-xl p-4 flex items-start gap-3">
        <AlertCircle className="w-5 h-5 text-cyan-400 mt-0.5 flex-shrink-0" />
        <div className="text-sm text-slate-300">
          <div className="font-semibold text-white mb-1">OSINT Verification</div>
          <p>
            This will trigger our advanced open-source intelligence pipeline including
            Tavily retrieval, forensic analysis, contradiction detection, and source verification.
          </p>
        </div>
      </div>

      {/* Submit Button */}
      <motion.button
        whileHover={{ scale: isValid() && !isLoading ? 1.02 : 1 }}
        whileTap={{ scale: isValid() && !isLoading ? 0.98 : 1 }}
        onClick={handleSubmit}
        disabled={!isValid() || isLoading}
        className={`w-full py-4 px-6 rounded-xl font-bold transition-all duration-300 flex items-center justify-center gap-2 ${
          isValid() && !isLoading
            ? "bg-cyan-500 hover:bg-cyan-400 text-black shadow-[0_0_40px_-10px_rgba(6,182,212,0.5)] hover:shadow-[0_0_60px_-10px_rgba(6,182,212,0.7)]"
            : "bg-slate-600/50 text-slate-400 cursor-not-allowed"
        }`}
      >
        <Search className="w-5 h-5" />
        {isLoading ? "Verifying Source..." : "Start Source Check"}
      </motion.button>
    </div>
  );
}
