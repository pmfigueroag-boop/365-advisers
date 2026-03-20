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
    Clock,
    ArrowRight
} from "lucide-react";

import type { FundamentalDataReady, AgentMemo, CommitteeVerdict } from "@/hooks/useFundamentalStream";

// ─── Formatting Helpers ────────────────────────────────────────────────────────

function signalColor(signal: string) {
    if (signal === "BUY" || signal === "STRONG_BUY") return "text-decision-green";
    if (signal === "SELL" || signal === "STRONG_SELL" || signal === "AVOID") return "text-decision-red";
    return "text-decision-yellow";
}

function signalBg(signal: string) {
    if (signal === "BUY" || signal === "STRONG_BUY") return "bg-decision-green/10 border-decision-green/30";
    if (signal === "SELL" || signal === "STRONG_SELL" || signal === "AVOID") return "bg-decision-red/10 border-decision-red/30";
    return "bg-decision-yellow/10 border-decision-yellow/30";
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

function ConvictionScoreBar({ score, conviction }: { score: number; conviction: number }) {
    const pct = (score / 10) * 100;
    const color = score >= 7 ? "bg-[#10b981]" : score >= 4 ? "bg-[#d4af37]" : "bg-[#f43f5e]";
    
    return (
        <div className="space-y-1.5 mt-auto pt-3 border-t border-[#30363d]/50">
            <div className="flex justify-between items-end">
                <span className="text-[9px] text-[#8b949e] uppercase tracking-widest font-bold">
                    Adjusted Score
                </span>
                <div className="flex items-baseline gap-1">
                    <span className="text-sm font-black text-slate-200">{score.toFixed(1)}</span>
                    <span className="text-[9px] text-[#8b949e]">/10</span>
                </div>
            </div>
            {/* Split Progress bar: Score Top */}
            <div className="h-1.5 bg-[#161b22] rounded-full overflow-hidden flex flex-col gap-[1px]">
                <div className="h-full w-full bg-[#21262d]">
                    <div className={`h-full transition-all duration-500 ${color}`} style={{ width: `${pct}%` }} />
                </div>
            </div>
            <div className="flex justify-between items-center text-[8px] text-[#8b949e] font-mono tracking-widest uppercase mt-1">
                <span>AI Conviction</span>
                <span className="text-[#d4af37]">{(conviction * 100).toFixed(0)}%</span>
            </div>
        </div>
    );
}

// ─── Micro Card: Agent ────────────────────────────────────────────────────────

function FundAgentCard({ memo, ratios }: { memo: AgentMemo, ratios: any }) {
    const [expanded, setExpanded] = useState(false);
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
    } else if (name.includes("capital") || name.includes("allocation")) {
        title = "Capital Allocation";
        icon = <Banknote size={14} className="text-orange-400" />;
        const q = ratios?.quality || {};
        // Map top capital metrics, relying on filter to clean up undefined ones, up to 4
        relevantMetrics = [
            { label: "Div Yield", val: q.dividend_yield },
            { label: "Payout", val: q.payout_ratio },
            { label: "Buybacks", val: q.buyback_yield },
            { label: "CapEx/Rev", val: q.capex_to_revenue }
        ];
    } else {
        title = memo.agent;
    }

    // Filter out undefined and incomplete metrics, keeping max 4
    const displayMetrics = relevantMetrics.filter(m => m.val !== undefined && m.val !== null && m.val !== "DATA_INCOMPLETE").slice(0, 4);

    // Calculate normalized score for the progress bar
    const baseScore = normalizeSignalNumber(memo.signal);
    const adjustedScore = 5 + (baseScore - 5) * memo.conviction;

    return (
        <div className={`glass-card p-4 flex flex-col gap-3 border transition-all ${signalBg(memo.signal)}`}>
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    {React.cloneElement(icon as React.ReactElement<{size?: number, className?: string}>, { size: 14, className: signalColor(memo.signal) })}
                    <h3 className="text-[10px] font-black uppercase tracking-widest text-[#c9d1d9]">{title}</h3>
                </div>
                <div className={`text-[8px] font-black px-1.5 py-0.5 rounded border shadow-inner uppercase ${signalBg(memo.signal)} border-[currentColor]/30 ${signalColor(memo.signal)}`}>
                    {memo.signal.replace("_", " ")}
                </div>
            </div>

            {/* Metrics Rows */}
            <div className="space-y-2 mt-1 text-[9px]">
                {displayMetrics.length > 0 ? displayMetrics.map((m, i) => (
                    <div key={i} className="flex justify-between items-center p-1.5 rounded bg-[#161b22]/80 border border-[#30363d]/50">
                        <span className="text-[#8b949e] font-medium">{m.label}</span>
                        <span className="font-mono font-bold text-[#c9d1d9]">{formatRatio(m.label, m.val)}</span>
                    </div>
                )) : (
                    <div className="text-[9px] text-[#8b949e] italic p-1.5 bg-[#161b22]/50 rounded text-center">No hard metrics mapped.</div>
                )}
            </div>

            {/* Score Weight Bar */}
            <ConvictionScoreBar score={adjustedScore} conviction={memo.conviction} />
            
            {/* AI Narrative snippet (Expandable) */}
            <div className="mt-1 pt-3 border-t border-[#30363d]/50">
                <button 
                    className="w-full flex items-center justify-between text-left group cursor-pointer"
                    onClick={() => setExpanded(!expanded)}
                    aria-expanded={expanded}
                >
                    <span className="text-[9px] text-[#8b949e] font-bold uppercase tracking-widest group-hover:text-indigo-400 transition-colors flex items-center gap-1.5">
                        <Activity size={10} /> Analyst Depth
                    </span>
                    <div className="flex items-center justify-center group-hover:bg-[#161b22] rounded p-0.5 transition-colors">
                        {expanded ? <ChevronUp size={12} className="text-indigo-400" /> : <ChevronDown size={12} className="text-[#8b949e] group-hover:text-indigo-400" />}
                    </div>
                </button>
                
                {expanded && (
                    <div className="mt-3 space-y-3 pt-3 border-t border-[#30363d]/30" style={{ animation: "fadeSlideIn 0.2s ease" }}>
                        <div className="bg-[#161b22] p-3 rounded-lg border border-[#30363d]/50">
                            <p className="text-[10px] text-[#c9d1d9] leading-relaxed font-serif italic border-l-2 border-indigo-500/40 pl-2">
                                "{memo.memo}"
                            </p>
                        </div>
                        
                        {memo.metric_insights && memo.metric_insights.length > 0 && (
                            <div>
                                <p className="text-[8px] text-indigo-400 font-bold uppercase tracking-widest mb-2 flex items-center gap-1.5">
                                    <Zap size={10} /> Explicación de Métricas
                                </p>
                                <div className="flex flex-col gap-2">
                                    {memo.metric_insights.map((mi, idx) => (
                                        <div key={idx} className="bg-[#0d1117] p-3 rounded border border-[#30363d]">
                                            <p className="text-[10px] font-black text-[#c9d1d9] mb-1 font-mono">{mi.metric}</p>
                                            <p className="text-[9px] text-[#8b949e] italic mb-2 border-l border-[#30363d] pl-2">{mi.definition}</p>
                                            <p className="text-[10px] text-[#8b949e] leading-relaxed">{mi.interpretation}</p>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                        
                        {(memo.catalysts?.length > 0 || memo.risks?.length > 0) && (
                            <div className="grid grid-cols-1 gap-2">
                                {memo.catalysts?.length > 0 && (
                                    <div className="bg-[#10b981]/10 p-2.5 rounded border border-[#10b981]/20">
                                        <p className="text-[8px] text-[#10b981] font-bold uppercase tracking-widest mb-1.5 flex items-center gap-1"><TrendingUp size={10}/> Catalysts</p>
                                        <ul className="space-y-1 ml-1">
                                            {memo.catalysts.map(c => <li key={c} className="text-[9px] text-[#8b949e] flex items-start gap-1.5"><span className="text-[#10b981] mt-0.5">▸</span><span>{c}</span></li>)}
                                        </ul>
                                    </div>
                                )}
                                {memo.risks?.length > 0 && (
                                    <div className="bg-[#f43f5e]/10 p-2.5 rounded border border-[#f43f5e]/20">
                                        <p className="text-[8px] text-[#f43f5e] font-bold uppercase tracking-widest mb-1.5 flex items-center gap-1"><AlertTriangle size={10}/> Risks</p>
                                        <ul className="space-y-1 ml-1">
                                            {memo.risks.map(r => <li key={r} className="text-[9px] text-[#8b949e] flex items-start gap-1.5"><span className="text-[#f43f5e] mt-0.5">▸</span><span>{r}</span></li>)}
                                        </ul>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}
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
        // Group scores by category to average them if multiple agents map to the same axis
        const categories: Record<string, number[]> = {
            Value: [], Quality: [], Growth: [], Solvency: []
        };

        agentMemos.forEach(memo => {
            const base = normalizeSignalNumber(memo.signal); 
            const adjustedScore = 5 + (base - 5) * memo.conviction;

            const name = memo.agent.toLowerCase();
            if (name.includes("value") || name.includes("margin")) categories.Value.push(adjustedScore);
            else if (name.includes("quality") || name.includes("moat")) categories.Quality.push(adjustedScore);
            else if (name.includes("growth") || name.includes("catalyst") || name.includes("momentum")) categories.Growth.push(adjustedScore);
            else if (name.includes("risk") || name.includes("solvency") || name.includes("allocation")) categories.Solvency.push(adjustedScore);
        });

        // Helper to get average or default 5
        const getAvg = (arr: number[]) => arr.length > 0 ? arr.reduce((a,b) => a+b, 0) / arr.length : 5;

        return [
            { subject: "Value", score: parseFloat(getAvg(categories.Value).toFixed(1)), fullMark: 10 },
            { subject: "Quality", score: parseFloat(getAvg(categories.Quality).toFixed(1)), fullMark: 10 },
            { subject: "Growth", score: parseFloat(getAvg(categories.Growth).toFixed(1)), fullMark: 10 },
            { subject: "Solvency", score: parseFloat(getAvg(categories.Solvency).toFixed(1)), fullMark: 10 },
        ];
    }, [agentMemos]);

    if (!dataReady && status !== "fetching_data" && status !== "analyzing") {
        return null;
    }

    return (
        <div className="space-y-4" style={{ animation: "fadeSlideIn 0.4s ease both" }}>
            
            {/* 1. TOP GRID: Executive Summary (Thesis Flow + Radar) */}
            <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
                
                {/* 1A. Institutuional Radar Chart (Left Module) */}
                <div className="md:col-span-3 glass-card border-[#30363d] p-4 flex flex-col h-full bg-[#0d1117] relative overflow-hidden">
                    <div className="absolute inset-0 bg-[url('/img/dot_grid.png')] opacity-10 pointer-events-none" />
                    <p className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-2">
                        Institutional Radar
                    </p>
                    {agentMemos.length >= 2 ? (
                        <div className="flex-1 w-full min-h-[160px] -ml-2">
                            <ResponsiveContainer width="100%" height="100%">
                                <RadarChart cx="50%" cy="50%" outerRadius="70%" data={radarData}>
                                    <PolarGrid stroke="#30363d" />
                                    <PolarAngleAxis dataKey="subject" tick={{ fill: '#8b949e', fontSize: 9, fontWeight: 700 }} />
                                    <Radar
                                        name="Score"
                                        dataKey="score"
                                        stroke={committee?.signal.includes("BUY") ? "#10b981" : committee?.signal.includes("SELL") ? "#f43f5e" : "#d4af37"}
                                        fill={committee?.signal.includes("BUY") ? "#10b981" : committee?.signal.includes("SELL") ? "#f43f5e" : "#d4af37"}
                                        fillOpacity={0.2}
                                    />
                                </RadarChart>
                            </ResponsiveContainer>
                        </div>
                    ) : (
                        <div className="flex-1 w-full flex items-center justify-center text-[10px] text-[#8b949e] font-black uppercase tracking-widest">
                            Awaiting Agents...
                        </div>
                    )}
                </div>

                {/* 1B. Actionable Logic Flow (Middle Module) */}
                <div className="md:col-span-6 glass-card border-[#30363d] p-5 flex flex-col justify-center bg-[#0d1117]/80">
                    <p className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-4">
                        Actionable Logic Flow
                    </p>
                    
                    {/* Loading State */}
                    {(status === "analyzing" || status === "fetching_data") && !committee && (
                        <div className="flex flex-col items-center justify-center w-full h-full my-auto">
                            <div className="flex justify-between w-full max-w-sm text-[9px] text-[#8b949e] mb-2 font-black uppercase tracking-widest">
                                <span>Analyst Committee</span>
                                <span>{agentCount} / {totalAgents}</span>
                            </div>
                            <div className="w-full max-w-sm h-1 bg-[#21262d] rounded-full overflow-hidden">
                                <div
                                    className="h-full bg-indigo-500 rounded-full transition-all duration-500"
                                    style={{ width: `${totalAgents > 0 ? (agentCount / totalAgents) * 100 : 0}%` }}
                                />
                            </div>
                            <p className="text-[9px] text-slate-600 mt-3 animate-pulse font-bold tracking-widest uppercase">Running LangGraph Agents...</p>
                        </div>
                    )}

                    {committee && (
                        <div className="flex flex-col sm:flex-row items-center gap-2 w-full mt-auto mb-auto">
                            {/* Block 1: Sector Context */}
                            <div className="flex-1 flex flex-col items-center justify-center p-3 rounded-lg border border-[#30363d] bg-[#161b22] text-center w-full min-h-[70px]">
                                <span className="text-[8px] uppercase tracking-widest text-[#8b949e] mb-1">Sector Context</span>
                                <span className="text-[10px] font-black uppercase text-blue-400">
                                    {dataReady?.sector || "GENERAL"}
                                </span>
                            </div>
                            
                            <ArrowRight size={14} className="text-[#8b949e] rotate-90 sm:rotate-0 flex-shrink-0" />
                            
                            {/* Block 2: Consensus */}
                            <div className="flex-1 flex flex-col items-center justify-center p-3 rounded-lg border border-[#30363d] bg-[#161b22] text-center w-full min-h-[70px]">
                                <span className="text-[8px] uppercase tracking-widest text-[#8b949e] mb-1">AI Conviction</span>
                                <span className="text-[10px] font-black uppercase text-indigo-400">
                                    {(committee.confidence * 100).toFixed(0)}%
                                </span>
                            </div>
                            
                            <ArrowRight size={14} className="text-[#8b949e] rotate-90 sm:rotate-0 flex-shrink-0" />

                            {/* Block 3: Final Action */}
                            <div className={`flex-1 flex flex-col items-center justify-center p-3 rounded-lg border text-center w-full min-h-[70px] transition-colors ${signalBg(committee.signal)}`}>
                                <ShieldCheck size={14} className={`mb-1 ${signalColor(committee.signal)}`} />
                                <span className={`text-[11px] font-black uppercase tracking-wider ${signalColor(committee.signal)}`}>
                                    {committee.signal.replace("_", " ")}
                                </span>
                            </div>
                        </div>
                    )}
                </div>

                {/* 1C. Fundamental Master Score (Right Module) */}
                <div className={`md:col-span-3 glass-card border flex flex-col justify-center items-center p-6 text-center shadow-lg ${committee ? signalBg(committee.signal) : "bg-[#0d1117] border-[#30363d]"}`}>
                    <p className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2">
                        Fundamental Score
                    </p>
                    <div className="flex items-start gap-1">
                        <span className={`text-6xl font-black tabular-nums tracking-tighter ${committee ? signalColor(committee.signal) : "text-slate-600"} drop-shadow-md`}>
                            {committee ? committee.score.toFixed(1) : "0.0"}
                        </span>
                        <span className="text-sm font-bold text-[#8b949e] mt-2">/10</span>
                    </div>
                    
                    <div className="mt-4 flex items-center justify-center gap-1.5 flex-wrap">
                        {committee ? (
                            <>
                                <span className="text-[8px] font-black text-[#8b949e] px-2 py-1 rounded border border-[#30363d] bg-[#161b22] uppercase tracking-wider">
                                    RISK-ADJ: {committee.risk_adjusted_score.toFixed(1)}
                                </span>
                                <span className="text-[8px] font-black text-[#8b949e] px-2 py-1 rounded border border-[#30363d] bg-[#161b22] uppercase tracking-wider">
                                    ALLOC: {committee.allocation_recommendation}
                                </span>
                            </>
                        ) : (
                            <span className="text-[8px] font-black text-slate-600 px-2 py-1 rounded border border-[#30363d] bg-[#161b22] uppercase tracking-wider">
                                PENDING...
                            </span>
                        )}
                    </div>
                </div>
            </div>

            {/* 2. MIDDLE GRID: Fundamental Agent Cards */}
            {agentMemos.length > 0 && (
                <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
                    {agentMemos.map((memo, i) => (
                        <FundAgentCard key={`agent-${i}`} memo={memo} ratios={dataReady?.ratios} />
                    ))}
                </div>
            )}

            {/* 3. BOTTOM ZONE: Research Memo Expandable */}
            {researchMemo && (
                <div className="glass-card p-5 border-[#30363d] mt-4" style={{ animation: "fadeSlideIn 0.5s ease both" }}>
                    <button
                        onClick={() => setMemoExpanded(!memoExpanded)}
                        className="w-full flex items-center justify-between text-left group min-h-[44px] rounded-xl transition-colors"
                        aria-expanded={memoExpanded}
                    >
                        <div className="flex items-center gap-2">
                            <Activity size={16} className="text-purple-400" />
                            <p className="text-[10px] font-black uppercase tracking-widest text-slate-400 group-hover:text-slate-200 transition-colors">
                                Fundamental Analyst
                                <span className="text-slate-600 font-normal ml-1">(Deep Dive Memo)</span>
                            </p>
                        </div>
                        <div className="flex items-center justify-center p-1 rounded group-hover:bg-[#161b22] transition-colors">
                            {memoExpanded ? <ChevronUp size={14} className="text-indigo-400" /> : <ChevronDown size={14} className="text-slate-500 group-hover:text-indigo-400" />}
                        </div>
                    </button>
                    
                    {memoExpanded && (
                        <div 
                            className="mt-4 pt-4 border-t border-[#30363d]/50 prose prose-invert prose-sm max-w-none"
                            style={{ animation: "fadeSlideIn 0.3s ease" }}
                            dangerouslySetInnerHTML={{
                                __html: researchMemo
                                    .replace(/^# (.+)$/gm, '<h1 class="text-xl sm:text-2xl font-black text-slate-100 mb-6 mt-6 tracking-tight">$1</h1>')
                                    .replace(/^## (.+)$/gm, '<h2 class="text-sm sm:text-base font-black uppercase tracking-widest text-indigo-400/90 mt-8 mb-4 border-b border-[#30363d] pb-2">$1</h2>')
                                    .replace(/\*\*(.+?)\*\*/g, '<strong class="text-[#c9d1d9] font-bold">$1</strong>')
                                    .replace(/^\|(.+)\|$/gm, (row) => {
                                        const cells = row.split('|').filter(c => c.trim() && !c.trim().match(/^-+$/));
                                        if (!cells.length) return '';
                                        return '<div class="flex flex-col md:flex-row md:items-center gap-2 md:gap-8 text-xs md:text-sm border-b border-[#30363d]/50 py-3 hover:bg-[#161b22] transition-colors px-3 rounded-md">' +
                                            cells.map((c, i) => `<span class="${i === 0 ? 'text-[#8b949e] font-bold md:w-64 flex-shrink-0' : 'text-[#c9d1d9] font-mono'}">` + c.trim().replace(/^\*\*(.+)\*\*$/, '$1') + '</span>').join('') +
                                            '</div>';
                                    })
                                    .replace(/^\|[-| ]+\|$/gm, '')
                                    .replace(/^- (.+)$/gm, '<li class="text-xs sm:text-sm text-[#8b949e] ml-6 list-disc space-y-2 my-2"><span class="text-[#c9d1d9]">$1</span></li>')
                                    .replace(/^([^<\n][^\n]+)$/gm, '<p class="text-xs sm:text-sm text-[#8b949e] leading-relaxed my-3">$1</p>')
                            }}
                        />
                    )}
                </div>
            )}
        </div>
    );
}
