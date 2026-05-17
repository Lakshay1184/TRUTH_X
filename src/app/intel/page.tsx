"use client";

import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import VerificationInput from "@/components/VerificationInput";
import IntelDashboard from "@/components/IntelDashboard";
import { classifyContent, analyzeIntel } from "@/services/api";
import { Shield, AlertCircle, Sparkles, CheckCircle2, Loader2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";
import Link from "next/link";
import IntelErrorBoundary from "@/components/IntelErrorBoundary";

type Stage = "input" | "classifying" | "analyzing" | "results";

export default function IntelPage() {
  const { user, isAuthenticated, loading } = useAuth();
  const { showToast } = useToast();
  const [stage, setStage] = useState<Stage>("input");
  const [scanProgress, setScanProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState("");
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [contentClassification, setContentClassification] = useState<any>(null);
  const [loadKey, setLoadKey] = useState(0);

  const timeline = useMemo(() => [
    "Analyzing claims",
    "Searching sources",
    "Verifying evidence",
    "Building report",
    "Preparing Source Check",
  ], []);

  const [timelineProgress, setTimelineProgress] = useState(0);

  const getCompletedSteps = (progress: number) => {
    if (progress >= 95) return 5;
    if (progress >= 80) return 4;
    if (progress >= 60) return 3;
    if (progress >= 35) return 2;
    if (progress >= 10) return 1;
    return 0;
  };

  const handleSubmit = async (data: { type: string; content: string; file?: File }) => {
    if (!isAuthenticated) {
      setError("Please log in to use Source Check features");
      return;
    }

    setError(null);
    setStage("classifying");
    setScanProgress(0);
    setTimelineProgress(0);
    setCurrentStep(timeline[0]);

    try {
      // Step 1: Classify content
      setCurrentStep(timeline[0]);
      setScanProgress(15);
      const classification = await classifyContent(data.content);
      setContentClassification(classification);
      
      showToast(`Content classified as: ${classification.type}`, "info");

      // Step 2: Perform intelligent analysis
      setStage("analyzing");
      setCurrentStep(timeline[0]);
      setScanProgress(10);

      const analysisResult = await analyzeIntel({
        content: data.content,
        content_type: classification.type,
        file: data.file, // Pass the local file if available
        onStatus: (status) => {
          setCurrentStep(status || timeline[0]);
        },
        onProgress: (progress) => {
          setTimelineProgress(progress);
          setScanProgress(progress);
        },
      });

      setScanProgress(100);
      setTimelineProgress(100);
      setCurrentStep("Preparing Source Check");

      setTimeout(() => {
        setResult({
          ...analysisResult,
          originalContent: data.file ? data.file.name : data.content,
          classification: classification,
          inputType: data.type,
        });
        setStage("results");
      }, 500);
    } catch (err) {
      console.error("Source Check failed:", err);
      setError(err instanceof Error ? err.message : "Source Check failed");
      showToast(err instanceof Error ? err.message : "Analysis failed", "error");
      setStage("input");
    }
  };

  const handleBack = () => {
    setStage("input");
    setResult(null);
    setError(null);
    setContentClassification(null);
  };

  if (loading) {
    return (
      <div className="min-h-screen pt-32 pb-20 px-4 sm:px-6 lg:px-8 flex items-center justify-center">
        <div className="text-center text-slate-400">Restoring session...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen pt-32 pb-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-2xl mx-auto text-center">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-yellow-500/10 border border-yellow-500/20 mb-6">
              <Shield className="w-4 h-4 text-yellow-400" />
              <span className="text-yellow-300 text-sm font-bold">AUTHENTICATION REQUIRED</span>
            </div>
            <h1 className="text-4xl font-black text-white mb-4">Sign In to Access Source Check</h1>
            <p className="text-slate-400 mb-8">
              To use our OSINT intelligence verification system, please log in or create an account.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link
                href="/login"
                className="px-8 py-3 rounded-xl bg-yellow-500 hover:bg-yellow-400 text-black font-bold transition-all"
              >
                Sign In
              </Link>
              <Link
                href="/signup"
                className="px-8 py-3 rounded-xl bg-white/5 hover:bg-white/10 text-white font-bold border border-white/10 transition-all"
              >
                Create Account
              </Link>
            </div>
          </motion.div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen pt-32 pb-20 px-4 sm:px-6 lg:px-8">
      <div className="max-w-5xl mx-auto">
        <AnimatePresence mode="wait">
          {(stage === "input" || stage === "classifying") && (
            <motion.div
              key="input"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.3 }}
            >
              <div className="mb-12">
                <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
                  <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-cyan-500/10 border border-cyan-500/20 mb-6">
                    <Sparkles className="w-4 h-4 text-cyan-300" />
                    <span className="text-cyan-200 text-sm font-bold">OSINT INTELLIGENCE</span>
                  </div>
                  <h1 className="text-5xl font-black text-white mb-4 uppercase tracking-tighter">
                    Information Verification<br />
                    <span className="bg-gradient-to-r from-cyan-300 via-sky-300 to-blue-400 bg-clip-text text-transparent">& Source Check</span>
                  </h1>
                  <p className="text-xl text-slate-400 max-w-2xl">
                    Submit content to retrieve actual evidence, analyze source credibility, and get investigative intelligence assessments grounded in real sources.
                  </p>
                </motion.div>
              </div>

              {error && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mb-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-start gap-3"
                >
                  <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" />
                  <div className="text-rose-300">{error}</div>
                </motion.div>
              )}

              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="glass-card rounded-2xl p-8 border border-white/10"
              >
                <VerificationInput onSubmit={handleSubmit} isLoading={stage === "classifying"} />
              </motion.div>
            </motion.div>
          )}

          {stage === "analyzing" && (
            <motion.div
              key="analyzing"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="flex flex-col items-center justify-center min-h-[60vh]"
            >
              <div className="text-center space-y-8">
                <motion.div animate={{ rotate: 360 }} transition={{ duration: 3, repeat: Infinity, ease: "linear" }}>
                  <Shield className="w-14 h-14 text-cyan-300 mx-auto" />
                </motion.div>

                <div>
                  <h2 className="text-3xl font-bold text-white mb-2">Running Source Check</h2>
                  <p className="text-slate-400">{currentStep || "Preparing Source Check"}</p>
                  {contentClassification && (
                    <p className="text-xs text-slate-500 mt-2">
                      Type: {contentClassification?.type || "unknown"} • Sources: {Array.isArray(contentClassification?.suggested_sources) ? contentClassification.suggested_sources.join(", ") : "n/a"}
                    </p>
                  )}
                </div>

                <div className="w-full max-w-md">
                  <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden">
                    <motion.div
                      className="h-full bg-gradient-to-r from-cyan-400 via-sky-400 to-blue-500 rounded-full"
                      initial={{ width: 0 }}
                      animate={{ width: `${scanProgress}%` }}
                      transition={{ duration: 0.5 }}
                    />
                  </div>
                  <div className="mt-3 text-sm text-slate-400 text-center">{Math.round(scanProgress)}% complete</div>
                </div>

                <div className="space-y-2 text-left mx-auto max-w-md">
                  {timeline.map((step, idx) => {
                    const completed = idx < getCompletedSteps(timelineProgress);
                    const active = idx === getCompletedSteps(timelineProgress);
                    return (
                      <motion.div
                        key={step}
                        initial={{ opacity: 0, x: -16 }}
                        animate={{ opacity: completed || active ? 1 : 0.45, x: 0 }}
                        className={`flex items-center gap-3 rounded-xl border px-4 py-3 text-sm ${
                          completed
                            ? "border-cyan-500/20 bg-cyan-500/10 text-cyan-100"
                            : active
                            ? "border-sky-500/25 bg-sky-500/10 text-sky-100"
                            : "border-white/5 bg-white/[0.03] text-slate-500"
                        }`}
                      >
                        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-black/20 text-xs">
                          {completed ? <CheckCircle2 className="h-4 w-4 text-cyan-300" /> : active ? <Loader2 className="h-4 w-4 animate-spin text-sky-300" /> : "○"}
                        </span>
                        <span>{step}</span>
                      </motion.div>
                    );
                  })}
                </div>
              </div>
            </motion.div>
          )}

          {stage === "results" && result && (
            <motion.div
              key={`results-${loadKey}`}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
            >
              <IntelErrorBoundary
                onRetry={() => setLoadKey((value) => value + 1)}
                retryLabel="Retry report"
              >
                <IntelDashboard result={result} onBack={handleBack} />
              </IntelErrorBoundary>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
