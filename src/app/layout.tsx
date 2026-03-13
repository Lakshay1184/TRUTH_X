import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/context/AuthContext";
import AgentScene from "@/components/AgentScene";
import Navbar from "@/components/Navbar";
import Sidebar from "@/components/Sidebar";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Truth X - AI Content Verification",
  description: "Detect deepfakes and AI-generated content with 99% accuracy.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.className} min-h-screen bg-black text-white selection:bg-cyan-500/30 overflow-x-hidden`}>
        <AuthProvider>
          <AgentScene />
          <Navbar />
          <div className="flex min-h-screen">
            <Sidebar />
            <main className="flex-1 transition-all duration-300 relative z-10 w-full">
              {children}
            </main>
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
