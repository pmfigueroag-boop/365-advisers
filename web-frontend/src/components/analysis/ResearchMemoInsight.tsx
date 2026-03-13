"use client";

/**
 * ResearchMemoInsight.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Reusable data-driven research memo card for analysis tabs.
 * Renders an interpretive narrative with signal badge, key bullets,
 * and optional risk factors — no LLM required.
 */

import {
    FileText,
    TrendingUp,
    TrendingDown,
    Minus,
    AlertTriangle,
    CheckCircle2,
    Info,
} from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface MemoInsight {
    title: string;
    signal: "BULLISH" | "BEARISH" | "NEUTRAL";
    conviction: "HIGH" | "MEDIUM" | "LOW";
    narrative: string;
    bullets: string[];
    risks?: string[];
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function signalBadge(signal: string) {
    switch (signal) {
        case "BULLISH":
            return {
                icon: <TrendingUp size={11} />,
                color: "text-green-400",
                bg: "bg-green-500/10 border-green-500/30",
            };
        case "BEARISH":
            return {
                icon: <TrendingDown size={11} />,
                color: "text-red-400",
                bg: "bg-red-500/10 border-red-500/30",
            };
        default:
            return {
                icon: <Minus size={11} />,
                color: "text-yellow-400",
                bg: "bg-yellow-500/10 border-yellow-500/30",
            };
    }
}

function convictionDots(conviction: string) {
    const level = conviction === "HIGH" ? 3 : conviction === "MEDIUM" ? 2 : 1;
    return (
        <span className="flex gap-0.5">
            {[1, 2, 3].map((i) => (
                <span
                    key={i}
                    className={`w-1.5 h-1.5 rounded-full ${
                        i <= level ? "bg-[#d4af37]" : "bg-[#30363d]"
                    }`}
                />
            ))}
        </span>
    );
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function ResearchMemoInsight({ memo }: { memo: MemoInsight }) {
    const badge = signalBadge(memo.signal);

    return (
        <div
            className="glass-card border-[#30363d] p-4 space-y-3"
            style={{ animation: "fadeSlideIn 0.25s ease both" }}
        >
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <FileText size={13} className="text-[#d4af37]" />
                    <h4 className="text-[10px] font-black uppercase tracking-widest text-gray-400">
                        {memo.title}
                    </h4>
                </div>
                <div className="flex items-center gap-2">
                    <span
                        className={`flex items-center gap-1 text-[9px] font-black px-2 py-0.5 rounded border uppercase ${badge.bg} ${badge.color}`}
                    >
                        {badge.icon}
                        {memo.signal}
                    </span>
                    <div className="flex items-center gap-1">
                        {convictionDots(memo.conviction)}
                        <span className="text-[7px] font-bold text-gray-600 uppercase">
                            {memo.conviction}
                        </span>
                    </div>
                </div>
            </div>

            {/* Narrative */}
            <p className="text-[11px] text-gray-300 leading-relaxed">
                {memo.narrative}
            </p>

            {/* Key Points */}
            {memo.bullets.length > 0 && (
                <div className="space-y-1.5">
                    {memo.bullets.map((bullet, i) => (
                        <div key={i} className="flex items-start gap-2">
                            <CheckCircle2
                                size={10}
                                className="text-[#d4af37] mt-0.5 flex-shrink-0"
                            />
                            <span className="text-[10px] text-gray-400 leading-relaxed">
                                {bullet}
                            </span>
                        </div>
                    ))}
                </div>
            )}

            {/* Risk Factors */}
            {memo.risks && memo.risks.length > 0 && (
                <div className="pt-2 border-t border-[#30363d]/50 space-y-1.5">
                    <div className="flex items-center gap-1.5">
                        <AlertTriangle size={10} className="text-orange-400" />
                        <span className="text-[8px] font-black uppercase tracking-wider text-gray-600">
                            Consideraciones
                        </span>
                    </div>
                    {memo.risks.map((risk, i) => (
                        <div key={i} className="flex items-start gap-2">
                            <Info
                                size={9}
                                className="text-orange-400/60 mt-0.5 flex-shrink-0"
                            />
                            <span className="text-[9px] text-gray-500 leading-relaxed">
                                {risk}
                            </span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
