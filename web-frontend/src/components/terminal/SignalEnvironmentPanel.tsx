"use client";

/**
 * SignalEnvironmentPanel.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Displays the current signal environment context:
 * CASE score, regime, confidence, crowding risk, and active categories.
 */

import { Radio, Layers, Shield, AlertTriangle, Activity } from "lucide-react";
import InfoTooltip from "@/components/shared/InfoTooltip";
import type { SignalProfileResponse } from "@/hooks/useAlphaSignals";
import type { CrowdingAssessment } from "@/hooks/useCrowding";

interface SignalEnvironmentPanelProps {
    alphaProfile: SignalProfileResponse | null;
    crowding?: CrowdingAssessment | null;
    className?: string;
}

const ENV_STYLE: Record<string, { color: string; bg: string; border: string }> = {
    "Strong Alpha Environment": { color: "text-green-400", bg: "bg-green-500/10", border: "border-green-500/30" },
    "Moderate Alpha Environment": { color: "text-blue-400", bg: "bg-blue-500/10", border: "border-blue-500/30" },
    "Transitional Environment": { color: "text-yellow-400", bg: "bg-yellow-500/10", border: "border-yellow-500/30" },
    "Weak Alpha Environment": { color: "text-orange-400", bg: "bg-orange-500/10", border: "border-orange-500/30" },
    "Negative Signal Environment": { color: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/30" },
};

export default function SignalEnvironmentPanel({ alphaProfile, crowding, className = "" }: SignalEnvironmentPanelProps) {
    if (!alphaProfile) return null;

    const composite = alphaProfile.composite_alpha;
    const environment = composite?.environment ?? "Unknown";
    const envCfg = ENV_STYLE[environment] ?? { color: "text-gray-400", bg: "bg-gray-500/10", border: "border-gray-500/30" };

    const caseScore = composite?.score ?? 0;
    const activeCats = composite?.active_categories ?? 0;
    const totalCats = composite ? Object.keys(composite.subscores).length : 0;
    const firedPct = alphaProfile.total_signals > 0
        ? Math.round((alphaProfile.fired_signals / alphaProfile.total_signals) * 100)
        : 0;

    const crowdingLevel = crowding?.risk_level ?? null;
    const crowdingColor = crowdingLevel === "low" ? "text-green-400" : crowdingLevel === "moderate" ? "text-yellow-400" :
        crowdingLevel === "high" ? "text-orange-400" : crowdingLevel === "extreme" ? "text-red-400" : "text-gray-500";

    return (
        <div className={`glass-card p-5 border-[#30363d] ${className}`}>
            <div className="flex items-center gap-2 mb-4">
                <Radio size={12} className="text-[#d4af37]" />
                <InfoTooltip text="Overview of active alpha signals. Shows the quantitative signal market strength for this asset." position="bottom">
                    <span className="text-[9px] font-black uppercase tracking-widest text-gray-400">
                        Signal Environment
                    </span>
                </InfoTooltip>
            </div>

            <div className="space-y-4">
                {/* CASE Score */}
                <div>
                    <div className="flex items-center justify-between mb-1">
                        <InfoTooltip text="CASE Score (Composite Alpha Score Engine): weighted aggregate of 50+ alpha signals across 8 categories." showIcon={false}>
                            <span className="text-[9px] uppercase text-gray-600">Composite Alpha</span>
                        </InfoTooltip>
                        <span className="text-lg font-black text-[#d4af37]" style={{ fontFamily: "var(--font-data)" }}>
                            {caseScore.toFixed(0)}
                        </span>
                    </div>
                    <div className="w-full bg-[#161b22] rounded-full h-1.5 overflow-hidden">
                        <div
                            className="h-full rounded-full bg-gradient-to-r from-[#d4af37] to-[#e8c84a] transition-all duration-700"
                            style={{ width: `${Math.min(caseScore, 100)}%` }}
                        />
                    </div>
                </div>

                {/* Environment Badge */}
                <div className="flex items-center justify-between">
                    <InfoTooltip text="Current market regime for signals: strong, moderate, transitional, weak, or negative. Defines investment environment quality." showIcon={false}>
                        <span className="text-[9px] uppercase text-gray-600">Regime</span>
                    </InfoTooltip>
                    <span className={`text-[9px] font-black px-2 py-0.5 rounded border ${envCfg.color} ${envCfg.bg} ${envCfg.border}`}>
                        {environment.replace(" Environment", "")}
                    </span>
                </div>

                {/* Signal Activity */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                        <Activity size={10} className="text-emerald-400" />
                        <InfoTooltip text="Number of alpha signals fired vs. total available. Higher percentage = more factors aligned in favor." showIcon={false}>
                            <span className="text-[9px] uppercase text-gray-600">Signals Active</span>
                        </InfoTooltip>
                    </div>
                    <span className="text-[10px] font-mono text-gray-300">
                        {alphaProfile.fired_signals}/{alphaProfile.total_signals} ({firedPct}%)
                    </span>
                </div>

                {/* Categories */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                        <Layers size={10} className="text-blue-400" />
                        <InfoTooltip text="Signal categories with at least one active signal (e.g., momentum, value, quality, growth, volatility)." showIcon={false}>
                            <span className="text-[9px] uppercase text-gray-600">Categories</span>
                        </InfoTooltip>
                    </div>
                    <span className="text-[10px] font-mono text-gray-300">
                        {activeCats}/{totalCats} active
                    </span>
                </div>

                {/* Crowding */}
                {crowdingLevel && (
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5">
                            {crowdingLevel === "high" || crowdingLevel === "extreme"
                                ? <AlertTriangle size={10} className="text-orange-400" />
                                : <Shield size={10} className="text-green-400" />
                            }
                            <InfoTooltip text="Crowding risk: measures if too many investors hold the same position. High crowding = greater risk of abrupt reversal." showIcon={false}>
                                <span className="text-[9px] uppercase text-gray-600">Crowding</span>
                            </InfoTooltip>
                        </div>
                        <span className={`text-[10px] font-black uppercase ${crowdingColor}`}>
                            {crowdingLevel}
                        </span>
                    </div>
                )}

                {/* Freshness */}
                {composite?.decay && (
                    <div className="flex items-center justify-between">
                        <InfoTooltip text="Alpha signal freshness. 'Fresh' = recent and reliable data. 'Stale' = aged signals that lose predictive power." showIcon={false}>
                            <span className="text-[9px] uppercase text-gray-600">Freshness</span>
                        </InfoTooltip>
                        <span className={`text-[9px] font-black uppercase ${composite.decay.freshness_level === "fresh" ? "text-green-400" :
                            composite.decay.freshness_level === "aging" ? "text-yellow-400" : "text-red-400"
                            }`}>
                            {composite.decay.freshness_level}
                        </span>
                    </div>
                )}
            </div>
        </div>
    );
}
