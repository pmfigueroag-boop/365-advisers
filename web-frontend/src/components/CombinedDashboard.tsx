"use client";

import {
    ShieldCheck,
    TrendingUp,
    TrendingDown,
    Minus,
    Zap,
    ChevronDown,
    ChevronUp,
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
    if (signal === "BUY" || signal === "STRONG_BUY") return "text-green-400";
    if (signal === "SELL" || signal === "STRONG_SELL" || signal === "AVOID") return "text-red-400";
    return "text-yellow-400";
}

function signalBg(signal: string) {
    if (signal === "BUY" || signal === "STRONG_BUY") return "bg-green-500/10 border-green-500/30";
    if (signal === "SELL" || signal === "STRONG_SELL" || signal === "AVOID") return "bg-red-500/10 border-red-500/30";
    return "bg-yellow-500/10 border-yellow-500/30";
}

// ─── Conviction Arc ───────────────────────────────────────────────────────────

function ConvictionGauge({ fund, tech }: { fund: number; tech: number }) {
    // Combine: fund score 0-10, tech score 0-10.  Display as a unified gauge.
    const combined = (fund + tech) / 2;
    const pct = combined / 10;
    const color = combined >= 7 ? "#4ade80" : combined >= 5 ? "#d4af37" : "#f87171";

    const r = 52;
    const circ = 2 * Math.PI * r;
    // Only upper semicircle (180°)
    const filled = pct * circ * 0.5;
    const gap = circ - filled;

    return (
        <div className="flex flex-col items-center">
            <svg width={140} height={80} viewBox="0 0 140 80">
                {/* Track */}
                <path
                    d={`M 14 70 A 56 56 0 0 1 126 70`}
                    fill="none"
                    stroke="#21262d"
                    strokeWidth={10}
                    strokeLinecap="round"
                />
                {/* Fill — using stroke-dasharray on an arc is fiddly; use a simpler bar */}
                <path
                    d={`M 14 70 A 56 56 0 0 1 126 70`}
                    fill="none"
                    stroke={color}
                    strokeWidth={10}
                    strokeLinecap="round"
                    strokeDasharray={`${pct * 176} 176`}
                    style={{ transition: "stroke-dasharray 0.7s ease" }}
                />
                {/* Centre text */}
                <text x="70" y="64" textAnchor="middle" fill="white" fontSize="22" fontWeight="900">
                    {combined.toFixed(1)}
                </text>
                <text x="70" y="78" textAnchor="middle" fill="#6b7280" fontSize="8" fontWeight="bold">
                    /10 COMBINED
                </text>
            </svg>
        </div>
    );
}

// ─── Status timeline ──────────────────────────────────────────────────────────

function StatusTimeline({ status }: { status: string }) {
    const steps = [
        { key: "fetching_data", label: "Data" },
        { key: "fundamental", label: "Analysts" },
        { key: "technical", label: "Technical" },
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

    const { status, ticker, committee, technical, agentMemos, researchMemo, fundamentalDataReady, processingMs, fromCache } = state;

    const fundScore = committee?.score ?? 0;
    const techScore = technical?.summary?.technical_score ?? 0;

    // Overall conviction
    const hasBoth = !!committee && !!technical;
    const overallSignal = (() => {
        if (!hasBoth) return null;
        const avg = (fundScore + techScore) / 2;
        if (avg >= 7.5) return "STRONG BUY";
        if (avg >= 6) return "BUY";
        if (avg <= 2.5) return "STRONG SELL";
        if (avg <= 4) return "SELL";
        return "HOLD";
    })();

    const isLoading = status === "fetching_data" || status === "fundamental" || status === "technical";

    return (
        <div className="space-y-6" style={{ animation: "fadeSlideIn 0.4s ease both" }}>

            {/* ── Header bar ── */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div>
                    <div className="flex items-center gap-2 mb-1">
                        <Zap size={14} className="text-[#d4af37]" />
                        <h2 className="text-[9px] font-black uppercase tracking-[0.2em] text-gray-500">Combined Analysis</h2>
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
                                    <Clock size={9} className="opacity-0 w-0 h-0 hidden" /> {/* spacer hack */}
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

            {/* ── Combined Verdict Hero (shown when both engines complete) ── */}
            {hasBoth && overallSignal && (
                <div className={`glass-card p-8 border flex flex-col sm:flex-row items-center gap-8 ${signalBg(overallSignal)} bg-opacity-20`} style={{ animation: "verdictReveal 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) both" }}>
                    {/* Gauge */}
                    <ConvictionGauge fund={fundScore} tech={techScore} />

                    {/* Verdict text */}
                    <div className="flex-1">
                        <div className="flex items-center gap-3 flex-wrap mb-2">
                            <ShieldCheck size={16} className="text-[#d4af37]" />
                            <span className="text-[9px] font-black uppercase tracking-[0.2em] text-gray-500">Unified Verdict</span>
                            <span className={`text-xs font-black px-3 py-1 rounded-lg border uppercase ${signalBg(overallSignal)} ${signalColor(overallSignal)}`}>
                                {overallSignal}
                            </span>
                            {committee.allocation_recommendation && (
                                <span className="text-[9px] text-gray-500 font-bold">{committee.allocation_recommendation}</span>
                            )}
                        </div>

                        {committee.consensus_narrative && (
                            <p className="font-serif text-[1.15rem] leading-[1.6] text-gray-200 italic mb-5">
                                &ldquo;{committee.consensus_narrative}&rdquo;
                            </p>
                        )}

                        {/* Summary Catalysts / Risks inline */}
                        {(committee.key_catalysts.length > 0 || committee.key_risks.length > 0) && (
                            <div className="flex flex-col sm:flex-row gap-6 mb-5">
                                {committee.key_catalysts.length > 0 && (
                                    <div className="flex-1">
                                        <p className="text-[8px] font-black uppercase tracking-widest text-green-500/80 mb-2 flex items-center gap-1"><TrendingUp size={10} /> Key Catalyst</p>
                                        <p className="text-[11px] text-gray-400 leading-snug"><span className="text-green-500 mr-1">•</span>{committee.key_catalysts[0]}</p>
                                    </div>
                                )}
                                {committee.key_risks.length > 0 && (
                                    <div className="flex-1">
                                        <p className="text-[8px] font-black uppercase tracking-widest text-red-500/80 mb-2 flex items-center gap-1"><TrendingDown size={10} /> Main Risk</p>
                                        <p className="text-[11px] text-gray-400 leading-snug"><span className="text-red-500 mr-1">•</span>{committee.key_risks[0]}</p>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Score breakdown */}
                        <div className="grid grid-cols-2 gap-4 max-w-sm">
                            <div>
                                <p className="text-[8px] text-gray-600 font-bold uppercase mb-1">Fundamental</p>
                                <div className="flex items-center gap-2">
                                    <div className="flex-1 h-1.5 bg-[#21262d] rounded-full overflow-hidden">
                                        <div className="h-full bg-[#d4af37] rounded-full" style={{ width: `${fundScore * 10}%`, transition: "width 0.6s ease" }} />
                                    </div>
                                    <span className="text-[9px] font-black text-white font-mono">{fundScore.toFixed(1)}</span>
                                </div>
                            </div>
                            <div>
                                <p className="text-[8px] text-gray-600 font-bold uppercase mb-1">Technical</p>
                                <div className="flex items-center gap-2">
                                    <div className="flex-1 h-1.5 bg-[#21262d] rounded-full overflow-hidden">
                                        <div className="h-full bg-[#60a5fa] rounded-full" style={{ width: `${techScore * 10}%`, transition: "width 0.6s ease" }} />
                                    </div>
                                    <span className="text-[9px] font-black text-white font-mono">{techScore.toFixed(1)}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* ── Sub-tab nav ── */}
            {(status === "fundamental" || status === "technical" || status === "complete") && (
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
                            {tab === "overview" ? "Overview" :
                                tab === "fundamental" ? `Analysts ${agentMemos.length > 0 ? `(${agentMemos.length}/4)` : ""}` :
                                    tab === "technical" ? (technical ? `Tech ${techScore.toFixed(1)}` : "Technical") :
                                        "History"}
                        </button>
                    ))}
                </div>
            )}

            {/* ── Overview: catalysts + risks grid ── */}
            {(activeView === "overview" || !committee) && committee && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4" style={{ animation: "fadeSlideIn 0.3s ease both" }}>
                    {committee.key_catalysts.length > 0 && (
                        <div className="glass-card p-4 border-green-500/20">
                            <p className="text-[8px] font-black uppercase tracking-widest text-green-500/60 mb-2">Catalysts</p>
                            {committee.key_catalysts.map((c) => (
                                <p key={c} className="text-[10px] text-gray-400 flex gap-1.5 mb-1.5">
                                    <TrendingUp size={9} className="text-green-500 mt-0.5 flex-shrink-0" />{c}
                                </p>
                            ))}
                        </div>
                    )}
                    {committee.key_risks.length > 0 && (
                        <div className="glass-card p-4 border-red-500/20">
                            <p className="text-[8px] font-black uppercase tracking-widest text-red-500/60 mb-2">Risks</p>
                            {committee.key_risks.map((r) => (
                                <p key={r} className="text-[10px] text-gray-400 flex gap-1.5 mb-1.5">
                                    <TrendingDown size={9} className="text-red-500 mt-0.5 flex-shrink-0" />{r}
                                </p>
                            ))}
                        </div>
                    )}
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
