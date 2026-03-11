"use client";

import { useState, useEffect } from "react";
import { Zap, CheckCircle2, Loader2, Clock } from "lucide-react";
import type { AgentMemo } from "../hooks/useFundamentalStream";

// ─── Cache Badge ─────────────────────────────────────────────────────────────
export function CacheBadge({ cachedAt }: { cachedAt: string | null }) {
    const [ageLabel, setAgeLabel] = useState<string>("just now");

    useEffect(() => {
        if (!cachedAt) return;
        const calculateAge = () => {
            const ageMs = Date.now() - new Date(cachedAt).getTime();
            const ageMin = Math.round(ageMs / 60000);
            return ageMin < 1 ? "just now" : `${ageMin} min ago`;
        };
        setAgeLabel(calculateAge());
        const idx = setInterval(() => setAgeLabel(calculateAge()), 60000);
        return () => clearInterval(idx);
    }, [cachedAt]);

    if (!cachedAt) return null;

    return (
        <span
            title={`Result from cache — Cached ${ageLabel}`}
            className="flex items-center gap-1 px-2 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest bg-amber-500/10 border border-amber-500/30 text-amber-400 cursor-help select-none"
        >
            <Zap size={9} fill="currentColor" />
            Cached · {ageLabel}
        </span>
    );
}

// ─── Signal Badge helper ─────────────────────────────────────────────────────
export function SignalBadge({ signal }: { signal?: string }) {
    if (!signal) return null;
    const s = signal.toUpperCase();
    const cls = s.includes("BUY") || s === "AGGRESSIVE"
        ? "bg-green-500/15 text-green-400 border-green-500/30"
        : s.includes("SELL") || s === "DEFENSIVE"
            ? "bg-red-500/15 text-red-400 border-red-500/30"
            : "bg-gray-500/15 text-gray-400 border-gray-500/30";
    return (
        <span className={`text-[8px] font-black uppercase tracking-widest px-1.5 py-0.5 rounded border ${cls}`}>
            {signal}
        </span>
    );
}

// ─── Fundamental Table ───────────────────────────────────────────────────────
export const FundamentalTable = ({ engine }: { engine: Record<string, Record<string, unknown>> }) => {
    if (!engine) return null;
    return (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            {Object.entries(engine).map(([category, metrics]) => (
                <div key={category} className="glass-card p-4 border-[#30363d] bg-[#0d1117]/30">
                    <h4 className="text-[10px] font-black uppercase text-[#d4af37] mb-3 tracking-widest">
                        {category.replace("_", " ")}
                    </h4>
                    <div className="space-y-2">
                        {Object.entries(metrics).map(([key, val]) => (
                            <div key={key} className="flex justify-between items-center">
                                <span className="text-[10px] text-gray-500 capitalize">{key.replace(/_/g, " ")}</span>
                                <span className={`text-[10px] font-mono ${val === "DATA_INCOMPLETE" ? "text-red-500/50" : "text-gray-200"}`}>
                                    {typeof val === "number"
                                        ? val > 1 || val < -1
                                            ? val.toLocaleString("en-US", { maximumFractionDigits: 2 })
                                            : (val * 100).toFixed(2) + "%"
                                        : String(val)}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
};

// ─── Agent Card ──────────────────────────────────────────────────────────────
export const AgentCard = ({ agent, index }: { agent: AgentMemo & { is_fallback?: boolean }; index: number }) => {
    const isBuy = ["BUY", "AGGRESSIVE"].includes(agent.signal?.toUpperCase());
    const isSell = ["SELL", "DEFENSIVE"].includes(agent.signal?.toUpperCase());
    return (
        <div
            className="agent-card glass-card p-5 border-[#30363d] flex flex-col h-[320px] glow-border transition-all group"
            style={{ animation: `fadeSlideIn 0.45s ease both`, animationDelay: `${index * 60}ms` }}
        >
            <div className="flex justify-between items-start mb-3">
                <div className="flex items-center gap-2">
                    <CheckCircle2 size={12} className="text-[#d4af37]" />
                    <h3 className="font-black text-base group-hover:text-[#d4af37] transition-colors">{agent.agent}</h3>
                    {agent.is_fallback && (
                        <span className="px-1.5 py-0.5 rounded text-[8px] font-bold bg-yellow-500/10 text-yellow-400 border border-yellow-500/30">⚠ Fallback</span>
                    )}
                </div>
                <span className={`px-2 py-0.5 rounded text-[9px] font-black tracking-tighter ${isBuy ? "bg-green-500/10 text-green-400" : isSell ? "bg-red-500/10 text-red-400" : "bg-gray-500/10 text-gray-400"}`}>
                    {agent.signal}
                </span>
            </div>
            <div className="flex-1 overflow-y-auto pr-2 custom-scrollbar">
                <p className="text-[11px] text-gray-400 leading-relaxed text-pretty mb-3">{agent.memo}</p>
                {agent.key_metrics_used && agent.key_metrics_used.length > 0 && (
                    <div className="space-y-1">
                        <span className="text-[8px] font-black text-[#d4af37] uppercase tracking-widest">Métricas Priorizadas</span>
                        <div className="flex flex-wrap gap-1">
                            {agent.key_metrics_used.map((m: unknown, idx: number) => {
                                const label = typeof m === "string" ? m : (m as Record<string, string>).metric || (m as Record<string, string>).name || `Metric ${idx}`;
                                const tooltip = typeof m === "object" && m !== null ? (m as Record<string, string>).justification || (m as Record<string, string>).reason : undefined;
                                return (
                                    <span key={idx} title={tooltip} className="px-1.5 py-0.5 bg-[#d4af37]/10 text-[#f9e29c] rounded-sm text-[8px] font-mono border border-[#d4af37]/20 cursor-help">
                                        {label}
                                    </span>
                                );
                            })}
                        </div>
                    </div>
                )}
            </div>
            <div className="mt-4 pt-3 border-t border-[#30363d] flex justify-between items-center bg-[#0d1117]/50 -mx-5 -mb-5 p-4 rounded-b-xl">
                <span className="text-[9px] text-gray-500 uppercase font-bold tracking-widest">Conviction</span>
                <div className="flex items-center gap-2">
                    <div className="w-12 h-1 bg-[#161b22] rounded-full overflow-hidden">
                        <div className="h-full bg-[#d4af37]" style={{ width: `${(agent.conviction || 0) * 100}%` }} />
                    </div>
                    <span className="text-[9px] font-mono text-[#d4af37]">{((agent.conviction || 0) * 100).toFixed(0)}%</span>
                </div>
            </div>
        </div>
    );
};

// ─── Skeleton Card ───────────────────────────────────────────────────────────
export const AgentSkeletonCard = ({ label }: { label: string }) => (
    <div className="glass-card p-5 border-[#30363d] flex flex-col h-[320px] opacity-60 shimmer">
        <div className="flex items-center gap-2 mb-3">
            <Loader2 size={12} className="text-[#d4af37] animate-spin" />
            <span className="font-black text-base text-gray-600">{label}</span>
        </div>
        <div className="flex-1 space-y-2 pt-2">
            {[100, 80, 90, 60, 75].map((w, i) => (
                <div key={i} className="h-2 bg-[#30363d] rounded animate-pulse" style={{ width: `${w}%` }} />
            ))}
        </div>
        <div className="mt-4 pt-3 border-t border-[#30363d] flex items-center justify-center -mx-5 -mb-5 p-4 rounded-b-xl bg-[#0d1117]/30">
            <Clock size={12} className="text-gray-600 mr-2" />
            <span className="text-[9px] text-gray-600 uppercase tracking-widest">Analyzing...</span>
        </div>
    </div>
);

// ─── Progress Bar ────────────────────────────────────────────────────────────
export const AGENT_ORDER = ["Lynch", "Buffett", "Marks", "Icahn", "Bollinger", "RSI", "MACD", "Gann"];

export const ProgressBar = ({ completed, total, status }: { completed: number; total: number; status: string }) => {
    const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
    const isDone = completed >= total;
    return (
        <div className="glass-card p-4 border-[#30363d] bg-[#0d1117]/40 mb-6">
            <div className="flex justify-between items-center mb-2">
                <div className="flex items-center gap-2">
                    {isDone ? <CheckCircle2 size={14} className="text-[#d4af37]" /> : <Loader2 size={14} className="text-[#d4af37] animate-spin" />}
                    <span className="text-xs font-black uppercase tracking-widest text-gray-400">
                        {status === "fetching_data" ? "Fetching market data..." : status === "analyzing" ? `Committee at work — ${completed} / ${total} minds reporting` : "Analysis complete"}
                    </span>
                </div>
                <span className="text-xs font-mono text-[#d4af37]">{pct}%</span>
            </div>
            <div className="h-1.5 bg-[#161b22] rounded-full overflow-hidden">
                <div className={`h-full bg-[#d4af37] transition-all duration-500 ease-out ${!isDone ? "progress-shimmer" : ""}`} style={{ width: `${pct}%` }} />
            </div>
        </div>
    );
};
