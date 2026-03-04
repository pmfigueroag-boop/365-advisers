"use client";

import {
    ShieldCheck,
    TrendingUp,
    TrendingDown,
    Zap,
    RefreshCw,
    Clock,
} from "lucide-react";
import { useState } from "react";
import type { CombinedState } from "@/hooks/useCombinedStream";
import ResearchMemoCard from "./ResearchMemoCard";
import IndicatorGrid from "./IndicatorGrid";
import ScoreHistoryChart from "./ScoreHistoryChart";
import { useCSVExport } from "@/hooks/useCSVExport";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function signalColor(signal: string) {
    if (signal === "BUY" || signal === "STRONG_BUY" || signal === "Strong Opportunity") return "text-green-400";
    if (signal === "SELL" || signal === "STRONG_SELL" || signal === "AVOID" || signal === "Avoid") return "text-red-400";
    if (signal === "Caution") return "text-orange-400";
    return "text-yellow-400";
}

function signalBg(signal: string) {
    if (signal === "BUY" || signal === "STRONG_BUY" || signal === "Strong Opportunity") return "bg-green-500/10 border-green-500/30";
    if (signal === "SELL" || signal === "STRONG_SELL" || signal === "AVOID" || signal === "Avoid") return "bg-red-500/10 border-red-500/30";
    if (signal === "Caution") return "bg-orange-500/10 border-orange-500/30";
    return "bg-yellow-500/10 border-yellow-500/30";
}

// ─── Status timeline ──────────────────────────────────────────────────────────

function StatusTimeline({ status }: { status: string }) {
    const steps = [
        { key: "fetching_data", label: "Data" },
        { key: "fundamental", label: "Analysts" },
        { key: "technical", label: "Technical" },
        { key: "decision", label: "CIO" },
        { key: "complete", label: "Done" },
    ];
    const idx = steps.findIndex((s) => s.key === status);

    return (
        <div className="flex items-center gap-1">
            {steps.map((s, i) => {
                const done = i < idx || status === "complete";
                const active = i === idx;
                return (
                    <div key={s.key} className="flex items-center gap-1">
                        <div
                            className={`w-2 h-2 rounded-full transition-all duration-300 ${done ? "bg-green-500" : active ? "bg-[#d4af37] animate-pulse" : "bg-[#30363d]"
                                }`}
                        />
                        <span
                            className={`text-[8px] font-bold ${done ? "text-green-500" : active ? "text-[#d4af37]" : "text-gray-700"
                                }`}
                        >
                            {s.label}
                        </span>
                        {i < steps.length - 1 && <div className={`w-4 h-px ${done ? "bg-green-500/30" : "bg-[#30363d]"}`} />}
                    </div>
                );
            })}
        </div>
    );
}

// ─── CombinedDashboard ────────────────────────────────────────────────────────

interface CombinedDashboardProps {
    state: CombinedState;
    onForceRefresh: () => void;
}

export default function CombinedDashboard({ state, onForceRefresh }: CombinedDashboardProps) {
    const [activeView, setActiveView] = useState<"overview" | "fundamental" | "technical" | "history">("overview");
    const { downloadCSV } = useCSVExport();

    const { status, ticker, committee, technical, decision, agentMemos, researchMemo, fundamentalDataReady, processingMs, fromCache } = state;

    const fundScore = committee?.score ?? 0;
    const techScore = technical?.summary?.technical_score ?? 0;

    const hasDecision = !!decision;
    const overallSignal = decision?.investment_position ?? null;

    const isLoading = status === "fetching_data" || status === "fundamental" || status === "technical" || status === "decision";

    return (
        <div className="space-y-6" style={{ animation: "fadeSlideIn 0.4s ease both" }}>

            {/* ── Header bar ── */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div>
                    <div className="flex items-center gap-2 mb-1">
                        <Zap size={14} className="text-[#d4af37]" />
                        <h2 className="text-[9px] font-black uppercase tracking-[0.2em] text-gray-500">Decision Engine</h2>
                        {fromCache && (
                            <span className="text-[7px] bg-[#30363d] text-gray-500 px-1.5 py-0.5 rounded font-bold">CACHED</span>
                        )}
                    </div>
                    <StatusTimeline status={status} />
                </div>

                <div className="flex items-center gap-3">
                    {processingMs && (
                        <span className="text-[8px] text-gray-600 flex items-center gap-1">
                            <Clock size={8} />
                            {(processingMs / 1000).toFixed(1)}s
                        </span>
                    )}
                    {(status === "complete" || isLoading) && (
                        <div className="flex items-center gap-2">
                            {status === "complete" && (
                                <button
                                    onClick={() => {
                                        if (ticker) downloadCSV(fundamentalDataReady, technical?.summary, ticker);
                                    }}
                                    className="flex items-center gap-1.5 text-[8px] font-bold text-[#d4af37] border border-[#d4af37]/30 hover:bg-[#d4af37]/10 px-2 py-1 rounded transition-colors tracking-wider uppercase"
                                >
                                    CSV
                                </button>
                            )}
                            <button
                                onClick={onForceRefresh}
                                disabled={isLoading}
                                className="flex items-center gap-1.5 text-[8px] font-bold text-gray-600 hover:text-[#d4af37] transition-colors disabled:opacity-40 uppercase tracking-wider"
                            >
                                <RefreshCw size={9} className={isLoading ? "animate-spin" : ""} />
                                Refresh
                            </button>
                        </div>
                    )}
                </div>
            </div>

            {/* ── CIO Decision Hero (shown when decision is ready) ── */}
            {hasDecision && decision && overallSignal && (
                <div className={`glass-card p-6 sm:p-8 border flex flex-col gap-6 ${signalBg(overallSignal)} bg-opacity-20`} style={{ animation: "verdictReveal 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) both" }}>

                    {/* Header: Position & Confidence */}
                    <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-[#30363d]/50 pb-4">
                        <div className="flex items-center gap-4">
                            <ShieldCheck size={28} className={signalColor(overallSignal)} />
                            <div>
                                <p className="text-[9px] font-black uppercase tracking-[0.2em] text-gray-500 mb-1">Institutional Posture</p>
                                <h1 className={`text-2xl font-black uppercase tracking-wider ${signalColor(overallSignal)}`}>
                                    {overallSignal}
                                </h1>
                            </div>
                        </div>
                        <div className="flex items-center gap-4 bg-[#0d1117]/60 px-4 py-2 rounded-xl border border-[#30363d]">
                            <div className="text-right">
                                <p className="text-[8px] font-black uppercase tracking-widest text-gray-500">Confidence</p>
                                <p className="text-lg font-black text-white font-mono">{(decision.confidence_score * 100).toFixed(0)}%</p>
                            </div>
                            <div className="w-px h-8 bg-[#30363d]"></div>
                            <div className="flex flex-col gap-1 w-20">
                                <div className="flex items-center justify-between gap-3 text-[9px] font-mono">
                                    <span className="text-gray-500 uppercase">Fund</span>
                                    <span className="text-white font-bold">{fundScore.toFixed(1)}</span>
                                </div>
                                <div className="flex items-center justify-between gap-3 text-[9px] font-mono">
                                    <span className="text-gray-500 uppercase">Tech</span>
                                    <span className="text-white font-bold">{techScore.toFixed(1)}</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* CIO Thesis */}
                    <div>
                        <p className="font-serif text-[1.15rem] leading-[1.6] text-gray-200 italic mb-2 border-l-2 border-[#d4af37] pl-4">
                            &ldquo;{decision.cio_memo.thesis_summary}&rdquo;
                        </p>
                    </div>
                </div>
            )}

            {/* ── Sub-tab nav ── */}
            {(status === "fundamental" || status === "technical" || status === "decision" || status === "complete") && (
                <div className="flex gap-1 p-1 bg-[#161b22]/60 rounded-xl border border-[#30363d] w-fit">
                    {(["overview", "fundamental", "technical", "history"] as const).map((tab) => (
                        <button
                            key={tab}
                            onClick={() => setActiveView(tab)}
                            className={`px-3 py-1.5 rounded-lg text-[9px] font-black uppercase tracking-wider transition-all ${activeView === tab
                                ? "bg-[#d4af37] text-black"
                                : "text-gray-500 hover:text-[#d4af37]"
                                }`}
                        >
                            {tab === "overview" ? "CIO Memo" :
                                tab === "fundamental" ? `Analysts ${agentMemos.length > 0 ? `(${agentMemos.length}/4)` : ""}` :
                                    tab === "technical" ? (technical ? `Tech ${techScore.toFixed(1)}` : "Technical") :
                                        "History"}
                        </button>
                    ))}
                </div>
            )}

            {/* ── CIO Memo Details (Overview tab) ── */}
            {activeView === "overview" && decision && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4" style={{ animation: "fadeSlideIn 0.3s ease both" }}>
                    <div className="glass-card p-5 space-y-4">
                        <div>
                            <p className="text-[9px] font-black uppercase tracking-widest text-[#d4af37] mb-2 flex items-center gap-1.5">
                                Valuation View
                            </p>
                            <p className="text-xs text-gray-300 leading-relaxed font-medium">{decision.cio_memo.valuation_view}</p>
                        </div>
                        <div className="pt-4 border-t border-[#30363d]/50">
                            <p className="text-[9px] font-black uppercase tracking-widest text-[#60a5fa] mb-2 flex items-center gap-1.5">
                                Technical Context
                            </p>
                            <p className="text-xs text-gray-300 leading-relaxed font-medium">{decision.cio_memo.technical_context}</p>
                        </div>
                    </div>

                    <div className="glass-card p-5 space-y-4 flex flex-col">
                        <div className="flex-1">
                            <p className="text-[9px] font-black uppercase tracking-widest text-green-500/80 mb-3 flex items-center gap-1.5"><TrendingUp size={12} /> Key Catalysts</p>
                            <ul className="space-y-2">
                                {decision.cio_memo.key_catalysts.map((c, i) => (
                                    <li key={i} className="text-[11px] text-gray-400 flex items-start gap-2">
                                        <span className="text-green-500 mt-0.5">•</span>
                                        <span className="leading-snug">{c}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                        <div className="flex-1 pt-4 border-t border-[#30363d]/50">
                            <p className="text-[9px] font-black uppercase tracking-widest text-red-500/80 mb-3 flex items-center gap-1.5"><TrendingDown size={12} /> Key Risks</p>
                            <ul className="space-y-2">
                                {decision.cio_memo.key_risks.map((r, i) => (
                                    <li key={i} className="text-[11px] text-gray-400 flex items-start gap-2">
                                        <span className="text-red-500 mt-0.5">•</span>
                                        <span className="leading-snug">{r}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    </div>
                </div>
            )}

            {/* Show loading state for overview if missing decision */}
            {activeView === "overview" && !decision && status !== "idle" && (
                <div className="glass-card p-8 flex items-center justify-center border-dashed border-[#30363d] h-32">
                    <div className="flex flex-col items-center gap-3">
                        <RefreshCw size={24} className="text-[#d4af37] animate-spin" />
                        <p className="text-[10px] text-[#d4af37] uppercase tracking-widest font-black">Synthesizing Decision...</p>
                    </div>
                </div>
            )}

            {/* ── Fundamental detail ── */}
            {activeView === "fundamental" && (
                <ResearchMemoCard
                    dataReady={fundamentalDataReady}
                    agentMemos={agentMemos}
                    committee={committee}
                    researchMemo={researchMemo}
                    agentCount={agentMemos.length}
                    totalAgents={4}
                    status={status}
                />
            )}

            {/* ── Technical detail ── */}
            {activeView === "technical" && technical && (
                <IndicatorGrid data={technical} />
            )}

            {/* ── History chart ── */}
            {activeView === "history" && ticker && (
                <ScoreHistoryChart ticker={ticker} />
            )}
        </div>
    );
}
