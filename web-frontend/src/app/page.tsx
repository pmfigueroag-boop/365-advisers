"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import TopNav, { ViewId } from "@/components/navigation/TopNav";
import CommandPalette from "@/components/navigation/CommandPalette";
import TerminalShell from "@/components/shell/TerminalShell";
import TerminalView from "@/components/views/TerminalView";
import MarketIntelligenceView from "@/components/views/MarketIntelligenceView";
import IdeaExplorerView from "@/components/views/IdeaExplorerView";
import DeepAnalysisView from "@/components/views/DeepAnalysisView";
import PortfolioView from "@/components/views/PortfolioView";
import SystemView from "@/components/views/SystemView";
import StrategyLabView from "@/components/views/StrategyLabView";
import MarketplaceView from "@/components/views/MarketplaceView";
import AIAssistantView from "@/components/views/AIAssistantView";
import SuperAlphaView from "@/components/views/SuperAlphaView";
import PilotDashboardView from "@/components/views/PilotDashboardView";
import HelpPanel from "@/components/HelpPanel";
import OnboardingOverlay, { useOnboarding } from "@/components/OnboardingOverlay";
import ReportHeader from "@/components/ReportHeader";
import ErrorBoundary from "@/components/ErrorBoundary";

import { useWatchlist } from "@/hooks/useWatchlist";
import { useAnalysisHistory } from "@/hooks/useAnalysisHistory";
import { useCombinedStream } from "@/hooks/useCombinedStream";
import { useIdeasEngine } from "@/hooks/useIdeasEngine";
import { useAlphaSignals } from "@/hooks/useAlphaSignals";

import {
  Activity,
  TrendingUp,
  Zap,
  BarChart3,
  Shield,
  Radio,
  Lightbulb,
  Target,
  Clock,
  Briefcase,
  Brain,
  Star,
} from "lucide-react";

// ─── Idea Context Type ───────────────────────────────────────────────────
export interface IdeaContext {
  idea_id: string;
  ticker: string;
  detector: string;
  idea_type: string;
  signal_strength: number;
  confidence: string;
  confidence_score?: number;
}

// ─── Inline Animations ───────────────────────────────────────────────────
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

// ─── Shell Content Hooks ──────────────────────────────────────────────────

function useShellContext(activeView: ViewId, combined: any, alphaProfile: any, watchlist: any, ideasEngine: any) {
  return useMemo(() => {
    const ticker = combined.state?.ticker;
    const isComplete = combined.state?.status === "complete";

    // ─── Right Intel Insights ─────────────────────────────────────────
    const insights: Array<{ type: "info" | "warn" | "success"; text: string }> = [];
    const sections: Array<{ title: string; icon: React.ReactNode; content: React.ReactNode }> = [];

    if (activeView === "terminal") {
      if (isComplete && combined.state.opportunity?.opportunity_score) {
        const score = combined.state.opportunity.opportunity_score;
        insights.push({
          type: score >= 7 ? "success" : score >= 5 ? "info" : "warn",
          text: `Opportunity Score: ${score.toFixed(1)}/10`,
        });
      }
      if (isComplete && combined.state.decision?.investment_position) {
        insights.push({
          type: combined.state.decision.investment_position === "BUY" ? "success" : "info",
          text: `Verdict: ${combined.state.decision.investment_position}`,
        });
      }
      if (alphaProfile?.profile?.fired_signals) {
        insights.push({
          type: "info",
          text: `${alphaProfile.profile.fired_signals} of ${alphaProfile.profile.total_signals} signals active`,
        });
      }
    } else if (activeView === "ideas") {
      const count = ideasEngine.ideas?.length ?? 0;
      insights.push({ type: "info", text: `${count} ideas discovered` });
      if (count > 10) {
        insights.push({ type: "success", text: "Rich opportunity set — consider strategy lab" });
      }
    } else if (activeView === "analysis") {
      if (ticker) insights.push({ type: "info", text: `Analyzing: ${ticker}` });
      if (isComplete) insights.push({ type: "success", text: "Full analysis available" });
    } else if (activeView === "portfolio") {
      const positions = watchlist.items?.length ?? 0;
      insights.push({ type: "info", text: `${positions} assets in coverage` });
    } else if (activeView === "system") {
      insights.push({ type: "success", text: "All systems nominal" });
      insights.push({ type: "info", text: "Signal pipeline healthy" });
    } else if (activeView === "marketplace") {
      insights.push({ type: "info", text: "6 institutional strategies available" });
      insights.push({ type: "info", text: "Import to Strategy Lab to customize" });
    } else if (activeView === "ai-assistant") {
      insights.push({ type: "info", text: "Knowledge Graph connected" });
      insights.push({ type: "info", text: "Strategy Lab integration active" });
    }

    // ─── Bottom Panel Metrics ─────────────────────────────────────────
    const bottomMetrics: Array<{ icon: React.ReactNode; label: string; value: string }> = [];
    let bottomTitle = "Analytics";
    let bottomSubtitle = "";

    if (activeView === "terminal" && isComplete) {
      bottomTitle = "Signal Matrix";
      bottomSubtitle = ticker ?? "";
      if (alphaProfile?.profile) {
        bottomMetrics.push(
          { icon: <Radio size={12} className="text-[#d4af37]" />, label: "Active Signals", value: `${alphaProfile.profile.fired_signals ?? 0}` },
          { icon: <TrendingUp size={12} className="text-emerald-400" />, label: "CASE Score", value: `${alphaProfile.profile.composite_score?.toFixed(0) ?? "—"}` },
        );
      }
      if (combined.state.opportunity) {
        bottomMetrics.push(
          { icon: <Target size={12} className="text-blue-400" />, label: "Opp. Score", value: `${combined.state.opportunity.opportunity_score?.toFixed(1) ?? "—"}` },
        );
      }
    } else if (activeView === "ideas") {
      bottomTitle = "Idea Distribution";
      bottomSubtitle = `${ideasEngine.ideas?.length ?? 0} opportunities`;
    } else if (activeView === "analysis") {
      bottomTitle = "Evidence Summary";
      bottomSubtitle = ticker ?? "";
    } else if (activeView === "portfolio") {
      bottomTitle = "Portfolio Metrics";
      bottomSubtitle = `${watchlist.items.length} assets`;
    } else if (activeView === "system") {
      bottomTitle = "System Metrics";
    }

    // ─── Watchlist for Left Nav ───────────────────────────────────────
    const wlItems = watchlist.items.map((item: any) => ({
      ticker: item.ticker,
      name: item.name,
      lastSignal: item.lastSignal,
      lastScore: item.lastScore,
    }));

    return {
      insights,
      sections,
      bottomMetrics,
      bottomTitle,
      bottomSubtitle,
      wlItems,
      activeSignals: alphaProfile?.profile?.fired_signals ?? undefined,
      lastUpdate: isComplete ? "now" : undefined,
    };
  }, [activeView, combined.state, alphaProfile, watchlist.items, ideasEngine.ideas]);
}

// ─── Main Page ───────────────────────────────────────────────────────────

export default function Home() {
  // ── View state ────────────────────────────────────────────────────────────
  const [activeView, setActiveView] = useState<ViewId>("terminal");
  const [ticker, setTicker] = useState("");
  const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false);
  const [rankingReady, setRankingReady] = useState(false);
  const [ideaContext, setIdeaContext] = useState<IdeaContext | null>(null);
  const { showOnboarding, dismiss: dismissOnboarding } = useOnboarding();

  // ── Hooks ─────────────────────────────────────────────────────────────────
  const combined = useCombinedStream();
  const watchlist = useWatchlist();
  const history = useAnalysisHistory();
  const ideasEngine = useIdeasEngine();
  const alphaSignals = useAlphaSignals();

  // ── Derived state ─────────────────────────────────────────────────────────
  const isLoading = combined.state.status === "fetching_data" || combined.state.status === "fundamental" || combined.state.status === "technical" || combined.state.status === "decision";
  const dataReady = combined.state.fundamentalDataReady;

  // ── Shell context ─────────────────────────────────────────────────────────
  const shellCtx = useShellContext(activeView, combined, alphaSignals, watchlist, ideasEngine);

  // ── Keyboard shortcuts ────────────────────────────────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Shift+? → Help (new window)
      if (e.shiftKey && e.key === "?") { e.preventDefault(); window.open("/help", "365help", "width=700,height=900,scrollbars=yes"); return; }
      // Ctrl+K / Cmd+K → Command Palette
      if ((e.ctrlKey || e.metaKey) && e.key === "k") { e.preventDefault(); setCmdPaletteOpen((v) => !v); return; }
      // Alt+1..9 → View switching
      if (e.altKey && !e.ctrlKey && !e.metaKey) {
        const viewMap: Record<string, ViewId> = {
          "1": "terminal", "2": "market", "3": "ideas", "4": "analysis",
          "5": "portfolio", "6": "system", "7": "strategy-lab",
          "8": "marketplace", "9": "ai-assistant", "0": "pilot",
        };
        const view = viewMap[e.key];
        if (view) { e.preventDefault(); setActiveView(view); return; }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
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

  // ── Auto-compute ranking when Ideas scan completes ────────────────────────
  useEffect(() => {
    if (ideasEngine.scanStatus === "done" && ideasEngine.ideas.length > 0) {
      const ideaDicts = ideasEngine.ideas.map((idea) => ({
        ticker: idea.ticker,
        name: idea.name,
        sector: idea.sector,
        idea_type: idea.idea_type,
        confidence: idea.confidence,
        signal_strength: idea.signal_strength,
      }));
      const oppScores: Record<string, number> = {};
      for (const idea of ideasEngine.ideas) {
        const current = oppScores[idea.ticker] ?? 0;
        oppScores[idea.ticker] = Math.max(current, idea.signal_strength * 10);
      }
      // Fire-and-forget: populate backend ranking cache
      const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      fetch(`${API}/ranking/compute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ideas: ideaDicts, case_scores: {}, opp_scores: oppScores }),
      }).then(() => setRankingReady(true)).catch(() => { /* silent */ });
    }
  }, [ideasEngine.scanStatus, ideasEngine.ideas]);

  // ── Handlers ──────────────────────────────────────────────────────────────
  const handleAnalyze = useCallback((symbol?: string, fromIdea?: IdeaContext) => {
    const t = symbol ?? ticker;
    if (!t.trim()) return;
    if (!symbol) setTicker(t);

    // If coming from an idea, navigate to analysis view and store context
    if (fromIdea) {
      setIdeaContext(fromIdea);
      setActiveView("analysis");
      // Auto-mark idea as analyzed
      ideasEngine.updateStatus(fromIdea.idea_id, "analyzed");
    } else {
      setIdeaContext(null);
      setActiveView("terminal");
    }

    combined.analyze(t);
  }, [ticker, combined, ideasEngine]);

  const handleForceRefresh = useCallback(() => {
    if (!dataReady?.ticker) return;
    combined.forceRefresh(dataReady.ticker);
  }, [dataReady, combined]);

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

  // ── Check if current view needs TerminalShell (all except strategy-lab) ──
  const useShell = activeView !== "strategy-lab";

  return (
    <>
      <style>{INLINE_STYLES}</style>

      <div className={`flex flex-col min-h-screen ${useShell ? "p-4 md:p-6" : "p-0"} max-w-[1920px] mx-auto`} suppressHydrationWarning>
        {/* Top Navigation */}
        <TopNav
          activeView={activeView}
          onViewChange={setActiveView}
          ticker={ticker}
          onTickerChange={setTicker}
          onAnalyze={() => handleAnalyze()}
          isLoading={isLoading}
          showCacheBadge={combined.state.fromCache ?? false}
          onForceRefresh={handleForceRefresh}
          showExport={combined.state.status === "complete" && !!dataReady}
          onExport={handleExport}
          showWatchlistToggle={!!dataReady?.ticker}
          inWatchlist={inWatchlist}
          onToggleWatchlist={handleToggleWatchlist}
          onOpenHelp={() => window.open("/help", "365help", "width=700,height=900,scrollbars=yes")}
          onOpenCommandPalette={() => setCmdPaletteOpen(true)}
          analysisScore={analysisScore}
          analysisLoading={isLoading}
        />

        {/* Print-only Report Header */}
        {dataReady && (
          <ReportHeader
            ticker={dataReady.ticker}
            name={dataReady.name}
            price={undefined}
          />
        )}

        {/* ── View Router with TerminalShell ── */}
        <ErrorBoundary key={activeView}>
          {useShell ? (
            <TerminalShell
              activeView={activeView}
              // Watchlist for left nav
              watchlistItems={shellCtx.wlItems}
              activeTicker={combined.state.ticker ?? undefined}
              onTickerSelect={(t) => handleAnalyze(t)}
              // Right intel
              insights={shellCtx.insights}
              intelSections={shellCtx.sections}
              // Bottom panel
              bottomTitle={shellCtx.bottomTitle}
              bottomSubtitle={shellCtx.bottomSubtitle}
              bottomMetrics={shellCtx.bottomMetrics}
              // Status bar
              regime="bull"
              activeSignals={shellCtx.activeSignals}
              lastUpdate={shellCtx.lastUpdate}
            >
              {(() => {
                switch (activeView) {
                  case "terminal":
                    return (
                      <TerminalView
                        combined={combined.state}
                        alphaProfile={alphaSignals.profile}
                        watchlistItems={watchlist.items}
                        onAnalyze={handleAnalyze}
                        onNavigateAnalysis={() => setActiveView("analysis")}
                      />
                    );
                  case "market":
                    return (
                      <MarketIntelligenceView
                        onSelectTicker={(t) => handleAnalyze(t)}
                        rankingReady={rankingReady}
                      />
                    );
                  case "ideas":
                    return (
                      <IdeaExplorerView
                        ideas={ideasEngine.ideas}
                        scanStatus={ideasEngine.scanStatus}
                        error={ideasEngine.error}
                        onScan={() => {
                          const tickers = watchlist.items.map((i) => i.ticker);
                          if (tickers.length > 0) ideasEngine.scan(tickers);
                        }}
                        onAutoScan={() => ideasEngine.autoScan()}
                        onAnalyze={(t) => {
                          // Find the idea to build context
                          const idea = ideasEngine.ideas.find((i) => i.ticker === t);
                          if (idea) {
                            handleAnalyze(t, {
                              idea_id: idea.id,
                              ticker: idea.ticker,
                              detector: idea.idea_type,
                              idea_type: idea.idea_type,
                              signal_strength: idea.signal_strength,
                              confidence: idea.confidence,
                              confidence_score: idea.confidence_score,
                            });
                          } else {
                            handleAnalyze(t);
                          }
                        }}
                        onDismiss={(id) => ideasEngine.dismiss(id)}
                        universeMeta={ideasEngine.lastUniverse}
                      />
                    );
                  case "analysis":
                    return (
                      <DeepAnalysisView
                        combined={combined.state}
                        alphaProfile={alphaSignals.profile}
                        alphaStatus={alphaSignals.status}
                        alphaError={alphaSignals.error}
                        onEvaluateSignals={() => {
                          const t = combined.state.ticker || ticker;
                          if (t) alphaSignals.evaluate(t);
                        }}
                        onBack={() => {
                          if (ideaContext) {
                            setActiveView("ideas");
                            setIdeaContext(null);
                          } else {
                            setActiveView("terminal");
                          }
                        }}
                        ideaContext={ideaContext}
                        isInWatchlist={combined.state.ticker ? watchlist.has(combined.state.ticker) : false}
                        onAddToWatchlist={() => {
                          const t = combined.state.ticker;
                          const name = combined.state.fundamentalDataReady?.name ?? t;
                          if (t) {
                            if (watchlist.has(t)) {
                              watchlist.remove(t);
                            } else {
                              watchlist.add(t, name ?? t);
                              // Update idea status to validated if from an idea
                              if (ideaContext) {
                                ideasEngine.updateStatus(ideaContext.idea_id, "validated");
                              }
                            }
                          }
                        }}
                      />
                    );
                  case "portfolio":
                    return <PortfolioView historyEntries={history.entries} />;
                  case "system":
                    return <SystemView />;
                  case "pilot":
                    return <PilotDashboardView />;
                  case "marketplace":
                    return <MarketplaceView />;
                  case "ai-assistant":
                    return <AIAssistantView />;
                  case "alpha-engine":
                    return <SuperAlphaView />;
                  default:
                    return null;
                }
              })()}
            </TerminalShell>
          ) : (
            /* Strategy Lab has its own shell */
            <StrategyLabView />
          )}
        </ErrorBoundary>
      </div>

      {/* ── Overlays ── */}
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
