"use client";

/**
 * DeepAnalysisView.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * 6-section tabbed deep-dive into a single asset's analysis data.
 *
 * Sections: Thesis · Fundamental · Technical · Alpha · Evidence · Signal Map · Backtest · Charts
 */

import { useState } from "react";
import {
    Lightbulb,
    Radio,
    Activity,
    Users,
    BarChart3,
    LineChart,
    ArrowLeft,
    Loader2,
    Star,
    CheckCircle,
} from "lucide-react";
import type { CombinedState } from "@/hooks/useCombinedStream";
import type { SignalProfileResponse, SignalStatus } from "@/hooks/useAlphaSignals";
import InvestmentStory from "@/components/InvestmentStory";
import AlphaSignalsView from "@/components/AlphaSignalsView";
import CompositeAlphaGauge from "@/components/CompositeAlphaGauge";
import IndicatorGrid from "@/components/IndicatorGrid";
import ResearchMemoCard from "@/components/ResearchMemoCard";
import TradingViewChart from "@/components/TradingViewChart";
import { CashFlowChart } from "@/components/Charts";
import ScoreHistoryChart from "@/components/ScoreHistoryChart";
import BacktestEvidenceTab from "@/components/analysis/BacktestEvidenceTab";
import SignalEvidenceTab from "@/components/analysis/SignalEvidenceTab";
import ErrorBoundary from "@/components/ErrorBoundary";
import SourceStatusStrip from "@/components/coverage/SourceStatusStrip";
import WarningBanner from "@/components/coverage/WarningBanner";
import ResearchMemoInsight from "@/components/analysis/ResearchMemoInsight";

// ─── Types ────────────────────────────────────────────────────────────────────

type Section = "thesis" | "signals" | "technical" | "fundamental" | "evidence" | "backtest" | "signal_evidence" | "charts";

const SECTIONS: { id: Section; label: string; icon: React.ReactNode }[] = [
    { id: "thesis", label: "Thesis", icon: <Lightbulb size={12} /> },
    { id: "fundamental", label: "Fundamental", icon: <Users size={12} /> },
    { id: "technical", label: "Technical", icon: <Activity size={12} /> },
    { id: "signals", label: "Alpha", icon: <Radio size={12} /> },
    { id: "evidence", label: "Evidence", icon: <BarChart3 size={12} /> },
    { id: "signal_evidence", label: "Signal Map", icon: <Radio size={12} /> },
    { id: "backtest", label: "Backtest", icon: <BarChart3 size={12} /> },
    { id: "charts", label: "Charts", icon: <LineChart size={12} /> },
];

interface DeepAnalysisViewProps {
    combined: CombinedState;
    alphaProfile: SignalProfileResponse | null;
    alphaStatus: SignalStatus;
    alphaError: string | null;
    onEvaluateSignals: () => void;
    onBack: () => void;
    ideaContext?: { idea_id: string; ticker: string; detector: string; idea_type: string; signal_strength: number; confidence: string; confidence_score?: number } | null;
    isInWatchlist?: boolean;
    onAddToWatchlist?: () => void;
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function DeepAnalysisView({
    combined,
    alphaProfile,
    alphaStatus,
    alphaError,
    onEvaluateSignals,
    onBack,
    ideaContext,
    isInWatchlist,
    onAddToWatchlist,
}: DeepAnalysisViewProps) {
    const [section, setSection] = useState<Section>("thesis");

    const isLoading = combined.status !== "complete" && combined.status !== "error" && combined.status !== "idle";
    const ticker = combined.ticker;

    // ── Idle/Loading State ────────────────────────────────────────────────────
    if (combined.status === "idle") {
        return (
            <div className="flex flex-col items-center justify-center py-24 text-center" style={{ animation: "fadeSlideIn 0.3s ease both" }}>
                <BarChart3 size={32} className="text-gray-700 mb-4" />
                <p className="text-gray-500 text-sm">No analysis data yet.</p>
                <p className="text-gray-700 text-xs mt-1">Analyze a ticker from the Terminal to see the deep dive.</p>
            </div>
        );
    }

    if (combined.status === "error") {
        return (
            <div className="flex flex-col items-center justify-center py-20 text-center">
                <Activity size={36} className="text-red-500 mb-3" />
                <p className="text-red-400 font-mono text-sm">{combined.error}</p>
            </div>
        );
    }

    return (
        <div className="space-y-4" style={{ animation: "fadeSlideIn 0.3s ease both" }}>
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <button
                        onClick={onBack}
                        className="p-2 rounded-xl text-gray-500 hover:text-[#d4af37] hover:bg-[#d4af37]/10 transition-all"
                        title={ideaContext ? "Back to Ideas" : "Back to Terminal"}
                    >
                        <ArrowLeft size={16} />
                    </button>
                    <div>
                        <h2 className="text-lg font-black text-white tracking-tight">
                            {ticker}
                            {combined.fundamentalDataReady?.name && (
                                <span className="text-gray-500 font-normal text-sm ml-2">
                                    {combined.fundamentalDataReady.name}
                                </span>
                            )}
                        </h2>
                        <p className="text-[9px] uppercase font-mono text-gray-600 tracking-widest">
                            Deep Analysis
                            {isLoading && <Loader2 size={10} className="animate-spin inline ml-2" />}
                        </p>
                    </div>
                </div>
                {/* Add to Watchlist button */}
                <div className="flex items-center gap-2">
                    {onAddToWatchlist && (
                        <button
                            onClick={onAddToWatchlist}
                            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider border transition-all ${
                                isInWatchlist
                                    ? "bg-[#d4af37]/15 text-[#d4af37] border-[#d4af37]/40"
                                    : "bg-[#161b22] text-gray-400 border-[#30363d] hover:text-[#d4af37] hover:border-[#d4af37]/40"
                            }`}
                        >
                            <Star size={11} fill={isInWatchlist ? "currentColor" : "none"} />
                            {isInWatchlist ? "In Watchlist" : "Add to Watchlist"}
                        </button>
                    )}
                </div>
            </div>

            {/* Idea Origin Banner */}
            {ideaContext && (
                <div className="flex items-center gap-3 px-4 py-2.5 bg-[#161b22] rounded-xl border border-[#30363d]" style={{ animation: "fadeSlideIn 0.2s ease both" }}>
                    <Lightbulb size={13} className="text-[#d4af37] flex-shrink-0" />
                    <span className="text-[10px] text-gray-400">
                        Initiated from <span className="font-bold text-[#d4af37] uppercase">{ideaContext.idea_type}</span> Detector
                        <span className="mx-1.5 text-gray-600">·</span>
                        Strength <span className="font-mono font-bold text-white">{(ideaContext.signal_strength * 100).toFixed(0)}%</span>
                        <span className="mx-1.5 text-gray-600">·</span>
                        Confidence <span className={`font-bold uppercase ${ideaContext.confidence === "high" ? "text-green-400" : ideaContext.confidence === "medium" ? "text-yellow-400" : "text-gray-500"}`}>{ideaContext.confidence}</span>
                        {ideaContext.confidence_score != null && (
                            <>
                                <span className="mx-1.5 text-gray-600">·</span>
                                Reliability <span className="font-mono font-bold text-teal-400">{(ideaContext.confidence_score * 100).toFixed(0)}%</span>
                            </>
                        )}
                    </span>
                </div>
            )}

            {/* BUY Recommendation prompt */}
            {combined.status === "complete" && combined.decision?.investment_position === "BUY" && !isInWatchlist && onAddToWatchlist && (
                <div
                    className="flex items-center gap-3 px-4 py-2.5 bg-green-500/5 rounded-xl border border-green-500/20 cursor-pointer hover:bg-green-500/10 transition-all"
                    onClick={onAddToWatchlist}
                    style={{ animation: "fadeSlideIn 0.25s ease both" }}
                >
                    <CheckCircle size={14} className="text-green-400 flex-shrink-0" />
                    <span className="text-[10px] text-green-400 font-bold">BUY Recommended</span>
                    <span className="text-[10px] text-gray-500">— Click to add to watchlist for tracking</span>
                </div>
            )}

            {/* Source Coverage Strip + Warning */}
            {combined.sourceCoverage && (
                <>
                    <SourceStatusStrip sources={combined.sourceCoverage.sources} />
                    <WarningBanner
                        messages={combined.sourceCoverage.messages}
                        unavailable={combined.sourceCoverage.unavailable}
                    />
                </>
            )}

            {/* Section Tabs */}
            <div className="flex gap-1 p-1 glass-card border-[#30363d] rounded-xl overflow-x-auto">
                {SECTIONS.map((s) => (
                    <button
                        key={s.id}
                        onClick={() => setSection(s.id)}
                        className={`flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all whitespace-nowrap ${section === s.id
                            ? "tab-active"
                            : "text-gray-500 tab-inactive"
                            }`}
                    >
                        {s.icon}
                        {s.label}
                    </button>
                ))}
            </div>

            {/* Section Content */}
            <ErrorBoundary>
                <div key={section} className="glass-card border-[#30363d] p-5 view-transition">
                    {section === "thesis" && (
                        <InvestmentStory combined={combined} />
                    )}

                    {section === "signals" && (
                        <AlphaSignalsView
                            profile={alphaProfile}
                            status={alphaStatus}
                            error={alphaError}
                            onEvaluate={onEvaluateSignals}
                        />
                    )}

                    {section === "technical" && combined.technical && (
                        <IndicatorGrid data={combined.technical} technicalMemo={combined.technicalMemo} />
                    )}
                    {section === "technical" && !combined.technical && (
                        <p className="text-gray-600 text-sm text-center py-8">Technical data not available yet.</p>
                    )}

                    {section === "fundamental" && (
                        <ResearchMemoCard
                            dataReady={combined.fundamentalDataReady}
                            agentMemos={combined.agentMemos}
                            committee={combined.committee}
                            researchMemo={combined.researchMemo}
                            agentCount={combined.agentMemos.length}
                            totalAgents={4}
                            status={combined.status === "complete" ? "complete" : "analyzing"}
                        />
                    )}

                    {section === "evidence" && (
                        <div className="space-y-6">
                            {/* Evidence Research Memo — LLM with deterministic fallback */}
                            {alphaProfile?.composite_alpha && (() => {
                                // Prefer LLM memo from backend
                                if (alphaProfile.evidence_memo) {
                                    return (
                                        <ResearchMemoInsight memo={{
                                            title: "Research Memo — Evidence",
                                            signal: (alphaProfile.evidence_memo.signal as "BULLISH" | "BEARISH" | "NEUTRAL") || "NEUTRAL",
                                            conviction: (alphaProfile.evidence_memo.conviction as "HIGH" | "MEDIUM" | "LOW") || "LOW",
                                            narrative: alphaProfile.evidence_memo.narrative,
                                            bullets: alphaProfile.evidence_memo.key_data || [],
                                            risks: alphaProfile.evidence_memo.risk_factors || [],
                                        }} />
                                    );
                                }

                                // Deterministic fallback
                                const ca = alphaProfile.composite_alpha;
                                const caseScore = ca.score;
                                const env = ca.environment;
                                const activeCats = ca.active_categories;
                                const subscores = ca.subscores || {};
                                const sortedSubs = Object.entries(subscores)
                                    .sort((a, b) => (b[1].score ?? 0) - (a[1].score ?? 0));
                                const strongest = sortedSubs[0];
                                const weakest = sortedSubs[sortedSubs.length - 1];

                                const signal: "BULLISH" | "BEARISH" | "NEUTRAL" =
                                    caseScore >= 65 ? "BULLISH" : caseScore <= 35 ? "BEARISH" : "NEUTRAL";
                                const conviction: "HIGH" | "MEDIUM" | "LOW" =
                                    caseScore >= 75 ? "HIGH" : caseScore >= 45 ? "MEDIUM" : "LOW";

                                const narrative =
                                    `CASE Composite Score: ${caseScore.toFixed(0)}/100 (Environment: ${env}). ` +
                                    `${activeCats} categorías activas` +
                                    (ca.convergence_bonus > 0 ? ` con bonus de convergencia +${ca.convergence_bonus.toFixed(1)}.` : ".") +
                                    (ca.cross_category_conflicts?.length > 0
                                        ? ` ${ca.cross_category_conflicts.length} conflictos inter-categoría detectados.`
                                        : "");

                                const bullets: string[] = [];
                                if (strongest) {
                                    bullets.push(`Categoría más fuerte: ${strongest[0]} (score ${strongest[1].score?.toFixed(0) ?? "N/A"}, ${strongest[1].fired}/${strongest[1].total} señales)`);
                                }
                                if (weakest && weakest !== strongest) {
                                    bullets.push(`Categoría más débil: ${weakest[0]} (score ${weakest[1].score?.toFixed(0) ?? "N/A"}, ${weakest[1].fired}/${weakest[1].total} señales)`);
                                }
                                if (ca.convergence_bonus > 0) {
                                    bullets.push(`Bonus de convergencia: +${ca.convergence_bonus.toFixed(1)} puntos por alineación multi-categoría`);
                                }

                                const risks: string[] = [];
                                if (ca.cross_category_conflicts?.length > 0) {
                                    risks.push(`Conflictos detectados: ${ca.cross_category_conflicts.join(", ")}`);
                                }
                                if (activeCats <= 2) {
                                    risks.push("Pocas categorías activas — el score depende de pocos factores");
                                }
                                const decay = ca.decay;
                                if (decay && (decay.freshness_level === "stale" || decay.freshness_level === "expired")) {
                                    risks.push(`Señales con frescura "${decay.freshness_level}" — datos pueden estar desactualizados`);
                                }

                                return (
                                    <ResearchMemoInsight memo={{
                                        title: "Research Memo — Evidence",
                                        signal,
                                        conviction,
                                        narrative,
                                        bullets,
                                        risks,
                                    }} />
                                );
                            })()}
                            {alphaProfile?.composite_alpha && (
                                <div>
                                    <h3 className="text-xs font-black uppercase tracking-widest text-gray-400 mb-3">
                                        CASE Breakdown
                                    </h3>
                                    <CompositeAlphaGauge data={alphaProfile.composite_alpha} />
                                </div>
                            )}
                            {ticker && (
                                <div>
                                    <h3 className="text-xs font-black uppercase tracking-widest text-gray-400 mb-3">
                                        Score History
                                    </h3>
                                    <ScoreHistoryChart ticker={ticker} />
                                </div>
                            )}
                        </div>
                    )}

                    {section === "backtest" && ticker && (
                        <BacktestEvidenceTab ticker={ticker} />
                    )}

                    {section === "signal_evidence" && alphaProfile && (
                        <SignalEvidenceTab
                            signals={alphaProfile.signals}
                            categorySummary={alphaProfile.category_summary}
                            ticker={ticker ?? ""}
                            llmMemo={alphaProfile.signal_map_memo}
                        />
                    )}

                    {section === "charts" && (
                        <div className="space-y-4">
                            {ticker && (
                                <div>
                                    <h3 className="text-xs font-black uppercase tracking-widest text-gray-400 mb-3">
                                        Price Chart
                                    </h3>
                                    <TradingViewChart symbol={ticker} />
                                </div>
                            )}
                            {combined.fundamentalDataReady?.cashflow_series &&
                                (combined.fundamentalDataReady.cashflow_series as any[]).length > 0 && (
                                    <div>
                                        <h3 className="text-xs font-black uppercase tracking-widest text-gray-400 mb-3">
                                            Cash Flow
                                        </h3>
                                        <CashFlowChart data={combined.fundamentalDataReady.cashflow_series as { year: string; fcf: number; revenue: number }[]} />
                                    </div>
                                )}
                        </div>
                    )}
                </div>
            </ErrorBoundary>
        </div>
    );
}
