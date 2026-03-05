"use client";

import React from "react";
import {
    Activity,
    TrendingUp,
    TrendingDown,
    Shield,
    Zap,
    BarChart3,
    Radio,
    Loader2,
    AlertTriangle,
    Rocket,
    Globe,
} from "lucide-react";
import type {
    SignalProfileResponse,
    CategoryScore,
    EvaluatedSignal,
} from "@/hooks/useAlphaSignals";

// ── Category config ─────────────────────────────────────────────────────────

const CATEGORY_CONFIG: Record<
    string,
    { label: string; color: string; bg: string; border: string; icon: React.ReactNode }
> = {
    value: {
        label: "Value",
        color: "text-emerald-400",
        bg: "bg-emerald-500/10",
        border: "border-emerald-500/30",
        icon: <Shield size={11} />,
    },
    quality: {
        label: "Quality",
        color: "text-blue-400",
        bg: "bg-blue-500/10",
        border: "border-blue-500/30",
        icon: <Zap size={11} />,
    },
    momentum: {
        label: "Momentum",
        color: "text-orange-400",
        bg: "bg-orange-500/10",
        border: "border-orange-500/30",
        icon: <TrendingUp size={11} />,
    },
    volatility: {
        label: "Volatility",
        color: "text-yellow-400",
        bg: "bg-yellow-500/10",
        border: "border-yellow-500/30",
        icon: <Activity size={11} />,
    },
    flow: {
        label: "Flow",
        color: "text-cyan-400",
        bg: "bg-cyan-500/10",
        border: "border-cyan-500/30",
        icon: <BarChart3 size={11} />,
    },
    event: {
        label: "Event",
        color: "text-purple-400",
        bg: "bg-purple-500/10",
        border: "border-purple-500/30",
        icon: <Radio size={11} />,
    },
    growth: {
        label: "Growth",
        color: "text-rose-400",
        bg: "bg-rose-500/10",
        border: "border-rose-500/30",
        icon: <Rocket size={11} />,
    },
    macro: {
        label: "Macro",
        color: "text-amber-400",
        bg: "bg-amber-500/10",
        border: "border-amber-500/30",
        icon: <Globe size={11} />,
    },
};

const STRENGTH_STYLE: Record<string, string> = {
    strong: "text-green-400 bg-green-500/15",
    moderate: "text-yellow-400 bg-yellow-500/15",
    weak: "text-gray-500 bg-gray-500/15",
};

const CONFIDENCE_DOTS: Record<string, number> = {
    high: 4,
    medium: 2,
    low: 1,
};

// ── Props ─────────────────────────────────────────────────────────────────────

interface AlphaSignalsViewProps {
    profile: SignalProfileResponse | null;
    status: "idle" | "loading" | "done" | "error";
    error: string | null;
    onEvaluate?: () => void;
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function AlphaSignalsView({
    profile,
    status,
    error,
    onEvaluate,
}: AlphaSignalsViewProps) {
    if (status === "loading") {
        return (
            <div className="flex flex-col items-center justify-center py-8 gap-2 text-gray-500">
                <Loader2 size={20} className="animate-spin text-[#d4af37]" />
                <p className="text-[10px] font-bold">Evaluating signals…</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="mx-3 mt-2 p-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-[10px] flex items-center gap-1.5">
                <AlertTriangle size={12} />
                {error}
            </div>
        );
    }

    if (!profile) {
        return (
            <div className="flex flex-col items-center justify-center h-full px-4 py-8 text-center gap-2">
                <Radio size={24} className="text-[#30363d]" />
                <p className="text-[10px] text-gray-600 leading-relaxed">
                    Analyze a ticker to view its alpha signals
                </p>
                {onEvaluate && (
                    <button
                        onClick={onEvaluate}
                        className="text-[9px] font-bold text-[#d4af37] hover:text-[#f0c040] transition-colors"
                    >
                        Evaluate Signals
                    </button>
                )}
            </div>
        );
    }

    const { composite } = profile;
    const allCategories = ["value", "quality", "growth", "momentum", "volatility", "flow", "event", "macro"];

    return (
        <div className="flex flex-col gap-1.5 px-2 py-2">
            {/* Header */}
            <div className="flex items-center justify-between px-1">
                <div className="flex items-center gap-1.5">
                    <Radio size={11} className="text-[#d4af37]" />
                    <span className="text-[9px] font-black uppercase tracking-widest text-[#d4af37]">
                        Alpha Signals
                    </span>
                    <span className="text-[10px] font-mono font-bold text-white">
                        {profile.ticker}
                    </span>
                </div>
                <span className="text-[8px] font-mono text-gray-600">
                    {profile.fired_signals}/{profile.total_signals}
                </span>
            </div>

            {/* Category rows */}
            {allCategories.map((catKey) => {
                const cfg = CATEGORY_CONFIG[catKey];
                const catScore = profile.category_summary[catKey];
                const firedSignals = catScore
                    ? profile.signals.filter(
                        (s) => s.category === catKey && s.fired
                    )
                    : [];

                return (
                    <CategoryRow
                        key={catKey}
                        catKey={catKey}
                        cfg={cfg}
                        score={catScore}
                        signals={firedSignals}
                    />
                );
            })}

            {/* Composite footer */}
            <div className="mt-1 p-2 rounded-lg border border-[#30363d] bg-[#0d1117]/80">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <span className="text-[9px] font-bold text-gray-400 uppercase">
                            Composite
                        </span>
                        <span className="text-[13px] font-black text-white font-mono">
                            {(composite.overall_strength * 100).toFixed(0)}%
                        </span>
                    </div>
                    <div className="flex items-center gap-2">
                        {composite.dominant_category && (
                            <span
                                className={`text-[7px] font-bold uppercase px-1.5 py-0.5 rounded border ${CATEGORY_CONFIG[composite.dominant_category]?.bg || ""
                                    } ${CATEGORY_CONFIG[composite.dominant_category]?.color || ""} ${CATEGORY_CONFIG[composite.dominant_category]?.border || ""
                                    }`}
                            >
                                {CATEGORY_CONFIG[composite.dominant_category]?.label || composite.dominant_category}
                            </span>
                        )}
                        {composite.multi_category_bonus && (
                            <span className="text-[7px] font-bold text-[#d4af37] bg-[#d4af37]/10 px-1.5 py-0.5 rounded border border-[#d4af37]/30">
                                ✓ Multi-Style
                            </span>
                        )}
                    </div>
                </div>
                {/* Strength bar */}
                <div className="w-full h-1.5 rounded-full bg-[#30363d] overflow-hidden mt-1.5">
                    <div
                        className={`h-full rounded-full transition-all duration-500 ${composite.overall_strength > 0.7
                            ? "bg-green-500"
                            : composite.overall_strength > 0.4
                                ? "bg-yellow-500"
                                : "bg-gray-500"
                            }`}
                        style={{ width: `${composite.overall_strength * 100}%` }}
                    />
                </div>
            </div>
        </div>
    );
}

// ── Category Row Sub-component ────────────────────────────────────────────────

function CategoryRow({
    catKey,
    cfg,
    score,
    signals,
}: {
    catKey: string;
    cfg: (typeof CATEGORY_CONFIG)[string];
    score?: CategoryScore;
    signals: EvaluatedSignal[];
}) {
    const [expanded, setExpanded] = React.useState(false);
    const hasFired = score && score.fired > 0;

    return (
        <div
            className={`rounded-lg border transition-all ${hasFired
                ? `${cfg.border} bg-[#161b22]/80`
                : "border-[#30363d]/50 bg-[#161b22]/30 opacity-50"
                }`}
        >
            {/* Summary row */}
            <button
                onClick={() => hasFired && setExpanded(!expanded)}
                className="w-full flex items-center gap-2 px-2.5 py-1.5 text-left"
                disabled={!hasFired}
            >
                {/* Category badge */}
                <span className={`flex items-center gap-0.5 ${cfg.color}`}>
                    {cfg.icon}
                </span>
                <span className={`text-[9px] font-bold uppercase tracking-wider ${cfg.color} w-16`}>
                    {cfg.label}
                </span>

                {/* Strength bar */}
                <div className="flex-1 h-1 rounded-full bg-[#30363d] overflow-hidden">
                    {score && (
                        <div
                            className={`h-full rounded-full transition-all ${score.composite_strength > 0.7
                                ? "bg-green-500"
                                : score.composite_strength > 0.4
                                    ? "bg-yellow-500"
                                    : "bg-gray-500"
                                }`}
                            style={{ width: `${score.composite_strength * 100}%` }}
                        />
                    )}
                </div>

                {/* Confidence dots */}
                <div className="flex gap-0.5 w-10 justify-end">
                    {score
                        ? Array.from({ length: 4 }).map((_, i) => (
                            <span
                                key={i}
                                className={`w-1.5 h-1.5 rounded-full ${i < (CONFIDENCE_DOTS[score.confidence] || 0)
                                    ? cfg.bg.replace("/10", "/60")
                                    : "bg-[#30363d]"
                                    }`}
                            />
                        ))
                        : Array.from({ length: 4 }).map((_, i) => (
                            <span key={i} className="w-1.5 h-1.5 rounded-full bg-[#30363d]" />
                        ))}
                </div>

                {/* Fired count */}
                <span className="text-[8px] font-mono text-gray-600 w-6 text-right">
                    {score ? `${score.fired}/${score.total}` : "0/0"}
                </span>
            </button>

            {/* Expanded signals */}
            {expanded && signals.length > 0 && (
                <div className="px-2.5 pb-2 pt-0 border-t border-[#30363d]/30 flex flex-col gap-0.5">
                    {signals.map((sig, idx) => (
                        <div
                            key={idx}
                            className="flex items-center justify-between text-[9px] bg-[#0d1117] rounded px-2 py-1"
                        >
                            <span className="text-gray-300 truncate flex-1">
                                {sig.description}
                            </span>
                            <span
                                className={`ml-2 text-[7px] font-bold uppercase px-1 rounded flex-shrink-0 ${STRENGTH_STYLE[sig.strength] || ""
                                    }`}
                            >
                                {sig.strength}
                            </span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
