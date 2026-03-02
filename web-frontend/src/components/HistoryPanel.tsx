"use client";

import { X, Clock, Trash2, History, Lock } from "lucide-react";
import { HistoryEntry } from "@/hooks/useAnalysisHistory";

const FREE_TIER_LIMIT = 3;

// ─── Helpers ─────────────────────────────────────────────────────────────────

function relativeTime(isoStr: string): string {
    const diffMs = Date.now() - new Date(isoStr).getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return "just now";
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffH = Math.floor(diffMin / 60);
    if (diffH < 24) return `${diffH}h ago`;
    const diffD = Math.floor(diffH / 24);
    return `${diffD}d ago`;
}

function signalColor(signal: string) {
    const s = signal.toUpperCase();
    if (s.includes("BUY")) return "text-green-400 bg-green-500/10 border-green-500/30";
    if (s.includes("SELL")) return "text-red-400 bg-red-500/10 border-red-500/30";
    return "text-gray-400 bg-gray-500/10 border-gray-500/30";
}

function agentDot(signal: string) {
    const s = signal.toUpperCase();
    if (s.includes("BUY") || s === "AGGRESSIVE") return "bg-green-500";
    if (s.includes("SELL") || s === "DEFENSIVE") return "bg-red-500";
    return "bg-gray-600";
}

// ─── Component ────────────────────────────────────────────────────────────────

interface HistoryPanelProps {
    entries: HistoryEntry[];
    onSelect: (ticker: string) => void;
    onRemove: (id: string) => void;
    onClear: () => void;
}

export default function HistoryPanel({
    entries,
    onSelect,
    onRemove,
    onClear,
}: HistoryPanelProps) {
    if (entries.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center flex-1 text-center px-4 py-8">
                <History size={28} className="text-gray-700 mb-3" />
                <p className="text-[10px] text-gray-600 leading-relaxed uppercase tracking-widest font-bold">
                    No history yet
                </p>
                <p className="text-[9px] text-gray-700 mt-1">
                    Each analysis auto-saves here
                </p>
            </div>
        );
    }

    return (
        <div className="flex flex-col flex-1 min-h-0">
            {/* Header row with Clear All */}
            <div className="flex items-center justify-between px-3 py-2 border-b border-[#30363d]">
                <span className="text-[9px] text-gray-600 uppercase tracking-widest font-bold">
                    {entries.length} {entries.length === 1 ? "entry" : "entries"}
                </span>
                <button
                    onClick={onClear}
                    title="Clear all history"
                    className="flex items-center gap-1 text-[8px] text-gray-700 hover:text-red-400 transition-colors uppercase tracking-widest font-bold"
                >
                    <Trash2 size={9} />
                    Clear
                </button>
            </div>

            {/* Entry list */}
            <div className="flex-1 overflow-y-auto">
                {entries.slice(0, FREE_TIER_LIMIT).map((entry) => (
                    <div
                        key={entry.id}
                        className="group relative px-3 py-2.5 border-b border-[#1c2129] hover:bg-[#161b22] cursor-pointer transition-colors"
                        onClick={() => onSelect(entry.ticker)}
                    >
                        {/* Remove button */}
                        <button
                            onClick={(e) => { e.stopPropagation(); onRemove(entry.id); }}
                            className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 text-gray-600 hover:text-red-400 transition-all"
                            title="Remove entry"
                        >
                            <X size={10} />
                        </button>

                        {/* Ticker + signal */}
                        <div className="flex items-center justify-between pr-4">
                            <div>
                                <span className="text-xs font-black text-white">{entry.ticker}</span>
                                {entry.name && entry.name !== entry.ticker && (
                                    <p className="text-[8px] text-gray-600 mt-0.5 truncate max-w-[100px]">{entry.name}</p>
                                )}
                            </div>
                            <span className={`text-[8px] font-black px-1.5 py-0.5 rounded border uppercase ${signalColor(entry.signal)}`}>
                                {entry.signal}
                            </span>
                        </div>

                        {/* Mini agent dots + time */}
                        <div className="flex items-center justify-between mt-1.5">
                            {/* 8 agent signal dots */}
                            <div className="flex items-center gap-0.5">
                                {entry.agentSummary.map((a) => (
                                    <div
                                        key={a.name}
                                        title={`${a.name}: ${a.signal}`}
                                        className={`w-1.5 h-1.5 rounded-full ${agentDot(a.signal)}`}
                                    />
                                ))}
                                {entry.fromCache && (
                                    <span className="ml-1 text-[7px] text-amber-600 font-bold">⚡</span>
                                )}
                            </div>

                            {/* Relative time */}
                            <div className="flex items-center gap-1 text-[8px] text-gray-700">
                                <Clock size={7} />
                                {relativeTime(entry.analyzedAt)}
                            </div>
                        </div>
                    </div>
                ))}

                {/* Pro upgrade CTA — shown when history exceeds free tier limit */}
                {entries.length > FREE_TIER_LIMIT && (
                    <div className="mx-2 my-2 rounded-lg border border-[#30363d]/60 bg-[#0d1117]/60 px-3 py-3 text-center">
                        <Lock size={12} className="text-gray-700 mx-auto mb-1.5" />
                        <p className="text-[8px] font-black uppercase tracking-widest text-gray-600">
                            {entries.length - FREE_TIER_LIMIT} more {entries.length - FREE_TIER_LIMIT === 1 ? "analysis" : "analyses"} locked
                        </p>
                        <p className="text-[7px] text-gray-700 mt-0.5 mb-2">Free tier: 3 most recent</p>
                        <span className="inline-flex items-center gap-1 text-[7px] font-black uppercase tracking-widest bg-[#d4af37]/10 border border-[#d4af37]/25 text-[#d4af37]/70 rounded-full px-2.5 py-1">
                            ✦ Upgrade to Pro
                        </span>
                    </div>
                )}
            </div>
        </div>
    );
}
