import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

/**
 * PWA Share Target Handler
 *
 * When a user shares a file/text from WhatsApp, Facebook, etc.
 * into the installed Truth X PWA, the browser sends a POST here.
 * We forward the file to our Python backend for analysis,
 * cache the result, and redirect to the results page.
 */
export async function POST(request: NextRequest) {
    try {
        const formData = await request.formData();

        // Extract shared data
        const title = formData.get("title") as string | null;
        const text = formData.get("text") as string | null;
        const url = formData.get("url") as string | null;
        const mediaFile = formData.get("media") as File | null;

        // Build FormData for Python backend
        const backendForm = new FormData();

        if (mediaFile && mediaFile.size > 0) {
            // Forward the shared file as "video" (backend accepts video field)
            backendForm.append("video", mediaFile, mediaFile.name);
        }

        // Combine text fields for query
        const queryParts = [title, text, url].filter(Boolean);
        if (queryParts.length > 0) {
            backendForm.append("query", queryParts.join(" — "));
        }

        // Helper to resolve the correct base URL (handles Cloudflare Tunnel / Proxies)
        const getBaseUrl = (req: NextRequest) => {
            const host = req.headers.get("x-forwarded-host") || req.headers.get("host");
            const proto = req.headers.get("x-forwarded-proto") || "http";
            return `${proto}://${host}`;
        };
        const baseUrl = getBaseUrl(request);

        // If nothing was shared, redirect to home
        if (!mediaFile && queryParts.length === 0) {
            return NextResponse.redirect(new URL("/", baseUrl), 303);
        }

        // Forward to Python backend for analysis
        console.log("Forwarding to backend:", `${BACKEND_URL}/analyze`);

        try {
            const analysisResponse = await fetch(`${BACKEND_URL}/analyze`, {
                method: "POST",
                body: backendForm,
                signal: AbortSignal.timeout(60000), // 60s timeout
            });

            if (!analysisResponse.ok) {
                const errorText = await analysisResponse.text();
                console.error("Backend analysis failed:", analysisResponse.status, errorText);
                return NextResponse.redirect(
                    new URL(`/analyze?error=analysis_failed&code=${analysisResponse.status}`, baseUrl),
                    303
                );
            }

            const result = await analysisResponse.json();

            // Cache the result on the Python backend
            const cacheResponse = await fetch(`${BACKEND_URL}/cache-result`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(result),
            });

            if (cacheResponse.ok) {
                const { id } = await cacheResponse.json();
                // Redirect to the shared results page
                return NextResponse.redirect(new URL(`/shared?id=${id}`, baseUrl), 303);
            } else {
                console.warn("Cache failed, falling back to URL params");
            }

            // Fallback: encode essential data in URL params
            const score = result.score ?? 0;
            const risk = result.risk_level ?? "unknown";
            const summary = encodeURIComponent(result.summary ?? "Analysis complete");

            return NextResponse.redirect(
                new URL(
                    `/shared?score=${score}&risk=${risk}&summary=${summary}`,
                    baseUrl
                ),
                303
            );

        } catch (fetchError: any) {
            console.error("Fetch error during analysis:", fetchError);
            const isTimeout = fetchError.name === 'TimeoutError' || fetchError.code === 'ETIMEDOUT';
            if (isTimeout) {
                return NextResponse.redirect(new URL("/analyze?error=timeout", baseUrl), 303);
            }
            return NextResponse.redirect(new URL(`/analyze?error=backend_connection_failed&details=${encodeURIComponent(String(fetchError).substring(0, 100))}`, baseUrl), 303);
        }
    } catch (error) {
        console.error("Share target fatal error:", error);
        // Use request.url fallback if baseUrl fails, but usually request.url header lookup handles it
        const host = request.headers.get("x-forwarded-host") || request.headers.get("host");
        const proto = request.headers.get("x-forwarded-proto") || "http";
        const baseUrl = `${proto}://${host}`;

        return NextResponse.redirect(
            new URL(`/analyze?error=share_failed&details=${encodeURIComponent(String(error).substring(0, 100))}`, baseUrl),
            303
        );
    }
}
