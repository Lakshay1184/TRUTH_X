const API_URL = "http://localhost:8000";

export async function checkBackendHealth(): Promise<boolean> {
    try {
        const res = await fetch(`${API_URL}/health`);
        return res.ok;
    } catch (e) {
        return false;
    }
}

export async function analyzeContent(file: File | null, text: string | null) {
    const formData = new FormData();

    if (file) {
        formData.append("video", file);
    }

    if (text) {
        formData.append("query", text);
    }

    // Debug log
    console.log("Analyzing content:", { file: file?.name, text });

    try {
        const response = await fetch(`${API_URL}/analyze`, {
            method: "POST",
            body: formData,
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`API Error: ${response.status} ${response.statusText} - ${errorText}`);
        }

        return await response.json();
    } catch (error) {
        console.error("Analysis failed:", error);
        throw error;
    }
}
