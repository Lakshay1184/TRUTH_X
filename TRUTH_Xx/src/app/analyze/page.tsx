
"use client";

import { useState, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import ResultsDashboard from "@/components/ResultsDashboard";
import { analyzeContent, checkBackendHealth } from "@/services/api";
import {
  Upload,
  Video,
  Mic,
  FileText,
  Image,
  Link as LinkIcon,
  X,
  Play,
  Shield,
  Zap,
  AlertTriangle,
  ChevronRight,
} from "lucide-react";

type Tab = "video" | "audio" | "text" | "image";
type Stage = "idle" | "uploading" | "scanning" | "results";

const tabs: { id: Tab; label: string; icon: typeof Video; accept: string; color: string }[] = [
  { id: "video", label: "Video", icon: Video, accept: "video/*", color: "#00d4ff" },
  { id: "audio", label: "Audio", icon: Mic, accept: "audio/*", color: "#00ff9d" },
  { id: "text", label: "Text / Article", icon: FileText, accept: ".txt,.pdf,.doc", color: "#a855f7" },
  { id: "image", label: "Image", icon: Image, accept: "image/*", color: "#ffd700" },
];

const scanMessages = [
  "Initializing neural analysis engine...",
  "Extracting metadata fingerprints...",
  "Running deepfake detection model...",
  "Analyzing frequency anomalies...",
  "Cross-referencing content database...",
  "Generating authenticity score...",
  "Compiling forensic report...",
];

export default function AnalyzePage() {
  const [activeTab, setActiveTab] = useState<Tab>("video");
  const [stage, setStage] = useState<Stage>("idle");
  const [dragOver, setDragOver] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [textInput, setTextInput] = useState("");
  const [urlInput, setUrlInput] = useState("");
  const [scanStep, setScanStep] = useState(0);
  const [scanProgress, setScanProgress] = useState(0);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [apiResult, setApiResult] = useState<any>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) setUploadedFile(file);
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) setUploadedFile(file);
  };

  const analyzeFile = async () => {
    if (!uploadedFile && !textInput.trim() && !urlInput.trim()) return;

    setStage("uploading");
    setUploadProgress(0);

    // Check health first
    const isBackendUp = await checkBackendHealth();
    if (!isBackendUp) {
      alert("Backend API is not running at http://localhost:8000. Please start the server.");
      setStage("idle");
      return;
    }

    // Simulate upload progress
    let progress = 0;
    const interval = setInterval(() => {
      progress += 5;
      setUploadProgress(progress);
      if (progress >= 100) {
        clearInterval(interval);
        setStage("scanning");
        startRealAnalysis();
      }
    }, 50);
  };

  const startRealAnalysis = async () => {
    setScanProgress(0);
    setScanStep(0);

    let step = 0;
    const stepInterval = setInterval(() => {
      step++;
      setScanStep(step);
      if (step >= scanMessages.length) {
        clearInterval(stepInterval);
        // This timeout is for visual effect, actual results will come from API
        setTimeout(async () => {
          try {
            // analyzeContent takes (file, text) - urlInput is treated as text query for now
            const query = textInput || urlInput;
            const result = await analyzeContent(uploadedFile, query);
            console.log("Analysis Result:", result);
            setApiResult(result);
            setStage("results");
          } catch (error) {
            console.error("Analysis failed:", error);
            alert("Analysis failed. See console for details.");
            setStage("idle");
          }
        }, 600);
      }
    }, 600);

    const progressInterval = setInterval(() => {
      setScanProgress((p) => {
        if (p >= 100) { clearInterval(progressInterval); return 100; }
        return p + 2;
      });
    }, 85);
  };

  const reset = () => {
    setStage("idle");
    setApiResult(null);
    setUploadedFile(null);
    setTextInput("");
    setUrlInput("");
    setScanProgress(0);
    setScanStep(0);
  };

  const activeTabData = tabs.find((t) => t.id === activeTab)!;

  if (stage === "results") {
    return <ResultsDashboard tab={activeTab} onReset={reset} fileName={uploadedFile?.name} textSnippet={textInput} apiResult={apiResult} />;
  }

  return (
    <div className="min-h-screen">
      <div className="pt-24 pb-16 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mb-10">
          <div className="flex items-center gap-2 mb-3">
            <Shield className="w-5 h-5 text-[#00d4ff]" />
            <span className="text-[#777777] text-sm">TRUTH X — Multimodal Analysis Engine</span>
          </div>
          <h1 className="text-4xl font-black text-white mb-2">Analyze Content</h1>
          <p className="text-[#777777]">
            Upload a file, paste text, or enter a URL to check for AI manipulation, deepfakes, or misinformation.
          </p>
        </motion.div>

        {/* Scanning Overlay */}
        <AnimatePresence>
          {stage === "scanning" && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-50 bg-black/80 backdrop-blur-xl flex items-center justify-center"
            >
              <div className="text-center max-w-md mx-auto px-4">
                {/* Radar animation */}
                <div className="relative w-40 h-40 mx-auto mb-8">
                  <div className="absolute inset-0 rounded-full border-2 border-cyan-500/20" />
                  <div className="absolute inset-4 rounded-full border border-cyan-500/15" />
                  <div className="absolute inset-8 rounded-full border border-cyan-500/10" />
                  <div className="absolute inset-0 rounded-full border-t-2 border-cyan-500 radar-spin" />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <Shield className="w-10 h-10 text-cyan-500" />
                  </div>
                  {/* Pulse rings */}
                  <div className="absolute inset-0 rounded-full border border-cyan-500/30 pulse-ring" />
                </div>

                <h2 className="text-2xl font-black text-white mb-2">Analyzing Content</h2>
                <p className="text-slate-400 text-sm mb-6">
                  {scanMessages[Math.min(scanStep, scanMessages.length - 1)]}
                </p>

                {/* Progress bar */}
                <div className="w-full bg-[#0d2137] rounded-full h-2 mb-3 overflow-hidden">
                  <motion.div
                    className="h-2 rounded-full bg-[#00d4ff] glow-cyan-sm"
                    animate={{ width: `${scanProgress}%` }}
                    transition={{ duration: 0.1 }}
                  />
                </div>
                <p className="text-[#00d4ff] text-sm font-mono">{scanProgress}% complete</p>

                {/* Steps */}
                <div className="mt-6 text-left space-y-1.5">
                  {scanMessages.slice(0, Math.min(scanStep + 1, scanMessages.length)).map((msg, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs">
                      {i < scanStep ? (
                        <Zap className="w-3 h-3 text-[#00ff9d] shrink-0" />
                      ) : (
                        <div className="w-3 h-3 rounded-full border border-[#00d4ff] blink shrink-0" />
                      )}
                      <span className={i < scanStep ? "text-[#00ff9d]" : "text-[#00d4ff]"}>{msg}</span>
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Tab Switcher */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
          <div className="flex gap-1 p-1 bg-white/5 rounded-xl border border-white/10 mb-6 overflow-x-auto">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => { setActiveTab(tab.id); setUploadedFile(null); }}
                  className={`flex-1 min-w-[100px] flex items-center justify-center gap-2 px-4 py-3 rounded-lg text-sm font-medium transition-all ${activeTab === tab.id
                    ? "bg-white/10 text-white border border-white/10 shadow-lg"
                    : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
                    }`}
                >
                  <Icon className="w-4 h-4" style={{ color: activeTab === tab.id ? tab.color : undefined }} />
                  {tab.label}
                </button>
              );
            })}
          </div>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main upload area */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="lg:col-span-2 space-y-6"
          >
            {/* File Drop Zone */}
            {(activeTab === "video" || activeTab === "audio" || activeTab === "image") && (
              <div
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => !uploadedFile && fileInputRef.current?.click()}
                className={`relative border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all ${dragOver
                  ? "border-[#00d4ff] bg-[#00d4ff]/5"
                  : uploadedFile
                    ? "border-[#00d4ff]/40 bg-[#00d4ff]/5 cursor-default"
                    : "border-[#222222] hover:border-[#00d4ff]/30 hover:bg-[#00d4ff]/3"
                  }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept={activeTabData.accept}
                  className="hidden"
                  onChange={handleFileChange}
                />

                {uploadedFile ? (
                  <div className="space-y-3">
                    <div
                      className="w-14 h-14 rounded-xl flex items-center justify-center mx-auto"
                      style={{ background: `${activeTabData.color}15`, border: `1px solid ${activeTabData.color}30` }}
                    >
                      {activeTab === "video" && <Play className="w-7 h-7" style={{ color: activeTabData.color }} />}
                      {activeTab === "audio" && <Mic className="w-7 h-7" style={{ color: activeTabData.color }} />}
                      {activeTab === "image" && <Image className="w-7 h-7" style={{ color: activeTabData.color }} />}
                    </div>
                    <div>
                      <p className="text-white font-semibold">{uploadedFile.name}</p>
                      <p className="text-[#777777] text-sm">
                        {(uploadedFile.size / 1024 / 1024).toFixed(2)} MB — Ready for analysis
                      </p>
                    </div>
                    <button
                      onClick={(e) => { e.stopPropagation(); setUploadedFile(null); }}
                      className="flex items-center gap-1 text-[#ff4444] text-sm hover:text-red-300 mx-auto"
                    >
                      <X className="w-3 h-3" /> Remove file
                    </button>
                  </div>
                ) : (
                  <div>
                    <div
                      className="w-16 h-16 rounded-xl flex items-center justify-center mx-auto mb-4"
                      style={{ background: `${activeTabData.color}10`, border: `1px solid ${activeTabData.color}20` }}
                    >
                      <Upload className="w-8 h-8" style={{ color: activeTabData.color }} />
                    </div>
                    <p className="text-white font-semibold mb-1">
                      Drop your {activeTab} file here
                    </p>
                    <p className="text-[#777777] text-sm mb-4">
                      or click to browse — supports{" "}
                      {activeTab === "video" ? "MP4, MOV, AVI, WebM" : activeTab === "audio" ? "MP3, WAV, M4A, OGG" : "JPG, PNG, WEBP, GIF"}
                    </p>
                    <span
                      className="text-xs px-3 py-1.5 rounded-full border"
                      style={{ color: activeTabData.color, borderColor: `${activeTabData.color}30`, background: `${activeTabData.color}10` }}
                    >
                      Max 500MB — Analyzed securely, deleted after scan
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Text input */}
            {activeTab === "text" && (
              <div className="space-y-4">
                <div className="glass rounded-xl overflow-hidden">
                  <div className="px-4 py-3 border-b border-[#222222] flex items-center gap-2">
                    <FileText className="w-4 h-4 text-[#a855f7]" />
                    <span className="text-[#b0b0b0] text-sm font-medium">Paste Text Content</span>
                  </div>
                  <textarea
                    value={textInput}
                    onChange={(e) => setTextInput(e.target.value)}
                    placeholder="Paste an article, social media post, message, or any text content you want to verify for AI generation or misinformation..."
                    className="w-full bg-transparent px-4 py-4 text-[#e0e0e0] placeholder-[#444444] text-sm outline-none resize-none h-48"
                  />
                  <div className="px-4 py-2 border-t border-[#222222] flex justify-between">
                    <span className="text-[#777777] text-xs">{textInput.length} characters</span>
                    {textInput && (
                      <button onClick={() => setTextInput("")} className="text-[#777777] text-xs hover:text-[#ff4444]">
                        Clear
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* URL input */}
            <div className="glass rounded-xl p-4">
              <div className="flex items-center gap-2 mb-3">
                <LinkIcon className="w-4 h-4 text-[#b0b0b0]" />
                <span className="text-[#b0b0b0] text-sm font-medium">Verify by URL</span>
                <span className="text-xs text-[#777777]">(articles, social posts, news links)</span>
              </div>
              <div className="flex gap-2">
                <input
                  type="url"
                  value={urlInput}
                  onChange={(e) => setUrlInput(e.target.value)}
                  placeholder="https://example.com/article-to-verify"
                  className="flex-1 bg-[#0a0a0a] border border-[#222222] rounded-lg px-4 py-2.5 text-[#e0e0e0] placeholder-[#444444] text-sm outline-none focus:border-[#00d4ff]/50"
                />
                <button
                  disabled={!urlInput}
                  className="px-4 py-2.5 rounded-lg bg-[#1a1a1a] border border-[#222222] text-[#b0b0b0] text-sm hover:border-[#00d4ff]/30 disabled:opacity-40"
                >
                  Load
                </button>
              </div>
            </div>

            {/* Analyze Button */}
            <motion.button
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.99 }}
              onClick={analyzeFile}
              disabled={!uploadedFile && !textInput.trim() && !urlInput.trim()}
              className="w-full flex items-center justify-center gap-3 px-6 py-4 rounded-xl bg-[#00d4ff] text-[#000000] font-black text-lg disabled:opacity-30 disabled:cursor-not-allowed glow-cyan transition-all hover:bg-[#00d4ff]/90"
            >
              <Shield className="w-6 h-6" />
              Analyze Content
              <ChevronRight className="w-5 h-5" />
            </motion.button>
          </motion.div>

          {/* Sidebar tips */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="space-y-4"
          >
            <div className="glass rounded-xl p-5">
              <div className="flex items-center gap-2 mb-4">
                <Zap className="w-4 h-4 text-[#ffd700]" />
                <span className="text-white font-semibold text-sm">What we detect</span>
              </div>
              <div className="space-y-3">
                {[
                  { label: "Face Deepfakes", desc: "AI-swapped faces in video/image", color: "#00d4ff" },
                  { label: "Voice Cloning", desc: "Synthetic AI voice generation", color: "#00ff9d" },
                  { label: "GAN Artifacts", desc: "AI-generated image patterns", color: "#ffd700" },
                  { label: "Text AI Patterns", desc: "LLM-generated writing style", color: "#a855f7" },
                  { label: "Metadata Forgery", desc: "Tampered file headers/EXIF", color: "#ff6b35" },
                  { label: "Context Shifting", desc: "Real content, false narrative", color: "#ff4444" },
                ].map((item, i) => (
                  <div key={i} className="flex items-start gap-3">
                    <div className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0" style={{ background: item.color }} />
                    <div>
                      <p className="text-[#b0b0b0] text-xs font-medium">{item.label}</p>
                      <p className="text-[#777777] text-xs">{item.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="glass rounded-xl p-5 border border-[#ffd700]/10">
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle className="w-4 h-4 text-[#ffd700]" />
                <span className="text-[#ffd700] font-semibold text-sm">Privacy Notice</span>
              </div>
              <p className="text-[#777777] text-xs leading-relaxed">
                Uploaded content is processed in an isolated environment and permanently deleted after analysis.
                No data is stored or shared with third parties.
              </p>
            </div>

            <div className="glass rounded-xl p-5">
              <div className="text-[#777777] text-xs mb-3 font-medium uppercase tracking-wider">Recent analyses</div>
              {[
                { name: "video_clip_01.mp4", score: 23, status: "AI-Generated" },
                { name: "news_article.txt", score: 78, status: "Mostly Authentic" },
                { name: "photo_share.jpg", score: 91, status: "Authentic" },
              ].map((item, i) => (
                <div key={i} className="flex items-center justify-between py-2 border-b border-[#222222] last:border-0">
                  <span className="text-[#b0b0b0] text-xs truncate max-w-[120px]">{item.name}</span>
                  <span
                    className="text-xs font-bold"
                    style={{ color: item.score < 40 ? "#ff4444" : item.score < 70 ? "#ffd700" : "#00ff9d" }}
                  >
                    {item.score}%
                  </span>
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
