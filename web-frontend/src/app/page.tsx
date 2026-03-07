"use client";

import { useState, useEffect, useCallback } from "react";
import TopNav, { ViewId } from "@/components/navigation/TopNav";
import CommandPalette from "@/components/navigation/CommandPalette";
import WatchlistPanel from "@/components/navigation/WatchlistPanel";
import TerminalView from "@/components/views/TerminalView";
import MarketIntelligenceView from "@/components/views/MarketIntelligenceView";
import IdeaExplorerView from "@/components/views/IdeaExplorerView";
import DeepAnalysisView from "@/components/views/DeepAnalysisView";
import PortfolioView from "@/components/views/PortfolioView";
import SystemView from "@/components/views/SystemView";
import HelpPanel from "@/components/HelpPanel";
import OnboardingOverlay, { useOnboarding } from "@/components/OnboardingOverlay";
import ReportHeader from "@/components/ReportHeader";
import ErrorBoundary from "@/components/ErrorBoundary";
import CompareView, { CompareState } from "@/components/CompareView";

import { useAnalysisStream } from "@/hooks/useAnalysisStream";
import { useWatchlist } from "@/hooks/useWatchlist";
import { useAnalysisHistory } from "@/hooks/useAnalysisHistory";
import { useTechnicalAnalysis } from "@/hooks/useTechnicalAnalysis";
import { useFundamentalStream } from "@/hooks/useFundamentalStream";
import { useCombinedStream } from "@/hooks/useCombinedStream";
import { useIdeasEngine } from "@/hooks/useIdeasEngine";
import { useAlphaSignals } from "@/hooks/useAlphaSignals";

// ─── Inline Animations ───────────────────────────────────────────────────────
const INLINE_STYLES = `
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
`;

// ─── Main Page ───────────────────────────────────────────────────────────────

export default function Home() {
  // ── View state ────────────────────────────────────────────────────────────
  const [activeView, setActiveView] = useState<ViewId>("terminal");
  const [ticker, setTicker] = useState("");
  const [panelCollapsed, setPanelCollapsed] = useState(true);
  const [helpOpen, setHelpOpen] = useState(false);
  const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false);
  const { showOnboarding, dismiss: dismissOnboarding } = useOnboarding();

  // ── Hooks ─────────────────────────────────────────────────────────────────
  const { state, analyze: legacyAnalyze, forceRefresh: legacyForceRefresh } = useAnalysisStream();
  const technical = useTechnicalAnalysis();
  const fundamental = useFundamentalStream();
  const combined = useCombinedStream();
  const watchlist = useWatchlist();
  const history = useAnalysisHistory();
  const ideasEngine = useIdeasEngine();
  const alphaSignals = useAlphaSignals();

  // ── Derived state ─────────────────────────────────────────────────────────
  const isLoading = combined.state.status === "fetching_data" || combined.state.status === "fundamental" || combined.state.status === "technical" || combined.state.status === "decision";
  const dataReady = state.dataReady;

  // ── Keyboard shortcuts ────────────────────────────────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Shift+? → Help
      if (e.shiftKey && e.key === "?") { e.preventDefault(); setHelpOpen((v) => !v); return; }
      // Ctrl+K / Cmd+K → Command Palette
      if ((e.ctrlKey || e.metaKey) && e.key === "k") { e.preventDefault(); setCmdPaletteOpen((v) => !v); return; }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // ── Auto-collapse panel on mobile ─────────────────────────────────────────
  useEffect(() => {
    if (typeof window !== "undefined" && window.innerWidth < 768) {
      setPanelCollapsed(true);
    }
  }, []);

  // ── Auto-evaluate alpha signals on combined complete ──────────────────────
  useEffect(() => {
    if (combined.state.status === "complete" && combined.state.ticker) {
      alphaSignals.evaluate(combined.state.ticker);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [combined.state.status, combined.state.ticker]);

  // ── Update history + watchlist on combined complete ───────────────────────
  useEffect(() => {
    if (combined.state.status === "complete" && combined.state.ticker && combined.state.fundamentalDataReady) {
      const signalToSave = combined.state.decision?.investment_position ?? "HOLD";
      const scoreToSave = combined.state.committee?.score ?? 0;

      watchlist.updateSignal(combined.state.ticker, signalToSave, scoreToSave);

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
    watchlist.updateSignal,
    history.add,
  ]);

  // ── Handlers ──────────────────────────────────────────────────────────────
  const handleAnalyze = useCallback((symbol?: string) => {
    const t = symbol ?? ticker;
    if (!t.trim()) return;
    if (!symbol) setTicker(t);
    setActiveView("terminal");
    legacyAnalyze(t);
    technical.analyze(t);
    fundamental.analyze(t);
    combined.analyze(t);
  }, [ticker, legacyAnalyze, technical, fundamental, combined]);

  const handleForceRefresh = useCallback(() => {
    if (!dataReady?.ticker) return;
    legacyForceRefresh(dataReady.ticker);
    combined.forceRefresh(dataReady.ticker);
  }, [dataReady, legacyForceRefresh, combined]);

  const handleToggleWatchlist = useCallback(() => {
    if (!dataReady?.ticker) return;
    if (watchlist.has(dataReady.ticker)) {
      watchlist.remove(dataReady.ticker);
    } else {
      watchlist.add(dataReady.ticker, dataReady.name);
    }
  }, [dataReady, watchlist]);

  const handleExport = useCallback(() => {
    document.body.setAttribute("data-print-date", new Date().toLocaleString());
    window.print();
  }, []);

  const inWatchlist = dataReady ? watchlist.has(dataReady.ticker) : false;
  const recentTickers = history.entries.slice(0, 8).map((e) => e.ticker);

  // ── Analysis score for tab badge ──────────────────────────────────────────
  const analysisScore = combined.state.status === "complete"
    ? (combined.state.opportunity?.opportunity_score ?? combined.state.committee?.score ?? null)
    : null;

  return (
    <>
      <style>{INLINE_STYLES}</style>

      <div className="flex min-h-screen gap-4 p-4 md:p-6 max-w-[1600px] mx-auto">
        {/* ── Main Content ── */}
        <main className="flex-1 min-w-0 flex flex-col gap-5">
          {/* Top Navigation */}
          <TopNav
            activeView={activeView}
            onViewChange={setActiveView}
            ticker={ticker}
            onTickerChange={setTicker}
            onAnalyze={() => handleAnalyze()}
            isLoading={isLoading}
            showCacheBadge={state.fromCache}
            cachedAt={state.cachedAt}
            onForceRefresh={handleForceRefresh}
            showExport={combined.state.status === "complete" && !!dataReady}
            onExport={handleExport}
            showWatchlistToggle={!!dataReady?.ticker}
            inWatchlist={inWatchlist}
            onToggleWatchlist={handleToggleWatchlist}
            onOpenHelp={() => setHelpOpen(true)}
            onOpenCommandPalette={() => setCmdPaletteOpen(true)}
            analysisScore={analysisScore}
            analysisLoading={isLoading}
          />

          {/* Print-only Report Header */}
          {dataReady && (
            <ReportHeader
              ticker={dataReady.ticker}
              name={dataReady.name}
              price={typeof dataReady.fundamental_metrics?.price === "number" ? dataReady.fundamental_metrics.price as number : undefined}
            />
          )}

          {/* ── View Router ── */}
          <ErrorBoundary>
            {activeView === "terminal" && (
              <TerminalView
                combined={combined.state}
                alphaProfile={alphaSignals.profile}
                watchlistItems={watchlist.items}
                onAnalyze={handleAnalyze}
                onNavigateAnalysis={() => setActiveView("analysis")}
              />
            )}

            {activeView === "market" && (
              <MarketIntelligenceView
                onSelectTicker={(t) => handleAnalyze(t)}
              />
            )}

            {activeView === "ideas" && (
              <IdeaExplorerView
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

            {activeView === "analysis" && (
              <DeepAnalysisView
                combined={combined.state}
                alphaProfile={alphaSignals.profile}
                alphaStatus={alphaSignals.status}
                alphaError={alphaSignals.error}
                onEvaluateSignals={() => {
                  const t = combined.state.ticker || ticker;
                  if (t) alphaSignals.evaluate(t);
                }}
                onBack={() => setActiveView("terminal")}
              />
            )}

            {activeView === "portfolio" && (
              <PortfolioView historyEntries={history.entries} />
            )}

            {activeView === "system" && (
              <SystemView />
            )}
          </ErrorBoundary>
        </main>

        {/* ── Right Side Panel (Watchlist/History/Ideas) ── */}
        <WatchlistPanel
          items={watchlist.items}
          onSelect={(t) => handleAnalyze(t)}
          onRemove={watchlist.remove}
          activeTicker={combined.state.ticker ?? undefined}
          historyEntries={history.entries}
          onHistorySelect={(t) => handleAnalyze(t)}
          onHistoryRemove={history.removeById}
          onHistoryClear={history.clear}
          ideas={ideasEngine.ideas}
          ideasScanStatus={ideasEngine.scanStatus}
          ideasError={ideasEngine.error}
          onIdeasScan={() => {
            const tickers = watchlist.items.map((i) => i.ticker);
            if (tickers.length > 0) ideasEngine.scan(tickers);
          }}
          onIdeasAnalyze={(t) => handleAnalyze(t)}
          onIdeasDismiss={(id) => ideasEngine.dismiss(id)}
          collapsed={panelCollapsed}
          onToggle={() => setPanelCollapsed((v) => !v)}
        />
      </div>

      {/* ── Overlays ── */}
      <HelpPanel open={helpOpen} onClose={() => setHelpOpen(false)} />
      <CommandPalette
        open={cmdPaletteOpen}
        onClose={() => setCmdPaletteOpen(false)}
        onNavigate={(v) => { setActiveView(v); setCmdPaletteOpen(false); }}
        onAnalyze={(t) => { handleAnalyze(t); setCmdPaletteOpen(false); }}
        recentTickers={recentTickers}
        watchlistTickers={watchlist.items.map((i) => i.ticker)}
      />
      {showOnboarding && <OnboardingOverlay onDone={dismissOnboarding} />}
    </>
  );
}
