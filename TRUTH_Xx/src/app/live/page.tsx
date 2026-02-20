"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Radio,
  Shield,
  AlertTriangle,
  CheckCircle,
  Mic,
  Video,
  PhoneOff,
  Phone,
  Volume2,
  Eye,
  X,
  Zap,
  Clock,
} from "lucide-react";

type DetectionStatus = "idle" | "scanning" | "safe" | "suspicious" | "deepfake" | "synthetic_voice";

interface LiveAlert {
  id: number;
  type: string;
  message: string;
  severity: "info" | "warning" | "danger";
  time: string;
}

const statusConfig: Record<DetectionStatus, { label: string; color: string; bg: string; border: string; icon: typeof Shield }> = {
  idle: { label: "Standby", color: "#777777", bg: "#77777710", border: "#77777730", icon: Shield },
  scanning: { label: "Scanning...", color: "#00d4ff", bg: "#00d4ff10", border: "#00d4ff30", icon: Eye },
  safe: { label: "Safe — Authentic", color: "#00ff9d", bg: "#00ff9d10", border: "#00ff9d30", icon: CheckCircle },
  suspicious: { label: "Suspicious Activity", color: "#ffd700", bg: "#ffd70010", border: "#ffd70030", icon: AlertTriangle },
  deepfake: { label: "DEEPFAKE DETECTED", color: "#ff4444", bg: "#ff444410", border: "#ff444430", icon: AlertTriangle },
  synthetic_voice: { label: "SYNTHETIC VOICE", color: "#ff4444", bg: "#ff444410", border: "#ff444430", icon: Mic },
};

const mockAlertSequence: Partial<LiveAlert>[] = [
  { type: "INFO", message: "Real-time stream connected — analyzing frames", severity: "info" },
  { type: "INFO", message: "Audio frequency analysis started", severity: "info" },
  { type: "WARNING", message: "Facial region detected — running deepfake check", severity: "warning" },
  { type: "WARNING", message: "Prosody pattern anomaly — checking voice authenticity", severity: "warning" },
  { type: "DANGER", message: "Face-swap artifact detected in video frame #847", severity: "danger" },
  { type: "DANGER", message: "AI voice synthesis pattern confirmed — THREAT DETECTED", severity: "danger" },
];

export default function LiveDetectionPage() {
  const [callActive, setCallActive] = useState(false);
  const [status, setStatus] = useState<DetectionStatus>("idle");
  const [alerts, setAlerts] = useState<LiveAlert[]>([]);
  const [showAlert, setShowAlert] = useState(false);
  const [alertDismissed, setAlertDismissed] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [audioLevel, setAudioLevel] = useState<number[]>([]);
  const [videoFrame, setVideoFrame] = useState(0);
  const alertIdRef = useRef(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // Generate mock audio waveform
  useEffect(() => {
    if (!callActive) return;
    const interval = setInterval(() => {
      setAudioLevel(Array.from({ length: 32 }, () => Math.random() * 100));
      setVideoFrame((f) => f + 1);
    }, 150);
    return () => clearInterval(interval);
  }, [callActive]);

  // Elapsed timer
  useEffect(() => {
    if (!callActive) { setElapsed(0); return; }
    timerRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [callActive]);

  // Alert sequence simulation
  useEffect(() => {
    if (!callActive) return;
    setStatus("scanning");

    const timeouts: NodeJS.Timeout[] = [];
    mockAlertSequence.forEach((alert, i) => {
      const t = setTimeout(() => {
        const newAlert: LiveAlert = {
          id: alertIdRef.current++,
          type: alert.type!,
          message: alert.message!,
          severity: alert.severity!,
          time: new Date().toLocaleTimeString(),
        };
        setAlerts((prev) => [newAlert, ...prev].slice(0, 20));

        if (i === 3) setStatus("suspicious");
        if (i === 4) setStatus("deepfake");
        if (i === 5) {
          setStatus("deepfake");
          setShowAlert(true);
        }
      }, (i + 1) * 2500);
      timeouts.push(t);
    });

    return () => timeouts.forEach(clearTimeout);
  }, [callActive]);

  const startCall = () => {
    setCallActive(true);
    setAlerts([]);
    setShowAlert(false);
    setAlertDismissed(false);
    setStatus("scanning");
  };

  const endCall = () => {
    setCallActive(false);
    setStatus("idle");
    setShowAlert(false);
  };

  const formatElapsed = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, "0")}`;
  };

  const statusCfg = statusConfig[status];
  const StatusIcon = statusCfg.icon;

  return (
    <div className="min-h-screen">

      {/* Deepfake Alert Modal */}
      <AnimatePresence>
        {showAlert && !alertDismissed && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-[#000000]/90 backdrop-blur-sm px-4"
          >
            <motion.div
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.8, opacity: 0 }}
              className="max-w-md w-full rounded-2xl border-2 border-[#ff4444] bg-[#071525] p-8 text-center glow-red"
            >
              <div className="relative w-20 h-20 mx-auto mb-6">
                <div className="absolute inset-0 rounded-full bg-[#ff4444]/20 border-2 border-[#ff4444] pulse-ring" />
                <div className="absolute inset-0 flex items-center justify-center">
                  <AlertTriangle className="w-10 h-10 text-[#ff4444]" />
                </div>
              </div>

              <div className="text-[#ff4444] text-xs font-bold tracking-widest mb-2">CRITICAL ALERT</div>
              <h2 className="text-2xl font-black text-white mb-3">Deepfake Detected!</h2>
              <p className="text-[#b0b0b0] text-sm mb-6">
                TRUTH X has identified this video/audio as{" "}
                <strong className="text-[#ff4444]">AI-generated synthetic media</strong>. This content may be an
                attempt to deceive, scam, or manipulate you.
              </p>

              <div className="bg-[#0a0a0a] rounded-xl p-4 mb-6 text-left space-y-2">
                <p className="text-[#ffd700] text-xs font-bold">Detected threats:</p>
                <p className="text-[#b0b0b0] text-xs flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#ff4444] shrink-0" />
                  Face-swap deepfake artifact in video stream
                </p>
                <p className="text-[#b0b0b0] text-xs flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#ff4444] shrink-0" />
                  AI voice synthesis pattern (ElevenLabs match)
                </p>
                <p className="text-[#b0b0b0] text-xs flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#ffd700] shrink-0" />
                  Confidence: 94% — High certainty
                </p>
              </div>

              <div className="flex gap-3">
                <button
                  onClick={endCall}
                  className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl bg-[#ff4444] text-white font-bold hover:bg-[#ff4444]/90 transition-all"
                >
                  <PhoneOff className="w-4 h-4" /> End Call Now
                </button>
                <button
                  onClick={() => setAlertDismissed(true)}
                  className="flex items-center justify-center gap-2 px-4 py-3 rounded-xl border border-[#222222] text-[#777777] hover:text-white transition-all"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="pt-24 pb-16 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-2 h-2 rounded-full bg-red-500 blink" />
            <span className="text-[#777777] text-sm">Real-Time Detection Interface</span>
          </div>
          <h1 className="text-4xl font-black text-white mb-2">Live Detection</h1>
          <p className="text-[#777777]">
            Simulate real-time deepfake and synthetic voice detection for active calls or live video.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Video Preview */}
          <div className="lg:col-span-2 space-y-6">
            {/* Video frame */}
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
              <div className="relative glass rounded-2xl overflow-hidden aspect-video border border-[#222222]">
                {/* Simulated video content */}
                <div className="absolute inset-0 bg-gradient-to-br from-[#0a0a0a] to-[#000000] flex items-center justify-center">
                  {callActive ? (
                    <>
                      {/* Mock face outline */}
                      <div className="relative">
                        <div
                          className="w-32 h-40 rounded-full border-2 opacity-30"
                          style={{ borderColor: status === "deepfake" || status === "suspicious" ? "#ff4444" : "#00d4ff" }}
                        />
                        <div
                          className="absolute inset-0 rounded-full border-2"
                          style={{
                            borderColor: status === "deepfake" ? "#ff4444" : status === "suspicious" ? "#ffd700" : "#00d4ff",
                            animation: callActive ? "pulse 2s infinite" : "none",
                            opacity: 0.5,
                          }}
                        />
                        {/* Face detection box */}
                        {(status === "scanning" || status === "deepfake" || status === "suspicious") && (
                          <div
                            className="absolute inset-[-20px] rounded-sm border-2"
                            style={{
                              borderColor: status === "deepfake" ? "#ff4444" : status === "suspicious" ? "#ffd700" : "#00d4ff",
                            }}
                          >
                            <div className="absolute top-0 left-0 w-4 h-4 border-t-2 border-l-2" style={{ borderColor: "inherit" }} />
                            <div className="absolute top-0 right-0 w-4 h-4 border-t-2 border-r-2" style={{ borderColor: "inherit" }} />
                            <div className="absolute bottom-0 left-0 w-4 h-4 border-b-2 border-l-2" style={{ borderColor: "inherit" }} />
                            <div className="absolute bottom-0 right-0 w-4 h-4 border-b-2 border-r-2" style={{ borderColor: "inherit" }} />
                          </div>
                        )}
                      </div>
                      {/* Scan line */}
                      <div className="absolute inset-0 overflow-hidden pointer-events-none">
                        <div
                          className="absolute left-0 right-0 h-px bg-gradient-to-r from-transparent via-[#00d4ff]/60 to-transparent scan-line"
                          style={{ top: "50%" }}
                        />
                      </div>
                    </>
                  ) : (
                    <div className="text-center">
                      <Video className="w-16 h-16 text-[#222222] mx-auto mb-3" />
                      <p className="text-[#777777] text-sm">Start a session to begin detection</p>
                    </div>
                  )}

                  {/* Frame counter */}
                  {callActive && (
                    <div className="absolute top-4 left-4 flex items-center gap-2 bg-[#000000]/80 rounded-lg px-3 py-1.5">
                      <div className="w-1.5 h-1.5 rounded-full bg-red-500 blink" />
                      <span className="text-white text-xs font-mono">LIVE {formatElapsed(elapsed)}</span>
                    </div>
                  )}

                  {/* Frame number */}
                  {callActive && (
                    <div className="absolute top-4 right-4 bg-[#000000]/80 rounded px-2 py-1">
                      <span className="text-[#777777] text-xs font-mono">Frame #{(videoFrame * 30).toLocaleString()}</span>
                    </div>
                  )}

                  {/* Status indicator */}
                  {callActive && (
                    <div
                      className="absolute bottom-4 left-4 flex items-center gap-2 rounded-lg px-3 py-2 border"
                      style={{ background: statusCfg.bg, borderColor: statusCfg.border }}
                    >
                      <StatusIcon className="w-3.5 h-3.5" style={{ color: statusCfg.color }} />
                      <span className="text-xs font-bold" style={{ color: statusCfg.color }}>{statusCfg.label}</span>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>

            {/* Audio waveform */}
            {callActive && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass rounded-xl p-5">
                <div className="flex items-center gap-2 mb-4">
                  <Volume2 className="w-4 h-4 text-[#00ff9d]" />
                  <span className="text-[#b0b0b0] text-sm font-medium">Real-Time Audio Analysis</span>
                  <span className="ml-auto text-xs px-2 py-0.5 rounded-full bg-[#00ff9d]/10 text-[#00ff9d] border border-[#00ff9d]/30">
                    Analyzing
                  </span>
                </div>
                <div className="flex items-end gap-0.5 h-16">
                  {audioLevel.map((h, i) => (
                    <div
                      key={i}
                      className="flex-1 rounded-sm transition-all duration-150"
                      style={{
                        height: `${h}%`,
                        background:
                          status === "deepfake" || status === "synthetic_voice"
                            ? i > 8 && i < 16
                              ? "#ff4444"
                              : "#ff444440"
                            : i % 4 === 0
                              ? "#00ff9d"
                              : "#00ff9d40",
                      }}
                    />
                  ))}
                </div>
                <div className="mt-3 flex justify-between text-xs text-[#777777]">
                  <span>Frequency: 8-22kHz</span>
                  <span>Prosody Score: {status === "deepfake" ? "0.12 (Synthetic)" : "0.78 (Natural)"}</span>
                  <span>Sample Rate: 44.1kHz</span>
                </div>
              </motion.div>
            )}

            {/* Call Controls */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="flex gap-4 justify-center"
            >
              {!callActive ? (
                <button
                  onClick={startCall}
                  className="flex items-center gap-3 px-8 py-4 rounded-2xl bg-[#00ff9d] text-[#000000] font-black text-lg hover:bg-[#00ff9d]/90 transition-all glow-green"
                >
                  <Phone className="w-6 h-6" />
                  Start Live Detection Session
                </button>
              ) : (
                <button
                  onClick={endCall}
                  className="flex items-center gap-3 px-8 py-4 rounded-2xl bg-[#ff4444] text-white font-black text-lg hover:bg-[#ff4444]/90 transition-all glow-red"
                >
                  <PhoneOff className="w-6 h-6" />
                  End Session
                </button>
              )}
            </motion.div>
          </div>

          {/* Right panel */}
          <div className="space-y-6">
            {/* Current Status */}
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
              <div
                className="glass rounded-xl p-5 border transition-all"
                style={{
                  borderColor: statusCfg.border,
                  boxShadow: callActive && status !== "idle" ? `0 0 30px ${statusCfg.color}20` : "none",
                }}
              >
                <div className="flex items-center gap-3 mb-4">
                  <StatusIcon className="w-5 h-5" style={{ color: statusCfg.color }} />
                  <span className="text-white font-semibold text-sm">Detection Status</span>
                </div>
                <div
                  className="text-2xl font-black mb-2"
                  style={{ color: statusCfg.color }}
                >
                  {statusCfg.label}
                </div>
                <div className="grid grid-cols-2 gap-3 mt-4">
                  {[
                    { label: "Face Check", active: callActive, ok: status !== "deepfake" },
                    { label: "Voice Check", active: callActive, ok: status !== "synthetic_voice" && status !== "deepfake" },
                    { label: "Frame Analysis", active: callActive, ok: true },
                    { label: "AI Pattern", active: callActive, ok: status !== "deepfake" && status !== "suspicious" },
                  ].map((check, i) => (
                    <div key={i} className="bg-[#0a0a0a] rounded-lg px-3 py-2 border border-[#222222]">
                      <div className="flex items-center gap-1.5 mb-1">
                        {check.active ? (
                          check.ok ? (
                            <CheckCircle className="w-3 h-3 text-[#00ff9d]" />
                          ) : (
                            <AlertTriangle className="w-3 h-3 text-[#ff4444]" />
                          )
                        ) : (
                          <div className="w-3 h-3 rounded-full border border-[#222222]" />
                        )}
                        <span className="text-[#777777] text-xs">{check.label}</span>
                      </div>
                      <span
                        className="text-xs font-bold"
                        style={{
                          color: !check.active ? "#777777" : check.ok ? "#00ff9d" : "#ff4444",
                        }}
                      >
                        {!check.active ? "Standby" : check.ok ? "CLEAR" : "FLAGGED"}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>

            {/* Detection Metrics */}
            {callActive && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass rounded-xl p-5">
                <div className="flex items-center gap-2 mb-4">
                  <Zap className="w-4 h-4 text-[#00d4ff]" />
                  <span className="text-white font-semibold text-sm">Live Metrics</span>
                </div>
                <div className="space-y-3">
                  {[
                    { label: "Deepfake Probability", value: status === "deepfake" ? 94 : status === "suspicious" ? 61 : 8, color: "#ff4444" },
                    { label: "Voice Authenticity", value: status === "deepfake" ? 12 : status === "suspicious" ? 45 : 87, color: "#00ff9d" },
                    { label: "Frame Confidence", value: status === "deepfake" ? 6 : 82, color: "#00d4ff" },
                  ].map((metric, i) => (
                    <div key={i}>
                      <div className="flex justify-between mb-1">
                        <span className="text-[#777777] text-xs">{metric.label}</span>
                        <span className="text-xs font-bold" style={{ color: metric.color }}>{metric.value}%</span>
                      </div>
                      <div className="w-full bg-[#1a1a1a] rounded-full h-1.5">
                        <motion.div
                          className="h-1.5 rounded-full transition-all duration-500"
                          style={{ background: metric.color, width: `${metric.value}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}

            {/* Live Alert Log */}
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
              <div className="glass rounded-xl overflow-hidden">
                <div className="flex items-center gap-2 px-5 py-4 border-b border-[#222222]">
                  <Clock className="w-4 h-4 text-[#777777]" />
                  <span className="text-white font-semibold text-sm">Alert Log</span>
                  {alerts.length > 0 && (
                    <span className="ml-auto text-xs text-[#5a8aaa] bg-[#0d2137] px-2 py-0.5 rounded-full">
                      {alerts.length} events
                    </span>
                  )}
                </div>
                <div className="p-4 space-y-2 max-h-64 overflow-y-auto">
                  {alerts.length === 0 ? (
                    <p className="text-[#5a8aaa] text-xs text-center py-4">
                      {callActive ? "Waiting for events..." : "Start a session to see live alerts"}
                    </p>
                  ) : (
                    <AnimatePresence>
                      {alerts.map((alert) => (
                        <motion.div
                          key={alert.id}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          className={`flex items-start gap-2 px-3 py-2 rounded-lg text-xs ${alert.severity === "danger"
                            ? "bg-[#ff4444]/10 border border-[#ff4444]/20"
                            : alert.severity === "warning"
                              ? "bg-[#ffd700]/10 border border-[#ffd700]/20"
                              : "bg-[#00d4ff]/5 border border-[#00d4ff]/10"
                            }`}
                        >
                          <span
                            className="font-bold shrink-0"
                            style={{
                              color: alert.severity === "danger" ? "#ff4444" : alert.severity === "warning" ? "#ffd700" : "#00d4ff",
                            }}
                          >
                            [{alert.type}]
                          </span>
                          <span className="text-[#a0c4e0] flex-1">{alert.message}</span>
                          <span className="text-[#5a8aaa] shrink-0">{alert.time}</span>
                        </motion.div>
                      ))}
                    </AnimatePresence>
                  )}
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </div>
    </div>
  );
}
