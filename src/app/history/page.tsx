"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  Clock,
  Search,
  Filter,
  Video,
  Mic,
  FileText,
  Image,
  AlertTriangle,
  CheckCircle,
  XCircle,
  ChevronRight,
  SlidersHorizontal,
  Trash2,
  Shield,
} from "lucide-react";

type FilterStatus = "all" | "authentic" | "ai-generated" | "tampered" | "suspicious";
type SortBy = "date" | "score" | "risk";

interface HistoryItem {
  id: string;
  name: string;
  type: "video" | "audio" | "text" | "image";
  score: number;
  status: string;
  risk: "low" | "medium" | "high";
  date: string;
  time: string;
  summary: string;
}

const mockHistory: HistoryItem[] = [
  {
    id: "1",
    name: "viral_video_leak.mp4",
    type: "video",
    score: 18,
    status: "AI-Generated",
    risk: "high",
    date: "2026-02-19",
    time: "14:32",
    summary: "Facial deepfake detected. GAN artifacts in frames 142–189.",
  },
  {
    id: "2",
    name: "bank_call_recording.mp3",
    type: "audio",
    score: 31,
    status: "Synthetic Voice",
    risk: "high",
    date: "2026-02-19",
    time: "11:05",
    summary: "TTS voice cloning pattern detected. Matches ElevenLabs model.",
  },
  {
    id: "3",
    name: "health_news_article.txt",
    type: "text",
    score: 72,
    status: "Partially AI-Generated",
    risk: "medium",
    date: "2026-02-18",
    time: "16:44",
    summary: "Mixed human/AI authorship. 4 unverifiable factual claims.",
  },
  {
    id: "4",
    name: "protest_photo.jpg",
    type: "image",
    score: 91,
    status: "Authentic",
    risk: "low",
    date: "2026-02-18",
    time: "09:21",
    summary: "No manipulation detected. EXIF metadata consistent.",
  },
  {
    id: "5",
    name: "politician_speech.mp4",
    type: "video",
    score: 44,
    status: "Tampered",
    risk: "medium",
    date: "2026-02-17",
    time: "20:15",
    summary: "Original video detected, but audio has been replaced synthetically.",
  },
  {
    id: "6",
    name: "vaccine_misinformation.txt",
    type: "text",
    score: 12,
    status: "AI-Generated",
    risk: "high",
    date: "2026-02-17",
    time: "13:58",
    summary: "Fully AI-generated misinformation. All citations fabricated.",
  },
  {
    id: "7",
    name: "celebrity_voice_note.mp3",
    type: "audio",
    score: 27,
    status: "Synthetic Voice",
    risk: "high",
    date: "2026-02-16",
    time: "08:37",
    summary: "Celebrity voice cloned using AI. Do not trust this recording.",
  },
  {
    id: "8",
    name: "product_photo.png",
    type: "image",
    score: 88,
    status: "Authentic",
    risk: "low",
    date: "2026-02-15",
    time: "17:12",
    summary: "Image appears authentic with minor color correction.",
  },
  {
    id: "9",
    name: "breaking_news_clip.mp4",
    type: "video",
    score: 79,
    status: "Mostly Authentic",
    risk: "low",
    date: "2026-02-14",
    time: "22:48",
    summary: "No deepfake detected. Slight context reframing suspected.",
  },
  {
    id: "10",
    name: "suspicious_whatsapp.txt",
    type: "text",
    score: 38,
    status: "Suspicious",
    risk: "medium",
    date: "2026-02-13",
    time: "10:20",
    summary: "Chain message with unverifiable claims and fear-based language.",
  },
];

const typeIcons = { video: Video, audio: Mic, text: FileText, image: Image };
const typeColors = { video: "#00d4ff", audio: "#00ff9d", text: "#a855f7", image: "#ffd700" };

function getScoreColor(score: number) {
  if (score >= 75) return "#00ff9d";
  if (score >= 45) return "#ffd700";
  return "#ff4444";
}

function getRiskConfig(risk: "low" | "medium" | "high") {
  return {
    low: { color: "#00ff9d", bg: "#00ff9d10", border: "#00ff9d30" },
    medium: { color: "#ffd700", bg: "#ffd70010", border: "#ffd70030" },
    high: { color: "#ff4444", bg: "#ff444410", border: "#ff444430" },
  }[risk];
}

const filterOptions: { value: FilterStatus; label: string }[] = [
  { value: "all", label: "All Results" },
  { value: "authentic", label: "Authentic" },
  { value: "ai-generated", label: "AI-Generated" },
  { value: "tampered", label: "Tampered" },
  { value: "suspicious", label: "Suspicious" },
];

export default function HistoryPage() {
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState<FilterStatus>("all");
  const [sortBy, setSortBy] = useState<SortBy>("date");
  const [selected, setSelected] = useState<string | null>(null);

  const filtered = mockHistory
    .filter((item) => {
      const matchSearch =
        item.name.toLowerCase().includes(search.toLowerCase()) ||
        item.status.toLowerCase().includes(search.toLowerCase()) ||
        item.summary.toLowerCase().includes(search.toLowerCase());
      const matchFilter =
        filterStatus === "all" ||
        (filterStatus === "authentic" && item.score >= 75) ||
        (filterStatus === "ai-generated" && item.status.toLowerCase().includes("ai")) ||
        (filterStatus === "tampered" && item.status.toLowerCase().includes("tamper")) ||
        (filterStatus === "suspicious" && item.status.toLowerCase().includes("suspicious"));
      return matchSearch && matchFilter;
    })
    .sort((a, b) => {
      if (sortBy === "score") return b.score - a.score;
      if (sortBy === "risk") {
        const riskOrder = { high: 0, medium: 1, low: 2 };
        return riskOrder[a.risk] - riskOrder[b.risk];
      }
      return b.date.localeCompare(a.date);
    });

  const stats = {
    total: mockHistory.length,
    high: mockHistory.filter((i) => i.risk === "high").length,
    medium: mockHistory.filter((i) => i.risk === "medium").length,
    safe: mockHistory.filter((i) => i.risk === "low").length,
  };

  return (
    <div className="min-h-screen">
      <div className="pt-24 pb-16 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
          <div className="flex items-center gap-2 mb-3">
            <Clock className="w-5 h-5 text-[#00d4ff]" />
            <span className="text-[#777777] text-sm">Detection Log</span>
          </div>
          <h1 className="text-4xl font-black text-white mb-2">Analysis History</h1>
          <p className="text-[#777777]">Review all previously analyzed content with full detection reports.</p>
        </motion.div>

        {/* Stats row */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8"
        >
          {[
            { label: "Total Analyzed", value: stats.total, color: "#00d4ff" },
            { label: "High Risk", value: stats.high, color: "#ff4444" },
            { label: "Medium Risk", value: stats.medium, color: "#ffd700" },
            { label: "Safe / Authentic", value: stats.safe, color: "#00ff9d" },
          ].map((stat, i) => (
            <div key={i} className="glass rounded-xl px-5 py-4 flex items-center justify-between">
              <div>
                <p className="text-[#777777] text-xs mb-1">{stat.label}</p>
                <p className="text-2xl font-black" style={{ color: stat.color }}>{stat.value}</p>
              </div>
              <div className="w-10 h-10 rounded-full" style={{ background: `${stat.color}15`, border: `1px solid ${stat.color}30` }}>
                <div className="w-full h-full rounded-full flex items-center justify-center">
                  <span className="text-xs font-bold" style={{ color: stat.color }}>
                    {Math.round((stat.value / stats.total) * 100)}%
                  </span>
                </div>
              </div>
            </div>
          ))}
        </motion.div>

        {/* Filters + Search */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="flex flex-col sm:flex-row gap-4 mb-6"
        >
          {/* Search */}
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#777777]" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by filename, status, or content..."
              className="w-full bg-[#0a0a0a] border border-[#222222] rounded-xl pl-10 pr-4 py-3 text-[#e0e0e0] placeholder-[#444444] text-sm outline-none focus:border-[#00d4ff]/40"
            />
          </div>

          {/* Filter pills */}
          <div className="flex gap-2 flex-wrap">
            {filterOptions.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setFilterStatus(opt.value)}
                className={`px-3 py-2 rounded-lg text-xs font-medium transition-all border ${filterStatus === opt.value
                  ? "bg-[#00d4ff]/10 text-[#00d4ff] border-[#00d4ff]/30"
                  : "text-[#777777] border-[#222222] hover:border-[#00d4ff]/20 hover:text-[#b0b0b0]"
                  }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {/* Sort */}
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="w-4 h-4 text-[#777777]" />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortBy)}
              className="bg-[#0a0a0a] border border-[#222222] rounded-lg px-3 py-2 text-[#b0b0b0] text-xs outline-none focus:border-[#00d4ff]/40"
            >
              <option value="date">Sort: Latest</option>
              <option value="score">Sort: Score</option>
              <option value="risk">Sort: Risk Level</option>
            </select>
          </div>
        </motion.div>

        {/* Results count */}
        <div className="flex items-center gap-2 mb-4">
          <Filter className="w-4 h-4 text-[#777777]" />
          <span className="text-[#777777] text-sm">
            Showing <span className="text-[#b0b0b0] font-medium">{filtered.length}</span> results
          </span>
        </div>

        {/* History List */}
        <div className="space-y-3">
          {filtered.length === 0 ? (
            <div className="text-center py-16 glass rounded-xl">
              <Shield className="w-12 h-12 text-[#222222] mx-auto mb-4" />
              <p className="text-[#777777]">No results match your search</p>
            </div>
          ) : (
            filtered.map((item, i) => {
              const Icon = typeIcons[item.type];
              const iconColor = typeColors[item.type];
              const scoreColor = getScoreColor(item.score);
              const riskConfig = getRiskConfig(item.risk);
              const isSelected = selected === item.id;

              return (
                <motion.div
                  key={item.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.04 }}
                >
                  <div
                    className={`glass rounded-xl border transition-all cursor-pointer ${isSelected ? "border-[#00d4ff]/30" : "border-[#222222] hover:border-[#222222]/80"
                      }`}
                    onClick={() => setSelected(isSelected ? null : item.id)}
                  >
                    <div className="flex items-center gap-4 p-4">
                      {/* Type icon */}
                      <div
                        className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
                        style={{ background: `${iconColor}15`, border: `1px solid ${iconColor}30` }}
                      >
                        <Icon className="w-5 h-5" style={{ color: iconColor }} />
                      </div>

                      {/* Main info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3 flex-wrap">
                          <span className="text-white font-medium text-sm truncate">{item.name}</span>
                          <span
                            className="text-xs font-bold px-2 py-0.5 rounded-full border shrink-0"
                            style={{ color: riskConfig.color, background: riskConfig.bg, borderColor: riskConfig.border }}
                          >
                            {item.risk.toUpperCase()} RISK
                          </span>
                        </div>
                        <p className="text-[#777777] text-xs mt-0.5 truncate">{item.summary}</p>
                      </div>

                      {/* Score */}
                      <div className="text-center shrink-0 hidden sm:block">
                        <div className="text-xl font-black" style={{ color: scoreColor }}>{item.score}%</div>
                        <div className="text-[#777777] text-xs">Authentic</div>
                      </div>

                      {/* Status */}
                      <div className="hidden md:flex items-center gap-1.5 shrink-0">
                        {item.score >= 75 ? (
                          <CheckCircle className="w-4 h-4 text-[#00ff9d]" />
                        ) : item.score >= 45 ? (
                          <AlertTriangle className="w-4 h-4 text-[#ffd700]" />
                        ) : (
                          <XCircle className="w-4 h-4 text-[#ff4444]" />
                        )}
                        <span className="text-[#b0b0b0] text-xs font-medium">{item.status}</span>
                      </div>

                      {/* Date */}
                      <div className="text-right shrink-0 hidden lg:block">
                        <div className="text-[#b0b0b0] text-xs">{item.date}</div>
                        <div className="text-[#777777] text-xs">{item.time}</div>
                      </div>

                      <ChevronRight
                        className={`w-4 h-4 text-[#777777] transition-transform shrink-0 ${isSelected ? "rotate-90" : ""}`}
                      />
                    </div>

                    {/* Expanded row */}
                    {isSelected && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        className="border-t border-[#222222] px-4 pb-4 pt-3"
                      >
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                          <div className="sm:col-span-2">
                            <p className="text-[#777777] text-xs font-medium mb-1">Full Summary</p>
                            <p className="text-[#b0b0b0] text-sm">{item.summary}</p>
                          </div>
                          <div className="flex gap-2">
                            <a
                              href="/analyze"
                              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-[#00d4ff] text-[#000000] text-xs font-bold hover:bg-[#00d4ff]/90 transition-all"
                            >
                              <Shield className="w-3 h-3" /> Re-Analyze
                            </a>
                            <button className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg border border-[#ff4444]/30 text-[#ff4444] text-xs hover:bg-[#ff4444]/10 transition-all">
                              <Trash2 className="w-3 h-3" />
                            </button>
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </div>
                </motion.div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
