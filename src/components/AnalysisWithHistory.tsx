/**
 * Unified Analysis View
 * Shows analysis form + recent analysis results in one place
 * No separate history page needed
 */

"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { HistoryCard } from "./HistoryCard";
import { 
  fetchUserHistory, 
  deleteHistoryEntry, 
  HistoryResponse,
  HistoryEntry 
} from "@/services/historyService";

interface AnalysisWithHistoryProps {
  children?: React.ReactNode; // The analyze form component
}

export const AnalysisWithHistory: React.FC<AnalysisWithHistoryProps> = ({
  children,
}) => {
  const { session } = useAuth();
  const [historyData, setHistoryData] = useState<HistoryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAllResults, setShowAllResults] = useState(false);

  const loadHistory = async () => {
    if (!session?.user?.id) return;

    setLoading(true);
    setError(null);

    try {
      const data = await fetchUserHistory(showAllResults ? 50 : 5, 0);
      setHistoryData(data);
    } catch (err) {
      console.error("Failed to load history:", err);
      setError("Failed to load analysis results");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, [session?.user?.id, showAllResults]);

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
      setError("Failed to delete entry");
    }
  };

  if (!session?.user) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-950 via-blue-950 to-slate-950 p-4 md:p-8">
        <div className="max-w-6xl mx-auto">
          <div className="text-center py-12">
            <p className="text-slate-400">Please sign in to use the analysis tool</p>
          </div>
        </div>
      </div>
    );
  }

  const displayedEntries = historyData?.entries || [];
  const totalResults = historyData?.total || 0;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-blue-950 to-slate-950">
      <div className="max-w-6xl mx-auto px-4 md:px-8 py-8">
        {/* Analysis Form Section */}
        <div className="mb-12">
          {children}
        </div>

        {/* Results Section */}
        <div className="mt-16">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-white">
              Analysis Results
              {totalResults > 0 && (
                <span className="text-sm text-slate-400 font-normal ml-3">
                  ({totalResults} total)
                </span>
              )}
            </h2>
          </div>

          {error && (
            <div className="mb-6 p-4 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300">
              {error}
            </div>
          )}

          {loading && !displayedEntries.length ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="h-24 rounded-xl bg-white/5 border border-white/10 animate-pulse"
                />
              ))}
            </div>
          ) : displayedEntries.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-slate-400 mb-2">No analysis results yet</p>
              <p className="text-sm text-slate-500">
                Run an analysis above to see results appear here
              </p>
            </div>
          ) : (
            <>
              {/* Results Grid */}
              <div className="space-y-3">
                {displayedEntries.map((entry) => (
                  <HistoryCard
                    key={entry.id}
                    entry={entry}
                    onDelete={handleDeleteEntry}
                  />
                ))}
              </div>

              {/* Show More Button */}
              {totalResults > 5 && !showAllResults && (
                <button
                  onClick={() => setShowAllResults(true)}
                  className="mt-6 w-full py-2 px-4 rounded-lg border border-cyan-500/30 
                           bg-cyan-500/10 text-cyan-300 hover:bg-cyan-500/20 
                           transition-colors duration-200 font-medium"
                >
                  Show All Results ({totalResults})
                </button>
              )}

              {showAllResults && totalResults > 5 && (
                <button
                  onClick={() => setShowAllResults(false)}
                  className="mt-6 w-full py-2 px-4 rounded-lg border border-slate-500/30 
                           bg-slate-500/10 text-slate-300 hover:bg-slate-500/20 
                           transition-colors duration-200 font-medium"
                >
                  Show Recent
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default AnalysisWithHistory;
