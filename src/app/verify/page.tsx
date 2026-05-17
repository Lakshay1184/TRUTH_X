"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import VerificationInput from "@/components/VerificationInput";
import VerificationDashboard from "@/components/VerificationDashboard";
import { verifyNews } from "@/services/api";
import { Shield, AlertCircle } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import Link from "next/link";

type Stage = "input" | "analyzing" | "results";

export default function VerifyPage() {
  const { user, isAuthenticated, loading } = useAuth();
  const [stage, setStage] = useState<Stage>("input");
  const [scanProgress, setScanProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState("");
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const steps = [
    "Extracting claims and factual statements",
    "Searching trusted sources via Tavily",
    "Retrieving relevant evidence from RAG",
    "Analyzing contradictions",
    "Verifying source credibility",
    "Analyzing social propagation",
    "Generating investigative findings",
    "Finalizing credibility score",
  ];

  const handleSubmit = async (data: { type: string; content: string; file?: File }) => {
    if (!isAuthenticated) {
      setError("Please log in to use verification features");
      return;
    }

    setError(null);
    setStage("analyzing");
    setScanProgress(0);
    setCurrentStep(steps[0]);

    try {
      let stepIndex = 0;
      const stepInterval = setInterval(() => {
        stepIndex = Math.min(stepIndex + 1, steps.length - 1);
        setCurrentStep(steps[stepIndex]);
        setScanProgress(Math.round((stepIndex / (steps.length - 1)) * 100));
      }, 3000);

      const verificationResult = await verifyNews({
        type: data.type,
        content: data.content,
        file: data.file,
        onProgress: (progress) => {
          setScanProgress(progress);
        },
      });

      clearInterval(stepInterval);
      setScanProgress(100);
      setCurrentStep("Analysis complete");

      setTimeout(() => {
        setResult(verificationResult);
        setStage("results");
      }, 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification failed");
      setStage("input");
    }
  };

  const handleBack = () => {
    setStage("input");
    setResult(null);
    setError(null);
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
                <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-cyan-500/10 border border-cyan-500/20 mb-6">
              <Shield className="w-4 h-4 text-cyan-400" />
              <span className="text-cyan-300 text-sm font-bold">Verification Required</span>
            </div>
            <h1 className="text-4xl font-black text-white mb-4">Sign In to Verify Content</h1>
            <p className="text-slate-400 mb-8">
              To use our advanced OSINT verification pipeline, please log in or create an account.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link
                href="/login"
                className="px-8 py-3 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-black font-bold transition-all"
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
      <div className="max-w-4xl mx-auto">
        <AnimatePresence mode="wait">
          {stage === "input" && (
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
                    <Shield className="w-4 h-4 text-cyan-400" />
                    <span className="text-cyan-300 text-sm font-bold">OSINT VERIFICATION</span>
                  </div>
                  <h1 className="text-5xl font-black text-white mb-4">
                    Fake News & Misinformation<br />
                    <span className="text-gradient-cyan">Verification</span>
                  </h1>
                  <p className="text-xl text-slate-400 max-w-2xl">
                    Submit an article or website URL to verify its credibility using advanced
                    open-source intelligence and contradiction analysis.
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
                <VerificationInput onSubmit={handleSubmit} isLoading={stage === "analyzing"} />
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
                  <Shield className="w-16 h-16 text-cyan-400 mx-auto" />
                </motion.div>

                <div>
                  <h2 className="text-3xl font-bold text-white mb-2">Analyzing Content</h2>
                  <p className="text-slate-400">{currentStep}</p>
                </div>

                <div className="w-full max-w-md">
                  <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden">
                    <motion.div
                      className="h-full bg-gradient-to-r from-cyan-500 to-emerald-500 rounded-full"
                      initial={{ width: 0 }}
                      animate={{ width: `${scanProgress}%` }}
                      transition={{ duration: 0.5 }}
                    />
                  </div>
                  <div className="mt-3 text-sm text-slate-400 text-center">{scanProgress}% complete</div>
                </div>

                <div className="space-y-2">
                  {steps.map((step, idx) => (
                    <motion.div
                      key={idx}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: idx <= Math.ceil((scanProgress / 100) * steps.length) ? 1 : 0.3, x: 0 }}
                      className={`text-sm ${
                        idx <= Math.ceil((scanProgress / 100) * steps.length)
                          ? "text-cyan-300"
                          : "text-slate-500"
                      }`}
                    >
                      {idx <= Math.ceil((scanProgress / 100) * steps.length) ? "✓" : "○"} {step}
                    </motion.div>
                  ))}
                </div>
              </div>
            </motion.div>
          )}

          {stage === "results" && result && (
            <motion.div
              key="results"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
            >
              <VerificationDashboard result={result} onBack={handleBack} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
