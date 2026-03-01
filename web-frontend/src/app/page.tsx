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
} from "lucide-react";



import { useAnalysisStream, AgentSignal } from "@/hooks/useAnalysisStream";
import { useWatchlist, WatchlistItem } from "@/hooks/useWatchlist";
import CompareView, { CompareState } from "@/components/CompareView";
import ReportHeader from "@/components/ReportHeader";
import HistoryPanel from "@/components/HistoryPanel";
import { useAnalysisHistory } from "@/hooks/useAnalysisHistory";




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
                        <p className="text-[9px] text-gray-500 truncate">{item.name}</p>
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

  // Compare mode state
  const [compareMode, setCompareMode] = useState(false);
  const [compareInput, setCompareInput] = useState("");
  const [compareState, setCompareState] = useState<CompareState>({ status: "idle", results: [] });

  const [sidebarTab, setSidebarTab] = useState<"watchlist" | "history">("watchlist");

  const { state, analyze, forceRefresh, TOTAL_AGENTS } = useAnalysisStream();
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
      watchlist.updateSignal(dataReady.ticker, derivedSignal);
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
    if (compareMode) setCompareMode(false); // switch to single mode
    analyze(t);
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
      `}</style>

      {/* Root layout: sidebar + main */}
      <div className="flex min-h-screen gap-4 p-4 md:p-6 max-w-[1600px] mx-auto">

        {/* ── Sidebar ── */}
        <aside
          className={`flex-shrink-0 flex flex-col transition-all duration-300 ${sidebarCollapsed ? "w-10" : "w-60"
            }`}
          style={{ minHeight: "100vh" }}
        >
          <div className="glass-card border-[#30363d] flex flex-col h-full overflow-hidden">
            {sidebarCollapsed ? (
              /* Collapsed state: just a sliver with expand button */
              <button
                onClick={() => setSidebarCollapsed(false)}
                className="flex-1 flex flex-col items-center justify-center gap-4 text-gray-600 hover:text-[#d4af37] transition-colors"
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
                      hideSidebarShell
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

              {/* Export PDF — show only when analysis complete */}
              {status === "complete" && dataReady && (
                <button
                  id="export-pdf-btn"
                  onClick={() => window.print()}
                  title="Download analysis as PDF"
                  className="p-2.5 rounded-xl border bg-[#161b22] border-[#30363d] text-gray-500 hover:border-[#d4af37]/40 hover:text-[#d4af37] transition-all"
                >
                  <Download size={14} />
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

          {/* ── Print-only Report Header (hidden on screen) ── */}
          {dataReady && (
            <ReportHeader
              ticker={dataReady.ticker}
              name={dataReady.name}
              price={typeof dataReady.fundamental_metrics?.price === "number" ? dataReady.fundamental_metrics.price as number : undefined}
            />
          )}

          {/* ── Empty State ── */}
          {status === "idle" && !compareMode && (

            <div className="flex flex-col items-center justify-center flex-1 text-center">
              <div className="w-20 h-20 bg-[#161b22] rounded-3xl flex items-center justify-center mb-6 border border-[#30363d]">
                <Activity size={40} className="text-[#d4af37]/20" />
              </div>
              <h2 className="text-xl font-bold mb-3">Investment Analysis Engine</h2>
              <p className="text-gray-500 max-w-sm mx-auto leading-relaxed text-sm">
                Enter a symbol to activate the 8-agent committee. Save tickers to your watchlist for quick access.
              </p>
              <div className="mt-6 flex gap-4 text-xs font-mono text-gray-600">
                <span className="flex items-center gap-1"><ShieldCheck size={12} /> Fundamental</span>
                <span className="flex items-center gap-1"><Search size={12} /> Web Search</span>
                <span className="flex items-center gap-1"><Star size={12} /> Watchlist</span>
              </div>
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

          {/* ── Live Dashboard ── */}
          {(status === "analyzing" || status === "complete") && dataReady && (
            <div className="space-y-6">
              <ProgressBar completed={agentCount} total={TOTAL_AGENTS} status={status} />

              {/* Charts & Verdict */}
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

              {/* 8-Agent Grid */}
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <Activity size={16} className="text-[#d4af37]" />
                  <h3 className="text-sm font-bold uppercase tracking-widest text-gray-400">Comité de 8 Mentes Maestras</h3>
                  <span className="ml-auto text-xs font-mono text-[#d4af37]">{agentCount} / {TOTAL_AGENTS}</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                  {agents.map((agent, i) => <AgentCard key={agent.agent_name} agent={agent} index={i} />)}
                  {showSkeletons && pendingSlots.map((name) => <AgentSkeletonCard key={name} label={name} />)}
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </>
  );
}
