const API_URL = "/py-api";

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
    onStatus?: (msg: string) => void
): Promise<any> {
    const formData = new FormData();

    if (file) {
        formData.append("video", file);
    }

    if (text) {
        formData.append("query", text);
    }

    console.log("Submitting analysis job:", { file: file?.name, text });

    // Step 1: Submit analysis job — returns immediately with job_id
    const submitRes = await fetch(`${API_URL}/analyze`, {
        method: "POST",
        body: formData,
    });

    if (!submitRes.ok) {
        const errorText = await submitRes.text();
        throw new Error(`Submit failed: ${submitRes.status} ${submitRes.statusText} - ${errorText}`);
    }

    const { job_id } = await submitRes.json();
    console.log("Job submitted:", job_id);

    if (!job_id) {
        throw new Error("No job_id returned from server.");
    }

    // Step 2: Poll for results until done
    const POLL_INTERVAL_MS = 2000; // poll every 2 seconds
    const MAX_WAIT_MS = 5 * 60 * 1000; // 5 minute max wait
    const startTime = Date.now();

    while (true) {
        if (Date.now() - startTime > MAX_WAIT_MS) {
            throw new Error("Analysis timed out after 5 minutes. Please try a shorter video.");
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
        console.log("Poll response:", pollData.status, pollData.status_message || "");

        if (onStatus && pollData.status_message) {
            onStatus(pollData.status_message);
        }

        if (pollData.status === "done") {
            return pollData.result;
        }

        if (pollData.status === "error") {
            throw new Error(pollData.error || "Server analysis error.");
        }

        // status is "pending" or "running" — keep polling
    }
}
