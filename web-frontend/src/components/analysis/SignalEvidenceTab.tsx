"use client";

/**
 * SignalEvidenceTab.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Shows individual signal firing timeline with validation metrics.
 */

import { Radio, TrendingUp, TrendingDown, Minus, Clock, CheckCircle2, XCircle } from "lucide-react";
import type { EvaluatedSignal, CategoryScore } from "@/hooks/useAlphaSignals";

interface SignalEvidenceTabProps {
    signals: EvaluatedSignal[];
    categorySummary: Record<string, CategoryScore>;
    ticker: string;
}

function strengthIcon(strength: string) {
    if (strength === "strong") return <TrendingUp size={11} className="text-green-400" />;
    if (strength === "moderate") return <Minus size={11} className="text-yellow-400" />;
    return <TrendingDown size={11} className="text-gray-500" />;
}

export default function SignalEvidenceTab({ signals, categorySummary, ticker }: SignalEvidenceTabProps) {
    // Group by category
    const categories = Object.entries(categorySummary).sort((a, b) =>
        (b[1].fired ?? 0) - (a[1].fired ?? 0)
    );

    const firedSignals = signals.filter((s) => s.fired);
    const notFired = signals.filter((s) => !s.fired);

    return (
        <div className="space-y-5" style={{ animation: "fadeSlideIn 0.3s ease both" }}>
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Radio size={14} className="text-purple-400" />
                    <h3 className="text-sm font-black uppercase tracking-widest text-gray-300">Signal Evidence</h3>
                </div>
                <span className="text-[9px] font-mono text-gray-600 bg-[#161b22] border border-[#30363d] rounded-lg px-2 py-1">
                    {firedSignals.length}/{signals.length} active
                </span>
            </div>

            {/* Category Summary Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {categories.map(([cat, summary]) => {
                    const firedPct = summary.total > 0 ? Math.round(((summary.fired ?? 0) / summary.total) * 100) : 0;
                    return (
                        <div key={cat} className="glass-card p-3 border-[#30363d]">
                            <p className="text-[8px] font-black uppercase tracking-wider text-gray-600 mb-1 capitalize">{cat}</p>
                            <div className="flex items-baseline gap-2">
                                <span className="text-lg font-black text-white" style={{ fontFamily: "var(--font-data)" }}>
                                    {summary.fired ?? 0}
                                </span>
                                <span className="text-[9px] text-gray-600">/ {summary.total}</span>
                            </div>
                            <div className="w-full bg-[#161b22] rounded-full h-1 mt-2 overflow-hidden">
                                <div
                                    className="h-full rounded-full bg-purple-500 transition-all duration-500"
                                    style={{ width: `${firedPct}%` }}
                                />
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Fired Signals Timeline */}
            {firedSignals.length > 0 && (
                <div className="glass-card border-[#30363d] overflow-hidden">
                    <div className="px-5 py-3 border-b border-[#30363d] flex items-center gap-2">
                        <CheckCircle2 size={11} className="text-green-400" />
                        <span className="text-[10px] font-black uppercase tracking-widest text-gray-400">Active Signals ({firedSignals.length})</span>
                    </div>
                    <div className="divide-y divide-[#30363d]/50">
                        {firedSignals.map((signal, i) => (
                            <div key={signal.signal_id ?? i} className="flex items-center gap-3 px-5 py-3 hover:bg-white/[0.02] transition-colors">
                                <div className="flex-shrink-0">{strengthIcon(signal.strength ?? "weak")}</div>
                                <div className="flex-1 min-w-0">
                                    <p className="text-[11px] text-white font-bold truncate">{signal.signal_name}</p>
                                    <p className="text-[9px] text-gray-600 capitalize">{signal.category}</p>
                                </div>
                                <div className="flex-shrink-0 text-right">
                                    <span className={`text-[9px] font-black uppercase ${signal.strength === "strong" ? "text-green-400" : signal.strength === "moderate" ? "text-yellow-400" : "text-gray-500"}`}>
                                        {signal.strength}
                                    </span>
                                </div>
                                {signal.value != null && (
                                    <span className="text-[9px] font-mono text-gray-500 flex-shrink-0 w-12 text-right">
                                        {typeof signal.value === "number" ? signal.value.toFixed(2) : String(signal.value)}
                                    </span>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Inactive Signals */}
            {notFired.length > 0 && (
                <details className="glass-card border-[#30363d] overflow-hidden">
                    <summary className="px-5 py-3 cursor-pointer flex items-center gap-2 hover:bg-white/[0.02] transition-colors">
                        <XCircle size={11} className="text-gray-600" />
                        <span className="text-[10px] font-black uppercase tracking-widest text-gray-600">
                            Inactive Signals ({notFired.length})
                        </span>
                    </summary>
                    <div className="border-t border-[#30363d] divide-y divide-[#30363d]/50">
                        {notFired.map((signal, i) => (
                            <div key={signal.signal_id ?? i} className="flex items-center gap-3 px-5 py-2.5 opacity-50">
                                <Clock size={9} className="text-gray-700 flex-shrink-0" />
                                <span className="text-[10px] text-gray-600 truncate">{signal.signal_name}</span>
                                <span className="text-[8px] text-gray-700 capitalize ml-auto">{signal.category}</span>
                            </div>
                        ))}
                    </div>
                </details>
            )}
        </div>
    );
}
