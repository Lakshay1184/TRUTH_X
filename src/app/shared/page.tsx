"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState, Suspense } from "react";
import ResultsDashboard from "@/components/ResultsDashboard";

const BACKEND_URL = "/py-api";

function SharedResultsContent() {
    const searchParams = useSearchParams();
    const id = searchParams.get("id");
    const score = searchParams.get("score");
    const risk = searchParams.get("risk");
    const summary = searchParams.get("summary");

    const [result, setResult] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        async function fetchResult() {
            if (id) {
                try {
                    const res = await fetch(`${BACKEND_URL}/result/${id}`);
                    if (res.ok) {
                        const data = await res.json();
                        setResult(data);
                    } else {
                        setError("Result not found or expired.");
                    }
                } catch (e) {
                    setError("Could not connect to analysis server.");
                }
            } else if (score !== null) {
                const parsed = {
                    score: parseInt(score),
                    risk_level: risk || "unknown",
                    summary: summary || "Analysis complete",
                };
                setResult(parsed);
            } else {
                setError("No analysis data provided.");
            }
            setLoading(false);
        }

        fetchResult();
    }, [id, score, risk, summary]);

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-black">
                <div className="text-center">
                    <div className="relative w-20 h-20 mx-auto mb-6">
                        <div className="absolute inset-0 rounded-full border-2 border-cyan-500/30 animate-ping" />
                        <div className="absolute inset-2 rounded-full border-2 border-cyan-400/60 animate-spin" />
                        <div className="absolute inset-4 rounded-full bg-cyan-500/20 animate-pulse" />
                    </div>
                    <h2 className="text-xl font-semibold text-white mb-2">
                        Loading Analysis Results
                    </h2>
                    <p className="text-gray-400 text-sm">
                        Retrieving your shared content analysis...
                    </p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-black px-4">
                <div className="bg-red-500/10 border border-red-500/30 rounded-2xl p-8 max-w-md text-center">
                    <div className="text-4xl mb-4">⚠️</div>
                    <h2 className="text-xl font-semibold text-white mb-2">
                        Analysis Not Found
                    </h2>
                    <p className="text-gray-400 text-sm mb-6">{error}</p>
                    <a
                        href="/analyze"
                        className="inline-flex items-center gap-2 px-6 py-3 bg-cyan-500 hover:bg-cyan-400 text-black font-semibold rounded-xl transition-colors"
                    >
                        Analyze New Content →
                    </a>
                </div>
            </div>
        );
    }

    if (!result) return null;

    // Determine tab type from result
    const hasVideo = !!result.video_analysis;
    const hasText = !!result.text_analysis;
    const tab = hasVideo ? "video" : hasText ? "text" : "video";

    return (
        <div className="min-h-screen bg-black pt-20 pb-12 px-4">
            {/* Shared Content Banner */}
            <div className="max-w-4xl mx-auto mb-6">
                <div className="bg-gradient-to-r from-cyan-500/10 to-purple-500/10 border border-cyan-500/20 rounded-2xl p-4 flex items-center gap-3">
                    <span className="text-2xl">📤</span>
                    <div>
                        <p className="text-white font-medium text-sm">
                            Shared Content Analysis
                        </p>
                        <p className="text-gray-400 text-xs">
                            This content was shared from another app and analyzed
                            automatically.
                        </p>
                    </div>
                    <div className="ml-auto">
                        <span
                            className={`px-3 py-1 rounded-full text-xs font-bold ${(result.score ?? 0) >= 70
                                ? "bg-green-500/20 text-green-400 border border-green-500/30"
                                : (result.score ?? 0) >= 40
                                    ? "bg-yellow-500/20 text-yellow-400 border border-yellow-500/30"
                                    : "bg-red-500/20 text-red-400 border border-red-500/30"
                                }`}
                        >
                            {result.score ?? 0}% Authentic
                        </span>
                    </div>
                </div>
            </div>

            {/* Results Dashboard */}
            <ResultsDashboard
                tab={tab}
                onReset={() => (window.location.href = "/analyze")}
                fileName={result.metadata?.original_filename}
                apiResult={result}
            />
        </div>
    );
}

export default function SharedPage() {
    return (
        <Suspense
            fallback={
                <div className="min-h-screen flex items-center justify-center bg-black">
                    <div className="animate-pulse text-cyan-400">Loading...</div>
                </div>
            }
        >
            <SharedResultsContent />
        </Suspense>
    );
}
