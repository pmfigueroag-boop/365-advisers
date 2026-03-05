"use client";

import {
    ShieldCheck,
    TrendingUp,
    TrendingDown,
    Zap,
    RefreshCw,
    Clock,
    Target,
    Activity,
    SlidersHorizontal
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
                            className={`w-1.5 h-1.5 rounded-full transition-all duration-300 ${done ? "bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.4)]" : active ? "bg-[#d4af37] animate-pulse shadow-[0_0_6px_rgba(212,175,55,0.4)]" : "bg-[#30363d]"
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

    const {
        status, ticker, committee, technical, decision,
        agentMemos, researchMemo, fundamentalDataReady,
        processingMs, fromCache, positionSizing
    } = state;

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
                                        if (ticker) downloadCSV(fundamentalDataReady ?? null, technical ?? null, ticker);
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
                <div className={`glass-card p-6 sm:p-8 border flex flex-col gap-6 decision-border ${signalBg(overallSignal)} bg-opacity-20`} style={{ animation: "verdictReveal 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) both" }}>

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

            {/* ── Portfolio Allocation Suggestion (Position Sizing) ── */}
            {hasDecision && positionSizing && (
                <div className="glass-card p-6 border border-[#30363d] bg-gradient-to-br from-[#0d1117] to-[#161b22] flex flex-col md:flex-row divide-y md:divide-y-0 md:divide-x divide-[#30363d]" style={{ animation: "fadeSlideIn 0.5s ease 0.2s both" }}>

                    {/* Left: Headline & Action */}
                    <div className="flex-1 md:pr-6 pb-6 md:pb-0 flex flex-col justify-center">
                        <div className="flex items-center gap-2 mb-4">
                            <Target size={16} className="text-[#60a5fa]" />
                            <h3 className="text-[10px] font-black uppercase tracking-[0.15em] text-gray-400">
                                Portfolio Allocation Suggestion
                            </h3>
                        </div>
                        <div className="flex items-end gap-3 mb-2">
                            <h2 className="text-4xl font-black text-white font-mono tracking-tight">
                                {positionSizing.suggested_allocation.toFixed(1)}<span className="text-xl text-gray-500">%</span>
                            </h2>
                            <span className={`text-[10px] font-black px-2 py-1 rounded uppercase mb-1 tracking-wider ${positionSizing.recommended_action.includes("Increase") ? "bg-green-500/20 text-green-400 border border-green-500/30" : positionSizing.recommended_action.includes("Reduce") || positionSizing.recommended_action.includes("Exit") ? "bg-red-500/20 text-red-400 border border-red-500/30" : "bg-yellow-500/20 text-yellow-400 border border-yellow-500/30"}`}>
                                {positionSizing.recommended_action}
                            </span>
                        </div>
                        <p className="text-[11px] text-gray-500 font-medium">
                            Risk-adjusted target based on Conviction and Volatility constraints. Max 10%.
                        </p>
                    </div>

                    {/* Middle: Math Breakdown 1 */}
                    <div className="flex-1 md:px-6 py-6 md:py-0 flex flex-col gap-4 justify-center">
                        <div className="flex justify-between items-center">
                            <div className="flex items-center gap-2">
                                <Activity size={12} className="text-[#d4af37]" />
                                <span className="text-[10px] uppercase font-bold text-gray-400 tracking-wider">Opportunity</span>
                            </div>
                            <span className="text-sm font-black text-white font-mono">{positionSizing.opportunity_score.toFixed(1)} <span className="text-gray-600 text-[10px]">/ 10</span></span>
                        </div>
                        <div className="flex justify-between items-center">
                            <span className="text-[10px] uppercase font-bold text-gray-500 tracking-wider ml-5">Conviction</span>
                            <span className="text-xs font-bold text-gray-300">{positionSizing.conviction_level}</span>
                        </div>
                        <div className="flex justify-between items-center bg-[#21262d]/50 px-3 py-1.5 rounded">
                            <span className="text-[10px] uppercase font-bold text-gray-400 tracking-wider">Base Size</span>
                            <span className="text-xs font-black text-white font-mono">{positionSizing.base_position_size.toFixed(1)}%</span>
                        </div>
                    </div>

                    {/* Right: Math Breakdown 2 & Total */}
                    <div className="flex-1 md:pl-6 pt-6 md:pt-0 flex flex-col gap-4 justify-center">
                        <div className="flex justify-between items-center">
                            <div className="flex items-center gap-2">
                                <SlidersHorizontal size={12} className="text-[#c084fc]" />
                                <span className="text-[10px] uppercase font-bold text-gray-400 tracking-wider">Risk Level</span>
                            </div>
                            <span className="text-xs font-bold text-[#c084fc]">{positionSizing.risk_level}</span>
                        </div>
                        <div className="flex justify-between items-center">
                            <span className="text-[10px] uppercase font-bold text-gray-500 tracking-wider ml-5">Adjustment</span>
                            <span className="text-xs font-bold text-gray-300 font-mono">× {positionSizing.risk_adjustment.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between items-center bg-[#21262d]/50 px-3 py-1.5 rounded border border-[#30363d]">
                            <span className="text-[10px] uppercase font-bold text-[#60a5fa] tracking-wider">Suggested</span>
                            <span className="text-xs font-black text-[#60a5fa] font-mono">{positionSizing.suggested_allocation.toFixed(1)}%</span>
                        </div>
                    </div>
                </div>
            )}

            {/* ── Sub-tab nav ── */}
            {(status === "fundamental" || status === "technical" || status === "decision" || status === "complete") && (
                <div className="flex gap-1 p-1.5 bg-[#161b22]/60 rounded-2xl border border-[#30363d] w-fit">
                    {(["overview", "fundamental", "technical", "history"] as const).map((tab) => (
                        <button
                            key={tab}
                            onClick={() => setActiveView(tab)}
                            className={`px-3 py-1.5 rounded-xl text-[9px] font-black uppercase tracking-wider transition-all ${activeView === tab
                                ? "tab-active"
                                : "text-gray-500 tab-inactive"
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
