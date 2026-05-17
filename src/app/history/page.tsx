"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { HistoryCard } from "@/components/HistoryCard";
import {
  fetchUserHistory,
  deleteHistoryEntry,
  HistoryResponse,
} from "@/services/historyService";

const TASK_TYPES = [
  "Source Check",
  "Video Analysis",
  "Fake News Check",
  "Image Analysis",
  "URL Verification",
  "Text Analysis",
  "AI Detection",
];

export default function HistoryPage() {
  const { user, loading: authLoading } = useAuth();
  const [historyData, setHistoryData] = useState<HistoryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);

  const loadHistory = async () => {
    if (!user?.id) return;

    setLoading(true);
    setError(null);

    try {
      const data = await fetchUserHistory(10, page * 10);
      setHistoryData(data);
    } catch (err) {
      console.error("Failed to load history:", err);
      setError("Failed to load analysis results");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!authLoading) {
      loadHistory();
    }
  }, [user?.id, page, authLoading]);

  const handleDeleteEntry = async (entryId: string) => {
    try {
      await deleteHistoryEntry(entryId);
      setHistoryData((prev) => {
        if (!prev) return null;
        return {
          ...prev,
          entries: prev.entries.filter((e) => e.id !== entryId),
          total: prev.total - 1,
        };
      });
    } catch (err) {
      console.error("Failed to delete entry:", err);
    }
  };

  if (authLoading) {
    return (
      <div className="relative z-10 min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-pulse text-cyan-400 font-mono tracking-widest">INITIALIZING SECURE ACCESS...</div>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="relative z-10 min-h-screen flex items-center justify-center px-4">
        <div className="max-w-md w-full glass-card p-8 text-center rounded-3xl border border-white/10 backdrop-blur-xl">
          <p className="text-slate-300 mb-8 text-lg">Identity verification required to access intelligence archives.</p>
          <a
            href="/login"
            className="block w-full py-4 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-black font-black transition-all shadow-[0_0_30px_-5px_rgba(6,182,212,0.4)]"
          >
            SIGN IN
          </a>
        </div>
      </div>
    );
  }

  const entries = historyData?.entries || [];
  const total = historyData?.total || 0;
  const hasMore = historyData?.has_more || false;

  return (
    <div className="relative z-10 min-h-screen pt-40 pb-20 px-4 md:px-8 overflow-auto">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-10">
          <h1 className="text-5xl md:text-6xl font-black tracking-tighter text-white mb-3 bg-clip-text text-transparent bg-gradient-to-b from-white to-white/50">
            History Logs
          </h1>
          <div className="flex items-center gap-4">
            <div className="h-px flex-1 bg-gradient-to-r from-cyan-500/50 to-transparent" />
            <p className="text-cyan-400 font-mono text-xs tracking-[0.3em] uppercase">
              {total} SECURE RECORDS
            </p>
          </div>
        </div>

        {/* Error State */}
        {error && (
          <div className="mb-6 p-4 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300">
            {error}
          </div>
        )}

        {/* Loading State */}
        {loading && !entries.length && (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-24 rounded-xl bg-white/5 border border-white/10 animate-pulse"
              />
            ))}
          </div>
        )}

        {/* Empty State */}
        {!loading && entries.length === 0 && (
          <div className="text-center py-20">
            <p className="text-slate-400 mb-4">No analysis results yet</p>
            <a
              href="/analyze"
              className="inline-block px-6 py-2 rounded-lg bg-cyan-500/20 border border-cyan-500/30 
                       text-cyan-300 hover:bg-cyan-500/30 transition-colors"
            >
              Run an Analysis
            </a>
          </div>
        )}

        {/* Results List */}
        {entries.length > 0 && (
          <>
            <div className="space-y-3">
              {entries.map((entry) => (
                <HistoryCard
                  key={entry.id}
                  entry={entry}
                  onDelete={handleDeleteEntry}
                />
              ))}
            </div>

            {/* Pagination */}
            {total > 10 && (
              <div className="mt-8 flex items-center justify-between">
                <button
                  onClick={() => setPage(Math.max(0, page - 1))}
                  disabled={page === 0 || loading}
                  className="px-4 py-2 rounded-lg border border-white/10 text-slate-300
                           hover:border-white/20 hover:text-white disabled:opacity-50 
                           transition-colors"
                >
                  Previous
                </button>

                <span className="text-sm text-slate-400">
                  Page {page + 1} of {Math.ceil(total / 10)}
                </span>

                <button
                  onClick={() => setPage(page + 1)}
                  disabled={!hasMore || loading}
                  className="px-4 py-2 rounded-lg border border-white/10 text-slate-300
                           hover:border-white/20 hover:text-white disabled:opacity-50 
                           transition-colors"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

