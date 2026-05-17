"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft,
  ExternalLink,
  Shield,
  Globe,
  AlertCircle,
  CheckCircle2,
  HelpCircle,
  Send,
  Loader2,
  ChevronDown,
} from "lucide-react";
import { askIntelQuestion } from "@/services/api";

interface Evidence {
  title: string;
  source: string;
  url: string;
  snippet: string;
  relation: "supporting" | "contradicting" | "neutral";
  credibility: number;
}

interface IntelResult {
  status: string;
  content_type: string | { type?: string; confidence?: number; reasoning?: string };
  classification: any;
  claims_found: number;
  sources_analyzed: number;
  evidence: Evidence[];
  analysis?: any;
  summary: string;
  supporting_count?: number;
  contradicting_count?: number;
  message?: string;
  originalContent: string;
  inputType: string;
  is_fallback?: boolean;
  pipeline_trace?: {
    trace_id: string;
    duration_ms: number;
    stages: Array<{ stage: string; status: string; duration_ms?: number; failure_reason?: string }>;
    events?: Array<{ stage: string; message: string; details?: any }>;
  };
  retrieval_errors?: Array<{ stage: string; reason: string }>;
  retrieval_diagnostics?: {
    claims?: string[];
    rewritten_queries?: string[][];
    searched_domains?: string[];
    retrieval_errors?: Array<{ stage: string; reason: string }>;
  };
  claim_evidence_map?: Record<string, Array<{
    title?: string;
    source?: string;
    url?: string;
    relation?: string;
    claim_text?: string;
    claim_relevance_score?: number;
    ranking_score?: number;
  }>>;
}

interface IntelDashboardProps {
  result: IntelResult;
  onBack: () => void;
}

const sourceIcons: Record<string, string> = {
  reuters: "🏢",
  bbc: "📡",
  ap: "📰",
  associated: "📰",
  nyt: "📰",
  new_york: "📰",
  guardian: "📰",
  cnn: "📺",
  "the_":  "📰",
  scientific: "🔬",
  nature: "🔬",
  science: "🔬",
  journal: "📊",
  research: "🔬",
  fact: "✓",
  snopes: "✓",
  political: "🏛️",
  government: "🏛️",
};

function getSourceIcon(source: string): string {
  const lower = String(source || "").toLowerCase();
  for (const [key, icon] of Object.entries(sourceIcons)) {
    if (lower.includes(key)) return icon;
  }
  return "🌐";
}

function getCredibilityColor(credibility: number): string {
  const score = Number.isFinite(credibility) ? credibility : 0.5;
  if (score >= 0.85) return "text-emerald-400";
  if (score >= 0.65) return "text-cyan-300";
  return "text-orange-400";
}

function getCredibilityBg(credibility: number): string {
  const score = Number.isFinite(credibility) ? credibility : 0.5;
  if (score >= 0.85) return "bg-emerald-500/10 border-emerald-500/20";
  if (score >= 0.65) return "bg-cyan-500/10 border-cyan-500/20";
  return "bg-orange-500/10 border-orange-500/20";
}

function getContentTypeLabel(value: IntelResult["content_type"]): string {
  if (typeof value === "string") {
    return value || "unknown";
  }

  if (value && typeof value === "object") {
    if (typeof value.type === "string" && value.type.trim()) {
      return value.type;
    }
    if (typeof value.reasoning === "string" && value.reasoning.trim()) {
      return value.reasoning;
    }
  }

  return "unknown";
}

// Helper to clean and format the intelligence summary
const formatSummary = (text: string) => {
  if (!text) return null;

  // Split by headers (e.g. **🧠 HEADER**)
  const sections = text.split(/\*\*([^*]+)\*\*/g);
  
  if (sections.length <= 1) {
    // No headers found, just clean raw symbols and return
    const cleanText = text.replace(/[*#_~`>]/g, "").trim();
    return <p className="text-slate-300 text-lg leading-relaxed">{cleanText}</p>;
  }

  const formatted = [];
  for (let i = 1; i < sections.length; i += 2) {
    const header = sections[i].trim();
    const content = sections[i + 1]?.trim() || "";
    
    // Clean content of markdown symbols
    const cleanContent = content
      .replace(/[*#_~`>]/g, "") // Remove common symbols
      .replace(/^\s*-\s+/gm, "• ") // Normalize bullets
      .trim();

    formatted.push(
      <div key={header} className="mb-6 last:mb-0">
        <h3 className="text-cyan-400 font-bold tracking-widest text-xs uppercase mb-2 flex items-center gap-2">
          {header}
          <div className="h-px flex-1 bg-gradient-to-r from-cyan-500/20 to-transparent" />
        </h3>
        <div className="text-slate-200 text-lg leading-relaxed whitespace-pre-line pl-1 break-words">
          {cleanContent}
        </div>
      </div>
    );
  }

  return <div className="space-y-4">{formatted}</div>;
};

export default function IntelDashboard({ result, onBack }: IntelDashboardProps) {
  const [qaMode, setQaMode] = useState(false);
  const [question, setQuestion] = useState("");
  const [qaLoading, setQaLoading] = useState(false);
  const [qaPairs, setQaPairs] = useState<Array<{ q: string; a: string }>>([]);
  const [showTrace, setShowTrace] = useState(false);

  const safeResult: IntelResult = {
    status: result?.status ?? "success",
    content_type: result?.content_type ?? result?.classification ?? "unknown",
    classification: result?.classification ?? {},
    claims_found: Number.isFinite(result?.claims_found) ? result.claims_found : 0,
    sources_analyzed: Number.isFinite(result?.sources_analyzed) ? result.sources_analyzed : 0,
    evidence: Array.isArray(result?.evidence) ? result.evidence : [],
    analysis: result?.analysis ?? {},
    summary: typeof result?.summary === "string" ? result.summary : "",
    supporting_count: typeof result?.supporting_count === "number" ? result.supporting_count : 0,
    contradicting_count: typeof result?.contradicting_count === "number" ? result.contradicting_count : 0,
    message: typeof result?.message === "string" ? result.message : undefined,
    originalContent: typeof result?.originalContent === "string" ? result.originalContent : "",
    inputType: typeof result?.inputType === "string" ? result.inputType : "text",
    pipeline_trace: result?.pipeline_trace
      ? {
          trace_id: result.pipeline_trace.trace_id ?? "unknown",
          duration_ms: Number.isFinite(result.pipeline_trace.duration_ms) ? result.pipeline_trace.duration_ms : 0,
          stages: Array.isArray(result.pipeline_trace.stages) ? result.pipeline_trace.stages : [],
          events: Array.isArray(result.pipeline_trace.events) ? result.pipeline_trace.events : [],
        }
      : undefined,
    retrieval_errors: Array.isArray(result?.retrieval_errors) ? result.retrieval_errors : [],
    retrieval_diagnostics: result?.retrieval_diagnostics ?? {},
    claim_evidence_map: result?.claim_evidence_map ?? {},
    verdict: result?.verdict ?? { label: "unverified", credibility_score: 50, confidence: 0 },
  };

  const verdict = safeResult.verdict;
  const verdictLabel = (verdict.verdict || verdict.label || "unverified").toUpperCase();
  const verdictScore = Math.round(verdict.authenticity_score || verdict.credibility_score || 0);

  const getVerdictStyle = (score: number) => {
    if (score <= 15) return { color: "#ff4444", label: "Fake News", glow: "rgba(255, 68, 68, 0.4)" };
    if (score <= 30) return { color: "#ff4444", label: "Likely False", glow: "rgba(255, 68, 68, 0.4)" };
    if (score <= 45) return { color: "#ff8c00", label: "Misleading", glow: "rgba(255, 140, 0, 0.4)" };
    if (score <= 60) return { color: "#ffd700", label: "Mixed Evidence", glow: "rgba(255, 215, 0, 0.4)" };
    if (score <= 80) return { color: "#00d4ff", label: "Likely True", glow: "rgba(0, 212, 255, 0.4)" };
    return { color: "#00ff9d", label: "Verified", glow: "rgba(0, 255, 157, 0.4)" };
  };

  const vStyle = getVerdictStyle(verdictScore);
  const displayLabel = verdictLabel === "INSUFFICIENT EVIDENCE" ? "Insufficient Evidence" : (vStyle.label || verdictLabel);

  const handleAskQuestion = async () => {
    if (!question.trim()) return;

    console.log("--- Frontend QA Request Start ---");
    console.log("Question:", question);
    console.log("Context Length:", safeResult.originalContent?.length);
    console.log("Evidence Count:", safeResult.evidence?.length);

    setQaLoading(true);
    try {
      const response = await askIntelQuestion({
        question,
        context: safeResult.originalContent,
        evidence: safeResult.evidence,
        verification_result: result, // Pass full previous result
      });

      console.log("Frontend QA Response received:", response);

      // Format QA answer to remove markdown while preserving readability
      const cleanAnswer = typeof response?.answer === "string" 
        ? response.answer
            .replace(/\*\*(.*?)\*\*/g, "$1") // Remove bold markers but keep text
            .replace(/^\s*[-*+]\s+/gm, "• ") // Normalize various bullet types to •
            .replace(/[*#_~`>]/g, "") // Remove other stray symbols
            .trim()
        : "No response available.";

      console.log("Cleaned Answer:", cleanAnswer);

      setQaPairs((previous) => [...previous, { q: question, a: cleanAnswer }]);
      setQuestion("");
    } catch (err) {
      console.error("Q&A error:", err);
      // Add error as answer to show user something went wrong
      setQaPairs((previous) => [...previous, { q: question, a: "⚠️ Connection error occurred while generating answer. Please check backend status." }]);
    } finally {
      setQaLoading(false);
      console.log("--- Frontend QA Request End ---");
    }
  };

  const containerVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { staggerChildren: 0.1, delayChildren: 0.2 },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 10 },
    visible: { opacity: 1, y: 0 },
  };

  const summaryText = safeResult.summary.trim();
  const hasGroundedSummary = summaryText.length > 0 && !summaryText.includes("Unable");
  const traceStages = safeResult.pipeline_trace?.stages ?? [];
  const traceEvents = safeResult.pipeline_trace?.events ?? [];
  const retrievalDiagnostics = safeResult.retrieval_diagnostics ?? {};
  const evidenceList = safeResult.evidence ?? [];
  const originalContent = safeResult.originalContent || "No original content was provided.";
  const contentTypeLabel = getContentTypeLabel(safeResult.content_type);
  const claimEvidenceMap = safeResult.claim_evidence_map ?? {};

  return (
    <motion.div variants={containerVariants} initial="hidden" animate="visible" className="space-y-8">
      {/* Header */}
      <motion.div variants={itemVariants} className="flex flex-col md:flex-row md:items-center gap-4 mb-8">
        <div className="flex items-center gap-4">
          <button
            onClick={onBack}
            className="p-2 rounded-lg bg-white/5 hover:bg-white/10 transition-colors"
            title="Back to input"
          >
            <ArrowLeft className="w-5 h-5 text-slate-400" />
          </button>
          <div className="flex-1">
            <h1 className="text-3xl font-bold text-white flex items-center gap-3">
              <Shield className="w-8 h-8 text-cyan-300" />
              Intelligence Report
            </h1>
          </div>
        </div>

        <div className="flex-1 flex items-center gap-4 bg-white/5 md:bg-transparent p-4 md:p-0 rounded-2xl md:justify-end">
          <div className="flex flex-col items-start md:items-end">
             <span className="text-[10px] text-slate-500 uppercase font-bold tracking-widest">Analysis Type</span>
             <span className="text-sm font-mono text-slate-300 uppercase">{contentTypeLabel}</span>
          </div>
          <div className="h-8 w-px bg-white/10 mx-2" />
          <div className="flex flex-col items-start md:items-end">
             <span className="text-[10px] text-slate-500 uppercase font-bold tracking-widest">Status</span>
             <span className="text-sm font-black tracking-wide" style={{ color: vStyle.color, textShadow: `0 0 10px ${vStyle.glow}` }}>{verdictLabel}</span>
          </div>
          <div className="h-8 w-px bg-white/10 mx-2" />
          <div className="flex flex-col items-start md:items-end">
             <span className="text-[10px] text-slate-500 uppercase font-bold tracking-widest">Credibility</span>
             <span className="text-sm font-black text-white">{verdictScore}%</span>
          </div>
        </div>
      </motion.div>

      {/* Summary Card */}
      <motion.div
        variants={itemVariants}
        className="glass-card rounded-3xl p-10 border border-white/10 shadow-[0_0_50px_-12px_rgba(0,0,0,0.5)]"
      >
        <div className="flex items-start gap-6">
          <div className="hidden sm:block">
            {!hasGroundedSummary || safeResult.sources_analyzed === 0 ? (
              <div className="w-12 h-12 rounded-2xl bg-orange-500/10 border border-orange-500/20 flex items-center justify-center">
                <AlertCircle className="w-6 h-6 text-orange-400" />
              </div>
            ) : (
              <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
                <CheckCircle2 className="w-6 h-6 text-emerald-400" />
              </div>
            )}
          </div>
          <div className="flex-1">
            <div className="mb-6">
               <h2 className="text-2xl font-black text-white tracking-tight">Intelligence Summary</h2>
               <p className="text-slate-500 text-sm mt-1">Investigations grounded in retrieved evidence and claim cross-referencing.</p>
            </div>
            
            {safeResult.is_fallback && (
              <motion.div 
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mb-6 p-4 rounded-xl bg-orange-500/10 border border-orange-500/20 flex items-start gap-3"
              >
                <AlertCircle className="w-5 h-5 text-orange-400 shrink-0 mt-0.5" />
                <div>
                  <div className="text-sm font-bold text-orange-300 uppercase tracking-tight">Transcript Unavailable</div>
                  <p className="text-xs text-orange-200/70 mt-0.5">Media ingestion failed. Analysis is based on available metadata and contextual signals.</p>
                </div>
              </motion.div>
            )}

            <div className="relative">
              {formatSummary(safeResult.summary)}
              {!summaryText && (
                <div className="py-12 text-center border-2 border-dashed border-white/5 rounded-2xl">
                  <p className="text-slate-600 italic">No summary was generated for this analysis.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </motion.div>

      {/* Evidence Metrics */}
      {safeResult.sources_analyzed > 0 && (
        <motion.div
          variants={itemVariants}
          className="grid grid-cols-1 sm:grid-cols-3 gap-6"
        >
          <div className="glass-card rounded-2xl p-6 border border-white/10 text-center">
            <div className="text-3xl font-black text-white mb-1">{safeResult.sources_analyzed}</div>
            <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Sources Retrieved</div>
          </div>
          <div className="glass-card rounded-2xl p-6 border border-emerald-500/20 bg-emerald-500/5 text-center">
            <div className="text-3xl font-black text-emerald-400 mb-1">{safeResult.supporting_count ?? 0}</div>
            <div className="text-[10px] font-bold text-emerald-500/70 uppercase tracking-widest">Supporting</div>
          </div>
          <div className="glass-card rounded-2xl p-6 border border-rose-500/20 bg-rose-500/5 text-center">
            <div className="text-3xl font-black text-rose-400 mb-1">{safeResult.contradicting_count ?? 0}</div>
            <div className="text-[10px] font-bold text-rose-500/70 uppercase tracking-widest">Contradicting</div>
          </div>
        </motion.div>
      )}

      {/* Evidence Sources */}
      {evidenceList.length > 0 && (
        <motion.div variants={itemVariants} className="space-y-6">
          <div className="flex items-center gap-3">
             <h2 className="text-2xl font-black text-white tracking-tight uppercase">Retrieved Intelligence</h2>
             <div className="h-px flex-1 bg-gradient-to-r from-white/10 to-transparent" />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {evidenceList.slice(0, 3).map((source, idx) => (
              <motion.a
                key={idx}
                href={source.url || "#"}
                target="_blank"
                rel="noopener noreferrer"
                className="glass-card rounded-2xl p-6 border border-white/5 transition-all hover:border-white/20 hover:bg-white/5 block group overflow-hidden"
                whileHover={{ y: -4 }}
              >
                <div className="flex items-start gap-4">
                  <div className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-xl group-hover:scale-110 transition-transform shrink-0">
                    {getSourceIcon(source.source)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-4 mb-1">
                      <div className="flex-1 min-w-0">
                        <h3 className="text-white font-bold truncate group-hover:text-cyan-400 transition-colors">{source.title}</h3>
                        <p className="text-[10px] font-mono text-slate-500 uppercase tracking-tighter truncate">{source.source}</p>
                      </div>
                      <ExternalLink className="w-4 h-4 text-slate-700 group-hover:text-cyan-500 transition-colors shrink-0" />
                    </div>
                    <p className="text-xs text-slate-400 mb-4 line-clamp-2 leading-relaxed italic break-words">"{source.snippet}"</p>
                    
                    <div className="flex items-center justify-between mt-auto pt-4 border-t border-white/5">
                      <div
                        className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-[10px] font-black uppercase tracking-widest ${
                          source.relation === "supporting" || (source.relation as string) === "entailment"
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : source.relation === "contradicting" || (source.relation as string) === "contradiction"
                            ? "bg-red-500/10 text-red-400 border border-red-500/20"
                            : "bg-white/5 text-slate-400 border border-white/10"
                        }`}
                      >
                        {(source.relation === "supporting" || (source.relation as string) === "entailment") && "✓ Corroborated"}
                        {(source.relation === "contradicting" || (source.relation as string) === "contradiction") && "✕ Contradicted"}
                        {source.relation === "neutral" && "○ Neutral"}
                        {(source.relation as string) === "uncertain" && "○ Neutral"}
                      </div>
                      
                      <div className="text-[9px] font-mono text-slate-600 truncate max-w-[80px] opacity-0 group-hover:opacity-100 transition-opacity">
                        {source.url}
                      </div>
                    </div>
                  </div>
                </div>
              </motion.a>
            ))}
          </div>
        </motion.div>
      )}

      {/* Q&A Section */}
      <motion.div variants={itemVariants} className="space-y-6">
        <div className="glass-card rounded-3xl overflow-hidden border border-white/10">
           <div className="bg-white/5 px-8 py-5 border-b border-white/10 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <HelpCircle className="w-5 h-5 text-cyan-400" />
                <h3 className="text-white font-bold uppercase tracking-widest text-sm">Q&A</h3>
              </div>
              <button
                onClick={() => setQaMode(!qaMode)}
                className="text-xs font-bold text-slate-400 hover:text-white transition-colors uppercase tracking-widest"
              >
                {qaMode ? "Close" : "Open"}
              </button>
           </div>

           <AnimatePresence>
            {qaMode && (
              <motion.div 
                initial={{ height: 0, opacity: 0 }} 
                animate={{ height: "auto", opacity: 1 }} 
                exit={{ height: 0, opacity: 0 }}
                className="overflow-hidden"
              >
                <div className="p-6 space-y-6 bg-black/20">
                  {/* Q&A Pairs */}
                  <div className="space-y-4">
                    {qaPairs.map((pair, idx) => (
                      <motion.div key={idx} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-2">
                        <div className="bg-cyan-500/10 border border-cyan-500/20 rounded-xl p-4">
                           <p className="text-cyan-100 text-sm font-bold">Q: {pair.q}</p>
                        </div>
                        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                           <p className="text-slate-300 text-sm leading-relaxed whitespace-pre-line">{pair.a}</p>
                        </div>
                      </motion.div>
                    ))}
                  </div>

                  {/* Input */}
                  <div className="flex gap-2">
                    <input
                      value={question}
                      onChange={(e) => setQuestion(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          handleAskQuestion();
                        }
                      }}
                      placeholder="Ask a follow-up question..."
                      className="flex-1 bg-black/30 text-white placeholder-slate-600 text-sm border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-cyan-500/50 transition-all"
                    />
                    <button
                      onClick={handleAskQuestion}
                      disabled={qaLoading || !question.trim()}
                      className="px-6 rounded-xl bg-cyan-500 hover:bg-cyan-400 disabled:bg-slate-800 disabled:text-slate-600 transition-all flex items-center justify-center text-black font-bold text-xs uppercase"
                    >
                      {qaLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Send"}
                    </button>
                  </div>
                </div>
              </motion.div>
            )}
           </AnimatePresence>
        </div>
      </motion.div>

      {/* Runtime Audit Toggle */}
      <motion.div variants={itemVariants} className="flex justify-center pt-4">
          <button 
            onClick={() => setShowTrace(!showTrace)}
            className="text-[10px] font-mono text-slate-600 hover:text-slate-400 uppercase tracking-[0.3em] transition-colors"
          >
            {showTrace ? "Hide System Diagnostics" : "View System Diagnostics"}
          </button>
      </motion.div>

      {showTrace && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="glass-card rounded-2xl p-6 border border-white/10">
              <h3 className="text-sm font-black text-white uppercase tracking-widest mb-4">Pipeline Execution Trace</h3>
              <div className="space-y-2">
                {traceStages.map((stage) => (
                  <div key={stage.stage} className="flex items-center justify-between rounded-xl bg-white/5 px-4 py-3 border border-white/5">
                    <div>
                      <div className="text-xs font-bold text-white uppercase tracking-wider">{stage.stage}</div>
                      {stage.failure_reason && <div className="text-[10px] text-rose-400 mt-1 font-mono">{stage.failure_reason}</div>}
                    </div>
                    <div className="text-[10px] font-mono text-slate-500">
                      {stage.status} {stage.duration_ms ? `• ${Math.round(stage.duration_ms)}ms` : ""}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="glass-card rounded-2xl p-6 border border-white/10">
              <h3 className="text-sm font-black text-white uppercase tracking-widest mb-4">Neural Event Log</h3>
              <div className="max-h-[300px] overflow-y-auto space-y-2 pr-2 custom-scrollbar">
                {traceEvents.length > 0 ? traceEvents.map((event, index) => (
                  <div key={`${event.stage}-${index}`} className="rounded-xl border border-white/5 bg-black/30 p-3">
                    <div className="text-[9px] text-cyan-500 uppercase font-mono mb-1">{event.stage}</div>
                    <div className="text-[11px] text-slate-400 leading-tight">{event.message}</div>
                  </div>
                )) : (
                  <div className="py-12 text-center text-slate-700 text-xs uppercase font-mono tracking-widest">No telemetry data captured</div>
                )}
              </div>
            </div>
          </div>

          {safeResult.retrieval_errors.length > 0 && (
            <div className="rounded-2xl border border-rose-500/20 bg-rose-500/5 p-4 text-rose-200">
              <div className="text-[10px] font-black uppercase tracking-widest mb-2">Retrieval Faults</div>
              <div className="space-y-1 text-[11px] font-mono">
                {safeResult.retrieval_errors.map((error, index) => (
                  <div key={`${error.stage}-${index}`}>[{error.stage.toUpperCase()}] {error.reason}</div>
                ))}
              </div>
            </div>
          )}
        </motion.div>
      )}

      {/* Original Content */}
      <motion.div variants={itemVariants} className="glass-card rounded-3xl p-10 border border-white/10">
        <h3 className="text-lg font-black text-white mb-6 uppercase tracking-widest flex items-center gap-2">
           <Globe className="w-5 h-5 text-slate-500" />
           Raw Signal Capture
        </h3>
        <div className="bg-black/50 rounded-2xl p-6 text-slate-400 text-sm leading-relaxed max-h-48 overflow-y-auto border border-white/5 font-mono">
          {originalContent}
        </div>
      </motion.div>
    </motion.div>
  );
}
