import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
    return {
        name: "Truth X — AI Content Verification",
        short_name: "Truth X",
        description:
            "Detect deepfakes and AI-generated content with 99% accuracy. Share any media from WhatsApp, Facebook, or any app for instant verification.",
        start_url: "/",
        display: "standalone",
        background_color: "#000000",
        theme_color: "#00d4ff",
        orientation: "portrait-primary",
        icons: [
            {
                src: "/icon-192.png",
                sizes: "192x192",
                type: "image/png",
                purpose: "any maskable" as any,
            },
            {
                src: "/icon-512.png",
                sizes: "512x512",
                type: "image/png",
                purpose: "any maskable" as any,
            },
        ],
        // PWA Share Target — allows receiving files from other apps
        share_target: {
            action: "/api/share-target",
            method: "POST",
            enctype: "multipart/form-data",
            params: {
                title: "title",
                text: "text",
                url: "url",
                files: [
                    {
                        name: "media",
                        accept: [
                            "video/*",
                            "image/*",
                            "video/mp4",
                            "video/quicktime",
                            "video/x-msvideo",
                            "image/jpeg",
                            "image/png",
                            "image/webp",
                            "image/gif"
                        ],
                    },
                ],
            },
        },
    };
}
