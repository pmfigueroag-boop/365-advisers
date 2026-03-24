"use client";

/**
 * InvestmentCommitteeDashboard.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Dedicated panel for the Investment Committee simulation.
 *
 * Shows 5 rounds of debate:
 *   Round 1 — Agent position memos (6 cards)
 *   Round 2 — Challenges
 *   Round 3 — Rebuttals
 *   Round 4 — Final votes + conviction drift
 *   Round 5 — Chairman's verdict
 */

import React, { useState } from "react";
import {
    Users,
    Swords,
    Shield,
    Vote as VoteIcon,
    Crown,
    Play,
    Loader2,
    ChevronDown,
    ChevronUp,
    TrendingUp,
    TrendingDown,
    Minus,
    AlertTriangle,
    CheckCircle,
    XCircle,
    ArrowRight,
    Scale,
    Target,
    Zap,
    ShieldCheck,
    Banknote,
    Activity,
    Globe,
} from "lucide-react";
import type {
    ICState,
    PositionMemo,
    Challenge,
    Rebuttal,
    Vote,
    ICVerdict,
} from "@/hooks/useICStream";
import { useICStream } from "@/hooks/useICStream";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function signalColor(signal: string) {
    const s = signal?.toUpperCase() ?? "";
    if (s.includes("STRONG_BUY")) return "text-emerald-400";
    if (s.includes("BUY")) return "text-green-400";
    if (s.includes("STRONG_SELL")) return "text-red-500";
    if (s.includes("SELL")) return "text-rose-400";
    return "text-amber-400";
}

function signalBg(signal: string) {
    const s = signal?.toUpperCase() ?? "";
    if (s.includes("BUY")) return "bg-emerald-500/8 border-emerald-500/25";
    if (s.includes("SELL")) return "bg-rose-500/8 border-rose-500/25";
    return "bg-amber-500/8 border-amber-500/25";
}

function severityColor(severity: string) {
    if (severity === "high") return "text-red-400 bg-red-500/10 border-red-500/25";
    if (severity === "moderate") return "text-amber-400 bg-amber-500/10 border-amber-500/25";
    return "text-blue-400 bg-blue-500/10 border-blue-500/25";
}

function agentIcon(name: string) {
    const n = name.toLowerCase();
    if (n.includes("value")) return <Scale size={14} className="text-blue-400" />;
    if (n.includes("quality")) return <ShieldCheck size={14} className="text-purple-400" />;
    if (n.includes("capital")) return <Banknote size={14} className="text-orange-400" />;
    if (n.includes("risk")) return <AlertTriangle size={14} className="text-amber-400" />;
    if (n.includes("growth")) return <Zap size={14} className="text-emerald-400" />;
    if (n.includes("macro")) return <Globe size={14} className="text-cyan-400" />;
    return <Activity size={14} className="text-gray-400" />;
}

function consensusLabel(strength: string) {
    const labels: Record<string, { text: string; color: string }> = {
        unanimous: { text: "UNANIMOUS", color: "text-emerald-400 bg-emerald-500/10" },
        strong_majority: { text: "STRONG MAJORITY", color: "text-green-400 bg-green-500/10" },
        majority: { text: "MAJORITY", color: "text-amber-400 bg-amber-500/10" },
        split: { text: "SPLIT", color: "text-orange-400 bg-orange-500/10" },
        contested: { text: "CONTESTED", color: "text-red-400 bg-red-500/10" },
    };
    return labels[strength] ?? labels.split;
}

// ─── Round Status ─────────────────────────────────────────────────────────────

type Round = "present" | "challenge" | "rebut" | "vote" | "verdict";

const ROUNDS: { id: Round; label: string; icon: React.ReactNode }[] = [
    { id: "present", label: "Present", icon: <Users size={12} /> },
    { id: "challenge", label: "Challenge", icon: <Swords size={12} /> },
    { id: "rebut", label: "Rebut", icon: <Shield size={12} /> },
    { id: "vote", label: "Vote", icon: <VoteIcon size={12} /> },
    { id: "verdict", label: "Verdict", icon: <Crown size={12} /> },
];

function getRoundStatus(round: Round, state: ICState): "pending" | "active" | "complete" {
    const statusMap: Record<string, Round> = {
        presenting: "present",
        challenging: "challenge",
        rebutting: "rebut",
        voting: "vote",
        synthesizing: "verdict",
    };
    const activeRound = statusMap[state.status];
    const roundOrder: Round[] = ["present", "challenge", "rebut", "vote", "verdict"];
    const currentIdx = roundOrder.indexOf(activeRound ?? "present");
    const roundIdx = roundOrder.indexOf(round);

    if (state.status === "complete") return "complete";
    if (roundIdx < currentIdx) return "complete";
    if (roundIdx === currentIdx) return "active";
    return "pending";
}

// ─── Sub-Components ───────────────────────────────────────────────────────────

function MemoCard({ memo }: { memo: PositionMemo }) {
    const [expanded, setExpanded] = useState(false);
    return (
        <div className={`glass-card p-4 border transition-all ${signalBg(memo.signal)}`}>
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    {agentIcon(memo.agent)}
                    <span className="text-[10px] font-black uppercase tracking-widest text-[#c9d1d9]">
                        {memo.agent}
                    </span>
                </div>
                <span className={`text-[9px] font-black uppercase px-2 py-0.5 rounded border ${signalBg(memo.signal)} ${signalColor(memo.signal)}`}>
                    {memo.signal?.replace("_", " ")}
                </span>
            </div>

            {/* Conviction Bar */}
            <div className="mb-3">
                <div className="flex justify-between text-[8px] text-[#8b949e] uppercase tracking-widest mb-1">
                    <span>Conviction</span>
                    <span className="text-[#d4af37]">{(memo.conviction * 100).toFixed(0)}%</span>
                </div>
                <div className="h-1 bg-[#21262d] rounded-full overflow-hidden">
                    <div
                        className="h-full bg-[#d4af37] rounded-full transition-all duration-700"
                        style={{ width: `${memo.conviction * 100}%` }}
                    />
                </div>
            </div>

            {/* Thesis */}
            <p className="text-[10px] text-[#8b949e] leading-relaxed italic border-l-2 border-[#30363d] pl-2">
                "{memo.thesis}"
            </p>

            {/* Expandable Details */}
            <button
                onClick={() => setExpanded(!expanded)}
                className="w-full flex items-center justify-between mt-3 pt-2 border-t border-[#30363d]/50 text-[8px] text-[#8b949e] uppercase tracking-widest hover:text-indigo-400 transition-colors cursor-pointer"
            >
                <span>Details</span>
                {expanded ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
            </button>
            {expanded && (
                <div className="mt-2 space-y-2" style={{ animation: "fadeSlideIn 0.2s ease" }}>
                    {memo.key_metrics?.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                            {memo.key_metrics.map((m, i) => (
                                <span key={i} className="text-[8px] px-1.5 py-0.5 bg-[#161b22] rounded border border-[#30363d] text-[#8b949e] font-mono">
                                    {m}
                                </span>
                            ))}
                        </div>
                    )}
                    {memo.catalysts?.length > 0 && (
                        <div className="space-y-1">
                            {memo.catalysts.map((c, i) => (
                                <div key={i} className="flex items-start gap-1.5 text-[9px] text-[#8b949e]">
                                    <TrendingUp size={9} className="text-emerald-400 mt-0.5 flex-shrink-0" />
                                    <span>{c}</span>
                                </div>
                            ))}
                        </div>
                    )}
                    {memo.risks?.length > 0 && (
                        <div className="space-y-1">
                            {memo.risks.map((r, i) => (
                                <div key={i} className="flex items-start gap-1.5 text-[9px] text-[#8b949e]">
                                    <AlertTriangle size={9} className="text-rose-400 mt-0.5 flex-shrink-0" />
                                    <span>{r}</span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

function ChallengeCard({ ch }: { ch: Challenge }) {
    return (
        <div className={`glass-card p-4 border ${severityColor(ch.severity)}`}>
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                    <Swords size={12} className="text-amber-400" />
                    <span className="text-[10px] font-black text-[#c9d1d9]">
                        {ch.challenger} <span className="text-[#8b949e] font-normal">→</span> {ch.target}
                    </span>
                </div>
                <span className={`text-[8px] font-black uppercase px-1.5 py-0.5 rounded border ${severityColor(ch.severity)}`}>
                    {ch.severity}
                </span>
            </div>
            <p className="text-[10px] text-[#8b949e] leading-relaxed">{ch.objection}</p>
            {ch.evidence?.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                    {ch.evidence.map((ev, i) => (
                        <span key={i} className="text-[8px] px-1.5 py-0.5 bg-[#161b22] rounded border border-[#30363d] text-[#8b949e]">
                            {ev}
                        </span>
                    ))}
                </div>
            )}
        </div>
    );
}

function RebuttalCard({ reb }: { reb: Rebuttal }) {
    return (
        <div className="glass-card p-4 border border-indigo-500/20 bg-indigo-500/5">
            <div className="flex items-center gap-2 mb-2">
                <Shield size={12} className="text-indigo-400" />
                <span className="text-[10px] font-black text-[#c9d1d9]">
                    {reb.agent} <span className="text-[#8b949e] font-normal">defends against</span> {reb.challenger}
                </span>
            </div>
            <p className="text-[10px] text-[#8b949e] leading-relaxed">{reb.defense}</p>
            {reb.concession && (
                <div className="mt-2 p-2 bg-amber-500/5 rounded border border-amber-500/20">
                    <p className="text-[9px] text-amber-400">
                        <span className="font-black uppercase tracking-widest">Concession:</span> {reb.concession}
                    </p>
                </div>
            )}
            {reb.conviction_adjustment !== 0 && (
                <div className="mt-1 flex items-center gap-1 text-[9px]">
                    {reb.conviction_adjustment < 0 ? (
                        <TrendingDown size={10} className="text-rose-400" />
                    ) : (
                        <TrendingUp size={10} className="text-emerald-400" />
                    )}
                    <span className={reb.conviction_adjustment < 0 ? "text-rose-400" : "text-emerald-400"}>
                        Conviction {reb.conviction_adjustment > 0 ? "+" : ""}{(reb.conviction_adjustment * 100).toFixed(0)}%
                    </span>
                </div>
            )}
        </div>
    );
}

function VoteCard({ vote }: { vote: Vote }) {
    return (
        <div className={`glass-card p-4 border transition-all ${signalBg(vote.signal)} ${vote.dissents ? "ring-1 ring-rose-500/30" : ""}`}>
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                    {agentIcon(vote.agent)}
                    <span className="text-[10px] font-black uppercase tracking-widest text-[#c9d1d9]">
                        {vote.agent}
                    </span>
                </div>
                <div className="flex items-center gap-1.5">
                    {vote.dissents && (
                        <span className="text-[7px] font-black uppercase px-1.5 py-0.5 rounded bg-rose-500/10 border border-rose-500/25 text-rose-400">
                            Dissent
                        </span>
                    )}
                    <span className={`text-[9px] font-black uppercase px-2 py-0.5 rounded border ${signalBg(vote.signal)} ${signalColor(vote.signal)}`}>
                        {vote.signal?.replace("_", " ")}
                    </span>
                </div>
            </div>

            {/* Conviction + Drift */}
            <div className="flex items-center gap-3 text-[9px] mb-2">
                <span className="text-[#8b949e]">
                    Conviction: <span className="text-[#d4af37] font-bold">{(vote.conviction * 100).toFixed(0)}%</span>
                </span>
                {vote.conviction_drift !== 0 && (
                    <span className={vote.conviction_drift < 0 ? "text-rose-400" : "text-emerald-400"}>
                        {vote.conviction_drift > 0 ? "↑" : "↓"} {Math.abs(vote.conviction_drift * 100).toFixed(0)}%
                    </span>
                )}
            </div>

            {vote.rationale && (
                <p className="text-[9px] text-[#8b949e] italic">{vote.rationale}</p>
            )}
        </div>
    );
}

function VerdictPanel({ verdict }: { verdict: ICVerdict }) {
    const cons = consensusLabel(verdict.consensus_strength);
    const pct = (verdict.score / 10) * 100;
    const barColor = verdict.score >= 7 ? "bg-emerald-500" : verdict.score >= 4 ? "bg-[#d4af37]" : "bg-rose-500";

    return (
        <div className="space-y-5" style={{ animation: "fadeSlideIn 0.4s ease both" }}>
            {/* Hero Score */}
            <div className="flex flex-col md:flex-row items-center gap-6">
                <div className={`flex-shrink-0 flex flex-col items-center justify-center p-8 rounded-2xl border ${signalBg(verdict.signal)} min-w-[160px]`}>
                    <span className={`text-6xl font-black tabular-nums tracking-tighter ${signalColor(verdict.signal)} drop-shadow-lg`}>
                        {verdict.score.toFixed(1)}
                    </span>
                    <span className="text-[10px] text-[#8b949e] font-bold mt-1">/10</span>
                    <span className={`text-sm font-black uppercase mt-2 tracking-wider ${signalColor(verdict.signal)}`}>
                        {verdict.signal?.replace("_", " ")}
                    </span>
                </div>

                <div className="flex-1 space-y-4">
                    {/* Consensus + Confidence */}
                    <div className="flex items-center gap-3 flex-wrap">
                        <span className={`text-[9px] font-black uppercase px-3 py-1.5 rounded-lg border ${cons.color}`}>
                            {cons.text}
                        </span>
                        <span className="text-[9px] font-black uppercase px-3 py-1.5 rounded-lg border border-[#30363d] bg-[#161b22] text-[#8b949e]">
                            Confidence: <span className="text-[#d4af37]">{(verdict.confidence * 100).toFixed(0)}%</span>
                        </span>
                    </div>

                    {/* Score Bar */}
                    <div>
                        <div className="h-2 bg-[#21262d] rounded-full overflow-hidden">
                            <div className={`h-full ${barColor} rounded-full transition-all duration-1000`} style={{ width: `${pct}%` }} />
                        </div>
                    </div>

                    {/* Vote Breakdown */}
                    {verdict.vote_breakdown && Object.keys(verdict.vote_breakdown).length > 0 && (
                        <div className="flex items-center gap-2 flex-wrap">
                            {Object.entries(verdict.vote_breakdown).map(([signal, count]) => (
                                <span key={signal} className={`text-[9px] font-bold px-2 py-1 rounded border ${signalBg(signal)} ${signalColor(signal)}`}>
                                    {signal.replace("_", " ")}: {count}
                                </span>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {/* Narrative */}
            <div className="glass-card p-5 border-[#30363d]">
                <div className="flex items-center gap-2 mb-3">
                    <Crown size={14} className="text-[#d4af37]" />
                    <span className="text-[10px] font-black uppercase tracking-widest text-[#d4af37]">
                        Chairman's Synthesis
                    </span>
                </div>
                <p className="text-[11px] text-[#c9d1d9] leading-relaxed font-serif italic border-l-2 border-[#d4af37]/40 pl-3">
                    "{verdict.narrative}"
                </p>
            </div>

            {/* Catalysts + Risks */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {verdict.key_catalysts?.length > 0 && (
                    <div className="glass-card p-4 border border-emerald-500/20 bg-emerald-500/5">
                        <p className="text-[9px] font-black uppercase tracking-widest text-emerald-400 mb-2 flex items-center gap-1.5">
                            <TrendingUp size={11} /> Key Catalysts
                        </p>
                        <ul className="space-y-1.5">
                            {verdict.key_catalysts.map((c, i) => (
                                <li key={i} className="text-[10px] text-[#8b949e] flex items-start gap-1.5">
                                    <span className="text-emerald-400 mt-0.5">▸</span>
                                    <span>{c}</span>
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
                {verdict.key_risks?.length > 0 && (
                    <div className="glass-card p-4 border border-rose-500/20 bg-rose-500/5">
                        <p className="text-[9px] font-black uppercase tracking-widest text-rose-400 mb-2 flex items-center gap-1.5">
                            <AlertTriangle size={11} /> Key Risks
                        </p>
                        <ul className="space-y-1.5">
                            {verdict.key_risks.map((r, i) => (
                                <li key={i} className="text-[10px] text-[#8b949e] flex items-start gap-1.5">
                                    <span className="text-rose-400 mt-0.5">▸</span>
                                    <span>{r}</span>
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>

            {/* Dissenting Opinions */}
            {verdict.dissenting_opinions?.length > 0 && (
                <div className="glass-card p-4 border border-amber-500/20 bg-amber-500/5">
                    <p className="text-[9px] font-black uppercase tracking-widest text-amber-400 mb-2 flex items-center gap-1.5">
                        <XCircle size={11} /> Dissenting Opinions
                    </p>
                    <ul className="space-y-2">
                        {verdict.dissenting_opinions.map((d, i) => (
                            <li key={i} className="text-[10px] text-[#8b949e] p-2 bg-[#161b22] rounded border border-[#30363d]">
                                {d}
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {/* Conviction Drift */}
            {verdict.conviction_drift_summary && (
                <div className="text-[9px] text-[#8b949e] italic px-3 py-2 bg-[#161b22] rounded border border-[#30363d]">
                    <span className="text-[#d4af37] font-bold uppercase tracking-wider not-italic">Conviction Drift:</span>{" "}
                    {verdict.conviction_drift_summary}
                </div>
            )}
        </div>
    );
}

// ─── Main Component ───────────────────────────────────────────────────────────

interface InvestmentCommitteeDashboardProps {
    ticker: string | null;
}

export default function InvestmentCommitteeDashboard({ ticker }: InvestmentCommitteeDashboardProps) {
    const { state, runIC, reset } = useICStream();
    const [activeRound, setActiveRound] = useState<Round>("present");

    const isRunning = state.status !== "idle" && state.status !== "complete" && state.status !== "error";
    const canRun = ticker && !isRunning;

    return (
        <div className="space-y-4" style={{ animation: "fadeSlideIn 0.4s ease both" }}>
            {/* Header Bar */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <Users size={16} className="text-[#d4af37]" />
                    <div>
                        <h3 className="text-xs font-black uppercase tracking-widest text-[#c9d1d9]">
                            Investment Committee
                        </h3>
                        <p className="text-[8px] text-[#8b949e] uppercase tracking-widest">
                            6-Agent Structured Debate · 5 Rounds
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    {state.status === "complete" && (
                        <span className="text-[8px] text-[#8b949e] font-mono">
                            {(state.elapsedMs / 1000).toFixed(1)}s
                        </span>
                    )}
                    <button
                        onClick={() => canRun && ticker && runIC(ticker)}
                        disabled={!canRun}
                        className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest border transition-all ${
                            canRun
                                ? "bg-[#d4af37]/10 text-[#d4af37] border-[#d4af37]/30 hover:bg-[#d4af37]/20 cursor-pointer"
                                : "bg-[#161b22] text-[#8b949e] border-[#30363d] cursor-not-allowed"
                        }`}
                    >
                        {isRunning ? (
                            <>
                                <Loader2 size={11} className="animate-spin" />
                                Running...
                            </>
                        ) : (
                            <>
                                <Play size={11} />
                                Run IC Session
                            </>
                        )}
                    </button>
                </div>
            </div>

            {/* Idle State */}
            {state.status === "idle" && (
                <div className="flex flex-col items-center justify-center py-16 text-center glass-card border-[#30363d]">
                    <Users size={36} className="text-[#30363d] mb-4" />
                    <p className="text-sm text-[#8b949e] font-bold">No IC Session Active</p>
                    <p className="text-[10px] text-[#8b949e] mt-1">
                        Click <span className="text-[#d4af37] font-bold">Run IC Session</span> to start a structured debate.
                    </p>
                </div>
            )}

            {/* Round Progress Bar */}
            {state.status !== "idle" && (
                <div className="flex items-center gap-1 p-1.5 glass-card border-[#30363d] rounded-xl">
                    {ROUNDS.map((r, idx) => {
                        const status = getRoundStatus(r.id, state);
                        return (
                            <React.Fragment key={r.id}>
                                {idx > 0 && (
                                    <div className={`flex-shrink-0 w-4 h-[1px] ${status === "pending" ? "bg-[#30363d]" : "bg-[#d4af37]/50"}`} />
                                )}
                                <button
                                    onClick={() => setActiveRound(r.id)}
                                    className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all whitespace-nowrap cursor-pointer ${
                                        activeRound === r.id
                                            ? "bg-[#d4af37]/15 text-[#d4af37] border border-[#d4af37]/30"
                                            : status === "complete"
                                            ? "text-emerald-400/80 hover:bg-[#161b22]"
                                            : status === "active"
                                            ? "text-[#d4af37] animate-pulse"
                                            : "text-[#8b949e]/50"
                                    }`}
                                >
                                    {status === "complete" ? <CheckCircle size={10} className="text-emerald-400" /> : r.icon}
                                    {r.label}
                                </button>
                            </React.Fragment>
                        );
                    })}
                </div>
            )}

            {/* Round Content */}
            {state.status !== "idle" && (
                <div className="glass-card border-[#30363d] p-5">
                    {/* Round 1: Present */}
                    {activeRound === "present" && (
                        <div>
                            <div className="flex items-center gap-2 mb-4">
                                <Users size={14} className="text-[#d4af37]" />
                                <span className="text-[10px] font-black uppercase tracking-widest text-[#d4af37]">
                                    Round 1 — Initial Positions
                                </span>
                                {state.memos.length > 0 && (
                                    <span className="text-[8px] text-[#8b949e] font-mono ml-auto">
                                        {state.memos.length}/6 agents
                                    </span>
                                )}
                            </div>
                            {state.memos.length > 0 ? (
                                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
                                    {state.memos.map((memo, i) => (
                                        <MemoCard key={`memo-${i}`} memo={memo} />
                                    ))}
                                </div>
                            ) : (
                                <div className="flex items-center justify-center py-12 text-[10px] text-[#8b949e] animate-pulse uppercase tracking-widest">
                                    <Loader2 size={14} className="animate-spin mr-2" />
                                    Agents are preparing their theses...
                                </div>
                            )}
                        </div>
                    )}

                    {/* Round 2: Challenge */}
                    {activeRound === "challenge" && (
                        <div>
                            <div className="flex items-center gap-2 mb-4">
                                <Swords size={14} className="text-amber-400" />
                                <span className="text-[10px] font-black uppercase tracking-widest text-amber-400">
                                    Round 2 — Challenges
                                </span>
                                {state.challenges.length > 0 && (
                                    <span className="text-[8px] text-[#8b949e] font-mono ml-auto">
                                        {state.challenges.length} challenges
                                    </span>
                                )}
                            </div>
                            {state.challenges.length > 0 ? (
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    {state.challenges.map((ch, i) => (
                                        <ChallengeCard key={`ch-${i}`} ch={ch} />
                                    ))}
                                </div>
                            ) : (
                                <div className="flex items-center justify-center py-12 text-[10px] text-[#8b949e] animate-pulse uppercase tracking-widest">
                                    <Loader2 size={14} className="animate-spin mr-2" />
                                    Agents are formulating challenges...
                                </div>
                            )}
                        </div>
                    )}

                    {/* Round 3: Rebut */}
                    {activeRound === "rebut" && (
                        <div>
                            <div className="flex items-center gap-2 mb-4">
                                <Shield size={14} className="text-indigo-400" />
                                <span className="text-[10px] font-black uppercase tracking-widest text-indigo-400">
                                    Round 3 — Rebuttals
                                </span>
                            </div>
                            {state.rebuttals.length > 0 ? (
                                <div className="flex flex-col gap-3">
                                    {state.rebuttals.map((reb, i) => (
                                        <RebuttalCard key={`reb-${i}`} reb={reb} />
                                    ))}
                                </div>
                            ) : (
                                <div className="flex items-center justify-center py-12 text-[10px] text-[#8b949e] animate-pulse uppercase tracking-widest">
                                    <Loader2 size={14} className="animate-spin mr-2" />
                                    Agents are defending their positions...
                                </div>
                            )}
                        </div>
                    )}

                    {/* Round 4: Vote */}
                    {activeRound === "vote" && (
                        <div>
                            <div className="flex items-center gap-2 mb-4">
                                <VoteIcon size={14} className="text-purple-400" />
                                <span className="text-[10px] font-black uppercase tracking-widest text-purple-400">
                                    Round 4 — Final Votes
                                </span>
                                {state.votes.length > 0 && (
                                    <span className="text-[8px] text-[#8b949e] font-mono ml-auto">
                                        {state.votes.length}/6 votes cast
                                    </span>
                                )}
                            </div>
                            {state.votes.length > 0 ? (
                                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
                                    {state.votes.map((vote, i) => (
                                        <VoteCard key={`vote-${i}`} vote={vote} />
                                    ))}
                                </div>
                            ) : (
                                <div className="flex items-center justify-center py-12 text-[10px] text-[#8b949e] animate-pulse uppercase tracking-widest">
                                    <Loader2 size={14} className="animate-spin mr-2" />
                                    Agents are casting their votes...
                                </div>
                            )}
                        </div>
                    )}

                    {/* Round 5: Verdict */}
                    {activeRound === "verdict" && (
                        <div>
                            {state.verdict ? (
                                <VerdictPanel verdict={state.verdict} />
                            ) : (
                                <div className="flex items-center justify-center py-16 text-[10px] text-[#8b949e] animate-pulse uppercase tracking-widest">
                                    <Loader2 size={14} className="animate-spin mr-2" />
                                    Chairman is synthesizing the verdict...
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* Error State */}
            {state.status === "error" && (
                <div className="glass-card p-4 border border-rose-500/20 bg-rose-500/5 flex items-center gap-3">
                    <XCircle size={16} className="text-rose-400 flex-shrink-0" />
                    <p className="text-[10px] text-rose-400">{state.error}</p>
                </div>
            )}
        </div>
    );
}
