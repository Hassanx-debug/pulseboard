import useSWR from "swr";

const API_URL = "https://hassan5858-pulseboard-backend.hf.space";

const fetcher = (url: string) =>
  fetch(url).then((res) => {
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  });

export interface TopUrl {
  title: string;
  url: string | null;
  source: "reddit" | "hackernews" | "github";
  heat: number;
}

export interface TrendingTopic {
  id: string;
  topic: string;
  mention_count: number;
  avg_heat: number;
  peak_heat: number;
  momentum: number;
  source_breakdown: Record<string, number>;
  top_urls: TopUrl[];
  ai_insight: string | null;
  sentiment: "bullish" | "bearish" | "neutral" | "controversial";
  category: string;
  computed_at: string;
}

export interface SnapshotItem {
  id: string;
  title: string;
  url: string | null;
  author: string | null;
  score: number;
  comment_count: number;
  heat_score: number;
  fetched_at: string;
  tags: string[];
  source: "reddit" | "hackernews" | "github";
  source_name: string;
}

export interface DashboardStats {
  total_24h: number;
  ingested_1h: number;
  peak_heat_1h: number;
  source_counts_24h: Record<string, number>;
}

export function useTrends(limit = 20) {
  const { data, error, isLoading, mutate } = useSWR(
    `${API_URL}/api/trends/?limit=${limit}`,
    fetcher,
    { refreshInterval: 60_000, dedupingInterval: 30_000 }
  );
  return {
    topics: (data?.topics ?? []) as TrendingTopic[],
    isLoading,
    error: error?.message ?? null,
    refresh: mutate,
    generatedAt: data?.generated_at ?? null,
  };
}

export function useFeed(limit = 30) {
  const { data, error, isLoading } = useSWR(
    `${API_URL}/api/trends/feed?limit=${limit}`,
    fetcher,
    { refreshInterval: 30_000, dedupingInterval: 15_000 }
  );
  return {
    items: (data?.items ?? []) as SnapshotItem[],
    isLoading,
    error: error?.message ?? null,
  };
}

export function useStats() {
  const { data, isLoading } = useSWR(
    `${API_URL}/api/trends/stats`,
    fetcher,
    { refreshInterval: 120_000 }
  );
  return { stats: data as DashboardStats | null, isLoading };
}

export const SOURCE_COLORS = {
  reddit: "#FF4500",
  hackernews: "#FF6600",
  github: "#58A6FF",
} as const;

export const SENTIMENT_COLORS = {
  bullish: "#00FF88",
  bearish: "#FF4444",
  neutral: "#888888",
  controversial: "#FF8C00",
} as const;

export const CATEGORY_ICONS: Record<string, string> = {
  ai: "ðŸ¤–", dev_tools: "ðŸ”§", security: "ðŸ”’",
  web: "ðŸŒ", infra: "âš™ï¸", language: "ðŸ“",
  hardware: "ðŸ’¾", business: "ðŸ“ˆ", other: "â—ˆ",
};

export function getMomentum(m: number) {
  if (m > 5)  return { label: "surging",  symbol: "â†‘â†‘", color: "#00FF88" };
  if (m > 1)  return { label: "rising",   symbol: "â†‘",  color: "#00CC66" };
  if (m < -5) return { label: "cooling",  symbol: "â†“â†“", color: "#FF4444" };
  if (m < -1) return { label: "fading",   symbol: "â†“",  color: "#CC3333" };
  return        { label: "steady",  symbol: "â†’",  color: "#666666" };
}
