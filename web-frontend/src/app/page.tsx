"use client";

import { useState, useEffect } from "react";
import { CashFlowChart } from "@/components/Charts";
import TradingViewChart from "@/components/TradingViewChart";
import TradingViewTechnicalWidget from "@/components/TradingViewTechnicalWidget";
import VerdictHero from "@/components/VerdictHero";
import InvestmentStory from "@/components/InvestmentStory";
import AnalyticsAccordion from "@/components/AnalyticsAccordion";
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
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  GitCompare,
  Download,
  History,
  LineChart,
  HelpCircle,
  Lightbulb,
  Menu,
  LayoutGrid,
  List,
  Briefcase,
  Radio,
} from "lucide-react";
import HelpPanel from "@/components/HelpPanel";

import { useAnalysisStream, AgentSignal } from "@/hooks/useAnalysisStream";
import { useWatchlist, WatchlistItem } from "@/hooks/useWatchlist";
import CompareView, { CompareState } from "@/components/CompareView";
import ReportHeader from "@/components/ReportHeader";
import HistoryPanel from "@/components/HistoryPanel";
import IdeasPanel from "@/components/IdeasPanel";
import AlphaSignalsView from "@/components/AlphaSignalsView";
import { useIdeasEngine } from "@/hooks/useIdeasEngine";
import { useAlphaSignals } from "@/hooks/useAlphaSignals";
import { useAnalysisHistory } from "@/hooks/useAnalysisHistory";
import { useTechnicalAnalysis } from "@/hooks/useTechnicalAnalysis";
import IndicatorGrid from "@/components/IndicatorGrid";
import { useFundamentalStream } from "@/hooks/useFundamentalStream";
import ResearchMemoCard from "@/components/ResearchMemoCard";
import OnboardingOverlay, { useOnboarding } from "@/components/OnboardingOverlay";
import { useCombinedStream } from "@/hooks/useCombinedStream";
import CombinedDashboard from "@/components/CombinedDashboard";
import PortfolioDashboard from "@/components/PortfolioDashboard";
import ErrorBoundary from "@/components/ErrorBoundary";



import { CacheBadge, SignalBadge, FundamentalTable, AgentCard, AgentSkeletonCard, ProgressBar, AGENT_ORDER } from "@/components/AnalysisWidgets";

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
  const [viewMode, setViewMode] = useState<"list" | "heatmap">("list");

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
        <div className={`flex items-center gap-2 p-4 border-b border-[#30363d] ${collapsed ? "justify-center" : "justify-between"}`}>
          <div className="flex items-center gap-2">
            <BookMarked size={14} className="text-[#d4af37] flex-shrink-0" />
            {!collapsed && (
              <span className="text-[10px] font-black uppercase tracking-widest text-[#d4af37]">
                Watchlist
              </span>
            )}
          </div>
          {!collapsed && (
            <div className="flex bg-[#161b22] border border-[#30363d] rounded p-0.5">
              <button
                onClick={() => setViewMode("list")}
                className={`p-1 rounded ${viewMode === "list" ? "bg-[#30363d] text-white" : "text-gray-500 hover:text-gray-300"}`}
                title="List View"
              >
                <List size={10} />
              </button>
              <button
                onClick={() => setViewMode("heatmap")}
                className={`p-1 rounded ${viewMode === "heatmap" ? "bg-[#30363d] text-white" : "text-gray-500 hover:text-gray-300"}`}
                title="Heatmap View"
              >
                <LayoutGrid size={10} />
              </button>
            </div>
          )}
        </div>

        {/* List / Heatmap */}
        <div className={`flex-1 overflow-y-auto custom-scrollbar p-2 ${viewMode === "heatmap" && !collapsed ? "grid grid-cols-2 gap-2 content-start" : "flex flex-col gap-0.5"}`}>
          {items.length === 0 && !collapsed ? (
            <div className="col-span-full flex flex-col items-center justify-center h-full px-4 py-8 text-center gap-2">
              <BookMarked size={24} className="text-[#30363d]" />
              <p className="text-[10px] text-gray-600 leading-relaxed">
                Add a ticker with ★ to track it here
              </p>
            </div>
          ) : (
            items.map((item) => {
              const isActive = item.ticker === activeTicker;
              const scoreDelta = (item.lastScore !== undefined && item.prevScore !== undefined) ? item.lastScore - item.prevScore : 0;
              const hasDelta = item.lastScore !== undefined && item.prevScore !== undefined && item.lastScore !== item.prevScore;

              const heatmapBg = !hasDelta ? "bg-[#161b22] border-[#30363d]"
                : scoreDelta > 0 ? "bg-green-500/10 border-green-500/30"
                  : "bg-red-500/10 border-red-500/30";

              if (viewMode === "heatmap" && !collapsed) {
                return (
                  <div
                    key={item.ticker}
                    className={`group relative flex flex-col items-center justify-center p-3 rounded-lg cursor-pointer transition-all border ${heatmapBg} hover:opacity-80`}
                    onClick={() => onSelect(item.ticker)}
                    title={`${item.name} (${item.lastSignal || "No Signal"})`}
                  >
                    <span className={`text-[12px] font-black ${isActive ? "text-[#d4af37]" : "text-gray-200"}`}>
                      {item.ticker}
                    </span>
                    {hasDelta && (
                      <span className={`text-[9px] font-mono font-black mt-1 ${scoreDelta > 0 ? "text-green-400" : "text-red-400"}`}>
                        {scoreDelta > 0 ? "+" : ""}{scoreDelta.toFixed(1)}
                      </span>
                    )}
                  </div>
                );
              }

              return (
                <div
                  key={item.ticker}
                  className={`group relative flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-all ${isActive
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
                          {hasDelta && (
                            <span className={`text-[8px] font-mono font-black flex-shrink-0 ${scoreDelta > 0 ? "text-green-400" : "text-red-400"
                              }`}>
                              {scoreDelta > 0 ? "+" : ""}{scoreDelta.toFixed(1)}
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


// ─── Main Page ───────────────────────────────────────────────────────────────
export default function Home() {
  const [ticker, setTicker] = useState("");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [legacyGridOpen, setLegacyGridOpen] = useState(false);
  const [chartsOpen, setChartsOpen] = useState(false);
  const [showProGate, setShowProGate] = useState(false);
  const { showOnboarding, dismiss: dismissOnboarding } = useOnboarding();

  // Main analysis tab
  const [mainTab, setMainTab] = useState<"analysis" | "portfolio">("analysis");

  // Compare mode state
  const [compareMode, setCompareMode] = useState(false);
  const [compareInput, setCompareInput] = useState("");
  const [compareState, setCompareState] = useState<CompareState>({ status: "idle", results: [] });

  const [sidebarTab, setSidebarTab] = useState<"watchlist" | "history" | "ideas">("watchlist");
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
  const ideasEngine = useIdeasEngine();
  const alphaSignals = useAlphaSignals();

  // Auto-evaluate alpha signals when a combined analysis completes
  useEffect(() => {
    if (combined.state.status === "complete" && combined.state.ticker) {
      alphaSignals.evaluate(combined.state.ticker);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [combined.state.status, combined.state.ticker]);


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

  // Update history + watchlist badge when COMBINED analysis completes
  useEffect(() => {
    if (combined.state.status === "complete" && combined.state.ticker && combined.state.fundamentalDataReady) {
      // derivedSignal uses dalio.final_verdict if legacy, or combined.state.decision.investment_position if combined
      const signalToSave = combined.state.decision?.investment_position ?? derivedSignal ?? "HOLD";
      const scoreToSave = combined.state.committee?.score ?? fundamental.state.committee?.score ?? 0;

      watchlist.updateSignal(
        combined.state.ticker,
        signalToSave,
        scoreToSave
      );

      history.add({
        ticker: combined.state.ticker,
        name: combined.state.fundamentalDataReady.name ?? combined.state.ticker,
        signal: signalToSave,
        agentSummary: combined.state.agentMemos.map((a) => ({
          name: a.agent,
          signal: a.signal,
          confidence: a.conviction ?? 0,
        })),
        dalioVerdict: combined.state.decision?.cio_memo.thesis_summary ?? "",
        fromCache: combined.state.fromCache ?? false,
        // Insert Institutional Data required by the Risk Parity / Portfolio Builder
        fundamental_score: scoreToSave,
        opportunity_score: combined.state.opportunity?.opportunity_score,
        dimensions: combined.state.opportunity?.dimensions,
        position_sizing: combined.state.positionSizing as any,
        sector: combined.state.fundamentalDataReady.sector,
        volatility_atr: combined.state.technical?.indicators?.volatility?.atr_pct,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    combined.state.status,
    combined.state.ticker,
    combined.state.fundamentalDataReady,
    combined.state.decision,
    combined.state.committee,
    combined.state.agentMemos,
    combined.state.fromCache,
    combined.state.opportunity,
    combined.state.positionSizing,
    derivedSignal,
    fundamental.state.committee?.score,
    watchlist.updateSignal,
    history.add,
  ]);


  const handleAnalyze = (symbol?: string) => {
    const t = symbol ?? ticker;
    if (!t.trim()) return;
    if (!symbol) setTicker(t);
    if (compareMode) setCompareMode(false);
    setMainTab("analysis");
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
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setCompareState({ status: "error", results: [], error: msg });
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
                    className={`flex-1 flex items-center justify-center gap-1 py-3 text-[10px] font-black uppercase tracking-wider transition-all border-b-2 ${sidebarTab === "watchlist"
                      ? "border-[#d4af37] text-[#d4af37] shadow-[0_2px_8px_-2px_rgba(212,175,55,0.5)]"
                      : "border-transparent text-gray-600 hover:text-gray-400"
                      }`}
                  >
                    <BookMarked size={11} />
                    Watch
                    {watchlist.items.length > 0 && (
                      <span className="bg-[#30363d] text-gray-400 rounded-full px-1.5 py-0.5 text-[7px] font-mono ml-0.5">
                        {watchlist.items.length}
                      </span>
                    )}
                  </button>
                  <button
                    onClick={() => setSidebarTab("history")}
                    className={`flex-1 flex items-center justify-center gap-1 py-3 text-[10px] font-black uppercase tracking-wider transition-all border-b-2 ${sidebarTab === "history"
                      ? "border-[#d4af37] text-[#d4af37] shadow-[0_2px_8px_-2px_rgba(212,175,55,0.5)]"
                      : "border-transparent text-gray-600 hover:text-gray-400"
                      }`}
                  >
                    <History size={11} />
                    Hist
                    {history.entries.length > 0 && (
                      <span className="bg-[#30363d] text-gray-400 rounded-full px-1.5 py-0.5 text-[7px] font-mono ml-0.5">
                        {history.entries.length}
                      </span>
                    )}
                  </button>
                  <button
                    onClick={() => setSidebarTab("ideas")}
                    className={`flex-1 flex items-center justify-center gap-1 py-3 text-[10px] font-black uppercase tracking-wider transition-all border-b-2 ${sidebarTab === "ideas"
                      ? "border-[#d4af37] text-[#d4af37] shadow-[0_2px_8px_-2px_rgba(212,175,55,0.5)]"
                      : "border-transparent text-gray-600 hover:text-gray-400"
                      }`}
                  >
                    <Lightbulb size={11} />
                    Ideas
                    {ideasEngine.ideas.length > 0 && (
                      <span className="bg-[#d4af37]/20 text-[#d4af37] rounded-full px-1.5 py-0.5 text-[7px] font-mono ml-0.5">
                        {ideasEngine.ideas.length}
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
                  ) : sidebarTab === "history" ? (
                    <HistoryPanel
                      entries={history.entries}
                      onSelect={handleWatchlistSelect}
                      onRemove={history.removeById}
                      onClear={history.clear}
                    />
                  ) : (
                    <IdeasPanel
                      ideas={ideasEngine.ideas}
                      scanStatus={ideasEngine.scanStatus}
                      error={ideasEngine.error}
                      onScan={() => {
                        const tickers = watchlist.items.map((i) => i.ticker);
                        if (tickers.length > 0) ideasEngine.scan(tickers);
                      }}
                      onAnalyze={(t) => handleAnalyze(t)}
                      onDismiss={(id) => ideasEngine.dismiss(id)}
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
          <header className="flex flex-col gap-4">
            <div className="flex flex-col md:flex-row justify-between items-center gap-4">
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
                <div className="relative bg-gradient-to-br from-[#d4af37] to-[#b8962e] p-2.5 rounded-xl glow-ring breathe">
                  <TrendingUp size={26} className="text-black" />
                </div>
                <div>
                  <h1 className="text-3xl font-black gold-gradient tracking-tighter leading-none">365 ADVISERS</h1>
                  <p className="text-[9px] font-mono text-gray-600 uppercase tracking-[0.2em] mt-0.5">Institutional Analysis Engine</p>
                </div>
              </div>

              <div className="flex gap-2 w-full md:w-auto items-center">
                <div className="relative flex-1 md:w-72">
                  <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-500" size={16} />
                  <input
                    type="text"
                    id="ticker-input"
                    placeholder="Ticker (e.g. NVDA)"
                    className="w-full bg-[#161b22] border border-[#30363d] pl-10 pr-4 py-2.5 rounded-2xl text-sm focus:outline-none focus:border-[#d4af37] focus:ring-2 focus:ring-[#d4af37]/15 transition-all placeholder:text-gray-600"
                    value={ticker}
                    onChange={(e) => setTicker(e.target.value.toUpperCase())}
                    onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
                  />
                </div>

                <button
                  id="analyze-btn"
                  onClick={() => handleAnalyze()}
                  disabled={isLoading}
                  className="bg-gradient-to-r from-[#d4af37] to-[#e8c84a] text-black font-bold px-6 py-2.5 rounded-2xl hover:brightness-110 transition-all disabled:opacity-50 flex items-center gap-2 text-sm shadow-[0_0_16px_-4px_rgba(212,175,55,0.3)]"
                >
                  {isLoading ? (
                    <><Loader2 className="animate-spin" size={16} /><span>Analyzing...</span></>
                  ) : (
                    <><Zap size={16} /><span>Analyze</span></>
                  )}
                </button>

                {/* Toolbar icons — grouped */}
                <div className="flex items-center gap-1.5 glass-card px-2 py-1 border-[#30363d] rounded-2xl">
                  {/* Cache badge + Force Refresh */}
                  {fromCache && dataReady?.ticker && (
                    <>
                      <CacheBadge cachedAt={cachedAt} />
                      <button
                        id="force-refresh-btn"
                        onClick={() => forceRefresh(dataReady.ticker)}
                        disabled={isLoading}
                        title="Force fresh analysis (bypass cache)"
                        className="p-2 rounded-xl text-gray-500 hover:text-[#d4af37] hover:bg-[#d4af37]/10 transition-all disabled:opacity-40"
                      >
                        <RefreshCw size={14} />
                      </button>
                    </>
                  )}

                  {/* Export PDF */}
                  {status === "complete" && dataReady && (
                    <button
                      id="export-pdf-btn"
                      onClick={() => {
                        document.body.setAttribute("data-print-date", new Date().toLocaleString());
                        window.print();
                      }}
                      title="Export Executive Memo as PDF"
                      className="p-2 rounded-xl text-gray-500 hover:text-[#d4af37] hover:bg-[#d4af37]/10 transition-all"
                    >
                      <Download size={14} />
                    </button>
                  )}

                  {/* Watchlist toggle */}
                  {dataReady?.ticker && (
                    <button
                      id="watchlist-btn"
                      onClick={handleToggleWatchlist}
                      title={inWatchlist ? "Remove from watchlist" : "Add to watchlist"}
                      className={`p-2 rounded-xl transition-all ${inWatchlist
                        ? "text-[#d4af37] hover:text-red-400"
                        : "text-gray-500 hover:text-[#d4af37] hover:bg-[#d4af37]/10"
                        }`}
                    >
                      {inWatchlist ? <Star size={15} fill="currentColor" /> : <Star size={15} />}
                    </button>
                  )}

                  {/* Compare mode toggle */}
                  <button
                    id="compare-btn"
                    onClick={() => { setCompareMode((v) => !v); }}
                    title={compareMode ? "Exit compare mode" : "Compare up to 3 tickers"}
                    className={`p-2 rounded-xl transition-all ${compareMode
                      ? "text-purple-400 bg-purple-500/10"
                      : "text-gray-500 hover:text-purple-400 hover:bg-purple-500/10"
                      }`}
                  >
                    <GitCompare size={15} />
                  </button>

                  {/* Help panel trigger */}
                  <button
                    id="help-btn"
                    onClick={() => setHelpOpen(true)}
                    title="Centro de ayuda (Shift + ?)"
                    className={`p-2 rounded-xl transition-all ${helpOpen
                      ? "text-[#d4af37] bg-[#d4af37]/10"
                      : "text-gray-500 hover:text-[#d4af37] hover:bg-[#d4af37]/10"
                      }`}
                  >
                    <HelpCircle size={15} />
                  </button>
                </div>
              </div>
            </div>
            {/* Gradient separator */}
            <div className="separator-gold" />
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

          {/* ── Analysis Mode Tab Bar (2 tabs) ── */}
          {!compareMode && (combined.state.status !== "idle" || status !== "idle") && (
            <div className="flex gap-1 p-1.5 glass-card border-[#30363d] rounded-2xl w-full md:w-fit overflow-x-auto">
              <button
                onClick={() => setMainTab("analysis")}
                className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-black uppercase tracking-widest transition-all ${mainTab === "analysis"
                  ? "tab-active"
                  : "text-gray-500 tab-inactive"
                  }`}
              >
                <Zap size={13} />
                Analysis
                {(combined.state.status === "fetching_data" || combined.state.status === "fundamental" || combined.state.status === "technical") && (
                  <Loader2 size={10} className="animate-spin" />
                )}
                {combined.state.status === "complete" && combined.state.committee && (
                  <span className="bg-black/20 text-black rounded-md px-1.5 text-[8px] font-mono">
                    {(combined.state.opportunity?.opportunity_score ?? combined.state.committee.score ?? 0).toFixed(1)}
                  </span>
                )}
              </button>
              <button
                onClick={() => setMainTab("portfolio")}
                className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-black uppercase tracking-widest transition-all ${mainTab === "portfolio"
                  ? "tab-active"
                  : "text-gray-500 tab-inactive"
                  }`}
              >
                <Briefcase size={13} />
                Portfolio
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
                /* ── Pristine empty state (no watchlist) */
                <div className="flex flex-col items-center justify-center flex-1 text-center mesh-gradient rounded-2xl py-20 px-6">
                  <div className="w-24 h-24 bg-[#161b22] rounded-3xl flex items-center justify-center mb-8 border border-[#d4af37]/15 glow-ring">
                    <Activity size={44} className="text-[#d4af37]/40 breathe" />
                  </div>
                  <h2 className="text-2xl font-black gold-gradient mb-3">Investment Analysis Engine</h2>
                  <p className="text-gray-500 max-w-md mx-auto leading-relaxed text-sm mb-2">
                    Convene the Investment Committee — fundamental, technical, and combined analysis in one institutional-grade report.
                  </p>
                  <p className="text-[#d4af37]/60 text-xs font-mono mb-8 blink-cursor">Type a ticker above to begin</p>
                  <div className="flex gap-3 text-xs font-mono text-gray-500 flex-wrap justify-center stagger-children">
                    <span className="flex items-center gap-1.5 glass-card px-3 py-1.5 border-[#30363d]"><ShieldCheck size={12} className="text-[#d4af37]/60" /> Fundamental</span>
                    <span className="flex items-center gap-1.5 glass-card px-3 py-1.5 border-[#30363d]"><LineChart size={12} className="text-[#60a5fa]/60" /> Technical</span>
                    <span className="flex items-center gap-1.5 glass-card px-3 py-1.5 border-[#30363d]"><Zap size={12} className="text-[#c084fc]/60" /> Combined</span>
                    <span className="flex items-center gap-1.5 glass-card px-3 py-1.5 border-[#30363d]"><Star size={12} className="text-[#d4af37]/60" /> Watchlist</span>
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
            <div className="flex flex-col items-center justify-center flex-1 py-16">
              <div className="orbital-spinner mb-6">
                <div className="orbital-ring orbital-ring-1" />
                <div className="orbital-ring orbital-ring-2" />
                <div className="orbital-ring orbital-ring-3" />
                <Activity className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-[#d4af37] breathe" size={22} />
              </div>
              <p className="text-[#d4af37] font-bold tracking-widest text-sm uppercase mb-3">
                Fetching Market Data for {state.ticker}...
              </p>
              <div className="flex items-center gap-2 text-[8px] font-mono uppercase tracking-widest">
                <span className="text-[#d4af37]">Data</span>
                <div className="w-3 h-px bg-[#d4af37]/30" />
                <span className="text-gray-700">Analysts</span>
                <div className="w-3 h-px bg-[#30363d]" />
                <span className="text-gray-700">Technical</span>
                <div className="w-3 h-px bg-[#30363d]" />
                <span className="text-gray-700">CIO</span>
                <div className="w-3 h-px bg-[#30363d]" />
                <span className="text-gray-700">Done</span>
              </div>
            </div>
          )}

          {/* ── Analysis View (3-Level Progressive Disclosure) ── */}
          {mainTab === "analysis" && (
            <div className="space-y-6" style={{ animation: "fadeSlideIn 0.3s ease both" }}>
              {/* Idle state */}
              {combined.state.status === "idle" && status === "idle" && (
                <div className="flex flex-col items-center justify-center py-20 text-center">
                  <div className="w-16 h-16 bg-[#161b22] rounded-3xl flex items-center justify-center mb-4 border border-[#30363d]">
                    <Zap size={28} className="text-[#d4af37]/30" />
                  </div>
                  <p className="text-gray-600 text-sm">Enter a ticker to start the Investment Committee.</p>
                  <p className="text-gray-700 text-xs mt-1">Fundamental + Technical + Decision — all in one flow.</p>
                </div>
              )}

              {/* Error state */}
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

              {/* Active analysis — 3 levels */}
              {combined.state.status !== "idle" && combined.state.status !== "error" && (
                <>
                  {/* Level 1 — Investment Verdict */}
                  <VerdictHero combined={combined.state} alphaProfile={alphaSignals.profile} />

                  {/* Level 2 — Investment Story */}
                  <InvestmentStory combined={combined.state} />

                  {/* Level 3 — Advanced Analytics (collapsed) */}
                  {combined.state.status === "complete" && (
                    <AnalyticsAccordion
                      combined={combined.state}
                      alphaProfile={alphaSignals.profile}
                      alphaStatus={alphaSignals.status}
                      alphaError={alphaSignals.error}
                      onEvaluateSignals={() => {
                        const t = combined.state.ticker || ticker;
                        if (t) alphaSignals.evaluate(t);
                      }}
                    />
                  )}
                </>
              )}
            </div>
          )}

          {/* ── Portfolio Dashboard ── */}
          {mainTab === "portfolio" && (
            <div style={{ animation: "fadeSlideIn 0.3s ease both" }}>
              <PortfolioDashboard historyEntries={history.entries} />
            </div>
          )}
        </main >

      </div >

      {/* ── Help Panel ── */}
      < HelpPanel open={helpOpen} onClose={() => setHelpOpen(false)
      } />

      {/* ── Pro Gate Modal (M16) ── */}
      {
        showProGate && (
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
        )
      }

      {/* ── Onboarding Overlay (M17) — first visit only ── */}
      {showOnboarding && <OnboardingOverlay onDone={dismissOnboarding} />}
    </>
  );
}
