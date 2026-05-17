"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Shield,
  ShieldCheck,
  AlertTriangle,
  CheckCircle,
  XCircle,
  ChevronLeft,
  Clock,
  Cpu,
  Mic,
  Video,
  FileText,
  Image as ImageIcon,
  Flag,
  Hash,
  TrendingDown,
  Download,
  Share2,
  Sparkles,
  Globe,
  ExternalLink,
  Scale,
  Fingerprint,
  Network,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from "recharts";

import { getVerificationKeyFindings } from "@/services/api";
import { useToast } from "@/context/ToastContext";


type Tab = "video" | "audio" | "text" | "image";
type ViewTab = Tab | "osint";

const mockResults: Record<Tab, {
  score: number;
  status: string;
  risk: "low" | "medium" | "high";
  confidence: number;
  anomalies: string[];
  insights: string[];
  timeline: { label: string; tag: string; color: string; suspicious: boolean }[];
  driftData: { t: string; v: number }[];
  fingerprint: { label: string; value: string; suspicious: boolean }[];
}> = {
  video: {
    score: 18,
    status: "AI-Generated",
    risk: "high",
    confidence: 94,
    anomalies: [
      "Facial blending artifacts detected at frames 142–189",
      "Eye blink pattern inconsistent with natural behavior",
      "Lighting discontinuity around jaw and hairline",
      "GAN fingerprint signature detected in pixel distribution",
      "Audio-visual sync drift +230ms at 0:14",
    ],
    insights: [
      "This video shows strong indicators of a face-swap deepfake. The facial region has been digitally replaced using a generative AI model.",
      "Natural eye blinking occurs 15–20 times per minute. This video shows irregular blinking that does not match normal human patterns.",
      "The audio does not perfectly match the lip movements — a common sign of synthetic media.",
    ],
    timeline: [
      { label: "Original upload", tag: "Source detected", color: "#00ff9d", suspicious: false },
      { label: "Frame manipulation", tag: "Edited", color: "#ffd700", suspicious: true },
      { label: "Audio replacement", tag: "Synthetic voice", color: "#ff6b35", suspicious: true },
      { label: "Re-encoded", tag: "Reused Media", color: "#ffd700", suspicious: true },
      { label: "Social post", tag: "Reposted 142x", color: "#a855f7", suspicious: false },
      { label: "Flagged by TRUTH X", tag: "Possible Manipulation", color: "#ff4444", suspicious: true },
    ],
    driftData: [
      { t: "0s", v: 82 }, { t: "5s", v: 78 }, { t: "10s", v: 71 }, { t: "15s", v: 34 },
      { t: "20s", v: 22 }, { t: "25s", v: 19 }, { t: "30s", v: 16 }, { t: "35s", v: 18 },
    ],
    fingerprint: [
      { label: "File Hash (SHA-256)", value: "a1f4...d892", suspicious: false },
      { label: "Creation Date", value: "2026-01-12 03:42 UTC", suspicious: true },
      { label: "GPS Metadata", value: "Stripped — suspicious", suspicious: true },
      { label: "Software Tag", value: "FaceSwap v2.3.1", suspicious: true },
      { label: "Resolution", value: "1920×1080 (upscaled)", suspicious: true },
      { label: "Codec", value: "H.264 — re-encoded", suspicious: false },
    ],
  },
  audio: {
    score: 31,
    status: "Synthetic Voice",
    risk: "high",
    confidence: 91,
    anomalies: [
      "Voice frequency spectrum shows TTS neural pattern",
      "Prosody pattern matches ElevenLabs voice model",
      "No natural breathing pauses detected between sentences",
      "Formant transitions too smooth — unnatural",
      "Background noise artificially added post-synthesis",
    ],
    insights: [
      "This audio clip appears to be generated using a neural text-to-speech (TTS) system, commonly used in AI voice scam calls.",
      "Natural human speech contains micro-pauses, breath sounds, and slight frequency variations. This audio is unusually clean — a sign of synthesis.",
      "The voice model matches a known commercial voice cloning platform with 91% confidence.",
    ],
    timeline: [
      { label: "Voice sample source", tag: "Public recording", color: "#00ff9d", suspicious: false },
      { label: "Voice cloned", tag: "Synthetic Voice", color: "#ff4444", suspicious: true },
      { label: "Script generated", tag: "AI Text", color: "#ffd700", suspicious: true },
      { label: "Call initiated", tag: "Scam attempt", color: "#ff4444", suspicious: true },
      { label: "Flagged by TRUTH X", tag: "Possible Manipulation", color: "#ff4444", suspicious: true },
    ],
    driftData: [
      { t: "0s", v: 70 }, { t: "3s", v: 65 }, { t: "6s", v: 50 }, { t: "9s", v: 35 },
      { t: "12s", v: 28 }, { t: "15s", v: 32 }, { t: "18s", v: 29 }, { t: "21s", v: 31 },
    ],
    fingerprint: [
      { label: "Audio Hash", value: "c8b2...f441", suspicious: false },
      { label: "Sample Rate", value: "22050 Hz (TTS default)", suspicious: true },
      { label: "Bit Depth", value: "16-bit PCM", suspicious: false },
      { label: "Voice Model Match", value: "ElevenLabs — 91% match", suspicious: true },
      { label: "Duration", value: "42.3 seconds", suspicious: false },
      { label: "Background Noise", value: "Artificially added", suspicious: true },
    ],
  },
  text: {
    score: 72,
    status: "Partially AI-Generated",
    risk: "medium",
    confidence: 83,
    anomalies: [
      "Burstiness score 0.12 — below human threshold (0.4+)",
      "Perplexity anomalies in paragraphs 2, 4, and 6",
      "Repetitive sentence structure typical of LLM output",
      "4 factual claims could not be verified against known sources",
      "Publication date inconsistency detected",
    ],
    insights: [
      "This article shows mixed signals — some sections appear human-written, others show strong AI generation patterns.",
      "AI-generated text tends to have a more uniform 'burstiness' — meaning sentences are similarly structured. Human writing is more varied.",
      "While the article is not entirely fabricated, key statistics cited in paragraphs 2 and 4 could not be verified and may be hallucinated by an AI model.",
    ],
    timeline: [
      { label: "Article published", tag: "Original post", color: "#00ff9d", suspicious: false },
      { label: "Partially rewritten", tag: "AI-assisted edit", color: "#ffd700", suspicious: true },
      { label: "Stats altered", tag: "Context Changed", color: "#ff6b35", suspicious: true },
      { label: "Reshared as news", tag: "Reused Media", color: "#ffd700", suspicious: true },
      { label: "Flagged by TRUTH X", tag: "Possible Manipulation", color: "#ff4444", suspicious: true },
    ],
    driftData: [
      { t: "P1", v: 85 }, { t: "P2", v: 72 }, { t: "P3", v: 80 },
      { t: "P4", v: 55 }, { t: "P5", v: 75 }, { t: "P6", v: 60 }, { t: "P7", v: 70 },
    ],
    fingerprint: [
      { label: "Word Count", value: "1,240 words", suspicious: false },
      { label: "Burstiness Score", value: "0.12 (below 0.4 threshold)", suspicious: true },
      { label: "Author", value: "Unknown / No byline", suspicious: true },
      { label: "Publication Date", value: "3 days in future", suspicious: true },
      { label: "Domain Age", value: "Created 4 weeks ago", suspicious: true },
      { label: "Citations", value: "2/6 verifiable", suspicious: true },
    ],
  },
  image: {
    score: 91,
    status: "Authentic",
    risk: "low",
    confidence: 97,
    anomalies: [
      "No GAN fingerprint detected",
      "EXIF metadata consistent with claimed device",
      "Noise distribution matches natural camera sensor",
    ],
    insights: [
      "This image shows no signs of digital manipulation or AI generation. The pixel distribution, noise pattern, and metadata are all consistent with a genuine photograph.",
      "The EXIF data matches an authentic Canon EOS R5 camera with standard settings.",
      "No signs of copy-paste manipulation, cloning, or AI upscaling were found.",
    ],
    timeline: [
      { label: "Photo taken", tag: "Original capture", color: "#00ff9d", suspicious: false },
      { label: "Minor color correction", tag: "Minor edit", color: "#00d4ff", suspicious: false },
      { label: "Published online", tag: "Social share", color: "#a855f7", suspicious: false },
      { label: "Verified by TRUTH X", tag: "Authentic", color: "#00ff9d", suspicious: false },
    ],
    driftData: [
      { t: "R1", v: 92 }, { t: "R2", v: 90 }, { t: "R3", v: 93 },
      { t: "R4", v: 91 }, { t: "R5", v: 94 }, { t: "R6", v: 89 },
    ],
    fingerprint: [
      { label: "File Hash (SHA-256)", value: "9e7c...a201", suspicious: false },
      { label: "Device", value: "Canon EOS R5", suspicious: false },
      { label: "GPS Location", value: "Present & consistent", suspicious: false },
      { label: "Software", value: "Adobe Lightroom (minor edit)", suspicious: false },
      { label: "Timestamp", value: "2026-02-20 10:42:15", suspicious: false },
      { label: "Resolution", value: "8192×5464 (original)", suspicious: false },
    ],
  },
};

const tabIcons: Record<Tab, typeof Video> = { video: Video, audio: Mic, text: FileText, image: ImageIcon };
const tabColors: Record<Tab, string> = { video: "#00d4ff", audio: "#00ff9d", text: "#a855f7", image: "#ffd700" };
const viewTabsBase: { id: Tab; label: string; icon: typeof Video; color: string }[] = [
  { id: "video", label: "Video", icon: Video, color: "#00d4ff" },
  { id: "audio", label: "Audio", icon: Mic, color: "#00ff9d" },
  { id: "text", label: "Text", icon: FileText, color: "#a855f7" },
  { id: "image", label: "Image", icon: ImageIcon, color: "#ffd700" },
];
const osintTab = { id: "osint" as const, label: "Source Verification", icon: ShieldCheck, color: "#00ff9d" };

interface Props {
  tab: Tab;
  onReset: () => void;
  fileName?: string;
  textSnippet?: string;
  apiResult?: any;
}

export default function ResultsDashboard({ tab, onReset, fileName, textSnippet, apiResult }: Props) {

  // When we have real API data, use it; otherwise fall back to mock
  const videoML = apiResult?.video_result;
  const audioML = apiResult?.audio_result;
  const textML = apiResult?.text_result;
  const imageML = apiResult?.image_result;
  const relatedArticles = apiResult?.related_articles || [];
  const newsVerification = apiResult?.news_verification || null;
  const hasVerificationData = !!(
    newsVerification ||
    (relatedArticles && relatedArticles.length > 0) ||
    apiResult?.social_graph
  );

  const [activeViewTab, setActiveViewTab] = useState<ViewTab>(tab);
  const resolvedViewTab: ViewTab = !hasVerificationData && activeViewTab === "osint" ? tab : activeViewTab;
  const analysisTab: Tab = resolvedViewTab === "osint" ? tab : resolvedViewTab;
  const viewTabs = hasVerificationData ? [...viewTabsBase, osintTab] : viewTabsBase;
  const viewMeta = viewTabs.find((item) => item.id === resolvedViewTab) || viewTabsBase[0];

  const hasRealData = !!apiResult;
  const realMeta = apiResult?.metadata || {};
  const realRisk = apiResult?.risk_assessment || {};
  const realScore = apiResult?.score ?? realRisk?.authenticity_score ?? null;
  const realRiskLevel = apiResult?.risk_level ?? realRisk?.risk_level ?? null;
  const mock = mockResults[analysisTab];
  const realModels = apiResult?.ai_models || [];
  const timeline = hasRealData ? (apiResult?.timeline || []) : mock.timeline;
  const processTime = apiResult?.processing_time_seconds;

  const toPercent = (value?: number, digits = 0) => {
    if (typeof value !== "number" || Number.isNaN(value)) return "N/A";
    const normalized = value <= 1 ? value * 100 : value;
    return `${normalized.toFixed(digits)}%`;
  };

  const formatTimestamp = (value?: string) => {
    if (!value) return "";
    const dt = new Date(value);
    if (Number.isNaN(dt.getTime())) return value;
    return dt.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
  };

  const rawKeyFindings = apiResult?.explainability?.key_findings;
  const keyFindingsFromReport = Array.isArray(rawKeyFindings)
    ? rawKeyFindings.filter((item: any) => typeof item === "string" && item.trim().length > 0)
    : typeof rawKeyFindings === "string"
      ? rawKeyFindings
        .split("\n")
        .map((item) => item.replace(/^[-•]\s*/, "").trim())
        .filter((item) => item.length > 0)
      : [];

  const keyFindingsFromReasons = Array.isArray(apiResult?.explainability?.overall_reasons)
    ? apiResult.explainability.overall_reasons
      .map((reason: any) => reason.detail || reason.indicator)
      .filter((item: any) => typeof item === "string" && item.trim().length > 0)
      .slice(0, 6)
    : [];

  const keyFindings = keyFindingsFromReport.length > 0 ? keyFindingsFromReport : keyFindingsFromReasons;

  const { showToast } = useToast();

  const evidenceSources = Array.isArray(newsVerification?.sources) ? newsVerification.sources : [];
  const getDomain = (url?: string) => {
    if (!url) return "";
    try {
      return new URL(url).hostname.replace(/^www\./, "");
    } catch {
      return "";
    }
  };

  const evidenceCards = [
    ...relatedArticles.map((article: any) => {
      const title = article?.title || article?.claim || article?.headline || "Untitled Source";
      const url = article?.url || "";
      const domain = getDomain(url) || article?.publisher || article?.source || "Unknown";
      const verdict = String(article?.verdict || article?.relation || "").toLowerCase();
      const stance = verdict.includes("contradict") || verdict.includes("false") || verdict.includes("misleading")
        ? "contradicting"
        : verdict.includes("support") || verdict.includes("true") || verdict.includes("verified")
          ? "supporting"
          : "informational";

      return {
        title,
        url,
        domain,
        score: article?.similarity_score ?? article?.score ?? null,
        timestamp: article?.published_at || article?.publishedAt || article?.date || article?.timestamp || "",
        stance,
      };
    }),
    ...evidenceSources.map((source: any) => ({
      title: String(source),
      url: "",
      domain: String(source),
      score: null,
      timestamp: "",
      stance: "informational",
    })),
  ];

  const contradictions = Array.isArray(newsVerification?.contradictions) ? newsVerification.contradictions : [];
  const provenance = apiResult?.credibility?.provenance || {};
  const socialGraph = apiResult?.social_graph || null;

  const [osintFindings, setOsintFindings] = useState<string[]>([]);
  const [osintFindingsLoading, setOsintFindingsLoading] = useState(false);
  const [osintFindingsSource, setOsintFindingsSource] = useState<"mistral" | "fallback" | null>(null);

  useEffect(() => {
    if (resolvedViewTab !== "osint" || !apiResult) return;

    let isActive = true;
    const run = async () => {
      setOsintFindingsLoading(true);
      try {
        const response = await getVerificationKeyFindings(apiResult);
        if (!isActive) return;
        const findings = Array.isArray(response?.findings) ? response.findings : [];
        if (findings.length > 0) {
          setOsintFindings(findings);
          setOsintFindingsSource(response?.source === "mistral" ? "mistral" : "fallback");
          return;
        }
      } catch {
        // fall back to local explainability
      }
      if (!isActive) return;
      setOsintFindings(keyFindings);
      setOsintFindingsSource("fallback");
      setOsintFindingsLoading(false);
    };

    run().finally(() => {
      if (isActive) setOsintFindingsLoading(false);
    });

    return () => {
      isActive = false;
    };
  }, [apiResult, keyFindings, resolvedViewTab]);

  // Build comprehensive fingerprint from real metadata
  const buildFingerprint = () => {
    if (!hasRealData) return mock.fingerprint;
    if (!realMeta || Object.keys(realMeta).length === 0) {
      return [{ label: "Metadata", value: "Not available for this input", suspicious: false }];
    }
    const fi = realMeta.file_info || {};
    const vid = realMeta.video || {};
    const aud = realMeta.audio || {};
    const tags = realMeta.tags || {};

    const items: { label: string; value: string; suspicious: boolean; section?: string }[] = [];

    // ── File Info
    items.push({ label: "File Name", value: realMeta.original_filename || fi.file_name || "Unknown", suspicious: false, section: "File" });
    items.push({ label: "Container Format", value: fi.container_format || "Unknown", suspicious: false, section: "File" });
    items.push({ label: "File Size", value: fi.file_size_mb ? `${fi.file_size_mb} MB` : "N/A", suspicious: false, section: "File" });
    items.push({ label: "Duration", value: fi.duration_human || `${fi.duration_seconds || 0}s`, suspicious: false, section: "File" });
    items.push({ label: "Total Bitrate", value: fi.total_bitrate_kbps ? `${fi.total_bitrate_kbps} kbps` : "N/A", suspicious: fi.total_bitrate_kbps > 0 && fi.total_bitrate_kbps < 2000 && (vid.width || 0) >= 1920, section: "File" });
    items.push({ label: "Streams", value: `${fi.nb_streams || 0}`, suspicious: false, section: "File" });

    // ── Video Stream
    if (vid.codec) {
      items.push({ label: "Video Codec", value: `${vid.codec}${vid.profile && vid.profile !== "unknown" ? ` (${vid.profile})` : ""}`, suspicious: false, section: "Video" });
      items.push({ label: "Resolution", value: vid.resolution || "N/A", suspicious: false, section: "Video" });
      items.push({ label: "Aspect Ratio", value: vid.display_aspect_ratio || "N/A", suspicious: false, section: "Video" });
      items.push({ label: "Frame Rate", value: `${vid.fps || "N/A"} fps${vid.avg_fps && vid.avg_fps !== vid.fps ? ` (avg: ${vid.avg_fps})` : ""}`, suspicious: false, section: "Video" });
      items.push({ label: "Video Bitrate", value: vid.bitrate_kbps !== "N/A" ? `${vid.bitrate_kbps} kbps` : "N/A", suspicious: false, section: "Video" });
      items.push({ label: "Pixel Format", value: vid.pixel_format || "unknown", suspicious: false, section: "Video" });
      items.push({ label: "Bit Depth", value: `${vid.bit_depth || 8}-bit`, suspicious: false, section: "Video" });
      items.push({ label: "Color Space", value: vid.color_space !== "unknown" ? vid.color_space : "N/A", suspicious: false, section: "Video" });
      if (vid.total_frames) items.push({ label: "Total Frames", value: `${vid.total_frames.toLocaleString()}`, suspicious: false, section: "Video" });
      if (vid.rotation && vid.rotation !== "0") items.push({ label: "Rotation", value: `${vid.rotation}°`, suspicious: false, section: "Video" });
    }

    // ── Audio Stream
    if (aud.codec) {
      items.push({ label: "Audio Codec", value: `${aud.codec}${aud.profile ? ` (${aud.profile})` : ""}`, suspicious: false, section: "Audio" });
      items.push({ label: "Sample Rate", value: aud.sample_rate_hz ? `${aud.sample_rate_hz.toLocaleString()} Hz` : "N/A", suspicious: false, section: "Audio" });
      items.push({ label: "Channels", value: `${aud.channels || "?"} (${aud.channel_layout || "unknown"})`, suspicious: false, section: "Audio" });
      items.push({ label: "Audio Bitrate", value: aud.bitrate_kbps !== "N/A" ? `${aud.bitrate_kbps} kbps` : "N/A", suspicious: false, section: "Audio" });
      if (aud.language && aud.language !== "unknown") items.push({ label: "Language", value: aud.language, suspicious: false, section: "Audio" });
    }

    // ── Device / Camera
    if (tags.camera_device) items.push({ label: "Camera / Device", value: tags.camera_device, suspicious: false, section: "Device" });
    if (tags.manufacturer) items.push({ label: "Manufacturer", value: tags.manufacturer, suspicious: false, section: "Device" });
    if (tags.software_version) items.push({ label: "Software", value: tags.software_version, suspicious: false, section: "Device" });

    // ── GPS
    if (tags.gps_location) {
      items.push({ label: "GPS Location", value: tags.gps_location, suspicious: false, section: "Location" });
    } else {
      items.push({ label: "GPS Location", value: "Not available", suspicious: true, section: "Location" });
    }

    // ── Tags / Encoder
    if (tags.creation_time) items.push({ label: "Creation Time", value: tags.creation_time, suspicious: false, section: "Tags" });
    if (tags.encoder) items.push({ label: "Encoder", value: tags.encoder, suspicious: true, section: "Tags" });
    if (tags.major_brand) items.push({ label: "Major Brand", value: tags.major_brand, suspicious: false, section: "Tags" });
    if (tags.title) items.push({ label: "Title", value: tags.title, suspicious: false, section: "Tags" });
    if (tags.comment) items.push({ label: "Comment", value: tags.comment, suspicious: false, section: "Tags" });

    return items;
  };



  // Build status text from real data
  const buildStatus = () => {
    // Primary: use the standardized verdict from backend if available
    if (apiResult?.verdict) return apiResult.verdict;

    // Fallback: Trust ML labels for the active tab
    if (analysisTab === "video" && videoML?.label && videoML.label !== "unknown") {
      if (videoML.label === "fake") return "Likely AI Generated / Manipulated";
      if (videoML.label === "real") return "Likely Authentic / Human";
    }
    if (analysisTab === "audio" && audioML?.label && audioML.label !== "unknown") {
      if (audioML.label === "fake") return "Likely AI Generated / Manipulated";
      if (audioML.label === "real") return "Likely Authentic / Human";
    }
    if (analysisTab === "text" && textML?.label && textML.label !== "unknown") {
      if (textML.label === "ai-generated") return "Likely AI Generated / Manipulated";
      if (textML.label === "human-written") return "Likely Authentic / Human";
    }
    if (analysisTab === "image" && imageML?.label && imageML.label !== "unknown") {
      if (imageML.label === "ai-generated") return "Likely AI Generated / Manipulated";
      if (imageML.label === "authentic") return "Likely Authentic / Human";
    }

    // 2. Score-based interpretation fallback (Standardized Scale)
    if (hasRealData && realScore !== null) {
      if (realScore <= 20) return "Likely AI Generated / Manipulated";
      if (realScore <= 40) return "Suspicious / Potentially Synthetic";
      if (realScore <= 60) return "Uncertain / Mixed Signals";
      if (realScore <= 80) return "Likely Authentic / Human";
      return "Strongly Authentic / Human";
    }

    return hasRealData ? "Analysis complete" : mock.status;
  };

  // Build anomalies from real flags + ML results
  const buildAnomalies = () => {
    const items: string[] = [];
    if (realRisk.flags && realRisk.flags.length > 0) {
      items.push(...realRisk.flags.map((f: any) => `${f.label}: ${f.detail}`));
    }
    if (apiResult?.credibility?.flags && apiResult.credibility.flags.length > 0) {
      items.push(...apiResult.credibility.flags.map((f: any) => `${f.label}: ${f.detail}`));
    }
    if (videoML && videoML.label === "fake" && !items.some(i => i.includes("Deepfake"))) {
      items.push(`Deepfake Detected: ML model confidence ${(videoML.confidence * 100).toFixed(1)}%`);
    }
    if (audioML && audioML.label === "fake") {
      items.push(`Synthetic Voice Detected: ${(audioML.confidence * 100).toFixed(1)}% confidence`);
    }
    if (textML && textML.label === "ai-generated") {
      items.push(`AI-Generated Text: ${(textML.ai_probability * 100).toFixed(1)}% probability`);
    }
    // If we have real data (even if no anomalies), return what we found (could be empty)
    if (hasRealData) return items;

    // Otherwise fallback to mock
    return items.length > 0 ? items : mock.anomalies;
  };

  // Build insights from real ML data
  const buildInsights = () => {
    const items: string[] = [];
    if (videoML && videoML.label && videoML.label !== "unknown") {
      if (videoML.label === "fake") {
        items.push(`The deepfake detection model classified this video as FAKE with ${(videoML.confidence * 100).toFixed(1)}% confidence. ${videoML.per_frame ? `${videoML.per_frame.length} frames were analyzed.` : ""}`);
      } else {
        items.push(`The deepfake detection model classified this video as REAL with ${(videoML.confidence * 100).toFixed(1)}% confidence. No manipulation artifacts were detected in the analyzed frames.`);
      }
    }
    if (textML && textML.label && textML.label !== "unknown") {
      if (textML.label === "ai-generated") {
        items.push(`The AI text detector identified this content as AI-generated with ${(textML.ai_probability * 100).toFixed(1)}% probability. The text shows patterns consistent with large language model output.`);
      } else {
        items.push(`The AI text detector identified this content as human-written with ${(textML.human_probability * 100).toFixed(1)}% probability.`);
      }
    }
    if (audioML && audioML.label && audioML.label !== "unknown") {
      if (audioML.label === "fake") {
        items.push(`The audio analysis detected synthetic voice patterns with ${(audioML.confidence * 100).toFixed(1)}% confidence.`);
      } else {
        items.push(`The audio analysis indicates the speech is likely authentic with ${(audioML.confidence * 100).toFixed(1)}% confidence.`);
      }
    }
    if (imageML && imageML.label && imageML.label !== "unknown") {
      if (imageML.label === "ai-generated") {
        items.push(`The image detector classified this image as AI-generated with ${(imageML.confidence * 100).toFixed(1)}% confidence.`);
      } else {
        items.push(`The image detector classified this image as authentic with ${(imageML.confidence * 100).toFixed(1)}% confidence.`);
      }
    }
    if (relatedArticles.length > 0) {
      const top = relatedArticles[0];
      items.push(`Found ${relatedArticles.length} related fact-check article(s). Top match: "${top.title || "Untitled"}" (similarity: ${((top.similarity_score || 0) * 100).toFixed(0)}%).`);
    }

    // ── NEW: Intelligence Report & Provenance ─────────────────────────────────
    if (apiResult?.explainability?.intelligence_report) {
      items.push(`Intelligence Report: ${apiResult.explainability.intelligence_report}`);
    }
    if (apiResult?.credibility?.provenance?.likely_origin && apiResult.credibility.provenance.likely_origin !== "Unknown / Natural") {
      const prov = apiResult.credibility.provenance;
      items.push(`Provenance Attribution: Likely generated by ${prov.likely_origin} using ${prov.manipulation_type} (${(prov.confidence * 100).toFixed(0)}% confidence).`);
    }
    if (apiResult?.news_verification?.evidence_summary) {
      items.push(`OSINT Verification: ${apiResult.news_verification.evidence_summary}`);
    }

    return items.length > 0 ? items : mock.insights;
  };

  // Merge real data over mock data
  const result = {
    ...mock,
    score: realScore ?? (hasRealData ? 0 : mock.score),
    risk: (realRiskLevel ?? (hasRealData ? "medium" : mock.risk)) as "low" | "medium" | "high",
    status: buildStatus(),
    confidence: realScore ?? realRisk.authenticity_score ?? (hasRealData ? 0 : mock.confidence),
    fingerprint: buildFingerprint(),
    anomalies: buildAnomalies(),
    insights: buildInsights(),
    // Use real drift data from API when available
    driftData: apiResult?.drift_data && apiResult.drift_data.length > 0
      ? apiResult.drift_data
      : hasRealData
        ? []
        : mock.driftData,
  };
  const Icon = tabIcons[tab];
  const color = tabColors[tab];
  const [expandedSection, setExpandedSection] = useState<string | null>("anomalies");

  const riskConfig = (() => {
    if (result.score <= 20) return { color: "#ff4444", bg: "rgba(255, 68, 68, 0.1)", border: "rgba(255, 68, 68, 0.2)", label: "HIGH RISK" };
    if (result.score <= 40) return { color: "#ff8c00", bg: "rgba(255, 140, 0, 0.1)", border: "rgba(255, 140, 0, 0.2)", label: "MODERATE RISK" };
    if (result.score <= 60) return { color: "#ffd700", bg: "rgba(255, 215, 0, 0.1)", border: "rgba(255, 215, 0, 0.2)", label: "UNCERTAIN" };
    if (result.score <= 80) return { color: "#98fb98", bg: "rgba(152, 251, 152, 0.1)", border: "rgba(152, 251, 152, 0.2)", label: "LOW RISK" };
    return { color: "#00ff9d", bg: "rgba(0, 255, 157, 0.1)", border: "rgba(0, 255, 157, 0.2)", label: "MINIMAL RISK" };
  })();

  const statusIcon =
    result.score >= 61 ? (
      <CheckCircle className="w-6 h-6" style={{ color: riskConfig.color }} />
    ) : result.score >= 21 ? (
      <AlertTriangle className="w-6 h-6" style={{ color: riskConfig.color }} />
    ) : (
      <XCircle className="w-6 h-6" style={{ color: riskConfig.color }} />
    );

  const scoreColor = riskConfig.color;

  const toggleSection = (s: string) => setExpandedSection(expandedSection === s ? null : s);

  // Animation variants
  const containerVars = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1
      }
    }
  };

  const itemVars = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0, transition: { type: "spring" as const, stiffness: 50 } }
  };

  return (
    <div className="min-h-screen pt-24 pb-16 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      {/* Background is handled globally */}

      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between mb-8"
      >
        <div className="flex items-center gap-4">
          <button
            onClick={onReset}
            className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors group"
          >
            <div className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center group-hover:bg-white/10 transition-colors">
              <ChevronLeft className="w-4 h-4" />
            </div>
            <span className="font-medium">New Analysis</span>
          </button>

          <div className="w-px h-8 bg-white/10" />

          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center glass-card" style={{ borderColor: `${color}30` }}>
              <Icon className="w-5 h-5" style={{ color }} />
            </div>
            <div>
              <h2 className="text-white font-bold text-lg leading-none capitalize">{tab} Report</h2>
              <div className="flex items-center gap-2 text-xs text-slate-400 mt-1">
                <span>{fileName || "Text Content"}</span>
                <span className="w-1 h-1 rounded-full bg-slate-600" />
                <span suppressHydrationWarning>{new Date().toLocaleString("en-IN", { timeZone: "Asia/Kolkata", dateStyle: "medium", timeStyle: "short" })}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="flex gap-3">

          <button
            onClick={async () => {
              const shareData = {
                title: `Truth X — ${tab} Report`,
                text: `Truth X Analysis: ${result.status} (Score: ${result.score}/100, Risk: ${result.risk}). File: ${fileName || "Text Content"}.`,
                url: window.location.href,
              };
              try {
                if (navigator.share) {
                  await navigator.share(shareData);
                } else {
                  await navigator.clipboard.writeText(
                    `${shareData.title}\n${shareData.text}\n${shareData.url}`
                  );
                  showToast("Report summary copied to clipboard!", "success");
                }
              } catch (err) {
                // user cancelled share dialog
              }
            }}
            className="glass-button px-4 py-2 rounded-xl text-slate-300 hover:text-white flex items-center gap-2 text-sm font-medium"
          >
            <Share2 className="w-4 h-4" /> Share
          </button>
          <button
            onClick={() => {
              // Add a temporary print stylesheet
              const style = document.createElement("style");
              style.id = "print-styles";
              style.textContent = `
                @media print {
                  body { background: #000000 !important; color: white !important; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
                  nav, .glass-button, button, canvas { display: none !important; }
                  .glass-card, .glass-panel { border: 1px solid #333333 !important; background: #0a0a0a !important; }
                  @page { size: A4; margin: 1cm; }
                }
              `;
              document.head.appendChild(style);
              window.print();
              setTimeout(() => document.getElementById("print-styles")?.remove(), 1000);
            }}
            className="bg-white text-black px-4 py-2 rounded-xl hover:bg-slate-200 flex items-center gap-2 text-sm font-bold shadow-lg shadow-white/10 transition-colors"
          >
            <Download className="w-4 h-4" /> Export PDF
          </button>
        </div>
      </motion.div>

      {/* View Tabs */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="glass-card rounded-2xl p-2 mb-8 flex flex-wrap gap-2"
      >
        {viewTabs.map((item) => {
          const IconEl = item.icon;
          const isActive = resolvedViewTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveViewTab(item.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all ${
                isActive
                  ? "bg-white/10 text-white shadow-lg"
                  : "text-slate-400 hover:text-white"
              }`}
              style={isActive ? { boxShadow: `0 0 20px ${item.color}30`, border: `1px solid ${item.color}30` } : { border: "1px solid transparent" }}
            >
              <IconEl className="w-4 h-4" style={{ color: item.color }} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </motion.div>

      {resolvedViewTab === "osint" ? (
        <motion.div
          variants={containerVars}
          initial="hidden"
          animate="show"
          className="space-y-6"
        >
          {/* Executive Intelligence Summary */}
          <motion.div variants={itemVars} className="glass-card rounded-3xl p-8 relative overflow-hidden">
            <div
              className="absolute inset-0 opacity-10 pointer-events-none blur-[120px]"
              style={{ background: "radial-gradient(circle at top, #00d4ff 0%, transparent 55%)" }}
            />
            <div className="relative z-10">
              <div className="flex items-center justify-between gap-6 flex-wrap">
                <div className="flex items-center gap-3">
                  <div className="p-3 rounded-xl bg-cyan-500/10 text-cyan-400">
                    <ShieldCheck className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="text-white font-bold text-2xl">Executive Source Summary</h3>
                    <p className="text-slate-400 text-sm">Source verification overview • forensic-grade verdict</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-[10px] px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-300 font-mono">
                    Credibility Score: {typeof apiResult?.credibility?.score === "number" ? `${apiResult.credibility.score}/100` : "N/A"}
                  </span>
                  <span className="text-[10px] px-3 py-1 rounded-full bg-cyan-500/10 text-cyan-300 font-mono">
                    Confidence: {toPercent(typeof apiResult?.combined_confidence === "number" ? apiResult.combined_confidence : typeof apiResult?.combined_fake_probability === "number" ? Math.abs(apiResult.combined_fake_probability - 0.5) * 2 : undefined)}
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-8">
                <div className="lg:col-span-2 space-y-4">
                  <div className="flex items-center gap-2 text-xs uppercase tracking-widest text-cyan-300/80">
                    Source Overview
                  </div>
                  <p className="text-slate-200 leading-relaxed text-base">
                    {apiResult?.explainability?.intelligence_report || "No source report available for this analysis."}
                  </p>
                </div>
                <div className="space-y-4">
                  <div className="bg-black/20 rounded-2xl border border-white/5 p-4">
                    <div className="text-xs text-slate-400">Source Credibility Status</div>
                    <div className="text-lg font-bold text-white mt-1">
                      {apiResult?.news_verification?.verdict || "Unverified"}
                    </div>
                    <div className="text-[11px] text-slate-500 mt-1 capitalize">
                      Evidence Strength: {apiResult?.news_verification?.confidence_level || "Medium"}
                    </div>
                  </div>
                  <div className="bg-black/20 rounded-2xl border border-white/5 p-4">
                    <div className="text-xs text-slate-400">Evidence Signals</div>
                    <div className="text-sm text-slate-200 mt-1">
                      {apiResult?.news_verification?.evidence_summary || "No external evidence summary reported."}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>

          {/* Key Findings */}
          <motion.div variants={itemVars} className="glass-card rounded-3xl p-6">
            <div className="flex items-center justify-between gap-4 mb-6">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
                  <Sparkles className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-bold text-white">Key Findings</h4>
                  <p className="text-xs text-slate-400">AI-generated investigative findings grounded in detector evidence</p>
                </div>
              </div>
              <span className="text-[10px] px-2 py-1 rounded bg-emerald-500/10 text-emerald-300 font-mono">
                {osintFindingsSource === "mistral" ? "MISTRAL VERIFIED" : "DETERMINISTIC"}
              </span>
            </div>

            <div className="space-y-3">
              {osintFindingsLoading && osintFindings.length === 0 && (
                <p className="text-xs text-slate-400">Generating intelligence findings...</p>
              )}
              {!osintFindingsLoading && osintFindings.length === 0 && (
                <p className="text-xs text-slate-400">No key findings reported for this analysis.</p>
              )}
              {osintFindings.map((finding, i) => (
                <div key={i} className="flex items-start gap-3 p-3 rounded-xl bg-white/5 border border-white/5 hover:border-emerald-500/30 transition-colors">
                  <div className="w-2 h-2 rounded-full bg-emerald-400 mt-2" />
                  <p className="text-slate-200 text-sm leading-relaxed">{finding}</p>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Sources & Evidence */}
          <motion.div variants={itemVars} className="glass-card rounded-3xl p-6">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400">
                  <Globe className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-bold text-white">Sources & Evidence</h4>
                  <p className="text-xs text-slate-400">Verification sources and evidence alignment</p>
                </div>
              </div>
              <span className="text-[10px] px-2 py-1 rounded bg-cyan-500/10 text-cyan-300 font-mono">
                {evidenceCards.length} sources
              </span>
            </div>

            {evidenceCards.length === 0 && (
              <p className="text-xs text-slate-400">No evidence sources reported yet.</p>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {evidenceCards.map((source, i) => {
                const stanceColor = source.stance === "supporting" ? "#00ff9d" : source.stance === "contradicting" ? "#ff6b6b" : "#38bdf8";
                return (
                  <div key={`${source.title}-${i}`} className="glass-card rounded-2xl p-4 border border-white/5 hover:border-white/20 transition-colors">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h5 className="text-white text-sm font-semibold leading-snug line-clamp-2">{source.title}</h5>
                        <p className="text-xs text-slate-400 mt-1">{source.domain}</p>
                      </div>
                      <div className="w-10 h-10 rounded-xl bg-white/5 border border-white/5 flex items-center justify-center">
                        <Globe className="w-5 h-5" style={{ color: stanceColor }} />
                      </div>
                    </div>

                    <div className="mt-4 space-y-2">
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="text-slate-400">Relevance</span>
                        <span className="font-mono" style={{ color: stanceColor }}>
                          {typeof source.score === "number" ? `${Math.round(source.score * 100)}%` : "N/A"}
                        </span>
                      </div>
                      <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{ width: `${Math.round((source.score ?? 0) * 100)}%`, background: stanceColor }}
                        />
                      </div>
                      {source.timestamp && (
                        <div className="text-[11px] text-slate-500">{formatTimestamp(source.timestamp)}</div>
                      )}
                    </div>

                    <div className="mt-4 flex items-center justify-between">
                      <span className="text-[10px] px-2 py-1 rounded-full" style={{ background: `${stanceColor}1A`, color: stanceColor }}>
                        {source.stance === "supporting" ? "SUPPORTING" : source.stance === "contradicting" ? "CONTRADICTS" : "INFORMATIONAL"}
                      </span>
                      {source.url ? (
                        <a
                          href={source.url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-[11px] text-cyan-300 hover:text-cyan-100 flex items-center gap-1"
                        >
                          View Source <ExternalLink className="w-3 h-3" />
                        </a>
                      ) : (
                        <span className="text-[11px] text-slate-500">No link</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </motion.div>

          {/* Claim Integrity */}
          <motion.div variants={itemVars} className="glass-card rounded-3xl p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
                <Scale className="w-5 h-5" />
              </div>
              <div>
                <h4 className="font-bold text-white">Claim Integrity</h4>
                <p className="text-xs text-slate-400">Claim vs evidence comparison</p>
              </div>
            </div>

            {contradictions.length === 0 && (
              <p className="text-xs text-slate-400">No claim integrity data reported.</p>
            )}

            <div className="space-y-4">
              {contradictions.map((item: any, i: number) => {
                const relation = String(item?.relation || "neutral").toLowerCase();
                const relationColor = relation === "entailment" ? "#00ff9d" : relation === "contradiction" ? "#ff6b6b" : "#38bdf8";
                return (
                  <div key={i} className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <div className="bg-black/20 rounded-2xl border border-white/5 p-4">
                      <div className="text-[11px] uppercase tracking-widest text-slate-500">Claim</div>
                      <p className="text-sm text-white mt-2 leading-relaxed">{item.claim}</p>
                    </div>
                    <div className="bg-black/20 rounded-2xl border border-white/5 p-4">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] uppercase tracking-widest text-slate-500">Counter-Evidence</span>
                        <span className="text-[10px] px-2 py-1 rounded-full" style={{ background: `${relationColor}1A`, color: relationColor }}>
                          {relation === "entailment" ? "SUPPORTED" : relation === "contradiction" ? "CONTRADICTED" : "INCONCLUSIVE"}
                        </span>
                      </div>
                      <p className="text-sm text-slate-200 mt-2 leading-relaxed">{item.evidence}</p>
                      <div className="mt-3 flex items-center justify-between text-[11px] text-slate-500">
                        <span>{item.source || "Unknown"}</span>
                        <span className="font-mono" style={{ color: relationColor }}>
                          {typeof item.confidence === "number" ? `${Math.round(item.confidence * 100)}%` : "N/A"}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </motion.div>

          {/* Provenance & Spread */}
          <motion.div variants={itemVars} className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 glass-card rounded-3xl p-6 relative overflow-hidden">
              <div
                className="absolute inset-0 opacity-10 pointer-events-none"
                style={{ background: "radial-gradient(circle at right, #38bdf8 0%, transparent 60%)" }}
              />
              <div className="relative z-10">
                <div className="flex items-center gap-3 mb-6">
                  <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400">
                    <Fingerprint className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="font-bold text-white">Digital Passport</h4>
                    <p className="text-xs text-slate-400">Provenance attribution & manipulation fingerprint</p>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="bg-black/20 rounded-2xl border border-white/5 p-4">
                    <div className="text-xs text-slate-400">Likely Origin</div>
                    <div className="text-sm text-white font-semibold mt-2">{provenance?.likely_origin || "Unknown"}</div>
                  </div>
                  <div className="bg-black/20 rounded-2xl border border-white/5 p-4">
                    <div className="text-xs text-slate-400">Manipulation Category</div>
                    <div className="text-sm text-white font-semibold mt-2">{provenance?.manipulation_type || "None detected"}</div>
                  </div>
                  <div className="bg-black/20 rounded-2xl border border-white/5 p-4">
                    <div className="text-xs text-slate-400">Confidence Level</div>
                    <div className="text-sm text-emerald-300 font-semibold mt-2">
                      {typeof provenance?.confidence === "number" ? `${Math.round(provenance.confidence * 100)}%` : "N/A"}
                    </div>
                  </div>
                  <div className="bg-black/20 rounded-2xl border border-white/5 p-4">
                    <div className="text-xs text-slate-400">Artifact Signatures</div>
                    <div className="text-sm text-slate-200 mt-2">
                      {Array.isArray(provenance?.signals) && provenance.signals.length > 0
                        ? provenance.signals.slice(0, 3).join(" • ")
                        : "No signature indicators detected"}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="glass-card rounded-3xl p-6">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-2 rounded-lg bg-rose-500/10 text-rose-400">
                  <Network className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-bold text-white">Propagation Graph</h4>
                  <p className="text-xs text-slate-400">Spread intelligence snapshot</p>
                </div>
              </div>

              {!socialGraph && (
                <div className="text-xs text-slate-400">No social propagation data available.</div>
              )}

              {socialGraph && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-400">Nodes</span>
                    <span className="text-white font-semibold">{socialGraph?.nodes?.length ?? socialGraph?.node_count ?? "N/A"}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-400">Connections</span>
                    <span className="text-white font-semibold">{socialGraph?.edges?.length ?? socialGraph?.edge_count ?? "N/A"}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-400">Virality</span>
                    <span className="text-rose-300 font-semibold">{socialGraph?.virality_score ?? "N/A"}</span>
                  </div>
                  <div className="h-24 rounded-2xl bg-gradient-to-br from-white/5 to-white/0 border border-white/5 flex items-center justify-center text-[11px] text-slate-500">
                    Network visualization placeholder
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        </motion.div>
      ) : (
        <motion.div
          variants={containerVars}
          initial="hidden"
          animate="show"
          className="grid grid-cols-1 lg:grid-cols-3 gap-6"
        >

        {/* Main Score Card - Full Width on Mobile, 2 Cols on Desktop */}
        <motion.div variants={itemVars} className="lg:col-span-2 glass-card rounded-3xl p-8 relative overflow-hidden">
          {/* Background Gradient */}
          <div
            className="absolute top-0 right-0 w-[50%] h-full opacity-10 pointer-events-none blur-[100px]"
            style={{ background: riskConfig.color }}
          />

          <div className="flex flex-col md:flex-row gap-8 items-center relative z-10">
            {/* Radial Progress */}
            <div className="relative w-48 h-48 flex-shrink-0">
              <svg className="w-full h-full -rotate-90" viewBox="0 0 128 128">
                {/* Track */}
                <circle cx="64" cy="64" r="56" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="8" />
                {/* Indicator */}
                <motion.circle
                  cx="64" cy="64" r="56"
                  fill="none"
                  stroke={scoreColor}
                  strokeWidth="8"
                  strokeDasharray="351"
                  strokeDashoffset={351 - (351 * result.score) / 100}
                  strokeLinecap="round"
                  initial={{ strokeDashoffset: 351 }}
                  animate={{ strokeDashoffset: 351 - (351 * result.score) / 100 }}
                  transition={{ duration: 1.5, ease: "easeOut" }}
                  style={{ filter: `drop-shadow(0 0 10px ${scoreColor}80)` }}
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <motion.span
                  initial={{ opacity: 0, scale: 0.5 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.5 }}
                  className="text-5xl font-black tracking-tighter"
                  style={{ color: scoreColor }}
                >
                  {result.score}%
                </motion.span>
                <span className="text-slate-400 text-xs uppercase tracking-widest font-semibold mt-1">Authenticity</span>
              </div>
            </div>

            {/* Status Text */}
            <div className="flex-1 text-center md:text-left">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border mb-4" style={{ borderColor: riskConfig.border, background: riskConfig.bg }}>
                {statusIcon}
                <span className="text-xs font-bold tracking-wide" style={{ color: riskConfig.color }}>{riskConfig.label}</span>
              </div>

              <h3 className="text-4xl font-bold text-white mb-2">{result.status}</h3>
              <p className="text-slate-400 leading-relaxed max-w-lg">
                {result.risk === 'high'
                  ? "Our deep forensic analysis has detected significant anomalies indicating this content is likely artificially generated or manipulated."
                  : "This content appears to be authentic, but we recommend reviewing the detailed insights below."}
              </p>

              {/* Mini Stats */}
              <div className="grid grid-cols-3 gap-4 mt-8">
                <div className="bg-black/20 rounded-xl p-3 border border-white/5">
                  <div className="text-slate-400 text-xs mb-1">Confidence</div>
                  <div className="text-xl font-bold text-white">{result.confidence}%</div>
                </div>
                <div className="bg-black/20 rounded-xl p-3 border border-white/5">
                  <div className="text-slate-400 text-xs mb-1">Anomalies</div>
                  <div className="text-xl font-bold text-white">{result.anomalies.length}</div>
                </div>
                <div className="bg-black/20 rounded-xl p-3 border border-white/5">
                  <div className="text-slate-400 text-xs mb-1">Process Time</div>
                  <div className="text-xl font-bold text-white">
                    {typeof processTime === "number" ? `${processTime}s` : "N/A"}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Right Sidebar - Detection Models & Fingerprint */}
        <motion.div variants={itemVars} className="space-y-6">
          {/* Intelligence Report / Insights */}
          <div className="glass-card rounded-3xl p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400">
                <Shield className="w-5 h-5" />
              </div>
              <h4 className="font-bold text-white">Intelligence Report</h4>
            </div>

            <div className="space-y-4">
              {result.insights.map((insight: string, i: number) => (
                <div key={i} className="flex gap-3 text-sm">
                  <div className="w-1.5 h-1.5 rounded-full bg-blue-400 shrink-0 mt-1.5" />
                  <p className="text-slate-300 leading-relaxed">{insight}</p>
                </div>
              ))}
              {result.insights.length === 0 && (
                <p className="text-xs text-slate-400">No insights available for this input.</p>
              )}
            </div>
          </div>

          {/* Models Card */}
          <div className="glass-card rounded-3xl p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400">
                <Cpu className="w-5 h-5" />
              </div>
              <h4 className="font-bold text-white">AI Models</h4>
            </div>

            <div className="space-y-4">
              {(hasRealData ? realModels : [
                { name: "FaceForensics++", score: 94 },
                { name: "DeepFakeDetector", score: 91 },
                { name: "AudioDeepDetect", score: 88 }
              ]).map((model: any, i: number) => (
                <div key={i} className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-300">{model.name}</span>
                    <span className="font-mono text-cyan-400">{model.score}%</span>
                  </div>
                  <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${model.score}%` }}
                      transition={{ duration: 1, delay: 0.5 + (i * 0.1) }}
                      className="h-full bg-cyan-500 rounded-full"
                    />
                  </div>
                </div>
              ))}
              {hasRealData && realModels.length === 0 && (
                <p className="text-xs text-slate-400">No model metadata reported.</p>
              )}
            </div>
          </div>

          {/* Fingerprint / Metadata Card */}
          <div className="glass-card rounded-3xl p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-violet-500/10 text-violet-400">
                  <Hash className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-bold text-white">{hasRealData ? "Media Metadata" : "Digital Fingerprint"}</h4>
                  {hasRealData && <p className="text-[10px] text-emerald-400 font-mono mt-0.5">● LIVE — extracted from the file</p>}
                </div>
              </div>
              {hasRealData && (
                <span className="text-[10px] px-2 py-1 rounded bg-violet-500/10 text-violet-300 font-mono">
                  {result.fingerprint.length} fields
                </span>
              )}
            </div>
            <div className="space-y-1 max-h-[400px] overflow-y-auto pr-1" style={{ scrollbarWidth: "thin", scrollbarColor: "rgba(255,255,255,0.1) transparent" }}>
              {(() => {
                let lastSection = "";
                return result.fingerprint.map((item: any, i: number) => {
                  const showHeader = item.section && item.section !== lastSection;
                  if (item.section) lastSection = item.section;
                  return (
                    <div key={i}>
                      {showHeader && (
                        <div className="flex items-center gap-2 mt-3 mb-2 first:mt-0">
                          <span className="text-[10px] uppercase font-bold tracking-wider text-violet-400/70">{item.section}</span>
                          <div className="flex-1 h-px bg-violet-500/10" />
                        </div>
                      )}
                      <div className="flex justify-between items-start text-sm py-1.5 border-b border-white/5 last:border-0">
                        <span className="text-slate-400 text-xs shrink-0">{item.label}</span>
                        <span suppressHydrationWarning className={`font-mono text-right text-xs max-w-[55%] break-all ${item.suspicious ? "text-amber-400" : "text-slate-200"}`}>
                          {item.value}
                        </span>
                      </div>
                    </div>
                  );
                });
              })()}
            </div>
          </div>
        </motion.div>

        {/* Detailed Analysis Section */}
        <div className="lg:col-span-3 grid grid-cols-1 md:grid-cols-2 gap-6">

          {/* Anomalies List */}
          <motion.div variants={itemVars} className="glass-card rounded-3xl p-6">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <Flag className="w-5 h-5 text-red-400" />
                <h4 className="font-bold text-white">Detected Anomalies</h4>
              </div>
              <span className="px-2 py-1 rounded bg-red-500/10 text-red-400 text-xs font-bold border border-red-500/20">
                {result.anomalies.length} Issues
              </span>
            </div>

            <div className="space-y-3">
              {result.anomalies.map((anomaly: string, i: number) => (
                <div key={i} className="flex gap-3 p-3 rounded-xl bg-white/5 border border-white/5 hover:border-red-500/30 transition-colors group">
                  <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
                  <p className="text-slate-300 text-sm group-hover:text-white transition-colors">{anomaly}</p>
                </div>
              ))}
              {result.anomalies.length === 0 && (
                <p className="text-xs text-slate-400">No anomalies detected for this input.</p>
              )}
            </div>
          </motion.div>

          {/* Timeline & Explanations */}
          <motion.div variants={itemVars} className="glass-card rounded-3xl p-6">
            <div className="flex items-center gap-3 mb-6">
              <Clock className="w-5 h-5 text-cyan-400" />
              <h4 className="font-bold text-white">Timeline Analysis</h4>
            </div>

            <div className="relative pl-4 space-y-6 before:absolute before:left-0 before:top-2 before:bottom-2 before:w-px before:bg-gradient-to-b before:from-cyan-500 before:to-transparent">
              {timeline.slice(0, 4).map((item: any, i: number) => (
                <div key={i} className="relative">
                  <div className={`absolute -left-[21px] top-1 w-3 h-3 rounded-full border-2 border-[#000000] ${item.suspicious ? "bg-red-500" : "bg-cyan-500"}`} />
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-white text-sm font-medium">{item.label}</p>
                      <p className="text-slate-500 text-xs mt-0.5">Step {i + 1}</p>
                    </div>
                    <span className={`text-[10px] uppercase font-bold px-2 py-1 rounded ${item.suspicious ? "bg-red-500/10 text-red-400" : "bg-cyan-500/10 text-cyan-400"
                      }`}>
                      {item.tag}
                    </span>
                  </div>
                </div>
              ))}
              {timeline.length === 0 && (
                <p className="text-xs text-slate-400">Timeline analysis is not available for this input.</p>
              )}
            </div>
          </motion.div>

        </div>

        {/* Chart Section */}
        <motion.div variants={itemVars} className="lg:col-span-3 glass-card rounded-3xl p-6">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <TrendingDown className="w-5 h-5 text-purple-400" />
              <div>
                <h4 className="font-bold text-white">Authenticity Drift</h4>
                {hasRealData && apiResult?.drift_data?.length > 0 && (
                  <p className="text-[10px] text-emerald-400 font-mono mt-0.5">
                    ● {apiResult.drift_data.length} segments • {realMeta.file_info?.duration_human || `${realMeta.file_info?.duration_seconds || 0}s`}
                  </p>
                )}
              </div>
            </div>
            {hasRealData && apiResult?.drift_data?.length > 0 && (
              <span className="text-[10px] px-2 py-1 rounded bg-purple-500/10 text-purple-300 font-mono">
                Frame-level analysis
              </span>
            )}
          </div>

          <div className="h-[200px] w-full">
            {result.driftData.length === 0 && (
              <div className="h-full flex items-center justify-center text-xs text-slate-400">
                No drift data available for this input.
              </div>
            )}
            {result.driftData.length > 0 && (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={result.driftData}>
                <defs>
                  <linearGradient id="colorAuth" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={scoreColor} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={scoreColor} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="t" stroke="#475569" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#475569" fontSize={12} tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#111111', borderColor: 'rgba(255,255,255,0.1)', borderRadius: '12px' }}
                  itemStyle={{ color: '#fff' }}
                />
                <Area type="monotone" dataKey="v" stroke={scoreColor} strokeWidth={3} fillOpacity={1} fill="url(#colorAuth)" />
              </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </motion.div>

        </motion.div>
      )}
    </div>
  );
}
