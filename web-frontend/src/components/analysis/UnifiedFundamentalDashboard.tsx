"use client";

import React, { useMemo, useState, useEffect } from "react";
import {
    Radar,
    RadarChart,
    PolarGrid,
    PolarAngleAxis,
    ResponsiveContainer,
} from "recharts";
import {
    ShieldCheck,
    TrendingUp,
    TrendingDown,
    Minus,
    Activity,
    AlertTriangle,
    Target,
    Banknote,
    Briefcase,
    Zap,
    Scale,
    ChevronDown,
    ChevronUp,
    Clock
} from "lucide-react";

import type { FundamentalDataReady, AgentMemo, CommitteeVerdict } from "@/hooks/useFundamentalStream";

// ─── Formatting Helpers ────────────────────────────────────────────────────────

function signalColor(signal: string) {
    if (signal === "BUY" || signal === "STRONG_BUY") return "text-emerald-400";
    if (signal === "SELL" || signal === "STRONG_SELL" || signal === "AVOID") return "text-rose-400";
    return "text-amber-400";
}

function signalBg(signal: string) {
    if (signal === "BUY" || signal === "STRONG_BUY") return "bg-emerald-500/10 border-emerald-500/30";
    if (signal === "SELL" || signal === "STRONG_SELL" || signal === "AVOID") return "bg-rose-500/10 border-rose-500/30";
    return "bg-amber-500/10 border-amber-500/30";
}

function normalizeSignalNumber(signal: string): number {
    const s = signal.toUpperCase();
    if (s.includes("STRONG_BUY")) return 10;
    if (s.includes("BUY")) return 8;
    if (s.includes("HOLD")) return 5;
    if (s.includes("STRONG_SELL") || s.includes("AVOID")) return 0;
    if (s.includes("SELL")) return 2;
    return 5;
}

function formatRatio(key: string, value: number | string | undefined): string {
    if (value === undefined || value === null) return "N/A";
    if (typeof value === "string") return value;
    
    // Format based on common ratio names
    const k = key.toLowerCase();
    if (k.includes("margin") || k.includes("yield") || k.includes("roe") || k.includes("roa") || k.includes("roic") || k.includes("growth")) {
        return `${(value * 100).toFixed(1)}%`;
    }
    if (k.includes("debt") || k.includes("ratio") || k.includes("multiple")) {
        return `${value.toFixed(2)}x`;
    }
    if (k.includes("pe") || k.includes("p/e") || k.includes("pb") || k.includes("ps") || k.includes("ev")) {
        return `${value.toFixed(1)}x`;
    }
    // Default for numbers
    if (value > 1000000) return `$${(value / 1000000).toFixed(1)}M`;
    return value.toLocaleString('en-US', { maximumFractionDigits: 2 });
}

// ─── Components ────────────────────────────────────────────────────────────────

function ScoreRing({ score, size = 64 }: { score: number; size?: number }) {
    const [displayed, setDisplayed] = useState(0);

    useEffect(() => {
        let rafId: number;
        const duration = 800;
        const startTime = performance.now();
        const startVal = 0;

        const tick = (now: number) => {
            const elapsed = now - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            setDisplayed(startVal + eased * (score - startVal));
            if (progress < 1) {
                rafId = requestAnimationFrame(tick);
            }
        };

        rafId = requestAnimationFrame(tick);
        return () => cancelAnimationFrame(rafId);
    }, [score]);

    const radius = size / 2 - 4;
    const circumference = 2 * Math.PI * radius;
    const filled = (displayed / 10) * circumference;
    const color = score >= 7 ? "#34d399" : score >= 4 ? "#fbbf24" : "#fb7185";

    return (
        <svg width={size} height={size} className="rotate-[-90deg]">
            <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#21262d" strokeWidth={4} />
            <circle
                cx={size / 2} cy={size / 2} r={radius}
                fill="none" stroke={color} strokeWidth={4}
                strokeDasharray={`${filled} ${circumference}`}
                strokeLinecap="round"
            />
            <text
                x={size / 2} y={size / 2 + 1}
                textAnchor="middle" dominantBaseline="middle"
                fill="white" fontSize={size * 0.25} fontWeight="900"
                style={{ transform: `rotate(90deg) translateX(0)`, transformOrigin: `${size / 2}px ${size / 2}px` }}
            >
                {displayed.toFixed(1)}
            </text>
        </svg>
    );
}

// ─── Micro Card: Agent ────────────────────────────────────────────────────────

function FundAgentCard({ memo, ratios }: { memo: AgentMemo, ratios: any }) {
    const name = memo.agent.toLowerCase();
    
    // Determine category based on agent name
    let title = "Analysis Module";
    let icon = <Activity size={14} className="text-gray-400" />;
    let relevantMetrics: Array<{label: string, val: any}> = [];

    if (name.includes("value") || name.includes("margin")) {
        title = "Value & Margin of Safety";
        icon = <Scale size={14} className="text-blue-400" />;
        const val = ratios?.valuation || {};
        relevantMetrics = [
            { label: "P/E", val: val.pe_ratio ?? val.forward_pe },
            { label: "P/B", val: val.pb_ratio },
            { label: "EV/EBITDA", val: val.ev_ebitda }
        ];
    } else if (name.includes("quality") || name.includes("moat")) {
        title = "Quality & Moat";
        icon = <ShieldCheck size={14} className="text-purple-400" />;
        const prof = ratios?.profitability || {};
        const q = ratios?.quality || {};
        relevantMetrics = [
            { label: "ROIC", val: prof.roic ?? q.roic },
            { label: "ROE", val: prof.roe },
            { label: "Net Margin", val: prof.net_margin ?? prof.profit_margin }
        ];
    } else if (name.includes("growth") || name.includes("catalyst")) {
        title = "Growth & Catalysts";
        icon = <Zap size={14} className="text-emerald-400" />;
        const prof = ratios?.profitability || {};
        relevantMetrics = [
            { label: "Rev Growth", val: prof.revenue_growth },
            { label: "EPS Growth", val: prof.eps_growth ?? prof.earnings_growth },
            { label: "Op Margin", val: prof.operating_margin }
        ];
    } else if (name.includes("risk") || name.includes("solvency")) {
        title = "Risk & Solvency";
        icon = <AlertTriangle size={14} className="text-amber-400" />;
        const lev = ratios?.leverage || {};
        relevantMetrics = [
            { label: "Debt/Eq", val: lev.debt_to_equity },
            { label: "Current", val: lev.current_ratio },
            { label: "Quick", val: lev.quick_ratio }
        ];
    } else {
        title = memo.agent;
    }

    // Filter out undefined metrics and fallback to agent's key_metrics_used 
    const displayMetrics = relevantMetrics.filter(m => m.val !== undefined && m.val !== null);

    // Calculate normalized score for the progress bar
    const baseScore = normalizeSignalNumber(memo.signal);
    const adjustedScore = 5 + (baseScore - 5) * memo.conviction;

    return (
        <div className={`glass-card p-4 flex flex-col gap-3 border transition-colors ${signalBg(memo.signal)} hover:border-white/20`}>
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    {icon}
                    <h3 className="text-xs font-black uppercase tracking-widest text-gray-200">{title}</h3>
                </div>
                <div className={`text-[9px] font-black px-2 py-0.5 rounded border uppercase ${signalBg(memo.signal)} ${signalColor(memo.signal)}`}>
                    {memo.signal}
                </div>
            </div>

            {/* Metrics */}
            <div className="grid grid-cols-3 gap-2 mt-1">
                {displayMetrics.length > 0 ? displayMetrics.map((m, i) => (
                    <div key={i} className="flex flex-col">
                        <span className="text-[9px] text-gray-500 uppercase tracking-widest">{m.label}</span>
                        <span className="text-xs font-mono font-medium text-gray-300">{formatRatio(m.label, m.val)}</span>
                    </div>
                )) : (
                    <div className="col-span-3 text-[10px] text-gray-500 italic">No hard metrics mapped.</div>
                )}
            </div>

            {/* Score Weight Bar */}
            <div className="mt-auto pt-2">
                <div className="flex justify-between items-end mb-1">
                    <span className="text-[9px] text-gray-500 uppercase font-bold">AI Conviction</span>
                    <span className="text-[10px] font-mono font-bold text-gray-300">{(memo.conviction * 100).toFixed(0)}%</span>
                </div>
                <div className="relative h-1.5 bg-[#21262d] rounded-full overflow-hidden">
                    <div 
                        className={`absolute top-0 left-0 h-full rounded-full transition-all duration-1000 ${memo.signal.includes("BUY") ? "bg-emerald-500" : memo.signal.includes("SELL") ? "bg-rose-500" : "bg-amber-500"}`}
                        style={{ width: `${memo.conviction * 100}%` }}
                    />
                </div>
            </div>
            
            {/* AI Narrative snippet */}
            <div className="mt-1 pt-2 border-t border-white/5">
                <p className="text-[10px] text-gray-400 leading-relaxed italic line-clamp-2" title={memo.memo}>
                    "{memo.memo}"
                </p>
            </div>
        </div>
    );
}

// ─── Main Interface ────────────────────────────────────────────────────────────

export interface UnifiedFundamentalDashboardProps {
    dataReady: FundamentalDataReady | null;
    agentMemos: AgentMemo[];
    committee: CommitteeVerdict | null;
    researchMemo: string | null;
    agentCount: number;
    totalAgents: number;
    status: string;
}

export default function UnifiedFundamentalDashboard({
    dataReady,
    agentMemos,
    committee,
    researchMemo,
    agentCount,
    totalAgents,
    status
}: UnifiedFundamentalDashboardProps) {
    const [memoExpanded, setMemoExpanded] = useState(false);

    // Compute Radar Chart Data
    const radarData = useMemo(() => {
        let value = 5, quality = 5, growth = 5, risk = 5;

        agentMemos.forEach(memo => {
            const base = normalizeSignalNumber(memo.signal); 
            const adjustedScore = 5 + (base - 5) * memo.conviction;

            const name = memo.agent.toLowerCase();
            if (name.includes("value") || name.includes("margin")) value = adjustedScore;
            else if (name.includes("quality") || name.includes("moat")) quality = adjustedScore;
            else if (name.includes("growth") || name.includes("catalyst")) growth = adjustedScore;
            else if (name.includes("risk") || name.includes("solvency")) risk = adjustedScore;
        });

        return [
            { subject: "Value", score: parseFloat(value.toFixed(1)), fullMark: 10 },
            { subject: "Quality", score: parseFloat(quality.toFixed(1)), fullMark: 10 },
            { subject: "Growth", score: parseFloat(growth.toFixed(1)), fullMark: 10 },
            { subject: "Solvency", score: parseFloat(risk.toFixed(1)), fullMark: 10 },
        ];
    }, [agentMemos]);

    if (!dataReady && status !== "fetching_data" && status !== "analyzing") {
        return null;
    }

    return (
        <div className="space-y-4" style={{ animation: "fadeSlideIn 0.4s ease both" }}>
            
            {/* 1. TOP HEADER: Radar & Logic Flow */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                
                {/* 1A. Radar Chart */}
                <div className="glass-card flex flex-col items-center justify-center p-4 border border-[#30363d] relative md:col-span-1 h-64">
                    <h3 className="absolute top-4 left-4 text-[9px] font-black uppercase tracking-widest text-gray-500">
                        Fund. Dimensions
                    </h3>
                    {agentMemos.length >= 2 ? (
                        <div className="w-full h-full mt-4">
                            <ResponsiveContainer width="100%" height="100%">
                                <RadarChart cx="50%" cy="50%" outerRadius="65%" data={radarData}>
                                    <PolarGrid stroke="#30363d" strokeDasharray="3 3" />
                                    <PolarAngleAxis 
                                        dataKey="subject" 
                                        tick={{ fill: "#8b949e", fontSize: 10, fontWeight: "bold" }} 
                                    />
                                    <Radar
                                        name="Score"
                                        dataKey="score"
                                        stroke="#a78bfa"
                                        fill="#a78bfa"
                                        fillOpacity={0.2}
                                        strokeWidth={2}
                                    />
                                </RadarChart>
                            </ResponsiveContainer>
                        </div>
                    ) : (
                        <div className="w-full h-full flex items-center justify-center text-[10px] text-gray-600 font-mono">
                            Awaiting Agents...
                        </div>
                    )}
                </div>

                {/* 1B. Actionable Logic Flow */}
                <div className="glass-card p-5 border border-[#30363d] flex flex-col justify-center md:col-span-2 relative h-64 overflow-hidden">
                    <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/5 blur-3xl rounded-full translate-x-1/2 -translate-y-1/2 pointer-events-none" />
                    <h3 className="absolute top-4 left-5 text-[9px] font-black uppercase tracking-widest text-gray-500">
                        Institutional Thesis Flow
                    </h3>

                    {/* Loading State */}
                    {(status === "analyzing" || status === "fetching_data") && !committee && (
                        <div className="flex flex-col items-center justify-center h-full mt-2">
                             <div className="flex justify-between w-full max-w-sm text-[9px] text-gray-500 mb-2">
                                <span className="font-bold uppercase tracking-widest">Analyst Committee</span>
                                <span className="font-mono">{agentCount} / {totalAgents}</span>
                            </div>
                            <div className="w-full max-w-sm h-1.5 bg-[#21262d] rounded-full overflow-hidden">
                                <div
                                    className="h-full bg-blue-500 rounded-full transition-all duration-500"
                                    style={{ width: `${(agentCount / totalAgents) * 100}%` }}
                                />
                            </div>
                            <p className="text-[10px] text-gray-500 mt-4 animate-pulse">Running LangGraph Agents...</p>
                        </div>
                    )}

                    {/* Completed State */}
                    {committee && (
                       <div className="mt-2 flex flex-col sm:flex-row items-center gap-6 justify-between w-full">
                           
                           {/* Step 1: Context */}
                           <div className="flex flex-col items-center text-center flex-1">
                               <div className="w-10 h-10 rounded-full bg-blue-500/10 border border-blue-500/20 flex items-center justify-center mb-2">
                                   <Briefcase className="text-blue-400" size={16} />
                               </div>
                               <span className="text-[9px] text-gray-500 font-black uppercase tracking-wide">Context</span>
                               <span className="text-xs font-mono text-gray-300 mt-1">{dataReady?.sector || "General"}</span>
                           </div>

                           <div className="w-8 h-px bg-[#30363d] hidden sm:block" />

                           {/* Step 2: Agent Consensus */}
                           <div className="flex flex-col items-center text-center flex-1">
                               <div className="w-10 h-10 rounded-full bg-purple-500/10 border border-purple-500/20 flex items-center justify-center mb-2">
                                   <Target className="text-purple-400" size={16} />
                               </div>
                               <span className="text-[9px] text-gray-500 font-black uppercase tracking-wide">Consensus</span>
                               <span className="text-xs font-mono text-gray-300 mt-1">{(committee.confidence * 100).toFixed(0)}% Conviction</span>
                           </div>

                           <div className="w-8 h-px bg-[#30363d] hidden sm:block" />

                           {/* Step 3: Action */}
                           <div className="flex flex-col items-center text-center flex-1">
                               <div className={`w-12 h-12 rounded-full flex items-center justify-center mb-2 ${signalBg(committee.signal)}`}>
                                   {committee.signal.includes("BUY") ? <TrendingUp className={signalColor(committee.signal)} size={20} /> : 
                                    committee.signal.includes("SELL") ? <TrendingDown className={signalColor(committee.signal)} size={20} /> : 
                                    <Minus className={signalColor(committee.signal)} size={20} />}
                               </div>
                               <span className="text-[9px] text-gray-500 font-black uppercase tracking-wide">Action</span>
                               <span className={`text-sm font-black uppercase mt-1 ${signalColor(committee.signal)}`}>{committee.signal}</span>
                           </div>

                           {/* Big Composite Score */}
                           <div className="flex-1 flex justify-end pl-6 sm:border-l border-[#30363d]">
                                <div className="flex flex-col items-end">
                                    <span className="text-[9px] text-gray-500 font-black uppercase tracking-widest mb-1.5 text-right w-full">Fundamental Score</span>
                                    <div className="flex items-center gap-3">
                                        <ScoreRing score={committee.score} size={70} />
                                    </div>
                                    <span className="text-[10px] text-gray-400 font-mono mt-1">Risk-Adj: {committee.risk_adjusted_score.toFixed(1)}</span>
                                </div>
                           </div>
                       </div>
                    )}
                </div>
            </div>

            {/* 2. MIDDLE GRID: Fundamental Agent Cards */}
            {agentMemos.length > 0 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    {agentMemos.map((memo, i) => (
                        <FundAgentCard key={`agent-${i}`} memo={memo} ratios={dataReady?.ratios} />
                    ))}
                </div>
            )}

            {/* 3. BOTTOM ZONE: Research Memo & Committee */}
            {(committee?.consensus_narrative || researchMemo) && (
                <div className="glass-card border border-[#30363d] overflow-hidden flex flex-col">
                    {/* Committee Header (Consensus) */}
                    {committee?.consensus_narrative && (
                        <div className="p-5 bg-gradient-to-br from-indigo-500/5 to-purple-500/5 border-b border-[#30363d]/50">
                            <div className="flex items-center gap-2 mb-3">
                                <ShieldCheck size={16} className="text-indigo-400" />
                                <h2 className="text-[10px] font-black uppercase tracking-widest text-indigo-400">
                                    Investment Committee Consensus
                                </h2>
                            </div>
                            <p className="text-sm text-gray-200 font-serif leading-relaxed italic mb-4">
                                "{committee.consensus_narrative}"
                            </p>
                            
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-4 pt-4 border-t border-[#30363d]/30">
                                {/* Catalysts */}
                                {committee.key_catalysts?.length > 0 && (
                                    <div>
                                        <h4 className="text-[9px] font-black uppercase tracking-widest text-emerald-500/70 mb-2">Key Catalysts</h4>
                                        <ul className="space-y-1.5">
                                            {committee.key_catalysts.map((cat, i) => (
                                                <li key={i} className="text-[11px] text-gray-400 flex items-start gap-2">
                                                    <span className="text-emerald-500/70 mt-0.5 text-[9px]">↗</span>
                                                    <span className="leading-tight">{cat}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                                {/* Risks */}
                                {committee.key_risks?.length > 0 && (
                                    <div>
                                        <h4 className="text-[9px] font-black uppercase tracking-widest text-rose-500/70 mb-2">Key Risks</h4>
                                        <ul className="space-y-1.5">
                                            {committee.key_risks.map((risk, i) => (
                                                <li key={i} className="text-[11px] text-gray-400 flex items-start gap-2">
                                                    <span className="text-rose-500/70 mt-0.5 text-[9px]">↘</span>
                                                    <span className="leading-tight">{risk}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {/* Deep Dive Memo Expandable */}
                    {researchMemo && (
                        <div className="px-5 py-3">
                            <button
                                onClick={() => setMemoExpanded(!memoExpanded)}
                                className="w-full flex items-center justify-between text-left group"
                            >
                                <div className="flex items-center gap-2">
                                    <Briefcase size={14} className="text-gray-500 group-hover:text-blue-400 transition-colors" />
                                    <span className="text-[10px] font-black uppercase tracking-widest text-gray-500 group-hover:text-gray-300 transition-colors">
                                        Fundamental Analyst Deep Dive Memo
                                    </span>
                                </div>
                                {memoExpanded ? <ChevronUp size={14} className="text-gray-500" /> : <ChevronDown size={14} className="text-gray-500" />}
                            </button>
                            
                            {memoExpanded && (
                                <div 
                                    className="mt-4 pt-4 border-t border-[#30363d] prose prose-invert prose-xs max-w-none pb-4"
                                    style={{ animation: "fadeSlideIn 0.3s ease" }}
                                    dangerouslySetInnerHTML={{
                                        __html: researchMemo
                                            .replace(/^# (.+)$/gm, '<h1 class="text-sm font-black text-white mb-2 mt-4">$1</h1>')
                                            .replace(/^## (.+)$/gm, '<h2 class="text-[11px] font-black uppercase tracking-widest text-blue-400/80 mt-6 mb-3 border-b border-[#30363d] pb-1">$1</h2>')
                                            .replace(/\*\*(.+?)\*\*/g, '<strong class="text-white">$1</strong>')
                                            .replace(/^\|(.+)\|$/gm, (row) => {
                                                const cells = row.split('|').filter(c => c.trim() && !c.trim().match(/^-+$/));
                                                if (!cells.length) return '';
                                                return '<div class="flex gap-4 text-[10px] border-b border-[#30363d]/40 py-1.5 hover:bg-white/5">' +
                                                    cells.map((c, i) => `<span class="${i === 0 ? 'text-gray-400 font-bold w-48 flex-shrink-0' : 'text-gray-300 font-mono'}">` + c.trim().replace(/^\*\*(.+)\*\*$/, '$1') + '</span>').join('') +
                                                    '</div>';
                                            })
                                            .replace(/^\|[-| ]+\|$/gm, '')
                                            .replace(/^- (.+)$/gm, '<li class="text-[11px] text-gray-400 ml-4 list-disc space-y-1 my-1">$1</li>')
                                            .replace(/^([^<\n][^\n]+)$/gm, '<p class="text-[11px] text-gray-400 leading-relaxed my-2">$1</p>')
                                    }}
                                />
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

