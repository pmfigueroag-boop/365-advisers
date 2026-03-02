"use client";

import { useState, useEffect } from "react";
import { PriceChart, CashFlowChart } from "@/components/Charts";
import TradingViewChart from "@/components/TradingViewChart";
import TradingViewTechnicalWidget from "@/components/TradingViewTechnicalWidget";
import {
  TrendingUp,
  AlertCircle,
  BarChart3,
  Search,
  Activity,
  ShieldCheck,
  Zap,
  CheckCircle2,
  Clock,
  Loader2,
  Star,
  X,
  BookMarked,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  GitCompare,
  Download,
  History,
  LineChart,
  HelpCircle,
  Menu,
} from "lucide-react";
import HelpPanel from "@/components/HelpPanel";

import { useAnalysisStream, AgentSignal } from "@/hooks/useAnalysisStream";
import { useWatchlist, WatchlistItem } from "@/hooks/useWatchlist";
import CompareView, { CompareState } from "@/components/CompareView";
import ReportHeader from "@/components/ReportHeader";
import HistoryPanel from "@/components/HistoryPanel";
import { useAnalysisHistory } from "@/hooks/useAnalysisHistory";
import { useTechnicalAnalysis } from "@/hooks/useTechnicalAnalysis";
import IndicatorGrid from "@/components/IndicatorGrid";
import { useFundamentalStream } from "@/hooks/useFundamentalStream";
import ResearchMemoCard from "@/components/ResearchMemoCard";
import OnboardingOverlay, { useOnboarding } from "@/components/OnboardingOverlay";
import { useCombinedStream } from "@/hooks/useCombinedStream";
import CombinedDashboard from "@/components/CombinedDashboard";




// ─── Cache Badge ─────────────────────────────────────────────────────────────
function CacheBadge({ cachedAt }: { cachedAt: string | null }) {
  if (!cachedAt) return null;
  const ageMs = Date.now() - new Date(cachedAt).getTime();
  const ageMin = Math.round(ageMs / 60000);
  const ageLabel = ageMin < 1 ? "just now" : `${ageMin} min ago`;
  return (
    <span
      title={`Result from cache — Cached ${ageLabel}`}
      className="flex items-center gap-1 px-2 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest bg-amber-500/10 border border-amber-500/30 text-amber-400 cursor-help select-none"
    >
      <Zap size={9} fill="currentColor" />
      Cached · {ageLabel}
    </span>
  );
}

// ─── Signal Badge helper ─────────────────────────────────────────────────────
function SignalBadge({ signal }: { signal?: string }) {
  if (!signal) return null;
  const s = signal.toUpperCase();
  const cls = s.includes("BUY") || s === "AGGRESSIVE"
    ? "bg-green-500/15 text-green-400 border-green-500/30"
    : s.includes("SELL") || s === "DEFENSIVE"
      ? "bg-red-500/15 text-red-400 border-red-500/30"
      : "bg-gray-500/15 text-gray-400 border-gray-500/30";
  return (
    <span className={`text-[8px] font-black uppercase tracking-widest px-1.5 py-0.5 rounded border ${cls}`}>
      {signal}
    </span>
  );
}

// ─── Watchlist Sidebar ───────────────────────────────────────────────────────
function WatchlistSidebar({
  items,
  collapsed,
  onToggle,
  onSelect,
  onRemove,
  activeTicker,
}: {
  items: WatchlistItem[];
  collapsed: boolean;
  onToggle: () => void;
  onSelect: (ticker: string) => void;
  onRemove: (ticker: string) => void;
  activeTicker?: string;
}) {
  return (
    <aside
      className="relative flex-shrink-0 transition-all duration-300"
      style={{ width: collapsed ? "48px" : "220px" }}
    >
      {/* Toggle button */}
      <button
        onClick={onToggle}
        className="absolute -right-3 top-6 z-10 w-6 h-6 bg-[#1c2128] border border-[#30363d] rounded-full flex items-center justify-center text-gray-500 hover:text-[#d4af37] hover:border-[#d4af37]/50 transition-all"
        title={collapsed ? "Expand watchlist" : "Collapse watchlist"}
      >
        {collapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
      </button>

      <div className="glass-card border-[#30363d] bg-[#0d1117]/60 h-full flex flex-col overflow-hidden">
        {/* Header */}
        <div className={`flex items-center gap-2 p-4 border-b border-[#30363d] ${collapsed ? "justify-center" : ""}`}>
          <BookMarked size={14} className="text-[#d4af37] flex-shrink-0" />
          {!collapsed && (
            <div className="flex items-center justify-between w-full min-w-0">
              <span className="text-[10px] font-black uppercase tracking-widest text-[#d4af37]">
                Watchlist
              </span>
              <span className="text-[9px] font-mono text-gray-600 ml-2">{items.length}</span>
            </div>
          )}
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto custom-scrollbar py-2">
          {items.length === 0 && !collapsed ? (
            <div className="flex flex-col items-center justify-center h-full px-4 py-8 text-center gap-2">
              <BookMarked size={24} className="text-[#30363d]" />
              <p className="text-[10px] text-gray-600 leading-relaxed">
                Add a ticker with ★ to track it here
              </p>
            </div>
          ) : (
            items.map((item) => {
              const isActive = item.ticker === activeTicker;
              return (
                <div
                  key={item.ticker}
                  className={`group relative flex items-center gap-2 px-3 py-2.5 mx-1 my-0.5 rounded-lg cursor-pointer transition-all ${isActive
                    ? "bg-[#d4af37]/10 border border-[#d4af37]/30"
                    : "hover:bg-[#161b22] border border-transparent"
                    }`}
                  onClick={() => onSelect(item.ticker)}
                  title={collapsed ? `${item.ticker} — ${item.name}` : undefined}
                >
                  {collapsed ? (
                    <div className="w-full text-center">
                      <span className="text-[11px] font-black text-gray-300">{item.ticker.slice(0, 4)}</span>
                    </div>
                  ) : (
                    <>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-1">
                          <span className={`text-[12px] font-black ${isActive ? "text-[#d4af37]" : "text-gray-200"}`}>
                            {item.ticker}
                          </span>
                          {item.lastSignal && <SignalBadge signal={item.lastSignal} />}
                        </div>
                        <div className="flex items-center gap-2">
                          <p className="text-[9px] text-gray-500 truncate">{item.name}</p>
                          {item.lastScore !== undefined && item.prevScore !== undefined && item.lastScore !== item.prevScore && (
                            <span className={`text-[8px] font-mono font-black flex-shrink-0 ${item.lastScore > item.prevScore ? "text-green-400" : "text-red-400"
                              }`}>
                              {item.lastScore > item.prevScore ? "+" : ""}{(item.lastScore - item.prevScore).toFixed(1)}
                            </span>
                          )}
                        </div>
                        {item.lastAnalyzedAt && (
                          <p className="text-[8px] text-gray-700 mt-0.5">
                            {new Date(item.lastAnalyzedAt).toLocaleDateString("en-US", {
                              month: "short",
                              day: "numeric",
                            })}
                          </p>
                        )}
                      </div>
                      {/* Remove button */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onRemove(item.ticker);
                        }}
                        className="opacity-0 group-hover:opacity-100 transition-opacity text-gray-600 hover:text-red-400 p-0.5 flex-shrink-0"
                        title="Remove from watchlist"
                      >
                        <X size={10} />
                      </button>
                    </>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </aside>
  );
}

// ─── Fundamental Table ───────────────────────────────────────────────────────
const FundamentalTable = ({ engine }: { engine: any }) => {
  if (!engine) return null;
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
      {Object.entries(engine).map(([category, metrics]: [string, any]) => (
        <div key={category} className="glass-card p-4 border-[#30363d] bg-[#0d1117]/30">
          <h4 className="text-[10px] font-black uppercase text-[#d4af37] mb-3 tracking-widest">
            {category.replace("_", " ")}
          </h4>
          <div className="space-y-2">
            {Object.entries(metrics).map(([key, val]: [string, any]) => (
              <div key={key} className="flex justify-between items-center">
                <span className="text-[10px] text-gray-500 capitalize">{key.replace(/_/g, " ")}</span>
                <span className={`text-[10px] font-mono ${val === "DATA_INCOMPLETE" ? "text-red-500/50" : "text-gray-200"}`}>
                  {typeof val === "number"
                    ? val > 1 || val < -1
                      ? val.toLocaleString("en-US", { maximumFractionDigits: 2 })
                      : (val * 100).toFixed(2) + "%"
                    : val}
                </span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};

// ─── Agent Card ──────────────────────────────────────────────────────────────
const AgentCard = ({ agent, index }: { agent: AgentSignal; index: number }) => {
  const isBuy = ["BUY", "AGGRESSIVE"].includes(agent.signal?.toUpperCase());
  const isSell = ["SELL", "DEFENSIVE"].includes(agent.signal?.toUpperCase());
  return (
    <div
      className="agent-card glass-card p-5 border-[#30363d] flex flex-col h-[320px] hover:border-[#d4af37]/50 transition-all group"
      style={{ animation: `fadeSlideIn 0.45s ease both`, animationDelay: `${index * 60}ms` }}
    >
      <div className="flex justify-between items-start mb-3">
        <div className="flex items-center gap-2">
          <CheckCircle2 size={12} className="text-[#d4af37]" />
          <h3 className="font-black text-base group-hover:text-[#d4af37] transition-colors">{agent.agent_name}</h3>
        </div>
        <span className={`px-2 py-0.5 rounded text-[9px] font-black tracking-tighter ${isBuy ? "bg-green-500/10 text-green-400" : isSell ? "bg-red-500/10 text-red-400" : "bg-gray-500/10 text-gray-400"}`}>
          {agent.signal}
        </span>
      </div>
      <div className="flex-1 overflow-y-auto pr-2 custom-scrollbar">
        <p className="text-[11px] text-gray-400 leading-relaxed text-pretty mb-3">{agent.analysis}</p>
        {agent.selected_metrics && agent.selected_metrics.length > 0 && (
          <div className="space-y-1">
            <span className="text-[8px] font-black text-[#d4af37] uppercase tracking-widest">Métricas Priorizadas</span>
            <div className="flex flex-wrap gap-1">
              {agent.selected_metrics.map((m: any, idx: number) => {
                const label = typeof m === "string" ? m : m.metric || m.name || `Metric ${idx}`;
                const tooltip = typeof m === "object" ? m.justification || m.reason : null;
                return (
                  <span key={idx} title={tooltip} className="px-1.5 py-0.5 bg-[#d4af37]/10 text-[#f9e29c] rounded-sm text-[8px] font-mono border border-[#d4af37]/20 cursor-help">
                    {label}
                  </span>
                );
              })}
            </div>
          </div>
        )}
      </div>
      <div className="mt-4 pt-3 border-t border-[#30363d] flex justify-between items-center bg-[#0d1117]/50 -mx-5 -mb-5 p-4 rounded-b-xl">
        <span className="text-[9px] text-gray-500 uppercase font-bold tracking-widest">Confidence</span>
        <div className="flex items-center gap-2">
          <div className="w-12 h-1 bg-[#161b22] rounded-full overflow-hidden">
            <div className="h-full bg-[#d4af37]" style={{ width: `${(agent.confidence || 0) * 100}%` }} />
          </div>
          <span className="text-[9px] font-mono text-[#d4af37]">{((agent.confidence || 0) * 100).toFixed(0)}%</span>
        </div>
      </div>
    </div>
  );
};

// ─── Skeleton Card ───────────────────────────────────────────────────────────
const AgentSkeletonCard = ({ label }: { label: string }) => (
  <div className="glass-card p-5 border-[#30363d] flex flex-col h-[320px] opacity-60">
    <div className="flex items-center gap-2 mb-3">
      <Loader2 size={12} className="text-[#d4af37] animate-spin" />
      <span className="font-black text-base text-gray-600">{label}</span>
    </div>
    <div className="flex-1 space-y-2 pt-2">
      {[100, 80, 90, 60, 75].map((w, i) => (
        <div key={i} className="h-2 bg-[#30363d] rounded animate-pulse" style={{ width: `${w}%` }} />
      ))}
    </div>
    <div className="mt-4 pt-3 border-t border-[#30363d] flex items-center justify-center -mx-5 -mb-5 p-4 rounded-b-xl bg-[#0d1117]/30">
      <Clock size={12} className="text-gray-600 mr-2" />
      <span className="text-[9px] text-gray-600 uppercase tracking-widest">Analyzing...</span>
    </div>
  </div>
);

// ─── Progress Bar ────────────────────────────────────────────────────────────
const AGENT_ORDER = ["Lynch", "Buffett", "Marks", "Icahn", "Bollinger", "RSI", "MACD", "Gann"];

const ProgressBar = ({ completed, total, status }: { completed: number; total: number; status: string }) => {
  const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
  const isDone = completed >= total;
  return (
    <div className="glass-card p-4 border-[#30363d] bg-[#0d1117]/40 mb-6">
      <div className="flex justify-between items-center mb-2">
        <div className="flex items-center gap-2">
          {isDone ? <CheckCircle2 size={14} className="text-[#d4af37]" /> : <Loader2 size={14} className="text-[#d4af37] animate-spin" />}
          <span className="text-xs font-black uppercase tracking-widest text-gray-400">
            {status === "fetching_data" ? "Fetching market data..." : status === "analyzing" ? `Committee at work — ${completed} / ${total} minds reporting` : "Analysis complete"}
          </span>
        </div>
        <span className="text-xs font-mono text-[#d4af37]">{pct}%</span>
      </div>
      <div className="h-1.5 bg-[#161b22] rounded-full overflow-hidden">
        <div className="h-full bg-[#d4af37] transition-all duration-500 ease-out" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
};

// ─── Main Page ───────────────────────────────────────────────────────────────
export default function Home() {
  const [ticker, setTicker] = useState("");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [legacyGridOpen, setLegacyGridOpen] = useState(false);
  const [chartsOpen, setChartsOpen] = useState(false);
  const [showProGate, setShowProGate] = useState(false);
  const { showOnboarding, dismiss: dismissOnboarding } = useOnboarding();

  // Main analysis tab: "fundamental" | "technical" | "combined"
  const [mainTab, setMainTab] = useState<"fundamental" | "technical" | "combined">("combined");

  // Compare mode state
  const [compareMode, setCompareMode] = useState(false);
  const [compareInput, setCompareInput] = useState("");
  const [compareState, setCompareState] = useState<CompareState>({ status: "idle", results: [] });

  const [sidebarTab, setSidebarTab] = useState<"watchlist" | "history">("watchlist");
  const [helpOpen, setHelpOpen] = useState(false);

  // Auto-collapse sidebar on mobile screens on first render
  useEffect(() => {
    if (typeof window !== "undefined" && window.innerWidth < 768) {
      setSidebarCollapsed(true);
    }
  }, []);

  // Shift+? opens/closes the Help panel
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.shiftKey && e.key === "?") {
        e.preventDefault();
        setHelpOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const { state, analyze, forceRefresh, TOTAL_AGENTS } = useAnalysisStream();
  const technical = useTechnicalAnalysis();
  const fundamental = useFundamentalStream();
  const combined = useCombinedStream();
  const watchlist = useWatchlist();
  const history = useAnalysisHistory();


  const { status, dataReady, agents, dalio, error, agentCount, fromCache, cachedAt } = state;
  const isLoading = status === "fetching_data" || status === "analyzing";
  const showSkeletons = status === "analyzing" || status === "fetching_data";
  const completedNames = new Set(agents.map((a) => a.agent_name));
  const pendingSlots = AGENT_ORDER.filter((n) => !completedNames.has(n));

  // Determine overall Dalio signal for watchlist badge
  const derivedSignal = dalio?.dalio_response?.verdict
    ? dalio.dalio_response.verdict.toUpperCase().includes("BUY") ? "BUY"
      : dalio.dalio_response.verdict.toUpperCase().includes("SELL") ? "SELL"
        : "HOLD"
    : undefined;

  // Update watchlist badge + save to history when analysis completes
  useEffect(() => {
    if (status === "complete" && dataReady?.ticker && derivedSignal) {
      watchlist.updateSignal(
        dataReady.ticker,
        derivedSignal,
        fundamental.state.committee?.score ?? undefined
      );
      history.add({
        ticker: dataReady.ticker,
        name: dataReady.name ?? dataReady.ticker,
        signal: derivedSignal,
        agentSummary: agents.map((a) => ({
          name: a.agent_name,
          signal: a.signal,
          confidence: a.confidence ?? 0,
        })),
        dalioVerdict: dalio?.final_verdict ?? dalio?.dalio_response?.verdict ?? "",
        fromCache: fromCache ?? false,
      });
    }
  }, [status]); // eslint-disable-line react-hooks/exhaustive-deps


  const handleAnalyze = (symbol?: string) => {
    const t = symbol ?? ticker;
    if (!t.trim()) return;
    if (!symbol) setTicker(t);
    if (compareMode) setCompareMode(false);
    analyze(t);
    // Kick off technical, fundamental, and combined engines in parallel
    technical.analyze(t);
    fundamental.analyze(t);
    combined.analyze(t);
  };

  const handleRunComparison = async () => {
    const tickers = compareInput.split(/[,\s]+/).map(t => t.trim().toUpperCase()).filter(Boolean).slice(0, 3);
    if (tickers.length < 2) return;
    setCompareState({ status: "loading", results: [] });
    try {
      const res = await fetch(`http://localhost:8000/compare?tickers=${tickers.join(",")}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setCompareState({ status: "done", results: json.results ?? [] });
    } catch (e: any) {
      setCompareState({ status: "error", results: [], error: e.message });
    }
  };

  const handleWatchlistSelect = (symbol: string) => {
    setTicker(symbol);
    analyze(symbol);
  };

  const handleToggleWatchlist = () => {
    if (!dataReady?.ticker) return;
    if (watchlist.has(dataReady.ticker)) {
      watchlist.remove(dataReady.ticker);
    } else {
      watchlist.add(dataReady.ticker, dataReady.name);
    }
  };

  const inWatchlist = dataReady ? watchlist.has(dataReady.ticker) : false;

  return (
    <>
      <style>{`
        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(16px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes badgePop {
          0%   { opacity: 0; transform: scale(0.6); }
          70%  { transform: scale(1.08); }
          100% { opacity: 1; transform: scale(1); }
        }
        @keyframes verdictReveal {
          0%   { opacity: 0; transform: translateY(12px) scale(0.97); }
          60%  { transform: translateY(-2px) scale(1.01); }
          100% { opacity: 1; transform: translateY(0) scale(1); }
        }
      `}</style>

      {/* Root layout: sidebar + main */}
      <div className="flex min-h-screen gap-4 p-4 md:p-6 max-w-[1600px] mx-auto">

        {/* ── Mobile sidebar backdrop overlay ── */}
        {!sidebarCollapsed && (
          <div
            className="fixed inset-0 z-30 bg-black/60 md:hidden"
            onClick={() => setSidebarCollapsed(true)}
            aria-hidden="true"
          />
        )}

        {/* ── Sidebar ── */}
        {/* Desktop: takes space in the flex row. Mobile: fixed left drawer overlay */}
        <aside
          className={`
            flex-shrink-0 flex flex-col transition-all duration-300
            md:relative md:top-auto md:left-auto md:z-auto md:translate-x-0
            fixed top-0 left-0 z-40 h-full
            ${sidebarCollapsed
              ? "w-10 -translate-x-full md:translate-x-0"
              : "w-60 translate-x-0"
            }
          `}
          style={{ minHeight: "100vh" }}
        >
          <div className="glass-card border-[#30363d] flex flex-col h-full overflow-hidden">
            {/* Collapsed state on desktop: show a sliver with expand button */}
            {sidebarCollapsed ? (
              <button
                onClick={() => setSidebarCollapsed(false)}
                className="hidden md:flex flex-1 flex-col items-center justify-center gap-4 text-gray-600 hover:text-[#d4af37] transition-colors"
                title="Expand sidebar"
              >
                <ChevronRight size={14} />
              </button>
            ) : (
              <>
                {/* Tab bar */}
                <div className="flex border-b border-[#30363d]">
                  <button
                    onClick={() => setSidebarTab("watchlist")}
                    className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 text-[9px] font-black uppercase tracking-widest transition-colors border-b-2 ${sidebarTab === "watchlist"
                      ? "border-[#d4af37] text-[#d4af37]"
                      : "border-transparent text-gray-600 hover:text-gray-400"
                      }`}
                  >
                    <BookMarked size={10} />
                    Watch
                    {watchlist.items.length > 0 && (
                      <span className="bg-[#30363d] text-gray-400 rounded-full px-1 text-[8px] font-mono">
                        {watchlist.items.length}
                      </span>
                    )}
                  </button>
                  <button
                    onClick={() => setSidebarTab("history")}
                    className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 text-[9px] font-black uppercase tracking-widest transition-colors border-b-2 ${sidebarTab === "history"
                      ? "border-[#d4af37] text-[#d4af37]"
                      : "border-transparent text-gray-600 hover:text-gray-400"
                      }`}
                  >
                    <History size={10} />
                    History
                    {history.entries.length > 0 && (
                      <span className="bg-[#30363d] text-gray-400 rounded-full px-1 text-[8px] font-mono">
                        {history.entries.length}
                      </span>
                    )}
                  </button>
                  <button
                    onClick={() => setSidebarCollapsed(true)}
                    className="px-2 text-gray-700 hover:text-gray-400 transition-colors"
                    title="Collapse sidebar"
                  >
                    <ChevronLeft size={12} />
                  </button>
                </div>

                {/* Tab content */}
                <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
                  {sidebarTab === "watchlist" ? (
                    <WatchlistSidebar
                      items={watchlist.items}
                      collapsed={false}
                      onToggle={() => setSidebarCollapsed(true)}
                      onSelect={handleWatchlistSelect}
                      onRemove={watchlist.remove}
                      activeTicker={dataReady?.ticker}
                    />
                  ) : (
                    <HistoryPanel
                      entries={history.entries}
                      onSelect={handleWatchlistSelect}
                      onRemove={history.removeById}
                      onClear={history.clear}
                    />
                  )}
                </div>
              </>
            )}
          </div>
        </aside>

        {/* ── Main Content ── */}
        <main className="flex-1 min-w-0 flex flex-col gap-6">

          {/* Header */}
          <header className="flex flex-col md:flex-row justify-between items-center gap-4">
            <div className="flex items-center gap-3">
              {/* Hamburger — only visible on mobile */}
              <button
                id="mobile-sidebar-btn"
                className="md:hidden p-2 rounded-lg border border-[#30363d] text-gray-500 hover:text-[#d4af37] hover:border-[#d4af37]/40 transition-colors"
                onClick={() => setSidebarCollapsed((v) => !v)}
                title="Toggle sidebar"
              >
                <Menu size={18} />
              </button>
              <div className="bg-[#d4af37] p-2 rounded-lg">
                <TrendingUp size={28} className="text-black" />
              </div>
              <h1 className="text-3xl font-black gold-gradient tracking-tighter">365 ADVISERS</h1>
            </div>

            <div className="flex gap-2 w-full md:w-auto items-center">
              <div className="relative flex-1 md:w-64">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" size={16} />
                <input
                  type="text"
                  id="ticker-input"
                  placeholder="Ticker (e.g. NVDA)"
                  className="w-full bg-[#161b22] border border-[#30363d] pl-9 pr-4 py-2.5 rounded-xl text-sm focus:outline-none focus:border-[#d4af37] transition-all"
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value.toUpperCase())}
                  onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
                />
              </div>

              <button
                id="analyze-btn"
                onClick={() => handleAnalyze()}
                disabled={isLoading}
                className="bg-[#d4af37] text-black font-bold px-6 py-2.5 rounded-xl hover:bg-[#f9e29c] transition-all disabled:opacity-50 flex items-center gap-2 text-sm"
              >
                {isLoading ? (
                  <><Loader2 className="animate-spin" size={16} /><span>Analyzing...</span></>
                ) : (
                  <><Zap size={16} /><span>Analyze</span></>
                )}
              </button>

              {/* Cache badge + Force Refresh */}
              {fromCache && dataReady?.ticker && (
                <>
                  <CacheBadge cachedAt={cachedAt} />
                  <button
                    id="force-refresh-btn"
                    onClick={() => forceRefresh(dataReady.ticker)}
                    disabled={isLoading}
                    title="Force fresh analysis (bypass cache)"
                    className="p-2.5 rounded-xl border bg-[#161b22] border-[#30363d] text-gray-500 hover:border-[#d4af37]/40 hover:text-[#d4af37] transition-all disabled:opacity-40"
                  >
                    <RefreshCw size={14} />
                  </button>
                </>
              )}

              {/* Export PDF — Pro gated */}
              {status === "complete" && dataReady && (
                <button
                  id="export-pdf-btn"
                  onClick={() => setShowProGate(true)}
                  title="Download analysis as PDF (Pro)"
                  className="p-2.5 rounded-xl border bg-[#161b22] border-[#30363d] text-gray-500 hover:border-[#d4af37]/40 hover:text-[#d4af37] transition-all relative"
                >
                  <Download size={14} />
                  <span className="absolute -top-1 -right-1 w-3 h-3 bg-[#d4af37] rounded-full flex items-center justify-center text-[6px] font-black text-black">✦</span>
                </button>
              )}

              {/* Watchlist toggle: only show when there's an active analyzed ticker */}
              {dataReady?.ticker && (
                <button
                  id="watchlist-btn"
                  onClick={handleToggleWatchlist}
                  title={inWatchlist ? "Remove from watchlist" : "Add to watchlist"}
                  className={`p-2.5 rounded-xl border transition-all ${inWatchlist
                    ? "bg-[#d4af37]/10 border-[#d4af37]/40 text-[#d4af37] hover:bg-red-500/10 hover:border-red-500/40 hover:text-red-400"
                    : "bg-[#161b22] border-[#30363d] text-gray-500 hover:border-[#d4af37]/40 hover:text-[#d4af37]"
                    }`}
                >
                  {inWatchlist ? <Star size={16} fill="currentColor" /> : <Star size={16} />}
                </button>
              )}

              {/* Compare mode toggle */}
              <button
                id="compare-btn"
                onClick={() => { setCompareMode((v) => !v); }}
                title={compareMode ? "Exit compare mode" : "Compare up to 3 tickers"}
                className={`p-2.5 rounded-xl border transition-all ${compareMode
                  ? "bg-purple-500/10 border-purple-500/40 text-purple-400"
                  : "bg-[#161b22] border-[#30363d] text-gray-500 hover:border-purple-500/40 hover:text-purple-400"
                  }`}
              >
                <GitCompare size={16} />
              </button>

              {/* Help panel trigger */}
              <button
                id="help-btn"
                onClick={() => setHelpOpen(true)}
                title="Centro de ayuda (Shift + ?)"
                className={`p-2.5 rounded-xl border transition-all ${helpOpen
                  ? "bg-[#d4af37]/10 border-[#d4af37]/40 text-[#d4af37]"
                  : "bg-[#161b22] border-[#30363d] text-gray-500 hover:border-[#d4af37]/40 hover:text-[#d4af37]"
                  }`}
              >
                <HelpCircle size={16} />
              </button>
            </div>
          </header>

          {/* ── Compare Input Panel ── */}
          {compareMode && (
            <div className="glass-card p-4 border-purple-500/30 bg-purple-500/5 flex flex-col sm:flex-row gap-3 items-center" style={{ animation: "fadeSlideIn 0.3s ease both" }}>
              <GitCompare size={16} className="text-purple-400 flex-shrink-0" />
              <div className="flex-1 w-full">
                <input
                  id="compare-input"
                  type="text"
                  placeholder="Enter 2–3 tickers separated by commas, e.g. AAPL, MSFT, NVDA"
                  className="w-full bg-[#161b22] border border-[#30363d] focus:border-purple-500/60 px-4 py-2 rounded-xl text-sm focus:outline-none transition-all font-mono uppercase"
                  value={compareInput}
                  onChange={(e) => setCompareInput(e.target.value.toUpperCase())}
                  onKeyDown={(e) => e.key === "Enter" && handleRunComparison()}
                />
              </div>
              <button
                id="run-comparison-btn"
                onClick={handleRunComparison}
                disabled={compareState.status === "loading"}
                className="bg-purple-600 text-white font-bold px-5 py-2 rounded-xl hover:bg-purple-500 transition-all disabled:opacity-50 flex items-center gap-2 text-sm flex-shrink-0"
              >
                {compareState.status === "loading" ? (
                  <><Loader2 size={14} className="animate-spin" /><span>Comparing...</span></>
                ) : (
                  <><GitCompare size={14} /><span>Compare</span></>
                )}
              </button>
            </div>
          )}

          {/* ── Compare View ── */}
          {compareMode && compareState.status !== "idle" && (
            <CompareView state={compareState} />
          )}

          {/* ── Analysis Mode Tab Bar ── */}
          {!compareMode && (status !== "idle" || technical.state.status !== "idle") && (
            <div className="flex gap-1 p-1 glass-card border-[#30363d] rounded-xl w-full md:w-fit overflow-x-auto">
              <button
                onClick={() => setMainTab("fundamental")}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-black uppercase tracking-widest transition-all ${mainTab === "fundamental"
                  ? "bg-[#d4af37] text-black"
                  : "text-gray-500 hover:text-[#d4af37]"
                  }`}
              >
                <ShieldCheck size={12} />
                Fundamental
              </button>
              <button
                onClick={() => setMainTab("technical")}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-black uppercase tracking-widest transition-all ${mainTab === "technical"
                  ? "bg-[#d4af37] text-black"
                  : "text-gray-500 hover:text-[#d4af37]"
                  }`}
              >
                <LineChart size={12} />
                Technical
                {technical.state.status === "loading" && (
                  <Loader2 size={10} className="animate-spin" />
                )}
                {technical.state.status === "done" && (
                  <span className="bg-[#d4af37]/20 text-[#d4af37] rounded px-1 text-[8px] font-mono">
                    {technical.state.data?.summary.technical_score.toFixed(1)}
                  </span>
                )}
              </button>
              <button
                onClick={() => setMainTab("combined")}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-black uppercase tracking-widest transition-all ${mainTab === "combined"
                  ? "bg-[#d4af37] text-black"
                  : "text-gray-500 hover:text-[#d4af37]"
                  }`}
              >
                <Zap size={12} />
                Combined
                {(combined.state.status === "fetching_data" || combined.state.status === "fundamental" || combined.state.status === "technical") && (
                  <Loader2 size={10} className="animate-spin" />
                )}
                {combined.state.status === "complete" && combined.state.committee && (
                  <span className="bg-[#d4af37]/20 text-[#d4af37] rounded px-1 text-[8px] font-mono">
                    {(((combined.state.committee.score ?? 0) + (combined.state.technical?.summary?.technical_score ?? 0)) / 2).toFixed(1)}
                  </span>
                )}
              </button>
            </div>
          )}


          {/* ── Print-only Report Header (hidden on screen) ── */}
          {dataReady && (
            <ReportHeader
              ticker={dataReady.ticker}
              name={dataReady.name}
              price={typeof dataReady.fundamental_metrics?.price === "number" ? dataReady.fundamental_metrics.price as number : undefined}
            />
          )}

          {/* \u2500\u2500 Smart Empty State \u2500\u2500 */}
          {status === "idle" && !compareMode && (
            <div className="flex flex-col flex-1" style={{ animation: "fadeSlideIn 0.4s ease both" }}>

              {watchlist.items.length > 0 ? (
                /* \u2500\u2500 Watchlist Quick-Access Dashboard */
                <div className="space-y-5">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-base font-black uppercase tracking-widest text-gray-300">Coverage List</h2>
                      <p className="text-xs text-gray-600 mt-0.5">Select an asset to convene the Investment Committee</p>
                    </div>
                    <span className="text-[9px] font-mono text-gray-700 bg-[#161b22] border border-[#30363d] rounded-lg px-2 py-1">
                      {watchlist.items.length} asset{watchlist.items.length !== 1 ? "s" : ""} tracked
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {watchlist.items.map((item, i) => {
                      const sig = item.lastSignal ?? "—";
                      const sigColor =
                        sig === "BUY" ? "text-green-400 border-green-500/30 bg-green-500/8" :
                          sig === "SELL" ? "text-red-400 border-red-500/30 bg-red-500/8" :
                            sig === "HOLD" ? "text-yellow-400 border-yellow-500/30 bg-yellow-500/8" :
                              "text-gray-500 border-[#30363d] bg-transparent";

                      return (
                        <button
                          key={item.ticker}
                          onClick={() => handleAnalyze(item.ticker)}
                          className="glass-card p-5 border-[#30363d] text-left hover:border-[#d4af37]/40 hover:bg-[#d4af37]/3 transition-all group"
                          style={{ animation: `fadeSlideIn 0.35s ease ${i * 0.07}s both` }}
                        >
                          <div className="flex items-start justify-between mb-3">
                            <div>
                              <p className="text-lg font-black tracking-tight text-white">{item.ticker}</p>
                              <p className="text-[10px] text-gray-600 truncate max-w-[140px]">{item.name ?? item.ticker}</p>
                            </div>
                            {sig !== "—" && (
                              <span className={`text-[9px] font-black px-2 py-1 rounded-md border uppercase flex-shrink-0 ${sigColor}`}>
                                {sig}
                              </span>
                            )}
                          </div>

                          {item.addedAt && (
                            <p className="text-[8px] text-gray-700 mb-3">
                              Last analyzed: {new Date(item.addedAt).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                            </p>
                          )}

                          <div className="flex items-center gap-1.5 text-[9px] font-black uppercase tracking-wider text-gray-600 group-hover:text-[#d4af37] transition-colors">
                            <Zap size={10} />
                            Run Committee
                          </div>
                        </button>
                      );
                    })}

                    {/* "+" add new card */}
                    <div className="glass-card p-5 border-[#30363d] border-dashed flex flex-col items-center justify-center gap-2 text-gray-700 min-h-[110px]">
                      <Search size={18} className="opacity-40" />
                      <p className="text-[10px] font-bold uppercase tracking-widest opacity-50">Analyze new asset</p>
                      <p className="text-[8px] text-gray-700 opacity-40">Type a ticker in the search bar</p>
                    </div>
                  </div>

                  {/* capability pills */}
                  <div className="flex gap-3 flex-wrap text-[8px] font-mono text-gray-700 pt-1">
                    <span className="flex items-center gap-1"><ShieldCheck size={9} /> Fundamental</span>
                    <span className="flex items-center gap-1"><LineChart size={9} /> Technical</span>
                    <span className="flex items-center gap-1"><Zap size={9} /> Combined</span>
                    <span className="flex items-center gap-1"><Star size={9} /> Watchlist</span>
                    <span className="flex items-center gap-1"><History size={9} /> History</span>
                  </div>
                </div>

              ) : (
                /* \u2500\u2500 Pristine empty state (no watchlist) */
                <div className="flex flex-col items-center justify-center flex-1 text-center">
                  <div className="w-20 h-20 bg-[#161b22] rounded-3xl flex items-center justify-center mb-6 border border-[#30363d]">
                    <Activity size={40} className="text-[#d4af37]/20" />
                  </div>
                  <h2 className="text-xl font-bold mb-3">Investment Analysis Engine</h2>
                  <p className="text-gray-500 max-w-sm mx-auto leading-relaxed text-sm">
                    Select an asset to convene the Investment Committee — fundamental, technical, and combined in one report.
                  </p>
                  <div className="mt-6 flex gap-4 text-xs font-mono text-gray-600 flex-wrap justify-center">
                    <span className="flex items-center gap-1"><ShieldCheck size={12} /> Fundamental</span>
                    <span className="flex items-center gap-1"><LineChart size={12} /> Technical</span>
                    <span className="flex items-center gap-1"><Zap size={12} /> Combined</span>
                    <span className="flex items-center gap-1"><Star size={12} /> Watchlist</span>
                  </div>
                </div>
              )}
            </div>
          )}


          {/* ── Error State ── */}
          {status === "error" && (
            <div className="flex flex-col items-center justify-center flex-1">
              <AlertCircle size={40} className="text-red-500 mb-3" />
              <p className="text-red-400 font-mono text-sm">{error}</p>
            </div>
          )}

          {/* ── Fetching State ── */}
          {status === "fetching_data" && (
            <div className="flex flex-col items-center justify-center flex-1">
              <div className="relative">
                <div className="w-16 h-16 border-4 border-[#d4af37]/20 border-t-[#d4af37] rounded-full animate-spin" />
                <Activity className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-[#d4af37]" size={20} />
              </div>
              <p className="mt-5 text-[#d4af37] font-bold animate-pulse tracking-widest text-sm uppercase">
                Fetching Market Data for {state.ticker}...
              </p>
            </div>
          )}

          {/* ── Live Dashboard (Fundamental tab) ── */}
          {mainTab === "fundamental" && (status === "analyzing" || status === "complete") && dataReady && (
            <div className="space-y-6">
              <ProgressBar completed={agentCount} total={TOTAL_AGENTS} status={status} />

              {/* New: Research Memo (Phase 3 Fundamental Engine) */}
              {(fundamental.state.status === "analyzing" ||
                fundamental.state.status === "complete" ||
                fundamental.state.dataReady) && (
                  <ResearchMemoCard
                    dataReady={fundamental.state.dataReady}
                    agentMemos={fundamental.state.agentMemos}
                    committee={fundamental.state.committee}
                    researchMemo={fundamental.state.researchMemo}
                    agentCount={fundamental.state.agentMemos.length}
                    totalAgents={4}
                    status={fundamental.state.status}
                  />
                )}

              {/* Charts ─ collapsible accordion */}
              <div className="border border-[#30363d]/60 rounded-xl overflow-hidden">
                <button
                  onClick={() => setChartsOpen(v => !v)}
                  className="w-full flex items-center gap-2 px-4 py-3 text-left hover:bg-white/5 transition-colors"
                >
                  <ChevronRight size={13} className={`text-gray-600 transition-transform duration-200 ${chartsOpen ? "rotate-90" : ""}`} />
                  <LineChart size={13} className="text-gray-600" />
                  <span className="text-xs font-black uppercase tracking-widest text-gray-600">Charts</span>
                  <span className="ml-1 text-[9px] font-mono bg-[#30363d]/80 text-gray-500 rounded px-1.5 py-0.5">TradingView · Cash Flow</span>
                  <ChevronRight size={10} className={`ml-auto text-gray-700 transition-transform duration-200 ${chartsOpen ? "rotate-90" : ""}`} />
                </button>
                {chartsOpen && (
                  <div className="px-4 pb-4 pt-1 border-t border-[#30363d]/40 space-y-4">
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                      <section className="lg:col-span-2 glass-card p-6 border-[#30363d]">
                        <div className="flex justify-between items-center mb-4">
                          <h3 className="text-sm font-bold uppercase tracking-widest text-gray-400">Advanced TradingView Chart</h3>
                          <span className="text-xs text-[#d4af37] font-mono">{dataReady.ticker} | Real-Time</span>
                        </div>
                        <TradingViewChart symbol={dataReady.ticker} />
                      </section>

                      <section className="glass-card p-6 border-[#d4af37]/30 bg-[#d4af37]/5 flex flex-col">
                        <div className="flex items-center gap-2 mb-4 text-[#d4af37]">
                          <ShieldCheck size={18} />
                          <h2 className="text-sm uppercase tracking-[0.2em] font-black">Veredicto Dalio</h2>
                        </div>
                        {dalio ? (
                          <div className="flex-1 overflow-y-auto custom-scrollbar">
                            <p className="text-lg leading-relaxed font-black gold-gradient italic mb-4" style={{ animation: "fadeSlideIn 0.5s ease both" }}>
                              "{dalio.final_verdict}"
                            </p>
                            {dalio.dalio_response?.summary_table && (
                              <div className="prose prose-invert prose-xs max-w-none bg-black/20 p-4 rounded-lg">
                                <div dangerouslySetInnerHTML={{ __html: dalio.dalio_response.summary_table.replace(/\n/g, "<br/>") }} />
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="flex-1 flex flex-col items-center justify-center gap-3 opacity-40">
                            <Loader2 size={24} className="text-[#d4af37] animate-spin" />
                            <span className="text-xs text-gray-500 uppercase tracking-widest text-center">Waiting for all 8 minds...</span>
                          </div>
                        )}
                        <div className="mt-4 pt-4 border-t border-[#d4af37]/20 flex justify-between items-center">
                          <span className="text-xs text-gray-500 uppercase">Decision Orchestrator</span>
                          <span className="text-[#d4af37] font-mono text-sm">Gemini 2.5 Pro</span>
                        </div>
                      </section>
                    </div>
                  </div>
                )}
              </div>

              {/* Fundamental Engine & TV Technical */}
              <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                <div className="lg:col-span-3 space-y-4">
                  <div className="flex items-center gap-2">
                    <ShieldCheck size={16} className="text-[#d4af37]" />
                    <h3 className="text-sm font-bold uppercase tracking-widest text-gray-400">Motor Fundamental Determinístico</h3>
                  </div>
                  <FundamentalTable engine={dataReady.fundamental_metrics} />
                </div>
                <div className="space-y-4">
                  <div className="flex items-center gap-2">
                    <TrendingUp size={16} className="text-[#d4af37]" />
                    <h3 className="text-sm font-bold uppercase tracking-widest text-gray-400">TV Validation</h3>
                  </div>
                  <div className="glass-card p-6 border-[#30363d] bg-[#0d1117]/40">
                    <TradingViewTechnicalWidget symbol={dataReady.ticker} />
                  </div>
                </div>
              </div>

              {/* Cash Flow */}
              <section className="glass-card p-6 border-[#30363d]">
                <div className="flex items-center gap-2 mb-4">
                  <BarChart3 size={16} className="text-[#d4af37]" />
                  <h3 className="text-sm font-bold uppercase tracking-widest text-gray-400">Flujo de Caja vs Ingresos</h3>
                </div>
                <CashFlowChart data={[]} />
              </section>

              {/* 8-Agent Legacy Grid — collapsible, hidden by default */}
              <div className="border border-[#30363d]/60 rounded-xl overflow-hidden">
                <button
                  onClick={() => setLegacyGridOpen((v) => !v)}
                  className="w-full flex items-center gap-2 px-4 py-3 text-left hover:bg-white/5 transition-colors"
                >
                  <ChevronRight
                    size={14}
                    className={`text-gray-600 transition-transform duration-200 ${legacyGridOpen ? "rotate-90" : ""}`}
                  />
                  <Activity size={13} className="text-gray-600" />
                  <span className="text-xs font-black uppercase tracking-widest text-gray-600">Raw Agent Output</span>
                  <span className="ml-1 text-[9px] font-mono bg-[#30363d]/80 text-gray-500 rounded px-1.5 py-0.5">LEGACY · {agentCount}/{TOTAL_AGENTS}</span>
                  <ChevronRight
                    size={12}
                    className={`ml-auto text-gray-700 transition-transform duration-200 ${legacyGridOpen ? "rotate-90" : ""}`}
                  />
                </button>
                {legacyGridOpen && (
                  <div className="px-4 pb-4 pt-1 border-t border-[#30363d]/40">
                    <p className="text-[10px] text-gray-600 mb-4 italic">
                      Individual agent outputs from the v1 pipeline. The Committee Verdict above synthesizes these into an actionable signal.
                    </p>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                      {agents.map((agent, i) => <AgentCard key={agent.agent_name} agent={agent} index={i} />)}
                      {showSkeletons && pendingSlots.map((name) => <AgentSkeletonCard key={name} label={name} />)}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ── Technical Dashboard ── */}
          {mainTab === "technical" && (
            <div style={{ animation: "fadeSlideIn 0.3s ease both" }}>
              {/* Loading */}
              {technical.state.status === "loading" && (
                <div className="flex flex-col items-center justify-center py-24">
                  <div className="relative mb-6">
                    <div className="w-16 h-16 border-4 border-[#d4af37]/20 border-t-[#d4af37] rounded-full animate-spin" />
                    <Activity className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-[#d4af37]" size={20} />
                  </div>
                  <p className="text-[#d4af37] font-bold tracking-widest text-sm uppercase animate-pulse">
                    Running Technical Engine...
                  </p>
                  <p className="text-gray-600 text-xs mt-2">RSI · MACD · Bollinger Bands · ATR · OBV · Support/Resistance</p>
                </div>
              )}

              {/* Error */}
              {technical.state.status === "error" && (
                <div className="flex flex-col items-center justify-center py-20">
                  <AlertCircle size={36} className="text-red-500 mb-3" />
                  <p className="text-red-400 font-mono text-sm">{technical.state.error}</p>
                  <button
                    onClick={() => technical.forceRefresh(state.ticker ?? "")}
                    className="mt-4 text-xs text-gray-500 hover:text-[#d4af37] flex items-center gap-1 transition-colors"
                  >
                    <RefreshCw size={11} /> Retry
                  </button>
                </div>
              )}

              {/* Result */}
              {technical.state.status === "done" && technical.state.data && (
                <div className="space-y-5">
                  {/* ── Technical Digest (Natural Language Narrative) ── */}
                  {(() => {
                    const s = technical.state.data.summary;
                    const ind = technical.state.data.indicators;
                    const score = s.technical_score;
                    const scoreLabel = score >= 7 ? "bullish" : score >= 5 ? "neutral" : "bearish";
                    const rsi = ind.momentum.rsi.toFixed(0);
                    const rsiNote = ind.momentum.rsi_zone === "OVERBOUGHT"
                      ? `RSI at ${rsi} signals overbought conditions — upside momentum may be exhausting`
                      : ind.momentum.rsi_zone === "OVERSOLD"
                        ? `RSI at ${rsi} is in oversold territory — a mean-reversion bounce is possible`
                        : `RSI at ${rsi} is in neutral territory`;
                    const macdNote = ind.trend.macd_crossover === "BULLISH"
                      ? "MACD is showing a bullish crossover" : ind.trend.macd_crossover === "BEARISH"
                        ? "MACD has turned bearish" : "MACD is flat";
                    const trendNote = ind.trend.price_vs_sma50 === "ABOVE"
                      ? "price is trading above the 50-day SMA"
                      : ind.trend.price_vs_sma50 === "BELOW"
                        ? "price has slipped below the 50-day SMA"
                        : "price is testing the 50-day SMA";
                    const volumeNote = ind.volume.obv_trend === "RISING"
                      ? "Volume is confirming the move (OBV rising)"
                      : ind.volume.obv_trend === "FALLING"
                        ? "Volume is diverging bearishly (OBV declining)"
                        : "Volume is neutral";
                    const signalColor = s.signal === "STRONG_BUY" || s.signal === "BUY" ? "text-green-400"
                      : s.signal === "STRONG_SELL" || s.signal === "SELL" ? "text-red-400"
                        : "text-yellow-400";
                    const signalLabel = s.signal.replace("_", " ");

                    return (
                      <div className="glass-card p-5 border-[#30363d]" style={{ animation: "fadeSlideIn 0.4s ease both" }}>
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-2">
                            <LineChart size={14} className="text-[#d4af37]" />
                            <h3 className="text-[9px] font-black uppercase tracking-[0.2em] text-gray-500">Technical Digest</h3>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className={`text-[9px] font-black uppercase tracking-widest ${signalColor}`}>{signalLabel}</span>
                            <span className="text-[8px] font-mono bg-[#161b22] border border-[#30363d] rounded px-1.5 py-0.5 text-gray-500">{score.toFixed(1)}/10</span>
                          </div>
                        </div>
                        <p className="text-[11px] text-gray-300 leading-relaxed">
                          The technical picture for this asset is <span className={`font-bold ${signalColor}`}>{scoreLabel}</span>. {rsiNote}; {macdNote}, and {trendNote}. {volumeNote}.
                          {ind.structure.breakout_probability > 0.5 && (
                            <> A <span className={ind.structure.breakout_direction === "BULLISH" ? "text-green-400" : "text-red-400"}>potential {ind.structure.breakout_direction.toLowerCase()} breakout</span> is developing with {(ind.structure.breakout_probability * 100).toFixed(0)}% probability.</>)
                          }
                        </p>
                        <div className="mt-3 pt-3 border-t border-[#30363d]/40 flex gap-4 flex-wrap">
                          {([
                            ["Trend", s.subscores.trend],
                            ["Momentum", s.subscores.momentum],
                            ["Volatility", s.subscores.volatility],
                            ["Volume", s.subscores.volume],
                            ["Structure", s.subscores.structure],
                          ] as [string, number][]).map(([label, val]) => (
                            <div key={label} className="flex flex-col items-center gap-0.5">
                              <span className="text-[7px] text-gray-600 uppercase tracking-widest">{label}</span>
                              <span className={`text-[10px] font-black ${val >= 7 ? "text-green-400" : val >= 5 ? "text-[#d4af37]" : "text-red-400"
                                }`}>{val.toFixed(1)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  })()}

                  <IndicatorGrid data={technical.state.data} />
                </div>
              )}

              {/* Prompt to analyze first */}
              {technical.state.status === "idle" && (
                <div className="flex flex-col items-center justify-center py-20 text-center">
                  <div className="w-16 h-16 bg-[#161b22] rounded-3xl flex items-center justify-center mb-4 border border-[#30363d]">
                    <LineChart size={28} className="text-[#d4af37]/30" />
                  </div>
                  <p className="text-gray-500 text-sm font-bold">Select an asset to run the Technical Engine</p>
                  <p className="text-gray-700 text-[10px] mt-1">RSI · MACD · Bollinger Bands · ATR · OBV · Support/Resistance</p>
                </div>
              )}
            </div>
          )}

          {/* ── Combined Dashboard (Phase 5) ── */}
          {mainTab === "combined" && (
            <div style={{ animation: "fadeSlideIn 0.3s ease both" }}>
              {combined.state.status === "idle" && (
                <div className="flex flex-col items-center justify-center py-20 text-center">
                  <div className="w-16 h-16 bg-[#161b22] rounded-3xl flex items-center justify-center mb-4 border border-[#30363d]">
                    <Zap size={28} className="text-[#d4af37]/30" />
                  </div>
                  <p className="text-gray-600 text-sm">Enter a ticker to activate the Combined Engine.</p>
                  <p className="text-gray-700 text-xs mt-1">Runs Fundamental + Technical simultaneously.</p>
                </div>
              )}

              {combined.state.status === "error" && (
                <div className="flex flex-col items-center justify-center py-20 text-center">
                  <AlertCircle size={36} className="text-red-500 mb-3" />
                  <p className="text-red-400 font-mono text-sm">{combined.state.error}</p>
                  <button
                    onClick={() => combined.forceRefresh(state.ticker ?? ticker)}
                    className="mt-4 text-xs text-gray-500 hover:text-[#d4af37] flex items-center gap-1 transition-colors"
                  >
                    <RefreshCw size={11} /> Retry
                  </button>
                </div>
              )}

              {combined.state.status !== "idle" && combined.state.status !== "error" && (
                <CombinedDashboard
                  state={combined.state}
                  onForceRefresh={() => {
                    const sym = state.ticker ?? ticker;
                    if (!sym) return;
                    combined.forceRefresh(sym);
                    fundamental.forceRefresh(sym);
                    technical.forceRefresh(sym);
                  }}
                />
              )}
            </div>
          )}
        </main>

      </div>

      {/* ── Help Panel ── */}
      <HelpPanel open={helpOpen} onClose={() => setHelpOpen(false)} />

      {/* ── Pro Gate Modal (M16) ── */}
      {showProGate && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4"
          style={{ backgroundColor: "rgba(0,0,0,0.75)", backdropFilter: "blur(6px)" }}
          onClick={() => setShowProGate(false)}
        >
          <div
            className="relative bg-[#0d1117] border border-[#d4af37]/30 rounded-2xl p-8 max-w-sm w-full shadow-2xl text-center"
            style={{ animation: "verdictReveal 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) both" }}
            onClick={(e) => e.stopPropagation()}
          >
            <button onClick={() => setShowProGate(false)} className="absolute top-4 right-4 text-gray-600 hover:text-gray-400 transition-colors">
              <X size={14} />
            </button>
            <div className="w-12 h-12 bg-[#d4af37]/10 border border-[#d4af37]/30 rounded-2xl flex items-center justify-center mx-auto mb-4">
              <Download size={20} className="text-[#d4af37]" />
            </div>
            <span className="inline-block text-[7px] font-black uppercase tracking-widest bg-[#d4af37]/10 border border-[#d4af37]/25 text-[#d4af37]/80 rounded-full px-2.5 py-1 mb-3">
              ✦ Pro Feature
            </span>
            <h2 className="text-base font-black text-white mb-2">Export Institutional Report</h2>
            <p className="text-[11px] text-gray-500 leading-relaxed mb-5">
              Download a full-format PDF with the Committee Verdict, analyst memos, technical analysis, and key catalysts — branded for institutional distribution.
            </p>
            <button
              onClick={() => { setShowProGate(false); window.print(); }}
              className="w-full bg-[#d4af37] text-black font-black text-sm py-2.5 rounded-xl hover:bg-[#f9e29c] transition-all mb-2"
            >
              Continue with Print Preview
            </button>
            <p className="text-[8px] text-gray-700">Full PDF export available in Pro · Coming soon</p>
          </div>
        </div>
      )}

      {/* ── Onboarding Overlay (M17) — first visit only ── */}
      {showOnboarding && <OnboardingOverlay onDone={dismissOnboarding} />}
    </>
  );
}
