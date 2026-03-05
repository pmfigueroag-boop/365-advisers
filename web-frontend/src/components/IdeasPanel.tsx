"use client";

import React, { useState } from "react";
import {
    Lightbulb,
    Zap,
    X,
    Loader2,
    TrendingUp,
    TrendingDown,
    Diamond,
    BarChart3,
    RefreshCw,
    ChevronDown,
    ChevronUp,
    Radio,
} from "lucide-react";
import type { IdeaItem, IdeaSignal } from "@/hooks/useIdeasEngine";
import SignalEnvironmentBadge from "./SignalEnvironmentBadge";

// ── Type colors + icons ──────────────────────────────────────────────────────

const TYPE_CONFIG: Record<
    string,
    { label: string; color: string; bg: string; border: string; icon: React.ReactNode }
> = {
    value: {
        label: "Value",
        color: "text-emerald-400",
        bg: "bg-emerald-500/10",
        border: "border-emerald-500/30",
        icon: <Diamond size={10} />,
    },
    quality: {
        label: "Quality",
        color: "text-blue-400",
        bg: "bg-blue-500/10",
        border: "border-blue-500/30",
        icon: <Zap size={10} />,
    },
    momentum: {
        label: "Momentum",
        color: "text-orange-400",
        bg: "bg-orange-500/10",
        border: "border-orange-500/30",
        icon: <TrendingUp size={10} />,
    },
    reversal: {
        label: "Reversal",
        color: "text-red-400",
        bg: "bg-red-500/10",
        border: "border-red-500/30",
        icon: <TrendingDown size={10} />,
    },
    event: {
        label: "Event",
        color: "text-purple-400",
        bg: "bg-purple-500/10",
        border: "border-purple-500/30",
        icon: <BarChart3 size={10} />,
    },
};

const CONFIDENCE_COLOR: Record<string, string> = {
    high: "text-green-400 bg-green-500/15 border-green-500/30",
    medium: "text-yellow-400 bg-yellow-500/15 border-yellow-500/30",
    low: "text-gray-400 bg-gray-500/15 border-gray-500/30",
};

// ── Props ────────────────────────────────────────────────────────────────────

interface IdeasPanelProps {
    ideas: IdeaItem[];
    scanStatus: "idle" | "scanning" | "done" | "error";
    error: string | null;
    onScan: () => void;
    onAnalyze: (ticker: string) => void;
    onDismiss: (ideaId: number) => void;
}

// ── Component ────────────────────────────────────────────────────────────────

export default function IdeasPanel({
    ideas,
    scanStatus,
    error,
    onScan,
    onAnalyze,
    onDismiss,
}: IdeasPanelProps) {
    const [filter, setFilter] = useState<string | null>(null);
    const [expandedId, setExpandedId] = useState<number | null>(null);

    const displayed = filter ? ideas.filter((i) => i.idea_type === filter) : ideas;

    return (
        <div className="flex flex-col h-full overflow-hidden">
            {/* Header bar */}
            <div className="flex items-center justify-between px-3 py-2 border-b border-[#30363d]">
                <div className="flex items-center gap-1.5">
                    <Lightbulb size={12} className="text-[#d4af37]" />
                    <span className="text-[9px] font-black uppercase tracking-widest text-[#d4af37]">
                        Ideas
                    </span>
                    {ideas.length > 0 && (
                        <span className="bg-[#d4af37]/20 text-[#d4af37] rounded-full px-1.5 text-[8px] font-mono font-bold">
                            {ideas.length}
                        </span>
                    )}
                </div>
                <button
                    onClick={onScan}
                    disabled={scanStatus === "scanning"}
                    title="Scan watchlist for ideas"
                    className="p-1 rounded text-gray-500 hover:text-[#d4af37] transition-colors disabled:opacity-40"
                >
                    {scanStatus === "scanning" ? (
                        <Loader2 size={12} className="animate-spin" />
                    ) : (
                        <RefreshCw size={12} />
                    )}
                </button>
            </div>

            {/* Type filter chips */}
            <div className="flex gap-1 px-3 py-1.5 overflow-x-auto flex-shrink-0">
                <button
                    onClick={() => setFilter(null)}
                    className={`px-2 py-0.5 rounded text-[8px] font-bold uppercase tracking-wider transition-all border ${filter === null
                        ? "bg-[#d4af37]/20 text-[#d4af37] border-[#d4af37]/40"
                        : "bg-transparent text-gray-600 border-transparent hover:text-gray-400"
                        }`}
                >
                    All
                </button>
                {Object.entries(TYPE_CONFIG).map(([key, cfg]) => (
                    <button
                        key={key}
                        onClick={() => setFilter(filter === key ? null : key)}
                        className={`px-2 py-0.5 rounded text-[8px] font-bold uppercase tracking-wider transition-all border flex items-center gap-1 ${filter === key
                            ? `${cfg.bg} ${cfg.color} ${cfg.border}`
                            : "bg-transparent text-gray-600 border-transparent hover:text-gray-400"
                            }`}
                    >
                        {cfg.icon}
                        {cfg.label}
                    </button>
                ))}
            </div>

            {/* Ideas list */}
            <div className="flex-1 overflow-y-auto custom-scrollbar">
                {scanStatus === "scanning" && (
                    <div className="flex flex-col items-center justify-center py-8 gap-2 text-gray-500">
                        <Loader2 size={20} className="animate-spin text-[#d4af37]" />
                        <p className="text-[10px] font-bold">Scanning universe…</p>
                    </div>
                )}

                {error && (
                    <div className="mx-3 mt-2 p-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-[10px]">
                        {error}
                    </div>
                )}

                {scanStatus !== "scanning" && displayed.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-full px-4 py-8 text-center gap-2">
                        <Lightbulb size={24} className="text-[#30363d]" />
                        <p className="text-[10px] text-gray-600 leading-relaxed">
                            {scanStatus === "idle"
                                ? "Click the refresh icon to scan your watchlist for opportunities"
                                : "No ideas detected for the current filter"}
                        </p>
                    </div>
                )}

                {displayed.map((idea) => {
                    const cfg = TYPE_CONFIG[idea.idea_type] ?? TYPE_CONFIG.event;
                    const confStyle = CONFIDENCE_COLOR[idea.confidence] ?? CONFIDENCE_COLOR.low;
                    const isExpanded = expandedId === idea.id;

                    return (
                        <div
                            key={idea.id ?? idea.idea_uid}
                            className="group relative mx-2 my-1 rounded-lg border border-[#30363d] bg-[#161b22]/60 hover:border-[#30363d] transition-all"
                        >
                            {/* Main row */}
                            <div className="flex items-center gap-2 px-3 py-2">
                                {/* Type badge */}
                                <span
                                    className={`flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[8px] font-bold uppercase border ${cfg.bg} ${cfg.color} ${cfg.border} flex-shrink-0`}
                                >
                                    {cfg.icon}
                                    {cfg.label}
                                </span>

                                {/* Ticker + Name */}
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-1.5">
                                        <span className="text-[11px] font-black text-white">{idea.ticker}</span>
                                        <span className={`text-[7px] font-bold uppercase px-1 py-0 rounded border ${confStyle}`}>
                                            {idea.confidence}
                                        </span>
                                    </div>
                                    {idea.name && (
                                        <p className="text-[8px] text-gray-600 truncate">{idea.name}</p>
                                    )}
                                    {/* Alpha Signals source indicator */}
                                    {idea.metadata?.source === "alpha_signals_library" && (
                                        <div className="flex items-center gap-1 mt-0.5">
                                            <Radio size={7} className="text-[#d4af37]" />
                                            <span className="text-[7px] font-bold text-[#d4af37]/70">
                                                α Signals
                                            </span>
                                            {idea.metadata.signals_fired != null && idea.metadata.total_possible != null && (
                                                <span className="text-[7px] font-mono text-gray-600">
                                                    {idea.metadata.signals_fired}/{idea.metadata.total_possible}
                                                </span>
                                            )}
                                        </div>
                                    )}
                                    {/* CASE badge */}
                                    {idea.metadata?.composite_alpha_score != null && idea.metadata?.signal_environment && (
                                        <div className="mt-0.5">
                                            <SignalEnvironmentBadge
                                                environment={idea.metadata.signal_environment}
                                                score={idea.metadata.composite_alpha_score}
                                                compact
                                            />
                                        </div>
                                    )}
                                </div>

                                {/* Signal strength bar */}
                                <div className="flex flex-col items-end gap-0.5 flex-shrink-0">
                                    <div className="w-10 h-1.5 rounded-full bg-[#30363d] overflow-hidden">
                                        <div
                                            className={`h-full rounded-full transition-all ${idea.signal_strength > 0.7
                                                ? "bg-green-500"
                                                : idea.signal_strength > 0.4
                                                    ? "bg-yellow-500"
                                                    : "bg-gray-500"
                                                }`}
                                            style={{ width: `${idea.signal_strength * 100}%` }}
                                        />
                                    </div>
                                    <span className="text-[7px] text-gray-600 font-mono">
                                        {(idea.signal_strength * 100).toFixed(0)}%
                                    </span>
                                </div>

                                {/* Actions */}
                                <div className="flex items-center gap-0.5 flex-shrink-0">
                                    <button
                                        onClick={() => setExpandedId(isExpanded ? null : idea.id)}
                                        className="p-0.5 text-gray-600 hover:text-gray-400 transition-colors"
                                        title="Toggle signals"
                                    >
                                        {isExpanded ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
                                    </button>
                                    <button
                                        onClick={() => onAnalyze(idea.ticker)}
                                        className="p-0.5 text-gray-500 hover:text-[#d4af37] transition-colors"
                                        title="Run full analysis"
                                    >
                                        <Zap size={10} />
                                    </button>
                                    <button
                                        onClick={() => onDismiss(idea.id)}
                                        className="p-0.5 text-gray-700 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100"
                                        title="Dismiss idea"
                                    >
                                        <X size={10} />
                                    </button>
                                </div>
                            </div>

                            {/* Expanded signals */}
                            {isExpanded && (
                                <div className="px-3 pb-2 pt-0 border-t border-[#30363d]/50 mt-0">
                                    <p className="text-[8px] font-bold uppercase text-gray-600 tracking-wider py-1">
                                        Detected Signals
                                    </p>
                                    <div className="flex flex-col gap-1">
                                        {idea.signals.map((sig: IdeaSignal, idx: number) => (
                                            <div
                                                key={idx}
                                                className="flex items-center justify-between text-[9px] bg-[#0d1117] rounded px-2 py-1"
                                            >
                                                <span className="text-gray-300 truncate flex-1">
                                                    {sig.description || sig.name}
                                                </span>
                                                <span
                                                    className={`ml-2 text-[7px] font-bold uppercase px-1 rounded flex-shrink-0 ${sig.strength === "strong"
                                                        ? "text-green-400 bg-green-500/15"
                                                        : sig.strength === "moderate"
                                                            ? "text-yellow-400 bg-yellow-500/15"
                                                            : "text-gray-500 bg-gray-500/15"
                                                        }`}
                                                >
                                                    {sig.strength}
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
