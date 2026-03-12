"use client";

/**
 * AnalyticsAccordion.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Level 3 — Analytics.
 *
 * Collapsed by default. For advanced users who want proof: signals, agents,
 * CASE breakdown, technical indicators, charts.
 */

import { useState } from "react";
import {
    ChevronRight,
    Radio,
    Users,
    Activity,
    BarChart3,
    LineChart,
    Loader2,
} from "lucide-react";
import type { CombinedState } from "@/hooks/useCombinedStream";
import type { SignalProfileResponse, SignalStatus } from "@/hooks/useAlphaSignals";
import AlphaSignalsView from "./AlphaSignalsView";
import IndicatorGrid from "./IndicatorGrid";
import ResearchMemoCard from "./ResearchMemoCard";
import CompositeAlphaGauge from "./CompositeAlphaGauge";
import TradingViewChart from "./TradingViewChart";
import { CashFlowChart } from "./Charts";

// ─── Accordion Section ────────────────────────────────────────────────────────

function AccordionSection({
    id,
    icon,
    label,
    badge,
    children,
    openId,
    onToggle,
}: {
    id: string;
    icon: React.ReactNode;
    label: string;
    badge?: string;
    children: React.ReactNode;
    openId: string | null;
    onToggle: (id: string) => void;
}) {
    const isOpen = openId === id;
    return (
        <div className="border-b border-[#30363d] last:border-b-0">
            <button
                onClick={() => onToggle(id)}
                className="w-full flex items-center gap-3 px-5 py-3.5 hover:bg-white/[0.02] transition-colors"
            >
                <ChevronRight
                    size={12}
                    className={`text-gray-600 transition-transform duration-200 ${isOpen ? "rotate-90" : ""}`}
                />
                <span className="text-gray-600">{icon}</span>
                <span className="text-[10px] font-black uppercase tracking-widest text-gray-500">{label}</span>
                {badge && (
                    <span className="ml-auto text-[9px] font-mono bg-[#30363d] text-gray-400 rounded px-2 py-0.5">
                        {badge}
                    </span>
                )}
            </button>
            {isOpen && (
                <div className="px-5 pb-5 pt-1" style={{ animation: "fadeSlideIn 0.25s ease both" }}>
                    {children}
                </div>
            )}
        </div>
    );
}

// ─── Component ────────────────────────────────────────────────────────────────

interface AnalyticsAccordionProps {
    combined: CombinedState;
    alphaProfile: SignalProfileResponse | null;
    alphaStatus: SignalStatus;
    alphaError: string | null;
    onEvaluateSignals?: () => void;
}

export default function AnalyticsAccordion({
    combined,
    alphaProfile,
    alphaStatus,
    alphaError,
    onEvaluateSignals,
}: AnalyticsAccordionProps) {
    const [openSection, setOpenSection] = useState<string | null>(null);

    const { fundamentalDataReady, agentMemos, committee, researchMemo, technical, ticker } = combined;

    const toggle = (id: string) => {
        setOpenSection((prev) => (prev === id ? null : id));
    };

    const firedSignals = alphaProfile?.fired_signals ?? 0;
    const totalSignals = alphaProfile?.total_signals ?? 0;
    const compositeAlpha = alphaProfile?.composite_alpha;

    return (
        <div className="glass-card border-[#30363d] overflow-hidden">
            {/* Section header */}
            <div className="flex items-center gap-2 px-5 py-3.5 border-b border-[#30363d] bg-[#0d1117]/50">
                <BarChart3 size={13} className="text-gray-600" />
                <span className="text-[10px] font-black uppercase tracking-widest text-gray-600">
                    Advanced Analytics
                </span>
                <span className="ml-auto text-[8px] font-mono text-gray-700">
                    Click to expand
                </span>
            </div>

            {/* Alpha Signals */}
            <AccordionSection
                id="signals"
                icon={<Radio size={13} />}
                label="Alpha Signals"
                badge={firedSignals > 0 ? `${firedSignals}/${totalSignals} fired` : undefined}
                openId={openSection}
                onToggle={toggle}
            >
                <AlphaSignalsView
                    profile={alphaProfile}
                    status={alphaStatus}
                    error={alphaError}
                    onEvaluate={onEvaluateSignals}
                />
            </AccordionSection>

            {/* CASE Breakdown */}
            {compositeAlpha && (
                <AccordionSection
                    id="case"
                    icon={<Activity size={13} />}
                    label="CASE Breakdown"
                    badge={`Score: ${compositeAlpha.score.toFixed(0)}`}
                    openId={openSection}
                    onToggle={toggle}
                >
                    <CompositeAlphaGauge data={compositeAlpha} />
                </AccordionSection>
            )}

            {/* Agent Reports */}
            {agentMemos.length > 0 && (
                <AccordionSection
                    id="agents"
                    icon={<Users size={13} />}
                    label="Agent Reports"
                    badge={`${agentMemos.length} analysts`}
                    openId={openSection}
                    onToggle={toggle}
                >
                    <ResearchMemoCard
                        dataReady={fundamentalDataReady}
                        agentMemos={agentMemos}
                        committee={committee}
                        researchMemo={researchMemo}
                        agentCount={agentMemos.length}
                        totalAgents={4}
                        status={combined.status === "complete" ? "complete" : "analyzing"}
                    />
                </AccordionSection>
            )}

            {/* Technical Indicators */}
            {technical && (
                <AccordionSection
                    id="technical"
                    icon={<Activity size={13} />}
                    label="Technical Indicators"
                    badge={`Score: ${technical.summary?.technical_score?.toFixed(1) ?? "—"}`}
                    openId={openSection}
                    onToggle={toggle}
                >
                    <IndicatorGrid data={technical} technicalMemo={combined.technicalMemo} />
                </AccordionSection>
            )}

            {/* Charts */}
            {ticker && (
                <AccordionSection
                    id="charts"
                    icon={<LineChart size={13} />}
                    label="Charts"
                    badge="TradingView · Cash Flow"
                    openId={openSection}
                    onToggle={toggle}
                >
                    <div className="space-y-4">
                        <div className="glass-card p-4 border-[#30363d]">
                            <TradingViewChart symbol={ticker} />
                        </div>
                        {fundamentalDataReady?.cashflow_series && fundamentalDataReady.cashflow_series.length > 0 && (
                            <div className="glass-card p-4 border-[#30363d]">
                                <CashFlowChart data={fundamentalDataReady.cashflow_series as { year: string; fcf: number; revenue: number }[]} />
                            </div>
                        )}
                    </div>
                </AccordionSection>
            )}
        </div>
    );
}
