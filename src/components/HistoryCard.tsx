/**
 * HistoryCard Component
 * Elegant, compact card displaying a single history entry
 * Matches Truth_X glassmorphism aesthetic
 */

"use client";

import React, { useState } from "react";
import { HistoryEntry } from "@/services/historyService";
import {
  getVerdictColor,
} from "@/services/historyService";

interface HistoryCardProps {
  entry: HistoryEntry;
  onDelete?: (entryId: string) => void;
  onExpanded?: (entryId: string) => void;
}

export const HistoryCard: React.FC<HistoryCardProps> = ({
  entry,
  onDelete,
  onExpanded,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const verdictColor = getVerdictColor(entry.verdict_label as any);

  const handleExpand = () => {
    const newExpanded = !isExpanded;
    setIsExpanded(newExpanded);
    if (newExpanded && onExpanded) {
      onExpanded(entry.id);
    }
  };

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isDeleting) return;

    if (!confirm("Delete this history entry?")) return;

    setIsDeleting(true);
    if (onDelete) {
      await onDelete(entry.id);
    }
    setIsDeleting(false);
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return "now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const truncateSummary = (text: string, maxLength: number = 60) => {
    if (text.length > maxLength) {
      return text.substring(0, maxLength) + "...";
    }
    return text;
  };

  const verdictBgColor: Record<string, string> = {
    green: "bg-emerald-500/20 border-emerald-500/30 text-emerald-300",
    red: "bg-red-500/20 border-red-500/30 text-red-300",
    yellow: "bg-amber-500/20 border-amber-500/30 text-amber-300",
    blue: "bg-blue-500/20 border-blue-500/30 text-blue-300",
    gray: "bg-slate-500/20 border-slate-500/30 text-slate-300",
  };

  return (
    <div className="group">
      {/* Compact Card */}
      <div
        onClick={handleExpand}
        className="relative overflow-hidden rounded-xl border border-white/10 bg-white/5 backdrop-blur-md 
                   hover:bg-white/8 hover:border-white/20 transition-all duration-300 
                   cursor-pointer transform hover:scale-[1.02]"
      >
        {/* Subtle glow on hover */}
        <div
          className="absolute inset-0 opacity-0 group-hover:opacity-20 transition-opacity duration-300
                     bg-gradient-to-br from-cyan-500/30 to-blue-500/30 blur-xl pointer-events-none"
        />

        <div className="relative p-4">
          <div className="flex items-start justify-between gap-3">
            {/* Left side: Content */}
            <div className="flex items-start gap-3 flex-1 min-w-0">
              {/* Content */}
              <div className="flex-1 min-w-0">
                {/* Task Type + Processing Time (one line) */}
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="text-xs font-medium text-cyan-300 tracking-wide">
                    {entry.task_type}
                  </span>
                  <span className="text-xs text-slate-400 flex-shrink-0">
                    {entry.processing_time_formatted}
                  </span>
                </div>

                {/* Input Summary */}
                <p className="text-sm text-slate-300 truncate mb-2">
                  {truncateSummary(entry.input_summary)}
                </p>

                {/* Verdict + Timestamp (bottom row) */}
                <div className="flex items-center justify-between gap-2">
                  {entry.verdict_label ? (
                    <span
                      className={`text-xs font-medium px-2 py-1 rounded-lg border ${verdictBgColor[verdictColor]}`}
                    >
                      {entry.verdict_label}
                    </span>
                  ) : (
                    <div className="w-12" />
                  )}
                  <span className="text-xs text-slate-500">
                    {formatDate(entry.created_at)}
                  </span>
                </div>
              </div>
            </div>

            {/* Right side: Delete Button + Expand Icon */}
            <div className="flex items-start gap-1 flex-shrink-0">
              <button
                onClick={handleDelete}
                disabled={isDeleting}
                className="opacity-0 group-hover:opacity-100 transition-opacity duration-200
                           p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-500/10 
                           rounded-lg disabled:opacity-50"
                title="Delete entry"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                  />
                </svg>
              </button>

              {/* Expand indicator */}
              <div
                className={`p-1.5 transition-transform duration-200 ${isExpanded ? "rotate-180" : ""}`}
              >
                <svg
                  className="w-4 h-4 text-slate-500"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 14l-7 7m0 0l-7-7m7 7V3"
                  />
                </svg>
              </div>
            </div>
          </div>

          {/* Expanded Details */}
          {isExpanded && (
            <div className="mt-4 pt-4 border-t border-white/5 space-y-3 animate-in fade-in slide-in-from-top-2 duration-200">
              {/* Evidence & Source Count */}
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="space-y-1">
                  <span className="text-xs text-slate-500 uppercase tracking-widest">
                    Evidence Sources
                  </span>
                  <div className="text-lg font-semibold text-cyan-300">
                    {entry.evidence_count || 0}
                  </div>
                </div>
                <div className="space-y-1">
                  <span className="text-xs text-slate-500 uppercase tracking-widest">
                    Sources Analyzed
                  </span>
                  <div className="text-lg font-semibold text-blue-300">
                    {entry.source_count || 0}
                  </div>
                </div>
              </div>

              {/* Verdict Score (if available) */}
              {entry.verdict_score !== undefined && (
                <div className="space-y-2">
                  <span className="text-xs text-slate-500 uppercase tracking-widest">
                    Credibility Score
                  </span>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1.5 bg-slate-700/50 rounded-full overflow-hidden">
                      <div
                        className={`h-full transition-all duration-300 ${
                          entry.verdict_score >= 75
                            ? "bg-emerald-500"
                            : entry.verdict_score >= 50
                            ? "bg-amber-500"
                            : "bg-red-500"
                        }`}
                        style={{ width: `${entry.verdict_score}%` }}
                      />
                    </div>
                    <span className="text-sm font-medium text-slate-300 w-8 text-right">
                      {entry.verdict_score}%
                    </span>
                  </div>
                </div>
              )}

              {/* Summary */}
              {entry.summary && (
                <div className="space-y-1">
                  <span className="text-xs text-slate-500 uppercase tracking-widest">
                    Source Summary
                  </span>
                  <p className="text-sm text-slate-300 leading-relaxed line-clamp-3">
                    {entry.summary}
                  </p>
                </div>
              )}

              {/* Metadata (if available) */}
              {entry.metadata && Object.keys(entry.metadata).length > 0 && (
                <div className="space-y-1">
                  <span className="text-xs text-slate-500 uppercase tracking-widest">
                    Additional Info
                  </span>
                  <div className="text-xs space-y-1 text-slate-400">
                    {Object.entries(entry.metadata).map(([key, value]) => (
                      <div key={key} className="flex justify-between">
                        <span className="capitalize">{key}:</span>
                        <span className="text-slate-300">
                          {typeof value === "string" ? value : JSON.stringify(value)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default HistoryCard;
