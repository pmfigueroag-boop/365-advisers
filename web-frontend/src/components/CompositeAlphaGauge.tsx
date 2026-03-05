"use client";

import React from "react";
import { Activity, AlertTriangle, Sparkles } from "lucide-react";
import type { CompositeAlphaResponse } from "@/hooks/useAlphaSignals";

// ── Environment → visual styling ─────────────────────────────────────────────

const ENV_STYLE: Record<string, { color: string; bg: string; border: string; glow: string }> = {
    "Very Strong Opportunity": {
        color: "text-green-400",
        bg: "bg-green-500/10",
        border: "border-green-500/40",
        glow: "shadow-green-500/20",
    },
    "Strong Opportunity": {
        color: "text-emerald-400",
        bg: "bg-emerald-500/10",
        border: "border-emerald-500/30",
        glow: "shadow-emerald-500/15",
    },
    Neutral: {
        color: "text-yellow-400",
        bg: "bg-yellow-500/10",
        border: "border-yellow-500/30",
        glow: "shadow-yellow-500/10",
    },
    Weak: {
        color: "text-orange-400",
        bg: "bg-orange-500/10",
        border: "border-orange-500/30",
        glow: "shadow-orange-500/10",
    },
    "Negative Signal Environment": {
        color: "text-red-400",
        bg: "bg-red-500/10",
        border: "border-red-500/30",
        glow: "shadow-red-500/10",
    },
};

// ── Gauge arc drawing ────────────────────────────────────────────────────────

function GaugeArc({ score }: { score: number }) {
    const cx = 100;
    const cy = 95;
    const r = 75;
    const startAngle = Math.PI;
    const endAngle = 0;
    const totalAngle = startAngle - endAngle;
    const progress = Math.min(Math.max(score / 100, 0), 1);
    const progressAngle = startAngle - totalAngle * progress;

    // Background arc
    const bgX1 = cx + r * Math.cos(startAngle);
    const bgY1 = cy - r * Math.sin(startAngle);
    const bgX2 = cx + r * Math.cos(endAngle);
    const bgY2 = cy - r * Math.sin(endAngle);
    const bgPath = `M ${bgX1} ${bgY1} A ${r} ${r} 0 0 1 ${bgX2} ${bgY2}`;

    // Progress arc
    const pX1 = bgX1;
    const pY1 = bgY1;
    const pX2 = cx + r * Math.cos(progressAngle);
    const pY2 = cy - r * Math.sin(progressAngle);
    const largeArc = progress > 0.5 ? 1 : 0;
    const progressPath = `M ${pX1} ${pY1} A ${r} ${r} 0 ${largeArc} 1 ${pX2} ${pY2}`;

    // Gradient color based on score
    const gradientId = `gauge-grad-${Math.random().toString(36).slice(2, 8)}`;
    const getGradientColors = () => {
        if (score >= 80) return ["#10b981", "#34d399"];
        if (score >= 60) return ["#22c55e", "#6ee7b7"];
        if (score >= 40) return ["#eab308", "#fde047"];
        if (score >= 20) return ["#f97316", "#fdba74"];
        return ["#ef4444", "#fca5a5"];
    };
    const [c1, c2] = getGradientColors();

    return (
        <svg viewBox="0 0 200 110" className="w-full max-w-[200px]">
            <defs>
                <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor={c1} />
                    <stop offset="100%" stopColor={c2} />
                </linearGradient>
                <filter id="gauge-glow">
                    <feGaussianBlur stdDeviation="3" result="blur" />
                    <feMerge>
                        <feMergeNode in="blur" />
                        <feMergeNode in="SourceGraphic" />
                    </feMerge>
                </filter>
            </defs>
            {/* Background arc */}
            <path
                d={bgPath}
                fill="none"
                stroke="#21262d"
                strokeWidth="10"
                strokeLinecap="round"
            />
            {/* Progress arc */}
            {progress > 0.01 && (
                <path
                    d={progressPath}
                    fill="none"
                    stroke={`url(#${gradientId})`}
                    strokeWidth="10"
                    strokeLinecap="round"
                    filter="url(#gauge-glow)"
                    style={{
                        transition: "all 1s cubic-bezier(0.34, 1.56, 0.64, 1)",
                    }}
                />
            )}
            {/* Score text */}
            <text
                x={cx}
                y={cy - 10}
                textAnchor="middle"
                className="fill-white text-3xl font-black font-mono"
                style={{ fontSize: "32px" }}
            >
                {score.toFixed(0)}
            </text>
            <text
                x={cx}
                y={cy + 8}
                textAnchor="middle"
                className="fill-gray-500 text-xs font-bold uppercase"
                style={{ fontSize: "9px", letterSpacing: "0.15em" }}
            >
                / 100
            </text>
        </svg>
    );
}

// ── Category subscore bar ────────────────────────────────────────────────────

const CATEGORY_LABELS: Record<string, string> = {
    value: "Value",
    quality: "Quality",
    momentum: "Momentum",
    growth: "Growth",
    volatility: "Volatility",
    flow: "Flow",
    event: "Event",
    macro: "Macro",
};

const CATEGORY_COLORS: Record<string, string> = {
    value: "bg-emerald-500",
    quality: "bg-blue-500",
    momentum: "bg-purple-500",
    growth: "bg-rose-500",
    volatility: "bg-orange-500",
    flow: "bg-cyan-500",
    event: "bg-yellow-500",
    macro: "bg-amber-500",
};

// ── Main Component ───────────────────────────────────────────────────────────

interface CompositeAlphaGaugeProps {
    data: CompositeAlphaResponse | null | undefined;
}

export default function CompositeAlphaGauge({ data }: CompositeAlphaGaugeProps) {
    if (!data) return null;

    const style = ENV_STYLE[data.environment] || ENV_STYLE["Neutral"];
    const sortedCategories = Object.entries(data.subscores)
        .sort(([, a], [, b]) => b.score - a.score);

    return (
        <div
            className={`glass-card p-5 border ${style.border} ${style.glow} shadow-lg`}
            style={{ animation: "fadeSlideIn 0.4s ease both" }}
        >
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <Sparkles size={14} className="text-[#d4af37]" />
                    <h3 className="text-[9px] font-black uppercase tracking-[0.2em] text-gray-500">
                        Composite Alpha Score
                    </h3>
                </div>
                <span
                    className={`text-[8px] font-black uppercase tracking-wider px-2 py-1 rounded border ${style.color} ${style.bg} ${style.border}`}
                >
                    {data.environment}
                </span>
            </div>

            {/* Gauge + Summary */}
            <div className="flex flex-col sm:flex-row items-center gap-6 mb-5">
                <GaugeArc score={data.score} />
                <div className="flex-1 space-y-3 w-full">
                    <div className="flex items-center justify-between text-[10px]">
                        <span className="text-gray-500 uppercase font-bold tracking-wider">Active Categories</span>
                        <span className="text-white font-black font-mono">{data.active_categories} / 8</span>
                    </div>
                    {data.convergence_bonus > 0 && (
                        <div className="flex items-center justify-between text-[10px]">
                            <span className="text-gray-500 uppercase font-bold tracking-wider">Convergence Bonus</span>
                            <span className="text-green-400 font-black font-mono">+{data.convergence_bonus}</span>
                        </div>
                    )}
                    {data.cross_category_conflicts.length > 0 && (
                        <div className="flex items-start gap-2 mt-2 p-2 rounded bg-orange-500/5 border border-orange-500/20">
                            <AlertTriangle size={12} className="text-orange-400 mt-0.5 shrink-0" />
                            <div className="space-y-1">
                                {data.cross_category_conflicts.map((c, i) => (
                                    <p key={i} className="text-[9px] text-orange-400/80 leading-snug">{c}</p>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Category Bars */}
            <div className="space-y-2">
                <p className="text-[8px] font-black uppercase tracking-[0.2em] text-gray-600 mb-2">
                    Category Breakdown
                </p>
                {sortedCategories.map(([key, sub]) => (
                    <div key={key} className="flex items-center gap-3">
                        <span className="text-[9px] font-bold text-gray-400 w-16 shrink-0 uppercase tracking-wider">
                            {CATEGORY_LABELS[key] || key}
                        </span>
                        <div className="flex-1 h-2 rounded-full bg-[#21262d] overflow-hidden">
                            <div
                                className={`h-full rounded-full ${CATEGORY_COLORS[key] || "bg-gray-500"} transition-all duration-700 ease-out`}
                                style={{ width: `${Math.min(sub.score, 100)}%` }}
                            />
                        </div>
                        <span className="text-[10px] font-black text-gray-300 font-mono w-8 text-right">
                            {sub.score.toFixed(0)}
                        </span>
                        {sub.conflict_detected && (
                            <AlertTriangle size={10} className="text-orange-400" />
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}
