"use client";

/**
 * OpportunityVerdict.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Decision-first verdict panel for the Investment Terminal.
 * Replaces VerdictHero with an opportunity-centric layout:
 *   Opportunity Score → Verdict → Allocation → Confidence → Risk
 */

import { TrendingUp, TrendingDown, Minus, Shield, Target, DollarSign } from "lucide-react";
import OpportunityScoreGauge from "@/components/shared/OpportunityScoreGauge";
import ConfidenceMeter from "@/components/shared/ConfidenceMeter";
import ScoreRing from "@/components/shared/ScoreRing";
import SignalBadge from "@/components/shared/SignalBadge";
import InfoTooltip from "@/components/shared/InfoTooltip";
import type { CombinedState } from "@/hooks/useCombinedStream";
import type { SignalProfileResponse } from "@/hooks/useAlphaSignals";

// ─── Types ────────────────────────────────────────────────────────────────────

interface OpportunityVerdictProps {
    combined: CombinedState;
    alphaProfile: SignalProfileResponse | null;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function riskColor(risk: string) {
    const r = risk.toLowerCase();
    if (r.includes("low")) return "text-green-400";
    if (r.includes("moderate")) return "text-yellow-400";
    if (r.includes("high")) return "text-red-400";
    if (r.includes("extreme")) return "text-red-500";
    return "text-gray-400";
}

function verdictIcon(position: string) {
    const p = position.toUpperCase();
    if (p.includes("BUY")) return <TrendingUp size={18} className="text-green-400" />;
    if (p.includes("SELL")) return <TrendingDown size={18} className="text-red-400" />;
    return <Minus size={18} className="text-yellow-400" />;
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function OpportunityVerdict({ combined, alphaProfile }: OpportunityVerdictProps) {
    const { decision, opportunity, positionSizing, committee, fundamentalDataReady, ticker } = combined;

    if (!decision || !ticker) return null;

    const oppScore = opportunity?.opportunity_score ?? committee?.score ?? 0;
    const caseScore = alphaProfile?.composite_alpha?.score ?? 0;
    const confidence = decision.confidence_score;
    const allocation = positionSizing?.suggested_allocation ?? 0;
    const riskLevel = positionSizing?.risk_level ?? "unknown";
    const position = decision.investment_position;
    const name = fundamentalDataReady?.name ?? ticker;

    return (
        <div
            className="glass-card border-[#30363d] overflow-hidden"
            style={{ animation: "verdictReveal 0.5s ease both" }}
        >
            {/* Gold accent bar */}
            <div className="h-1 bg-gradient-to-r from-[#d4af37] to-[#e8c84a]" />

            <div className="p-6">
                {/* Ticker + Name */}
                <div className="flex items-start justify-between mb-5">
                    <div>
                        <div className="flex items-center gap-3">
                            <h2 className="text-2xl font-black tracking-tight text-white" style={{ fontFamily: "var(--font-data)" }}>
                                {ticker}
                            </h2>
                            <SignalBadge signal={position} size="md" />
                        </div>
                        <p className="text-xs text-gray-500 mt-0.5">{name}</p>
                    </div>
                    {verdictIcon(position)}
                </div>

                {/* Score Row — Opportunity + CASE + Committee */}
                <div className="flex items-center gap-8 mb-6">
                    <InfoTooltip text="Composite score 0–100 evaluating business quality, valuation, financial strength, and market behavior." showIcon={false}>
                        <OpportunityScoreGauge score={oppScore} size={100} label="Opportunity" />
                    </InfoTooltip>
                    <InfoTooltip text="Composite Alpha Score Engine — aggregated score from 50+ alpha signals across 8 categories (momentum, value, quality, etc.)." showIcon={false}>
                        <ScoreRing value={caseScore} max={100} size={64} label="CASE" color="#d4af37" />
                    </InfoTooltip>
                    <InfoTooltip text="Investment Committee verdict (4 AI analysts). Score 0–10 based on multi-agent fundamental analysis." showIcon={false}>
                        <ScoreRing value={committee?.score ?? 0} max={10} size={64} label="Committee" />
                    </InfoTooltip>
                </div>

                {/* Key Metrics Strip */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-5">
                    <div className="bg-[#161b22] rounded-xl p-3 border border-[#30363d]">
                        <div className="flex items-center gap-1.5 mb-1">
                            <Target size={10} className="text-[#d4af37]" />
                            <InfoTooltip text="Suggested portfolio percentage to allocate to this position, based on opportunity score and risk conditions." position="bottom">
                                <span className="text-[8px] font-black uppercase tracking-wider text-gray-600">Allocation</span>
                            </InfoTooltip>
                        </div>
                        <p className="text-lg font-black text-white" style={{ fontFamily: "var(--font-data)" }}>
                            {allocation.toFixed(1)}%
                        </p>
                    </div>

                    <div className="bg-[#161b22] rounded-xl p-3 border border-[#30363d]">
                        <div className="flex items-center gap-1.5 mb-1">
                            <Shield size={10} className="text-blue-400" />
                            <InfoTooltip text="Overall position risk level, derived from asset volatility and current market conditions." position="bottom">
                                <span className="text-[8px] font-black uppercase tracking-wider text-gray-600">Risk Level</span>
                            </InfoTooltip>
                        </div>
                        <p className={`text-sm font-black uppercase ${riskColor(riskLevel)}`}>
                            {riskLevel}
                        </p>
                    </div>

                    <div className="bg-[#161b22] rounded-xl p-3 border border-[#30363d]">
                        <div className="flex items-center gap-1.5 mb-1">
                            <DollarSign size={10} className="text-emerald-400" />
                            <InfoTooltip text="System conviction level: how strong the investment signal is. High = multiple factors aligned." position="bottom">
                                <span className="text-[8px] font-black uppercase tracking-wider text-gray-600">Conviction</span>
                            </InfoTooltip>
                        </div>
                        <p className="text-sm font-black text-white capitalize">
                            {positionSizing?.conviction_level ?? "—"}
                        </p>
                    </div>

                    <div className="bg-[#161b22] rounded-xl p-3 border border-[#30363d]">
                        <div className="flex items-center gap-1.5 mb-1">
                            <InfoTooltip text="Recommended action from the Position Sizing model: accumulate, initiate position, reduce, etc." position="bottom">
                                <span className="text-[8px] font-black uppercase tracking-wider text-gray-600">Action</span>
                            </InfoTooltip>
                        </div>
                        <p className="text-sm font-black text-[#d4af37]">
                            {positionSizing?.recommended_action ?? "—"}
                        </p>
                    </div>
                </div>

                {/* Confidence Meter */}
                <InfoTooltip text="Aggregated system confidence in its verdict. Combines fundamental committee consensus with technical analysis." showIcon={false}>
                    <ConfidenceMeter value={confidence} label="System Confidence" />
                </InfoTooltip>

                {/* Investment Thesis (collapsed) */}
                {decision.cio_memo.thesis_summary && (
                    <div className="mt-5 pt-4 border-t border-[#30363d]">
                        <InfoTooltip text="Investment thesis summary generated by the AI CIO (Chief Investment Officer) after synthesizing all analyses." position="bottom">
                            <p className="text-[9px] font-black uppercase tracking-widest text-gray-600 mb-2">Investment Thesis</p>
                        </InfoTooltip>
                        <p className="text-xs text-gray-300 leading-relaxed" style={{ fontFamily: "var(--font-insight)" }}>
                            {decision.cio_memo.thesis_summary}
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
}
