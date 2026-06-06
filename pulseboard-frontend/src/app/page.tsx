"use client";
import { useState, useEffect } from "react";
import { motion, AnimatePresence, LayoutGroup } from "framer-motion";
import { useTrends, useFeed, useStats, SOURCE_COLORS, SENTIMENT_COLORS, CATEGORY_ICONS, getMomentum, type TrendingTopic, type SnapshotItem } from "@/hooks/useTrendsHook";
import TrendChart from "@/components/TrendChart";
import { useWebSocket } from "@/hooks/useWebSocket";

function SourceBadge({ source }: { source: string }) {
  const color = SOURCE_COLORS[source as keyof typeof SOURCE_COLORS] ?? "#888";
  const labels: Record<string, string> = { reddit: "RDT", hackernews: "HN", github: "GH" };
  return <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded shrink-0" style={{ color, border: `1px solid ${color}33`, background: `${color}11` }}>{labels[source] ?? source.toUpperCase()}</span>;
}

function SentimentBadge({ sentiment }: { sentiment: string }) {
  const color = SENTIMENT_COLORS[sentiment as keyof typeof SENTIMENT_COLORS] ?? "#888";
  const icons: Record<string, string> = { bullish: "â–²", bearish: "â–¼", neutral: "â—†", controversial: "âš¡" };
  return <span className="text-[9px] font-mono px-1.5 py-0.5 rounded shrink-0" style={{ color, border: `1px solid ${color}33`, background: `${color}11` }}>{icons[sentiment] ?? "â—†"} {sentiment}</span>;
}

function HeatBar({ heat, max }: { heat: number; max: number }) {
  const pct = Math.min((heat / Math.max(max, 1)) * 100, 100);
  const color = heat > 100 ? "#FF4500" : heat > 50 ? "#FF8C00" : "#00FF88";
  return <div className="h-0.5 w-full bg-white/5 rounded-full overflow-hidden"><motion.div className="h-full rounded-full" style={{ backgroundColor: color }} initial={{ width: 0 }} animate={{ width: `${pct}%` }} transition={{ duration: 0.8 }} /></div>;
}

function TopicCard({ topic, index, maxHeat }: { topic: TrendingTopic; index: number; maxHeat: number }) {
  const [expanded, setExpanded] = useState(false);
  const momentum = getMomentum(topic.momentum);
  const icon = CATEGORY_ICONS[topic.category] ?? "◆";
  return (
    <motion.div layoutId={topic.id} layout initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: index * 0.035 }} whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} className="border border-white/5 hover:border-white/10 rounded-lg bg-white/10 hover:bg-white/20 backdrop-blur-md transition-all cursor-pointer overflow-hidden" onClick={() => setExpanded(e => !e)}>
      <div className="flex items-center gap-3 px-4 py-3">
        <span className="text-white/20 font-mono text-[10px] w-4 shrink-0 text-right">{String(index + 1).padStart(2, "0")}</span>
        <span className="text-sm shrink-0">{icon}</span>
        <span className="font-mono text-sm text-white/90 flex-1 truncate tracking-wide">#{topic.topic}</span>
        <SentimentBadge sentiment={topic.sentiment} />
        <div className="flex gap-1 shrink-0">{Object.keys(topic.source_breakdown).map(src => <SourceBadge key={src} source={src} />)}</div>
        <span className="text-white/30 font-mono text-[10px] shrink-0">{topic.mention_count}×</span>
        <span className="font-mono text-[10px] shrink-0" style={{ color: momentum.color }}>{momentum.symbol} {momentum.label}</span>
        <span className="font-mono text-[10px] text-white/50 shrink-0 w-14 text-right">⚡{topic.avg_heat.toFixed(1)}</span>
        <span className="text-white/20 text-[10px] shrink-0 transition-transform duration-200" style={{ transform: expanded ? "rotate(180deg)" : "none" }}>▼</span>
      </div>
      <div className="px-4 pb-2"><HeatBar heat={topic.avg_heat} max={maxHeat} /></div>
      {topic.ai_insight && <div className="px-4 pb-2"><p className="text-[10px] text-white/40 font-mono leading-relaxed"><span className="text-white/20">AI › </span>{topic.ai_insight}</p></div>}
      <AnimatePresence>
        {expanded && topic.top_urls?.length > 0 && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.2 }} className="border-t border-white/5 overflow-hidden">
            <div className="px-4 py-3 space-y-2">
              {topic.top_urls.map((item, i) => (
                <div key={i} className="flex items-start gap-2">
                  <SourceBadge source={item.source} />
                  <a href={item.url ?? "#"} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()} className="text-[10px] text-white/40 hover:text-white/80 transition-colors flex-1 line-clamp-2">{item.title}</a>
                  <span className="text-[9px] font-mono text-white/20 shrink-0">⚡{item.heat.toFixed(1)}</span>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

function FeedItem({ item }: { item: SnapshotItem }) {
  return (
    <div className="flex items-start gap-3 py-2.5 border-b border-white/[0.04] last:border-0">
      <SourceBadge source={item.source} />
      <div className="flex-1 min-w-0">
        <a href={item.url ?? "#"} target="_blank" rel="noopener noreferrer" className="text-[11px] text-white/60 hover:text-white/90 transition-colors line-clamp-2 leading-relaxed">{item.title}</a>
        <div className="flex items-center gap-2 mt-1 flex-wrap">
          <span className="text-[9px] text-white/25 font-mono">↑{item.score} · 💬{item.comment_count}</span>
          {(item.tags ?? []).slice(0, 3).map(tag => <span key={tag} className="text-[9px] text-white/20 font-mono">#{tag}</span>)}
        </div>
      </div>
      <span className="text-[9px] font-mono text-white/25 shrink-0">⚡{item.heat_score.toFixed(1)}</span>
    </div>
  );
}

function StatsBar() {
  const { stats } = useStats();
  if (!stats) return <div className="flex gap-6 text-[10px] font-mono text-white/20 animate-pulse">LOADING STATS...</div>;
  return (
    <div className="flex items-center gap-6 flex-wrap text-[10px] font-mono">
      <span className="text-white/30">TOTAL <span className="text-white/70">{stats.total_24h.toLocaleString()}</span>/24H</span>
      <span className="text-white/30">LAST HOUR <span className="text-white/70">{stats.ingested_1h}</span></span>
      <span className="text-white/30">PEAK <span style={{ color: "#FF4500" }}>⚡{stats.peak_heat_1h?.toFixed(1)}</span></span>
      {Object.entries(stats.source_counts_24h ?? {}).map(([src, count]) => (
        <span key={src} className="text-white/30"><span style={{ color: SOURCE_COLORS[src as keyof typeof SOURCE_COLORS] ?? "#888" }}>{src.toUpperCase()}</span> <span className="text-white/70">{count}</span></span>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const { isConnected, isSyncing, userCount } = useWebSocket();
  const { topics, isLoading, error, refresh, generatedAt } = useTrends(25);
  const { items, isLoading: feedLoading } = useFeed(30);
  const [tab, setTab] = useState<"topics" | "feed">("topics");

  // userCount is now provided by useWebSocket hook


  const syncTime = generatedAt ? new Date(generatedAt).toLocaleTimeString() : "";
  return (
    <main className="min-h-screen bg-[#080808] bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-indigo-950/20 via-[#080808] to-[#040404] text-white">
      <div className="sticky top-0 z-50 backdrop-blur-md bg-[#080808]/80 border-b border-white/5 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`w-2 h-2 rounded-full transition-all duration-500 ${isConnected ? "bg-[#00FF88] shadow-[0_0_8px_#00FF88] animate-pulse" : "bg-[#FF4444] shadow-[0_0_8px_#FF4444]"}`} />
          <span className="font-mono text-sm text-white/80 tracking-widest">PULSE_BOARD</span>
          <span className="font-mono text-[9px] text-white/45 border border-white/10 px-1.5 py-0.5 rounded uppercase tracking-wider">{isConnected ? "live" : "offline"}</span>
          <span className="font-mono text-[9px] text-white/20">v3.0</span>
          <span className="font-mono text-[9px] text-white/40 ml-2">👥 {userCount}</span>
        </div>
        <div className="flex items-center gap-4">
          {isSyncing && (
            <span className="font-mono text-[10px] text-[#00FF88] animate-pulse">
              ● SYNCING...
            </span>
          )}
          {syncTime && <span className="font-mono text-[10px] text-white/25">SYNCED {syncTime}</span>}
          <button onClick={() => refresh()} className="font-mono text-[10px] text-white/30 hover:text-white/70 border border-white/10 hover:border-white/20 px-3 py-1.5 rounded transition-all">↺ REFRESH</button>
        </div>
      </div>
      <div className="max-w-6xl mx-auto px-6 py-6 space-y-6">
        <StatsBar />
        <div className="flex items-center justify-between">
          <div className="flex border border-white/10 rounded overflow-hidden">
            {(["topics", "feed"] as const).map(t => (
              <button key={t} onClick={() => setTab(t)} className={`px-4 py-2 text-[10px] font-mono uppercase tracking-widest transition-colors ${tab === t ? "bg-white/10 text-white/90" : "text-white/30 hover:text-white/60"}`}>
                {t === "topics" ? `â—ˆ Topics (${topics.length})` : `âš¡ Live Feed (${items.length})`}
              </button>
            ))}
          </div>
          {tab === "topics" && (
            <div className="flex gap-2 flex-wrap">
              {["ai","dev_tools","security","web","infra"].map(cat => {
                const count = topics.filter(t => t.category === cat).length;
                if (!count) return null;
                return <span key={cat} className="font-mono text-[9px] text-white/30 border border-white/10 px-2 py-1 rounded">{CATEGORY_ICONS[cat]} {cat} ({count})</span>;
              })}
            </div>
          )}
        </div>
        {tab === "topics" && (
          <div className="space-y-2">
            {isLoading && (
              <div className="flex items-center gap-3 py-12 justify-center">
                <div className="w-1.5 h-1.5 bg-green-400 rounded-full animate-bounce" />
                <span className="font-mono text-xs text-white/30">FETCHING TRENDS...</span>
              </div>
            )}
            {error && (
              <div className="font-mono text-xs text-red-400/70 py-4 px-3 border border-red-400/20 rounded-lg bg-red-400/5">
                ✖ {error}{' '}
                <button onClick={() => refresh()} className="ml-3 underline text-white/40 hover:text-white/70">
                  retry
                </button>
              </div>
            )}
          <TrendChart topics={topics} />
            {!isLoading && !error && topics.length === 0 && (
              <div className="text-center py-12">
                <p className="font-mono text-xs text-white/30">NO TREND DATA YET</p>
              </div>
            )}
            <LayoutGroup>
              {topics.map((topic, i) => (
                <TopicCard key={topic.id} topic={topic} index={i} maxHeat={maxHeat} />
              ))}
            </LayoutGroup>
          </div>
        )}
        {tab === "feed" && (
          <div className="border border-white/5 rounded-lg bg-white/[0.02] px-4 divide-y divide-white/[0.04]">
            {feedLoading && <div className="flex items-center gap-3 py-12 justify-center"><div className="w-1.5 h-1.5 bg-green-400 rounded-full animate-bounce" /><span className="font-mono text-xs text-white/30">LOADING FEED...</span></div>}
            {!feedLoading && items.length === 0 && <div className="text-center py-12"><p className="font-mono text-xs text-white/30">NO ITEMS IN FEED</p></div>}
            <AnimatePresence>{items.map(item => <FeedItem key={item.id} item={item} />)}</AnimatePresence>
          </div>
        )}
      </div>
    </main>
  );
}


