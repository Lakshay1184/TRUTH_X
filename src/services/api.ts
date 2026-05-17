import { supabase } from "@/lib/supabase";

const API_URL = "/py-api";

async function getAuthHeaders() {
    try {
        const { data: { session } } = await supabase.auth.getSession();
        if (session?.access_token) {
            return {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${session.access_token}`,
            };
        }
    } catch (e) {
        console.error("Error getting auth session:", e);
    }
    return {
        "Content-Type": "application/json",
    };
}

export async function getBackendStatus(): Promise<string> {
    try {
        const res = await fetch(`${API_URL}/analyze/status`);
        if (res.ok) {
            const data = await res.json();
            return data.status;
        }
        return "Processing...";
    } catch (e) {
        return "Unknown state";
    }
}

export async function checkBackendHealth(): Promise<boolean> {
    try {
        const res = await fetch(`${API_URL}/health`);
        return res.ok;
    } catch (e) {
        return false;
    }
}

export async function analyzeContent(
    file: File | null,
    text: string | null,
    options?: {
        fileField?: "video" | "audio" | "image" | "text_file";
        onStatus?: (msg: string) => void;
        onProgress?: (progress: number) => void;
        maxWaitMs?: number;
        verifyNews?: boolean;
    }
): Promise<any> {
    const formData = new FormData();

    const fileField = options?.fileField ?? "video";
    if (file) {
        formData.append(fileField, file);
    }

    if (text) {
        formData.append("query", text);
    }
    if (options?.verifyNews) {
        formData.append("verify_news", "true");
    }

    console.info("Submitting analysis job:", { file: file?.name, fileField, hasText: Boolean(text), verifyNews: Boolean(options?.verifyNews) });

    const authHeaders = await getAuthHeaders();
    // Remove Content-Type from authHeaders for FormData, fetch will set it correctly with boundary
    const headers: Record<string, string> = { ...authHeaders };
    delete headers["Content-Type"];

    // Step 1: Submit analysis job — returns immediately with job_id
    const submitRes = await fetch(`${API_URL}/analyze`, {
        method: "POST",
        headers,
        body: formData,
    });

    if (!submitRes.ok) {
        const errorText = await submitRes.text();
        throw new Error(`Submit failed: ${submitRes.status} ${submitRes.statusText} - ${errorText}`);
    }

    const { job_id } = await submitRes.json();
    console.info("Job submitted:", job_id);

    if (!job_id) {
        throw new Error("No job_id returned from server.");
    }

    // Step 2: Poll for results until done
    const POLL_INTERVAL_MS = 2000; // poll every 2 seconds
    const fileMb = file ? file.size / (1024 * 1024) : 0;
    const defaultMaxWait = fileField === "text_file" || (!file && text)
        ? 90 * 1000
        : fileMb > 100 ? 20 * 60 * 1000 : 5 * 60 * 1000;
    const MAX_WAIT_MS = options?.maxWaitMs ?? defaultMaxWait;
    const startTime = Date.now();

    while (true) {
        if (Date.now() - startTime > MAX_WAIT_MS) {
            throw new Error(`Analysis timed out after ${Math.round(MAX_WAIT_MS / 1000)} seconds.`);
        }

        await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));

        const pollRes = await fetch(`${API_URL}/analyze/result/${job_id}`);

        if (!pollRes.ok) {
            if (pollRes.status === 404) {
                throw new Error("Analysis job not found (server may have restarted).");
            }
            const errorText = await pollRes.text();
            throw new Error(`Analysis failed: ${pollRes.status} - ${errorText}`);
        }

        const pollData = await pollRes.json();
        console.debug("Poll response:", pollData.status, pollData.status_message || "");

        if (options?.onStatus && pollData.status_message) {
            options.onStatus(pollData.status_message);
        }
        if (options?.onProgress && typeof pollData.progress === "number") {
            options.onProgress(pollData.progress);
        }

        if (pollData.status === "done") {
            return pollData.result;
        }

        if (pollData.status === "error" || pollData.status === "failed") {
            throw new Error(pollData.error || "Server analysis error.");
        }

        // status is "pending" or "running" — keep polling
    }
}

export async function getVerificationKeyFindings(analysis: any): Promise<{ findings: string[]; source?: string }> {
    try {
        const res = await fetch(`${API_URL}/explainability/key-findings`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ analysis }),
        });

        if (!res.ok) {
            return { findings: [], source: "fallback" };
        }

        const data = await res.json();
        return {
            findings: Array.isArray(data.findings) ? data.findings : [],
            source: data.source,
        };
    } catch (e) {
        return { findings: [], source: "fallback" };
    }
}

export async function verifyNews(options: {
    type: "headline" | "url" | "social" | "screenshot";
    content: string;
    file?: File;
    onProgress?: (progress: number) => void;
}): Promise<any> {
    const formData = new FormData();

    // Route as text query for verification
    formData.append("query", options.content);
    formData.append("verify_news", "true");

    // If screenshot, add as image
    if (options.type === "screenshot" && options.file) {
        formData.append("image", options.file);
    }

    console.info("Submitting verification job:", { type: options.type, content: options.content.substring(0, 50) });

    const authHeaders = await getAuthHeaders();
    const headers: Record<string, string> = { ...authHeaders };
    delete headers["Content-Type"];

    // Step 1: Submit verification job
    const submitRes = await fetch(`${API_URL}/analyze`, {
        method: "POST",
        headers,
        body: formData,
    });

    if (!submitRes.ok) {
        const errorText = await submitRes.text();
        throw new Error(`Verification submission failed: ${submitRes.status} - ${errorText}`);
    }

    const { job_id } = await submitRes.json();
    if (!job_id) {
        throw new Error("No job_id returned from server.");
    }

    console.info("Verification job submitted:", job_id);

    // Step 2: Poll for results
    const POLL_INTERVAL_MS = 3000;
    const MAX_WAIT_MS = 5 * 60 * 1000; // 5 minutes for deep analysis
    const startTime = Date.now();

    while (true) {
        if (Date.now() - startTime > MAX_WAIT_MS) {
            throw new Error("Verification analysis timed out.");
        }

        await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));

        const pollRes = await fetch(`${API_URL}/analyze/result/${job_id}`);

        if (!pollRes.ok) {
            if (pollRes.status === 404) {
                throw new Error("Verification job not found.");
            }
            const errorText = await pollRes.text();
            throw new Error(`Verification failed: ${pollRes.status} - ${errorText}`);
        }

        const pollData = await pollRes.json();

        if (options.onProgress && typeof pollData.progress === "number") {
            options.onProgress(pollData.progress);
        }

        if (pollData.status === "done") {
            // Transform analysis result to verification dashboard format
            const result = pollData.result;
            return transformAnalysisToVerification(result, options.content);
        }

        if (pollData.status === "error" || pollData.status === "failed") {
            throw new Error(pollData.error || "Verification analysis failed.");
        }
    }
}

function transformAnalysisToVerification(analysis: any, query: string): any {
    // Transform backend analysis result to VerificationDashboard format
    return {
        query,
        verified: analysis.overall_label === "Real" || analysis.overall_label === "Authentic",
        credibilityScore: Math.round((1 - (analysis.combined_fake_probability || 0)) * 100),
        riskLevel: (analysis.combined_fake_probability || 0) > 0.7 ? "HIGH" : (analysis.combined_fake_probability || 0) > 0.4 ? "MEDIUM" : "LOW",
        findings: analysis.explainability?.key_findings || generateFindings(analysis),
        contradictions: analysis.rag?.contradictions || [],
        evidence: analysis.rag?.evidence_sources || [],
        sources: analysis.rag?.source_reliability || [],
        provenanceData: analysis.provenance || {},
        propagationMetrics: analysis.social_propagation || {},
        timestamp: new Date().toISOString(),
    };
}

function generateFindings(analysis: any): string[] {
    const findings: string[] = [];

    if (analysis.combined_fake_probability > 0.7) {
        findings.push("High probability of manipulated or AI-generated content detected");
    } else if (analysis.combined_fake_probability > 0.4) {
        findings.push("Moderate indicators of potential fabrication identified");
    } else {
        findings.push("Content appears consistent with authentic material");
    }

    if (analysis.video_label === "Fake") {
        findings.push("Video analysis detected deepfake artifacts and temporal inconsistencies");
    }

    if (analysis.audio_label === "Fake") {
        findings.push("Audio processing identified synthetic voice characteristics");
    }

    return findings;
}

// ============================================================================
// NEW INTEL-SPECIFIC ENDPOINTS (Real OSINT Verification)
// ============================================================================

export async function classifyContent(content: string): Promise<{
    type: string;
    confidence: number;
    reasoning: string;
    sub_types: string[];
    suggested_sources: string[];
}> {
    try {
        const res = await fetch(`${API_URL}/intel/classify`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ content }),
        });

        if (!res.ok) {
            throw new Error(`Classification failed: ${res.status}`);
        }

        const data = await res.json();
        return data.classification;
    } catch (e) {
        console.error("Content classification error:", e);
        // Fallback classification
        return {
            type: "factual_explanation",
            confidence: 0.5,
            reasoning: "Unable to classify - treating as factual content",
            sub_types: [],
            suggested_sources: ["general"],
        };
    }
}

export async function analyzeIntel(options: {
    content: string;
    content_type?: string;
    file?: File;
    onProgress?: (progress: number) => void;
    onStatus?: (status: string) => void;
}): Promise<any> {
    try {
        const authHeaders = await getAuthHeaders();
        let startRes;

        if (options.file) {
            const formData = new FormData();
            formData.append("file", options.file);
            if (options.content_type) formData.append("content_type", options.content_type);
            
            startRes = await fetch(`${API_URL}/intel/analyze/start`, {
                method: "POST",
                headers: { "Authorization": authHeaders.Authorization || "" },
                body: formData,
            });
        } else {
            if (!options.content.trim()) throw new Error("Content cannot be empty");
            startRes = await fetch(`${API_URL}/intel/analyze/start`, {
                method: "POST",
                headers: { ...authHeaders, "Content-Type": "application/json" },
                body: JSON.stringify({ content: options.content, content_type: options.content_type }),
            });
        }

        if (!startRes.ok) {
            const errorText = await startRes.text();
            throw new Error(`Analysis start failed: ${startRes.status} - ${errorText}`);
        }

        const startData = await startRes.json();
        const jobId = startData.job_id;
        if (!jobId) {
            throw new Error("No job_id returned from Intel analysis start.");
        }

        if (options.onProgress && typeof startData.progress === "number") {
            options.onProgress(startData.progress);
        }
        if (options.onStatus && typeof startData.status_message === "string") {
            options.onStatus(startData.status_message);
        }

        const pollIntervalMs = 1200;
        const timeoutMs = 10 * 60 * 1000;
        const startedAt = Date.now();

        while (true) {
            if (Date.now() - startedAt > timeoutMs) {
                throw new Error("Intel analysis timed out.");
            }

            await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));

            const pollRes = await fetch(`${API_URL}/intel/analyze/result/${jobId}`);
            if (!pollRes.ok) {
                const errorText = await pollRes.text();
                throw new Error(`Intel polling failed: ${pollRes.status} - ${errorText}`);
            }

            const pollData = await pollRes.json();
            if (options.onProgress && typeof pollData.progress === "number") {
                options.onProgress(pollData.progress);
            }
            if (options.onStatus && typeof pollData.status_message === "string") {
                options.onStatus(pollData.status_message);
            }

            if (pollData.status === "complete") {
                return pollData.result;
            }

            if (pollData.status === "failed" || pollData.status === "error") {
                throw new Error(pollData.error || pollData.status_message || "Intel analysis failed.");
            }
        }
    } catch (e) {
        console.error("Intel analysis error:", e);
        throw e;
    }
}

export async function askIntelQuestion(options: {
    question: string;
    context: string;
    evidence: any[];
    verification_result?: any;
}): Promise<any> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 45000); // 45s timeout

    try {
        const authHeaders = await getAuthHeaders();
        const res = await fetch(`${API_URL}/intel/qa`, {
            method: "POST",
            headers: authHeaders,
            body: JSON.stringify({
                question: options.question,
                context: options.context,
                evidence: options.evidence,
                verification_result: options.verification_result,
            }),
            signal: controller.signal,
        });

        clearTimeout(timeoutId);

        if (!res.ok) {
            throw new Error(`Q&A failed: ${res.status}`);
        }

        return await res.json();
    } catch (e: any) {
        clearTimeout(timeoutId);
        if (e.name === "AbortError") {
            console.error("Intel Q&A request timed out");
            return { answer: "🔍 Answer\nThe analysis terminal timed out while generating a response. This usually happens when the investigation context is extremely dense. Please try a more specific question.", status: "timeout" };
        }
        console.error("Intel Q&A error:", e);
        throw e;
    }
}
