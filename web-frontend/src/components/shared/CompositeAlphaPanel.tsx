"use client";

/**
 * CompositeAlphaPanel.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Compact panel showing CASE score + environment + category breakdown.
 * Reusable across Terminal, Market Intelligence, and Deep Analysis.
 */

import { Layers, Sparkles } from "lucide-react";
import type { CompositeAlphaResponse } from "@/hooks/useAlphaSignals";

interface CompositeAlphaPanelProps {
    data: CompositeAlphaResponse | null | undefined;
    compact?: boolean;
    className?: string;
}

const ENV_STYLE: Record<string, { color: string; bg: string }> = {
    "Strong Alpha Environment": { color: "text-green-400", bg: "bg-green-500/10" },
    "Moderate Alpha Environment": { color: "text-blue-400", bg: "bg-blue-500/10" },
    "Transitional Environment": { color: "text-yellow-400", bg: "bg-yellow-500/10" },
    "Weak Alpha Environment": { color: "text-orange-400", bg: "bg-orange-500/10" },
    "Negative Signal Environment": { color: "text-red-400", bg: "bg-red-500/10" },
};

const CAT_COLORS: Record<string, string> = {
    value: "bg-emerald-500",
    quality: "bg-blue-500",
    momentum: "bg-purple-500",
    technical: "bg-cyan-500",
    sentiment: "bg-pink-500",
    growth: "bg-rose-500",
    risk: "bg-orange-500",
    macro: "bg-amber-500",
};

export default function CompositeAlphaPanel({ data, compact = false, className = "" }: CompositeAlphaPanelProps) {
    if (!data) return null;

    const envStyle = ENV_STYLE[data.environment] ?? { color: "text-gray-400", bg: "bg-gray-500/10" };

    return (
        <div className={`glass-card p-4 border-[#30363d] ${className}`}>
            {/* Header */}
            <div className="flex items-center gap-2 mb-3">
                <Sparkles size={12} className="text-[#d4af37]" />
                <span className="text-[9px] font-black uppercase tracking-widest text-gray-400">
                    Composite Alpha
                </span>
            </div>

            {/* Score + Environment */}
            <div className="flex items-center gap-4 mb-4">
                <div className="relative">
                    <div className="w-16 h-16 rounded-full border-2 border-[#d4af37]/30 flex items-center justify-center bg-[#d4af37]/5">
                        <span className="text-xl font-black text-[#d4af37]" style={{ fontFamily: "var(--font-data)" }}>
                            {data.score.toFixed(0)}
                        </span>
                    </div>
                </div>
                <div>
                    <span className={`text-[10px] font-black px-2 py-1 rounded ${envStyle.color} ${envStyle.bg}`}>
                        {data.environment}
                    </span>
                    <div className="flex items-center gap-1.5 mt-1.5">
                        <Layers size={9} className="text-gray-600" />
                        <span className="text-[9px] text-gray-600">
                            {data.active_categories} / {Object.keys(data.subscores).length} categories active
                        </span>
                    </div>
                </div>
            </div>

            {/* Category bars */}
            {!compact && (
                <div className="space-y-2">
                    {Object.entries(data.subscores).map(([cat, sub]) => (
                        <div key={cat} className="flex items-center gap-2">
                            <span className="text-[9px] text-gray-500 w-16 truncate capitalize">{cat}</span>
                            <div className="flex-1 bg-[#161b22] rounded-full h-1.5 overflow-hidden">
                                <div
                                    className={`h-full rounded-full ${CAT_COLORS[cat] ?? "bg-gray-500"} transition-all duration-500`}
                                    style={{ width: `${Math.min(sub.score ?? 0, 100)}%` }}
                                />
                            </div>
                            <span className="text-[9px] font-mono text-gray-500 w-6 text-right">{(sub.score ?? 0).toFixed(0)}</span>
                        </div>
                    ))}
                </div>
            )}

            {/* Decay info */}
            {data.decay && (
                <div className="flex items-center justify-between mt-3 pt-2 border-t border-[#30363d]">
                    <span className="text-[8px] text-gray-600 uppercase">Freshness</span>
                    <span className={`text-[9px] font-black uppercase ${data.decay.freshness_level === "fresh" ? "text-green-400" :
                        data.decay.freshness_level === "aging" ? "text-yellow-400" : "text-red-400"
                        }`}>
                        {data.decay.freshness_level}
                    </span>
                </div>
            )}
        </div>
    );
}
