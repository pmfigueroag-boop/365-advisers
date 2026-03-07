"use client";

/**
 * DeepAnalysisView.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * 6-section tabbed deep-dive into a single asset's analysis data.
 *
 * Sections: Thesis · Alpha Signals · Technical · Fundamental · Evidence · Charts
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

// ─── Types ────────────────────────────────────────────────────────────────────

type Section = "thesis" | "signals" | "technical" | "fundamental" | "evidence" | "backtest" | "signal_evidence" | "charts";

const SECTIONS: { id: Section; label: string; icon: React.ReactNode }[] = [
    { id: "thesis", label: "Thesis", icon: <Lightbulb size={12} /> },
    { id: "signals", label: "Alpha Signals", icon: <Radio size={12} /> },
    { id: "technical", label: "Technical", icon: <Activity size={12} /> },
    { id: "fundamental", label: "Fundamental", icon: <Users size={12} /> },
    { id: "evidence", label: "Evidence", icon: <BarChart3 size={12} /> },
    { id: "backtest", label: "Backtest", icon: <BarChart3 size={12} /> },
    { id: "signal_evidence", label: "Signal Map", icon: <Radio size={12} /> },
    { id: "charts", label: "Charts", icon: <LineChart size={12} /> },
];

interface DeepAnalysisViewProps {
    combined: CombinedState;
    alphaProfile: SignalProfileResponse | null;
    alphaStatus: SignalStatus;
    alphaError: string | null;
    onEvaluateSignals: () => void;
    onBack: () => void;
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function DeepAnalysisView({
    combined,
    alphaProfile,
    alphaStatus,
    alphaError,
    onEvaluateSignals,
    onBack,
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
                        title="Back to Terminal"
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
            </div>

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
                <div className="glass-card border-[#30363d] p-5">
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
                        <IndicatorGrid data={combined.technical} />
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
