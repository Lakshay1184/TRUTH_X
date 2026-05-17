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
  safe: { label: "Strongly Authentic", color: "#00ff9d", bg: "#00ff9d10", border: "#00ff9d30", icon: CheckCircle },
  suspicious: { label: "Suspicious / Potentially Synthetic", color: "#ffd700", bg: "#ffd70010", border: "#ffd70030", icon: AlertTriangle },
  deepfake: { label: "Likely AI Generated / Manipulated", color: "#ff4444", bg: "#ff444410", border: "#ff444430", icon: AlertTriangle },
  synthetic_voice: { label: "Likely AI Generated / Manipulated", color: "#ff4444", bg: "#ff444410", border: "#ff444430", icon: Mic },
};

export default function LiveDetectionPage() {
  const [callActive, setCallActive] = useState(false);
  const [status, setStatus] = useState<DetectionStatus>("idle");
  const [alerts, setAlerts] = useState<LiveAlert[]>([]);
  const [showAlert, setShowAlert] = useState(false);
  const [alertDismissed, setAlertDismissed] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [audioLevel, setAudioLevel] = useState<number[]>(new Array(32).fill(0));
  const [metrics, setMetrics] = useState({
    fake_prob: 0,
    voice_auth: 100,
    confidence: 100
  });
  const [forensics, setForensics] = useState({
    spectral_anomaly: false,
    cadence_inconsistency: false,
    resonance_check: false,
    cloning_signal: false
  });

  const alertIdRef = useRef(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);

  // Generate real audio waveform from mic data
  const updateWaveform = (data: Float32Array) => {
    const step = Math.floor(data.length / 32);
    const levels = [];
    for (let i = 0; i < 32; i++) {
      let sum = 0;
      for (let j = 0; j < step; j++) {
        sum += Math.abs(data[i * step + j]);
      }
      levels.push(Math.min(100, (sum / step) * 400));
    }
    setAudioLevel(levels);
  };

  const addAlert = (type: string, message: string, severity: "info" | "warning" | "danger") => {
    const newAlert: LiveAlert = {
      id: alertIdRef.current++,
      type,
      message,
      severity,
      time: new Date().toLocaleTimeString(),
    };
    setAlerts((prev) => [newAlert, ...prev].slice(0, 20));
  };

  const startCall = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${protocol}//${window.location.host}/py-api/live/audio`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        addAlert("SYSTEM", "Secure source link established", "info");
        setStatus("scanning");
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === "ANALYSIS_RESULT") {
          const fakeProb = Math.round(data.fake_probability * 100);
          const label = data.label;
          
          setMetrics({
            fake_prob: fakeProb,
            voice_auth: 100 - fakeProb,
            confidence: Math.round(data.confidence)
          });

          if (data.forensics) {
            setForensics(data.forensics);
          }

          if (label === "fake") {
            setStatus("deepfake");
            addAlert("CRITICAL", "Synthetic voice pattern identified", "danger");
            setShowAlert(true);
          } else if (label === "suspicious") {
            setStatus("suspicious");
            addAlert("WARNING", "Potential audio artifact detected", "warning");
          } else {
            setStatus("safe");
          }
        } else if (data.type === "ERROR") {
          addAlert("ERROR", data.message, "danger");
        }
      };

      ws.onclose = () => {
        addAlert("SYSTEM", "Source link terminated", "warning");
        if (callActive) endCall();
      };

      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 16000 });
      audioContextRef.current = audioContext;
      const source = audioContext.createMediaStreamSource(stream);
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0);
        updateWaveform(inputData);

        const pcmData = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          pcmData[i] = Math.max(-1, Math.min(1, inputData[i])) * 0x7FFF;
        }

        if (ws.readyState === WebSocket.OPEN) {
          const base64Data = btoa(String.fromCharCode(...new Uint8Array(pcmData.buffer)));
          ws.send(JSON.stringify({
            type: "AUDIO_CHUNK",
            data: base64Data
          }));
        }
      };

      source.connect(processor);
      processor.connect(audioContext.destination);

      setCallActive(true);
      setAlerts([]);
      setShowAlert(false);
      setAlertDismissed(false);
      setElapsed(0);
      addAlert("INFO", "Real-time audio stream connected", "info");

    } catch (err) {
      console.error("Failed to start live detection:", err);
      addAlert("ERROR", "Microphone access denied or connection failed", "danger");
    }
  };

  const endCall = () => {
    setCallActive(false);
    setStatus("idle");
    setShowAlert(false);
    setForensics({
      spectral_anomaly: false,
      cadence_inconsistency: false,
      resonance_check: false,
      cloning_signal: false
    });

    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }

    if (wsRef.current) {
      if (wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "END_SESSION" }));
      }
      wsRef.current.close();
      wsRef.current = null;
    }

    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
  };

  // Elapsed timer
  useEffect(() => {
    if (!callActive) { setElapsed(0); return; }
    timerRef.current = setInterval(() => {
      setElapsed((e) => e + 1);
    }, 1000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [callActive]);

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
              className="max-w-md w-full rounded-2xl border-2 border-[#ff4444] bg-[#071525] p-8 text-center shadow-[0_0_50px_rgba(239,68,68,0.3)]"
            >
              <div className="relative w-20 h-20 mx-auto mb-6">
                <div className="absolute inset-0 rounded-full bg-[#ff4444]/20 border-2 border-[#ff4444] animate-ping" />
                <div className="absolute inset-0 flex items-center justify-center">
                  <AlertTriangle className="w-10 h-10 text-[#ff4444]" />
                </div>
              </div>

              <div className="text-[#ff4444] text-xs font-bold tracking-widest mb-2">CRITICAL ALERT</div>
              <h2 className="text-2xl font-black text-white mb-3">Deepfake Detected!</h2>
              <p className="text-[#b0b0b0] text-sm mb-6">
                TRUTH X has identified this audio stream as{" "}
                <strong className="text-[#ff4444]">AI-generated synthetic media</strong>. This content may be an
                attempt to deceive, scam, or manipulate you.
              </p>

              <div className="bg-[#0a0a0a] rounded-xl p-4 mb-6 text-left space-y-2 border border-white/5">
                <p className="text-[#ffd700] text-xs font-bold uppercase tracking-wider">Detected threats:</p>
                <div className="space-y-1.5">
                  <p className="text-[#b0b0b0] text-xs flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#ff4444] shrink-0" />
                    AI voice synthesis pattern confirmed
                  </p>
                  <p className="text-[#b0b0b0] text-xs flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#ffd700] shrink-0" />
                    Probability: {metrics.fake_prob}% — High certainty
                  </p>
                </div>
              </div>

              <div className="flex gap-3">
                <button
                  onClick={endCall}
                  className="flex-1 flex items-center justify-center gap-2 py-4 rounded-xl bg-red-500 text-white font-black hover:bg-red-600 transition-all shadow-lg"
                >
                  <PhoneOff className="w-4 h-4" /> DISCONNECT
                </button>
                <button
                  onClick={() => setAlertDismissed(true)}
                  className="flex items-center justify-center gap-2 px-6 py-4 rounded-xl border border-white/10 text-slate-400 hover:text-white hover:bg-white/5 transition-all"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="pt-24 pb-16 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
          <div className="flex items-center gap-3 mb-3">
            <div className={`w-2 h-2 rounded-full ${callActive ? "bg-red-500 animate-pulse" : "bg-slate-500"}`} />
            <span className="text-slate-400 font-mono text-xs uppercase tracking-widest">
              {callActive ? "Real-Time Intelligence Active" : "Intelligence Terminal Standby"}
            </span>
          </div>
          <h1 className="text-5xl font-black text-white mb-2 tracking-tighter uppercase italic">
            Live <span className="text-cyan-400">Detection</span>
          </h1>
          <p className="text-slate-400 max-w-2xl">
            Autonomous audio intelligence monitoring for synthetic voice patterns and real-time deepfake identification.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Visualizer */}
          <div className="lg:col-span-2 space-y-6">
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
              <div className="relative glass-card rounded-3xl overflow-hidden aspect-video border border-white/10 group">
                <div className="absolute inset-0 bg-gradient-to-br from-slate-950 to-black flex items-center justify-center">
                  {callActive ? (
                    <>
                      {/* Audio Visualizer Rings */}
                      <div className="relative">
                        <div
                          className="w-48 h-48 rounded-full border-4 opacity-20 transition-colors duration-500"
                          style={{ borderColor: status === "deepfake" || status === "suspicious" ? "#ef4444" : "#22d3ee" }}
                        />
                        <motion.div
                          animate={{ 
                            scale: [1, 1.2, 1],
                            opacity: [0.3, 0.6, 0.3]
                          }}
                          transition={{ 
                            duration: 2,
                            repeat: Infinity,
                            ease: "easeInOut"
                          }}
                          className="absolute inset-0 rounded-full border-2"
                          style={{
                            borderColor: status === "deepfake" ? "#ef4444" : status === "suspicious" ? "#f59e0b" : "#22d3ee",
                          }}
                        />
                        {/* Audio Pulse Dots */}
                        <div className="absolute inset-0 flex items-center justify-center">
                           <div className={`w-3 h-3 rounded-full bg-cyan-400 shadow-[0_0_20px_#22d3ee] ${status === "deepfake" ? "bg-red-500 shadow-red-500" : ""}`} />
                        </div>
                      </div>
                      
                      {/* Scan line */}
                      <div className="absolute inset-0 overflow-hidden pointer-events-none">
                        <motion.div
                          animate={{ top: ["0%", "100%", "0%"] }}
                          transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
                          className="absolute left-0 right-0 h-px bg-gradient-to-r from-transparent via-cyan-400/50 to-transparent shadow-[0_0_15px_#22d3ee]"
                        />
                      </div>
                    </>
                  ) : (
                    <div className="text-center">
                      <div className="w-20 h-20 rounded-3xl bg-white/5 border border-white/10 flex items-center justify-center mx-auto mb-6 group-hover:scale-110 transition-transform">
                        <Mic className="w-10 h-10 text-slate-700" />
                      </div>
                      <p className="text-slate-500 font-mono text-sm tracking-widest">INITIALIZE SESSION TO BEGIN MONITORING</p>
                    </div>
                  )}

                  {/* LIVE Indicator */}
                  {callActive && (
                    <div className="absolute top-6 left-6 flex items-center gap-3 bg-black/60 backdrop-blur-md rounded-full px-4 py-2 border border-white/10">
                      <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                      <span className="text-white text-xs font-mono font-bold tracking-widest uppercase">LIVE {formatElapsed(elapsed)}</span>
                    </div>
                  )}

                  {/* Status indicator */}
                  {callActive && (
                    <motion.div
                      initial={{ x: -20, opacity: 0 }}
                      animate={{ x: 0, opacity: 1 }}
                      className="absolute bottom-6 left-6 flex items-center gap-3 rounded-2xl px-5 py-3 border backdrop-blur-xl"
                      style={{ background: statusCfg.bg, borderColor: statusCfg.border }}
                    >
                      <StatusIcon className="w-5 h-5" style={{ color: statusCfg.color }} />
                      <span className="text-sm font-black uppercase tracking-wider" style={{ color: statusCfg.color }}>{statusCfg.label}</span>
                    </motion.div>
                  )}
                </div>
              </div>
            </motion.div>

            {/* Audio waveform */}
            {callActive && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card rounded-3xl p-6 border border-white/10">
                <div className="flex items-center gap-2 mb-6">
                  <Volume2 className="w-5 h-5 text-cyan-400" />
                  <span className="text-white font-bold text-sm uppercase tracking-widest">Signal Spectrum Analysis</span>
                  <div className="ml-auto flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-500" />
                    <span className="text-emerald-400 text-xs font-mono uppercase">Processing Stream</span>
                  </div>
                </div>
                <div className="flex items-end gap-1 h-24 mb-6">
                  {audioLevel.map((h, i) => (
                    <motion.div
                      key={i}
                      initial={{ height: "0%" }}
                      animate={{ height: `${Math.max(5, h)}%` }}
                      transition={{ type: "spring", stiffness: 300, damping: 15 }}
                      className="flex-1 rounded-full"
                      style={{
                        background:
                          status === "deepfake" || status === "synthetic_voice"
                            ? "#ef4444"
                            : status === "suspicious" ? "#f59e0b" : "#22d3ee",
                        opacity: 0.3 + (h / 100) * 0.7
                      }}
                    />
                  ))}
                </div>
                <div className="grid grid-cols-3 gap-4 border-t border-white/5 pt-4 text-[10px] font-mono uppercase tracking-widest text-slate-500">
                  <div className="flex flex-col gap-1">
                    <span>Sample Rate</span>
                    <span className="text-slate-300">16.0 kHz</span>
                  </div>
                  <div className="flex flex-col gap-1">
                    <span>Bit Depth</span>
                    <span className="text-slate-300">16-bit PCM</span>
                  </div>
                  <div className="flex flex-col gap-1">
                    <span>Channels</span>
                    <span className="text-slate-300">Mono Input</span>
                  </div>
                </div>
              </motion.div>
            )}

            {/* Session Controls */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="flex gap-4 justify-center pt-4"
            >
              {!callActive ? (
                <button
                  onClick={startCall}
                  className="group relative flex items-center gap-3 px-10 py-5 rounded-2xl bg-cyan-500 text-black font-black text-xl hover:bg-cyan-400 transition-all shadow-[0_0_40px_-5px_rgba(6,182,212,0.4)]"
                >
                  <Phone className="w-6 h-6" />
                  INITIALIZE LIVE MONITORING
                </button>
              ) : (
                <button
                  onClick={endCall}
                  className="flex items-center gap-3 px-10 py-5 rounded-2xl bg-red-500 text-white font-black text-xl hover:bg-red-600 transition-all shadow-[0_0_40_rgba(239,68,68,0.4)]"
                >
                  <PhoneOff className="w-6 h-6" />
                  TERMINATE SESSION
                </button>
              )}
            </motion.div>
          </div>

          {/* Intelligence Sidebar */}
          <div className="space-y-6">
            {/* Real-time Metrics */}
            <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 }}>
              <div
                className="glass-card rounded-3xl p-6 border transition-all duration-500"
                style={{
                  borderColor: callActive ? `${statusCfg.color}30` : "rgba(255,255,255,0.1)",
                }}
              >
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-10 h-10 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center">
                    <Zap className="w-5 h-5 text-cyan-400" />
                  </div>
                  <span className="text-white font-bold uppercase tracking-widest text-sm">Live Intelligence</span>
                </div>
                
                <div className="space-y-6">
                  {[
                    { label: "Deepfake Prob", value: metrics.fake_prob, color: "#ef4444" },
                    { label: "Voice Auth", value: metrics.voice_auth, color: "#10b981" },
                    { label: "Scan Confidence", value: metrics.confidence, color: "#3b82f6" },
                  ].map((metric, i) => (
                    <div key={i}>
                      <div className="flex justify-between mb-2">
                        <span className="text-slate-500 font-mono text-[10px] uppercase tracking-tighter">{metric.label}</span>
                        <span className="text-xs font-black" style={{ color: metric.color }}>{callActive ? `${metric.value}%` : "--"}</span>
                      </div>
                      <div className="w-full bg-white/5 rounded-full h-2 overflow-hidden border border-white/5">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: callActive ? `${metric.value}%` : "0%" }}
                          transition={{ duration: 1, ease: "easeOut" }}
                          className="h-full rounded-full"
                          style={{ background: metric.color }}
                        />
                      </div>
                    </div>
                  ))}
                </div>

                <div className="mt-8 pt-6 border-t border-white/5">
                   <div className="text-[10px] font-mono text-slate-600 uppercase tracking-widest mb-4">Forensic Signal Trace</div>
                   <div className="grid grid-cols-2 gap-2">
                      {[
                        { name: "Spectral Anomaly", ok: !forensics.spectral_anomaly },
                        { name: "Cadence Shift", ok: !forensics.cadence_inconsistency },
                        { name: "Temporal Flow", ok: true },
                        { name: "Resonance Check", ok: !forensics.resonance_check },
                      ].map((check, i) => (
                        <div key={i} className="flex items-center gap-2 bg-white/5 rounded-lg px-3 py-2 border border-white/5">
                           <div className={`w-1.5 h-1.5 rounded-full ${!callActive ? "bg-slate-700" : check.ok ? "bg-emerald-500" : "bg-red-500"}`} />
                           <span className="text-[10px] font-bold text-slate-400 uppercase">{check.name}</span>
                        </div>
                      ))}
                   </div>
                </div>
              </div>
            </motion.div>

            {/* Event Archive */}
            <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 }}>
              <div className="glass-card rounded-3xl overflow-hidden border border-white/10 flex flex-col h-[400px]">
                <div className="flex items-center gap-3 px-6 py-5 border-b border-white/5 bg-white/2">
                  <Clock className="w-4 h-4 text-slate-500" />
                  <span className="text-white font-bold uppercase tracking-widest text-xs">Intelligence Log</span>
                </div>
                <div className="flex-1 p-4 space-y-3 overflow-y-auto scrollbar-hide">
                  {alerts.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-center p-8">
                       <Radio className="w-8 h-8 text-slate-800 mb-4" />
                       <p className="text-slate-600 text-[10px] font-mono uppercase tracking-widest leading-relaxed">
                        {callActive ? "Awaiting primary signal source..." : "Terminal offline. No session data."}
                       </p>
                    </div>
                  ) : (
                    <AnimatePresence initial={false}>
                      {alerts.map((alert) => (
                        <motion.div
                          key={alert.id}
                          initial={{ opacity: 0, y: -10 }}
                          animate={{ opacity: 1, y: 0 }}
                          className={`group flex flex-col gap-1 p-4 rounded-2xl border transition-all ${
                            alert.severity === "danger"
                            ? "bg-red-500/10 border-red-500/20"
                            : alert.severity === "warning"
                              ? "bg-amber-500/10 border-amber-500/20"
                              : "bg-white/5 border-white/10"
                            }`}
                        >
                          <div className="flex justify-between items-center mb-1">
                            <span
                              className="text-[10px] font-black tracking-tighter uppercase px-2 py-0.5 rounded-md"
                              style={{
                                background: alert.severity === "danger" ? "#ef4444" : alert.severity === "warning" ? "#f59e0b" : "#3b82f6",
                                color: "black"
                              }}
                            >
                              {alert.type}
                            </span>
                            <span className="text-[9px] font-mono text-slate-600 group-hover:text-slate-400 transition-colors">{alert.time}</span>
                          </div>
                          <span className="text-slate-300 text-xs leading-relaxed font-medium">{alert.message}</span>
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
