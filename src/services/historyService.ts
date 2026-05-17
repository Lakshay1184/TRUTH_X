/**
 * Frontend History Service
 * Handles all communication with Supabase analysis_history table
 */

import { supabase } from "@/lib/supabase";

export type TaskType =
  | "Source Check"
  | "Video Analysis"
  | "Fake News Check"
  | "Image Analysis"
  | "URL Verification"
  | "Text Analysis"
  | "AI Detection";

export type VerdictLabel =
  | "Supported"
  | "Contradicted"
  | "Partially Supported"
  | "AI Generated"
  | "Likely Real"
  | "Unverified"
  | "Limited Evidence";

export interface HistoryEntry {
  id: string;
  user_id: string;
  task_type: TaskType;
  input_summary: string;
  verdict_label?: VerdictLabel;
  verdict_score?: number;
  processing_time_ms: number;
  processing_time_formatted: string;
  evidence_count: number;
  source_count: number;
  summary?: string;
  metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface HistoryResponse {
  entries: HistoryEntry[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface HistoryStats {
  total_analyses: number;
  task_type_distribution: Record<string, number>;
  top_task_type?: string;
}

/**
 * Save a new history entry to Supabase
 */
export async function saveHistoryEntry(
  taskType: TaskType,
  inputSummary: string,
  options?: {
    verdictLabel?: VerdictLabel;
    verdictScore?: number;
    processingTimeMs?: number;
    evidenceCount?: number;
    sourceCount?: number;
    summary?: string;
    metadata?: Record<string, any>;
  }
): Promise<HistoryEntry | null> {
  try {
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session?.user?.id) {
      console.error("No authenticated user");
      return null;
    }

    const processingTimeMs = options?.processingTimeMs || 0;
    const processingTimeFormatted = formatProcessingTime(processingTimeMs);

    const { data, error } = await supabase
      .from("analysis_history")
      .insert([
        {
          user_id: session.user.id,
          task_type: taskType,
          input_summary: inputSummary,
          verdict_label: options?.verdictLabel,
          verdict_score: options?.verdictScore,
          processing_time_ms: processingTimeMs,
          processing_time_formatted: processingTimeFormatted,
          evidence_count: options?.evidenceCount || 0,
          source_count: options?.sourceCount || 0,
          summary: options?.summary,
          metadata: options?.metadata || {},
          created_at: new Date().toISOString(),
        },
      ])
      .select()
      .single();

    if (error) {
      console.error("Error saving history entry:", error);
      return null;
    }

    return data as HistoryEntry;
  } catch (err) {
    console.error("Error in saveHistoryEntry:", err);
    return null;
  }
}

/**
 * Fetch user's analysis history with pagination
 */
export async function fetchUserHistory(
  limit = 20,
  offset = 0
): Promise<HistoryResponse | null> {
  try {
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session?.user?.id) {
      console.error("No authenticated user");
      return null;
    }

    // Get total count
    const { count } = await supabase
      .from("analysis_history")
      .select("*", { count: "exact", head: true })
      .eq("user_id", session.user.id);

    // Get paginated entries
    const { data, error } = await supabase
      .from("analysis_history")
      .select("*")
      .eq("user_id", session.user.id)
      .order("created_at", { ascending: false })
      .range(offset, offset + limit - 1);

    if (error) {
      console.error("Error fetching history:", error);
      return null;
    }

    return {
      entries: data as HistoryEntry[],
      total: count || 0,
      limit,
      offset,
      has_more: (offset + limit) < (count || 0),
    };
  } catch (err) {
    console.error("Error in fetchUserHistory:", err);
    return null;
  }
}

/**
 * Fetch history filtered by task type
 */
export async function fetchHistoryByType(
  taskType: TaskType,
  limit = 20,
  offset = 0
): Promise<HistoryResponse | null> {
  try {
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session?.user?.id) {
      console.error("No authenticated user");
      return null;
    }

    // Get total count
    const { count } = await supabase
      .from("analysis_history")
      .select("*", { count: "exact", head: true })
      .eq("user_id", session.user.id)
      .eq("task_type", taskType);

    // Get paginated entries
    const { data, error } = await supabase
      .from("analysis_history")
      .select("*")
      .eq("user_id", session.user.id)
      .eq("task_type", taskType)
      .order("created_at", { ascending: false })
      .range(offset, offset + limit - 1);

    if (error) {
      console.error("Error fetching history by type:", error);
      return null;
    }

    return {
      entries: data as HistoryEntry[],
      total: count || 0,
      limit,
      offset,
      has_more: (offset + limit) < (count || 0),
    };
  } catch (err) {
    console.error("Error in fetchHistoryByType:", err);
    return null;
  }
}

/**
 * Delete a history entry
 */
export async function deleteHistoryEntry(entryId: string): Promise<boolean> {
  try {
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session?.user?.id) {
      console.error("No authenticated user");
      return false;
    }

    const { error } = await supabase
      .from("analysis_history")
      .delete()
      .eq("id", entryId)
      .eq("user_id", session.user.id);

    if (error) {
      console.error("Error deleting history entry:", error);
      return false;
    }

    return true;
  } catch (err) {
    console.error("Error in deleteHistoryEntry:", err);
    return false;
  }
}

/**
 * Clear all history for current user
 */
export async function clearAllHistory(): Promise<boolean> {
  try {
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session?.user?.id) {
      console.error("No authenticated user");
      return false;
    }

    const { error } = await supabase
      .from("analysis_history")
      .delete()
      .eq("user_id", session.user.id);

    if (error) {
      console.error("Error clearing history:", error);
      return false;
    }

    return true;
  } catch (err) {
    console.error("Error in clearAllHistory:", err);
    return false;
  }
}

/**
 * Get history statistics
 */
export async function fetchHistoryStats(): Promise<HistoryStats | null> {
  try {
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session?.user?.id) {
      console.error("No authenticated user");
      return null;
    }

    const { data, count } = await supabase
      .from("analysis_history")
      .select("task_type", { count: "exact" })
      .eq("user_id", session.user.id);

    const taskTypeDistribution: Record<string, number> = {};
    (data || []).forEach((entry: any) => {
      const taskType = entry.task_type;
      taskTypeDistribution[taskType] =
        (taskTypeDistribution[taskType] || 0) + 1;
    });

    const topTaskType = Object.entries(taskTypeDistribution).sort(
      ([, a], [, b]) => b - a
    )[0]?.[0];

    return {
      total_analyses: count || 0,
      task_type_distribution: taskTypeDistribution,
      top_task_type: topTaskType,
    };
  } catch (err) {
    console.error("Error in fetchHistoryStats:", err);
    return null;
  }
}

/**
 * Format milliseconds to human-readable time string
 */
export function formatProcessingTime(milliseconds: number): string {
  if (milliseconds < 1000) {
    return `${milliseconds}ms`;
  } else if (milliseconds < 60000) {
    const seconds = (milliseconds / 1000).toFixed(1);
    return `${seconds}s`;
  } else {
    const minutes = Math.floor(milliseconds / 60000);
    const seconds = Math.floor((milliseconds % 60000) / 1000);
    return `${minutes}m ${seconds}s`;
  }
}

/**
 * Get appropriate icon for task type
 */
export function getTaskTypeIcon(taskType: TaskType): string {
  // No icons - just return empty string
  return "";
}

/**
 * Get appropriate color for verdict label
 */
export function getVerdictColor(
  verdict?: VerdictLabel
): "green" | "red" | "yellow" | "blue" | "gray" {
  const colorMap: Record<string, "green" | "red" | "yellow" | "blue" | "gray"> =
    {
      Supported: "green",
      "Partially Supported": "yellow",
      "Limited Evidence": "yellow",
      Contradicted: "red",
      "AI Generated": "red",
      "Likely Real": "green",
      Unverified: "gray",
    };
  return colorMap[verdict || "Unverified"] || "gray";
}
