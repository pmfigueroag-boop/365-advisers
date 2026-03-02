"use client";

import { ShieldCheck, TrendingUp, TrendingDown, Minus, ChevronDown, ChevronUp, ExternalLink } from "lucide-react";
import { useState } from "react";
import type { AgentMemo, CommitteeVerdict, FundamentalDataReady } from "@/hooks/useFundamentalStream";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function signalColor(signal: string) {
    if (signal === "BUY") return "text-green-400";
    if (signal === "SELL" || signal === "AVOID") return "text-red-400";
    return "text-yellow-400";
}

function signalBg(signal: string) {
    if (signal === "BUY") return "bg-green-500/10 border-green-500/30";
    if (signal === "SELL" || signal === "AVOID") return "bg-red-500/10 border-red-500/30";
    return "bg-yellow-500/10 border-yellow-500/30";
}

function allocationColor(rec: string) {
    if (rec === "Overweight") return "text-green-400";
    if (rec === "Underweight" || rec === "Avoid") return "text-red-400";
    return "text-gray-400";
}

function ScoreRing({ score, size = 72 }: { score: number; size?: number }) {
    const radius = size / 2 - 6;
    const circumference = 2 * Math.PI * radius;
    const filled = (score / 10) * circumference;
    const color = score >= 7 ? "#4ade80" : score >= 5 ? "#d4af37" : "#f87171";

    return (
        <svg width={size} height={size} className="rotate-[-90deg]">
            <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#21262d" strokeWidth={5} />
            <circle
                cx={size / 2} cy={size / 2} r={radius}
                fill="none" stroke={color} strokeWidth={5}
                strokeDasharray={`${filled} ${circumference}`}
                strokeLinecap="round"
                style={{ transition: "stroke-dasharray 0.6s ease" }}
            />
            <text
                x={size / 2} y={size / 2 + 1}
                textAnchor="middle" dominantBaseline="middle"
                fill="white" fontSize={size * 0.22} fontWeight="900"
                style={{ transform: `rotate(90deg) translateX(0)`, transformOrigin: `${size / 2}px ${size / 2}px` }}
            >
                {score.toFixed(1)}
            </text>
        </svg>
    );
}

// ─── Agent Memo Card ──────────────────────────────────────────────────────────

function AgentMemoCard({ memo, index }: { memo: AgentMemo; index: number }) {
    const [open, setOpen] = useState(false);
    const [frameworkName] = memo.framework.split("—");

    return (
        <div
            className={`glass-card p-4 border flex flex-col gap-3 ${signalBg(memo.signal)}`}
            style={{ animation: `fadeSlideIn 0.3s ease ${index * 0.08}s both` }}
        >
            {/* Header */}
            <div className="flex items-start justify-between gap-2">
                <div>
                    <p className="text-[10px] font-black uppercase tracking-widest text-gray-500 mb-0.5">
                        {frameworkName.trim()}
                    </p>
                    <p className="text-sm font-black text-white leading-tight">{memo.agent}</p>
                </div>
                <span className={`text-[9px] font-black px-2 py-1 rounded border uppercase flex-shrink-0 ${signalBg(memo.signal)} ${signalColor(memo.signal)}`}>
                    {memo.signal}
                </span>
            </div>

            {/* Conviction bar */}
            <div>
                <div className="flex justify-between text-[8px] text-gray-600 mb-1">
                    <span>Conviction</span>
                    <span className="font-mono font-bold text-gray-400">{(memo.conviction * 100).toFixed(0)}%</span>
                </div>
                <div className="h-1 bg-[#21262d] rounded-full overflow-hidden">
                    <div
                        className={`h-full rounded-full transition-all duration-700 ${memo.signal === "BUY" ? "bg-green-500" : memo.signal === "SELL" ? "bg-red-500" : "bg-yellow-500"}`}
                        style={{ width: `${memo.conviction * 100}%` }}
                    />
                </div>
            </div>

            {/* Memo text */}
            <p className="text-[11px] text-gray-400 leading-relaxed italic">&ldquo;{memo.memo}&rdquo;</p>

            {/* Expandable detail */}
            <button
                onClick={() => setOpen((o) => !o)}
                className="flex items-center gap-1 text-[8px] text-gray-600 hover:text-[#d4af37] transition-colors font-bold uppercase tracking-wider"
            >
                {open ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
                {open ? "Less" : "Detail"}
            </button>

            {open && (
                <div className="space-y-2 text-[9px] border-t border-[#30363d] pt-2" style={{ animation: "fadeSlideIn 0.2s ease" }}>
                    {memo.key_metrics_used.length > 0 && (
                        <div>
                            <p className="text-gray-600 font-bold mb-1">Metrics Used</p>
                            <div className="flex flex-wrap gap-1">
                                {memo.key_metrics_used.map((m) => (
                                    <span key={m} className="bg-[#21262d] text-gray-400 px-1.5 py-0.5 rounded text-[8px] font-mono">{m}</span>
                                ))}
                            </div>
                        </div>
                    )}
                    {memo.catalysts.length > 0 && (
                        <div>
                            <p className="text-green-500/70 font-bold mb-1">Catalysts</p>
                            {memo.catalysts.map((c) => <p key={c} className="text-gray-400">↗ {c}</p>)}
                        </div>
                    )}
                    {memo.risks.length > 0 && (
                        <div>
                            <p className="text-red-500/70 font-bold mb-1">Risks</p>
                            {memo.risks.map((r) => <p key={r} className="text-gray-400">↘ {r}</p>)}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// ─── Research Memo Card ───────────────────────────────────────────────────────

interface ResearchMemoCardProps {
    dataReady: FundamentalDataReady | null;
    agentMemos: AgentMemo[];
    committee: CommitteeVerdict | null;
    researchMemo: string | null;
    agentCount: number;
    totalAgents: number;
    status: string;
}

export default function ResearchMemoCard({
    dataReady,
    agentMemos,
    committee,
    researchMemo,
    agentCount,
    totalAgents,
    status,
}: ResearchMemoCardProps) {
    const [memoExpanded, setMemoExpanded] = useState(false);

    if (!dataReady) return null;

    return (
        <div className="space-y-6" style={{ animation: "fadeSlideIn 0.4s ease both" }}>

            {/* ── Committee Verdict Header ─── */}
            {committee && (
                <div className="glass-card p-6 border-[#d4af37]/30 bg-[#d4af37]/5" style={{ animation: "fadeSlideIn 0.4s ease both" }}>
                    <div className="flex flex-col sm:flex-row items-start sm:items-center gap-6">

                        {/* Score ring */}
                        <div className="flex-shrink-0">
                            <ScoreRing score={committee.score} size={80} />
                        </div>

                        {/* Main info */}
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-3 mb-2 flex-wrap">
                                <ShieldCheck size={16} className="text-[#d4af37]" />
                                <h2 className="text-xs font-black uppercase tracking-[0.2em] text-gray-400">
                                    Investment Committee Verdict
                                </h2>
                                <span className={`text-xs font-black px-2.5 py-1 rounded-lg border uppercase ${signalBg(committee.signal)} ${signalColor(committee.signal)}`}>
                                    {committee.signal}
                                </span>
                                <span className={`text-xs font-semibold ${allocationColor(committee.allocation_recommendation)}`}>
                                    {committee.allocation_recommendation}
                                </span>
                            </div>

                            <p className="text-sm text-gray-300 leading-relaxed italic mb-3">
                                &ldquo;{committee.consensus_narrative}&rdquo;
                            </p>

                            <div className="flex gap-4 flex-wrap text-[9px] text-gray-600">
                                <span>Score: <b className="text-white">{committee.score}/10</b></span>
                                <span>Risk-Adj: <b className="text-white">{committee.risk_adjusted_score}/10</b></span>
                                <span>Confidence: <b className="text-white">{(committee.confidence * 100).toFixed(0)}%</b></span>
                                {committee.elapsed_ms && <span>Time: <b className="text-gray-400">{(committee.elapsed_ms / 1000).toFixed(1)}s</b></span>}
                            </div>
                        </div>
                    </div>

                    {/* Catalysts / Risks */}
                    {(committee.key_catalysts.length > 0 || committee.key_risks.length > 0) && (
                        <div className="mt-4 pt-4 border-t border-[#d4af37]/20 grid grid-cols-1 sm:grid-cols-2 gap-4">
                            {committee.key_catalysts.length > 0 && (
                                <div>
                                    <p className="text-[8px] font-black uppercase tracking-widest text-green-500/60 mb-2">Key Catalysts</p>
                                    {committee.key_catalysts.map((c) => (
                                        <p key={c} className="text-[10px] text-gray-400 flex gap-1 mb-1"><span className="text-green-500">↗</span>{c}</p>
                                    ))}
                                </div>
                            )}
                            {committee.key_risks.length > 0 && (
                                <div>
                                    <p className="text-[8px] font-black uppercase tracking-widest text-red-500/60 mb-2">Key Risks</p>
                                    {committee.key_risks.map((r) => (
                                        <p key={r} className="text-[10px] text-gray-400 flex gap-1 mb-1"><span className="text-red-500">↘</span>{r}</p>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* ── Progress bar while analyzing ─── */}
            {status === "analyzing" && (
                <div className="glass-card p-4 border-[#30363d]">
                    <div className="flex justify-between text-[9px] text-gray-500 mb-2">
                        <span className="font-bold uppercase tracking-widest">Analyst Committee</span>
                        <span className="font-mono">{agentCount} / {totalAgents}</span>
                    </div>
                    <div className="h-1 bg-[#21262d] rounded-full overflow-hidden">
                        <div
                            className="h-full bg-[#d4af37] rounded-full transition-all duration-500"
                            style={{ width: `${(agentCount / totalAgents) * 100}%` }}
                        />
                    </div>
                </div>
            )}

            {/* ── 4 Agent Memo Cards ─── */}
            {agentMemos.length > 0 && (
                <div>
                    <p className="text-[9px] font-black uppercase tracking-widest text-gray-500 mb-3">Analyst Memos</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        {agentMemos.map((memo, i) => (
                            <AgentMemoCard key={memo.agent} memo={memo} index={i} />
                        ))}
                    </div>
                </div>
            )}

            {/* ── Research Memo 1-Pager ─── */}
            {researchMemo && (
                <div className="glass-card p-5 border-[#30363d]">
                    <div className="flex items-center justify-between mb-3">
                        <p className="text-[9px] font-black uppercase tracking-widest text-gray-500">Research Memo</p>
                        <button
                            onClick={() => setMemoExpanded((e) => !e)}
                            className="text-[8px] font-bold text-gray-600 hover:text-[#d4af37] flex items-center gap-1 transition-colors uppercase tracking-wider"
                        >
                            {memoExpanded ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
                            {memoExpanded ? "Collapse" : "Expand 1-Pager"}
                        </button>
                    </div>
                    {memoExpanded && (
                        <pre className="text-[10px] text-gray-400 whitespace-pre-wrap font-mono leading-relaxed border-t border-[#30363d] pt-3" style={{ animation: "fadeSlideIn 0.3s ease" }}>
                            {researchMemo}
                        </pre>
                    )}
                </div>
            )}
        </div>
    );
}
