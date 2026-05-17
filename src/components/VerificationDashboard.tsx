"use client";

import { motion, AnimatePresence } from "framer-motion";
import {
  ChevronLeft,
  Shield,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Globe,
  ExternalLink,
  Zap,
  Network,
  TrendingDown,
  Clock,
  Sparkles,
  Flag,
  BarChart3,
  Share2,
} from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

interface Evidence {
  title: string;
  source: string;
  publisher?: string;
  url?: string;
  relevance: number;
  credibility: number;
  snippet?: string;
}

interface Contradiction {
  claim: string;
  evidence: string;
  relation: "contradiction" | "entailment" | "neutral";
  confidence: number;
}

interface VerificationResult {
  query: string;
  verified: boolean;
  credibilityScore: number;
  riskLevel: "LOW" | "MEDIUM" | "HIGH";
  findings: string[];
  contradictions: Contradiction[];
  evidence: Evidence[];
  sources: { name: string; credibility: number; url: string }[];
  provenanceData: any;
  propagationMetrics: any;
  timestamp: string;
}

interface VerificationDashboardProps {
  result: VerificationResult;
  onBack: () => void;
}

export default function VerificationDashboard({ result, onBack }: VerificationDashboardProps) {
  const getRiskColor = (level: string) => {
    switch (level) {
      case "LOW":
        return "#00ff9d"; // Green
      case "MEDIUM":
        return "#ffd700"; // Yellow
      case "HIGH":
        return "#ff4444"; // Red
      default:
        return "#00d4ff"; // Cyan
    }
  };

  const getRiskIcon = (level: string) => {
    switch (level) {
      case "LOW":
        return CheckCircle;
      case "MEDIUM":
        return AlertTriangle;
      case "HIGH":
        return XCircle;
      default:
        return Shield;
    }
  };

  const contradictionRelationLabel = (relation: string) => {
    switch (relation) {
      case "contradiction":
        return "Contradicts Evidence";
      case "entailment":
        return "Supported";
      case "neutral":
        return "Neutral";
      default:
        return relation;
    }
  };

  const mockPropagationData = [
    { time: "0h", count: 0 },
    { time: "2h", count: 45 },
    { time: "4h", count: 120 },
    { time: "6h", count: 280 },
    { time: "8h", count: 350 },
    { time: "10h", count: 420 },
    { time: "12h", count: 580 },
  ];

  const RiskIcon = getRiskIcon(result.riskLevel);
  const confidenceScore = Math.round(result.credibilityScore);
  
  const riskConfig = (() => {
    if (confidenceScore <= 15) return { color: "#ff4444", label: "Fake News", glow: "rgba(255, 68, 68, 0.4)" };
    if (confidenceScore <= 30) return { color: "#ff4444", label: "Likely False", glow: "rgba(255, 68, 68, 0.4)" };
    if (confidenceScore <= 45) return { color: "#ff8c00", label: "Misleading", glow: "rgba(255, 140, 0, 0.4)" };
    if (confidenceScore <= 60) return { color: "#ffd700", label: "Mixed Evidence", glow: "rgba(255, 215, 0, 0.4)" };
    if (confidenceScore <= 80) return { color: "#00d4ff", label: "Likely True", glow: "rgba(0, 212, 255, 0.4)" };
    return { color: "#00ff9d", label: "Verified", glow: "rgba(0, 255, 157, 0.4)" };
  })();

  const displayLabel = confidenceScore === 0 ? "Insufficient Evidence" : riskConfig.label;

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="flex items-center gap-4 mb-8">
        <button
          onClick={onBack}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-slate-400 hover:text-white transition-all"
        >
          <ChevronLeft className="w-4 h-4" />
          Back
        </button>
        <h1 className="text-3xl font-black text-white italic uppercase tracking-tighter">Source Check Report</h1>
      </motion.div>

      {/* Executive Summary: Sources First */}
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="glass-card rounded-2xl p-8 border border-white/10"
      >
        <div className="flex items-start justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold text-white mb-2">Credibility Summary</h2>
            <p className="text-slate-400 text-sm">
              Evidence-based assessment • Analyzed on {new Date(result.timestamp).toLocaleString()}
            </p>
          </div>
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
            className="opacity-10"
          >
            <Sparkles className="w-8 h-8 text-yellow-400" />
          </motion.div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Supporting Evidence */}
          <div className="p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/20">
            <div className="text-sm font-semibold text-emerald-300 uppercase tracking-wider mb-2">Supporting Sources</div>
            <div className="text-3xl font-black text-emerald-400">
              {result.contradictions.filter((c) => c.relation === "entailment").length}
            </div>
            <div className="text-xs text-slate-400 mt-2">corroborating evidence found</div>
          </div>

          {/* Contradictory Evidence */}
          <div className="p-4 rounded-xl bg-rose-500/5 border border-rose-500/20">
            <div className="text-sm font-semibold text-rose-300 uppercase tracking-wider mb-2">Contradictory Sources</div>
            <div className="text-3xl font-black text-rose-400">
              {result.contradictions.filter((c) => c.relation === "contradiction").length}
            </div>
            <div className="text-xs text-slate-400 mt-2">conflicting evidence detected</div>
          </div>

          {/* Sources Analyzed */}
          <div className="p-4 rounded-xl bg-cyan-500/5 border border-cyan-500/20">
            <div className="text-sm font-semibold text-cyan-300 uppercase tracking-wider mb-2">Trusted Sources</div>
            <div className="text-3xl font-black text-cyan-400">{result.evidence.length}</div>
            <div className="text-xs text-slate-400 mt-2">analyzed in this session</div>
          </div>
        </div>

        {/* Risk Assessment */}
        <div className="mt-6 p-4 rounded-xl bg-white/5 border border-white/10">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold text-white uppercase tracking-wider mb-1">Status Verdict</div>
              <div className="text-slate-400 text-sm">
                {confidenceScore > 60
                  ? "✓ Information appears credible based on corroborating sources"
                  : confidenceScore > 30
                    ? "⚠ Mixed signals — some sources contradict, others support"
                    : confidenceScore > 0 ? "✕ Strong contradictions from trusted sources suggest misinformation" : "No external evidence retrieved for this claim"}
              </div>
            </div>
            <div
              className={`px-4 py-2 rounded-lg font-bold text-sm shadow-lg`}
              style={{ background: `${riskConfig.color}20`, color: riskConfig.color, boxShadow: `0 0 20px ${riskConfig.color}10` }}
            >
              {displayLabel.toUpperCase()}
            </div>
          </div>
        </div>
      </motion.div>

      {/* Evidence Sources: Primary Focus */}
      {result.findings.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="glass-card rounded-2xl p-8 border border-white/10"
        >
          <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
            <Zap className="w-5 h-5 text-cyan-400" />
            AI-Generated Investigative Findings
          </h3>
          <ul className="space-y-3">
            {result.findings.map((finding, idx) => (
              <motion.li
                key={idx}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.05 }}
                className="flex gap-3 text-slate-300"
              >
                <div className="flex-shrink-0 w-2 h-2 rounded-full bg-cyan-400 mt-2" />
                <span>{finding}</span>
              </motion.li>
            ))}
          </ul>
        </motion.div>
      )}

      {/* Contradictions Analysis */}
      {result.contradictions.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="glass-card rounded-2xl p-8 border border-white/10"
        >
          <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-rose-400" />
            Contradiction Analysis
          </h3>
          <div className="space-y-4">
            {result.contradictions.map((contradiction, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: idx * 0.05 }}
                className={`p-4 rounded-lg border ${
                  contradiction.relation === "contradiction"
                    ? "bg-rose-500/5 border-rose-500/20"
                    : contradiction.relation === "entailment"
                      ? "bg-emerald-500/5 border-emerald-500/20"
                      : "bg-white/5 border-white/10"
                }`}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="text-sm font-semibold text-white">{contradiction.claim}</div>
                  <div
                    className={`px-2 py-1 rounded text-xs font-bold ${
                      contradiction.relation === "contradiction"
                        ? "bg-rose-500/20 text-rose-300"
                        : contradiction.relation === "entailment"
                          ? "bg-emerald-500/20 text-emerald-300"
                          : "bg-slate-500/20 text-slate-300"
                    }`}
                  >
                    {contradictionRelationLabel(contradiction.relation)}
                  </div>
                </div>
                <p className="text-sm text-slate-400 mb-2">{contradiction.evidence}</p>
                <div className="flex items-center justify-between">
                  <div className="text-xs text-slate-500">Confidence: {Math.round(contradiction.confidence * 100)}%</div>
                  <div className="flex-grow mx-2 h-1 bg-white/10 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-cyan-500 to-emerald-500 rounded-full"
                      style={{ width: `${contradiction.confidence * 100}%` }}
                    />
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Evidence Cards */}
      {result.evidence.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="space-y-4"
        >
          <h3 className="text-xl font-bold text-white flex items-center gap-2">
            <Globe className="w-5 h-5 text-cyan-400" />
            Related Sources & Evidence
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {result.evidence.slice(0, 6).map((evidence, idx) => (
              <motion.a
                key={idx}
                href={evidence.url}
                target="_blank"
                rel="noopener noreferrer"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: idx * 0.05 }}
                className="group glass-card rounded-xl p-4 border border-white/10 hover:border-cyan-500/30 transition-all hover:bg-white/5 cursor-pointer"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1">
                    <h4 className="font-semibold text-white text-sm line-clamp-2 group-hover:text-cyan-300 transition-colors">
                      {evidence.title}
                    </h4>
                    <p className="text-xs text-slate-400 mt-1">{evidence.source}</p>
                  </div>
                  <ExternalLink className="w-4 h-4 text-slate-400 group-hover:text-cyan-400 transition-colors flex-shrink-0 ml-2" />
                </div>
                {evidence.snippet && <p className="text-xs text-slate-400 line-clamp-2 mb-3">{evidence.snippet}</p>}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="text-xs text-slate-500">Relevance:</div>
                    <div className="flex gap-1">
                      {Array.from({ length: 5 }).map((_, i) => (
                        <div
                          key={i}
                          className={`w-1.5 h-1.5 rounded-full ${
                            i < Math.round(evidence.relevance * 5) ? "bg-cyan-400" : "bg-white/10"
                          }`}
                        />
                      ))}
                    </div>
                  </div>
                </div>
              </motion.a>
            ))}
          </div>
        </motion.div>
      )}

      {/* Source Reliability */}
      {result.sources.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="glass-card rounded-2xl p-8 border border-white/10"
        >
          <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-cyan-400" />
            Source Reliability Matrix
          </h3>
          <div className="space-y-3">
            {result.sources.map((source, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: idx * 0.05 }}
                className="p-4 rounded-lg bg-white/5 border border-white/10"
              >
                <div className="flex items-center justify-between mb-2">
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-semibold text-cyan-300 hover:text-cyan-200 transition-colors flex items-center gap-2"
                  >
                    {source.name}
                    <ExternalLink className="w-3 h-3" />
                  </a>
                  <div className="text-sm font-bold text-white">{Math.round(source.credibility * 100)}%</div>
                </div>
                <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${
                      source.credibility > 0.7 ? "bg-emerald-500" : source.credibility > 0.4 ? "bg-yellow-500" : "bg-rose-500"
                    }`}
                    style={{ width: `${source.credibility * 100}%` }}
                  />
                </div>
              </motion.div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Propagation Metrics */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        className="glass-card rounded-2xl p-8 border border-white/10"
      >
        <h3 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
          <Network className="w-5 h-5 text-cyan-400" />
          Social Propagation Intelligence
        </h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={mockPropagationData}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
            <XAxis dataKey="time" stroke="rgba(255,255,255,0.5)" />
            <YAxis stroke="rgba(255,255,255,0.5)" />
            <Tooltip
              contentStyle={{
                backgroundColor: "rgba(0,0,0,0.8)",
                border: "1px solid rgba(0,212,255,0.3)",
                borderRadius: "8px",
              }}
              labelStyle={{ color: "#fff" }}
            />
            <Line
              type="monotone"
              dataKey="count"
              stroke="#00d4ff"
              dot={false}
              strokeWidth={2}
              isAnimationActive={true}
            />
          </LineChart>
        </ResponsiveContainer>
      </motion.div>

      {/* Actions */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
        className="flex flex-col sm:flex-row gap-4"
      >
        <button className="flex-1 px-6 py-3 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-black font-bold transition-all hover:shadow-[0_0_40px_-10px_rgba(6,182,212,0.5)]">
          <div className="flex items-center justify-center gap-2">
            <Share2 className="w-4 h-4" />
            Share Report
          </div>
        </button>
        <button className="flex-1 px-6 py-3 rounded-xl bg-white/5 hover:bg-white/10 text-white font-bold border border-white/10 transition-all">
          <div className="flex items-center justify-center gap-2">
            <Flag className="w-4 h-4" />
            Save to History
          </div>
        </button>
      </motion.div>
    </div>
  );
}
