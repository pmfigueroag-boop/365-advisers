"use client";

/**
 * TopSignalsList.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Displays top N fired signals in a compact, ranked list format.
 * Part of the Tier 2 "Insight" layer in the progressive disclosure model.
 */

import { TrendingUp, TrendingDown, Minus, Radio } from "lucide-react";
import InfoTooltip from "@/components/shared/InfoTooltip";
import type { EvaluatedSignal } from "@/hooks/useAlphaSignals";

interface TopSignalsListProps {
    signals: EvaluatedSignal[];
    maxSignals?: number;
    totalFired?: number;
    totalSignals?: number;
}

export default function TopSignalsList({
    signals,
    maxSignals = 6,
    totalFired,
    totalSignals,
}: TopSignalsListProps) {
    const firedSignals = signals
        .filter((s) => s.fired)
        .sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0))
        .slice(0, maxSignals);

    if (firedSignals.length === 0) {
        return (
            <div className="flex items-center gap-2 text-gray-600 text-xs py-3">
                <Radio size={12} className="text-gray-700" />
                <span>No signals fired</span>
            </div>
        );
    }

    const strengthIcon = (s: string) => {
        if (s === "strong") return <TrendingUp size={10} className="text-green-400" />;
        if (s === "moderate") return <Minus size={10} className="text-yellow-400" />;
        return <TrendingDown size={10} className="text-gray-500" />;
    };

    const strengthColor = (s: string) => {
        if (s === "strong") return "text-green-400 bg-green-500/12";
        if (s === "moderate") return "text-yellow-400 bg-yellow-500/12";
        return "text-gray-500 bg-gray-500/12";
    };

    return (
        <div>
            {/* Header */}
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    <Radio size={12} className="text-[#d4af37]" />
                    <InfoTooltip text="Strongest active alpha signals for this asset, ranked by confidence. Each signal comes from quantitative factors like momentum, value, quality, or growth." position="bottom">
                        <span className="text-[10px] font-black uppercase tracking-widest text-gray-400">
                            Top Signals
                        </span>
                    </InfoTooltip>
                </div>
                {totalFired != null && totalSignals != null && (
                    <span className="text-[9px] font-mono text-gray-600">
                        {totalFired}/{totalSignals} active
                    </span>
                )}
            </div>

            {/* Signal rows */}
            <div className="space-y-1.5">
                {firedSignals.map((sig, idx) => (
                    <div
                        key={sig.signal_id}
                        className="flex items-center gap-2.5 px-2 py-1.5 rounded-lg hover:bg-white/[0.02] transition-colors group"
                    >
                        {/* Rank */}
                        <span className="text-[9px] font-mono text-gray-700 w-4 text-right">
                            {idx + 1}
                        </span>

                        {/* Direction icon */}
                        {strengthIcon(sig.strength)}

                        {/* Signal name */}
                        <span className="text-[11px] text-gray-300 flex-1 truncate group-hover:text-white transition-colors">
                            {sig.signal_name}
                        </span>

                        {/* Strength badge */}
                        <span className={`text-[8px] font-black uppercase px-1.5 py-0.5 rounded ${strengthColor(sig.strength)}`}>
                            {sig.strength}
                        </span>

                        {/* Confidence */}
                        <span className="text-[10px] font-mono text-gray-500 w-10 text-right">
                            {(sig.confidence * 100).toFixed(0)}%
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
}
