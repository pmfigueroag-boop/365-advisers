"use client";

import React, { useState, useEffect } from "react";
import {
    Activity,
    TrendingUp,
    TrendingDown,
    Shield,
    Zap,
    BarChart3,
    Radio,
    Loader2,
    AlertTriangle,
    Rocket,
    Globe,
    Minus,
    Briefcase,
    Target,
} from "lucide-react";
import type {
    SignalProfileResponse,
    CategoryScore,
    EvaluatedSignal,
} from "@/hooks/useAlphaSignals";
import AlphaRadarChart from "../AlphaRadarChart";
import FreshnessBadge from "../FreshnessBadge";
import ResearchMemoInsight from "./ResearchMemoInsight";
import type { MemoInsight } from "./ResearchMemoInsight";

// ── Category Config ────────────────────────────────────────────────────────

const CATEGORY_CONFIG: Record<string, { label: string; color: string; bg: string; border: string; icon: React.ReactNode }> = {
    value: { label: "Value", color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/30", icon: <Shield size={14} className="text-emerald-400" /> },
    quality: { label: "Quality", color: "text-blue-400", bg: "bg-blue-500/10", border: "border-blue-500/30", icon: <Zap size={14} className="text-blue-400" /> },
    momentum: { label: "Momentum", color: "text-orange-400", bg: "bg-orange-500/10", border: "border-orange-500/30", icon: <TrendingUp size={14} className="text-orange-400" /> },
    volatility: { label: "Volatility", color: "text-yellow-400", bg: "bg-yellow-500/10", border: "border-yellow-500/30", icon: <Activity size={14} className="text-yellow-400" /> },
    flow: { label: "Flow", color: "text-cyan-400", bg: "bg-cyan-500/10", border: "border-cyan-500/30", icon: <BarChart3 size={14} className="text-cyan-400" /> },
    event: { label: "Event", color: "text-purple-400", bg: "bg-purple-500/10", border: "border-purple-500/30", icon: <Radio size={14} className="text-purple-400" /> },
    growth: { label: "Growth", color: "text-rose-400", bg: "bg-rose-500/10", border: "border-rose-500/30", icon: <Rocket size={14} className="text-rose-400" /> },
    macro: { label: "Macro", color: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/30", icon: <Globe size={14} className="text-amber-400" /> },
};

const STRENGTH_STYLE: Record<string, string> = {
    strong: "text-emerald-400 bg-emerald-500/15 border border-emerald-500/30",
    moderate: "text-yellow-400 bg-yellow-500/15 border border-yellow-500/30",
    weak: "text-gray-500 bg-gray-500/15 border border-gray-500/30",
};

// ── Formatting Helpers ─────────────────────────────────────────────────────

function signalColor(signal: string) {
    if (signal === "BULLISH" || signal === "BUY") return "text-emerald-400";
    if (signal === "BEARISH" || signal === "SELL") return "text-rose-400";
    return "text-amber-400";
}

function signalBg(signal: string) {
    if (signal === "BULLISH" || signal === "BUY") return "bg-emerald-500/10 border-emerald-500/30";
    if (signal === "BEARISH" || signal === "SELL") return "bg-rose-500/10 border-rose-500/30";
    return "bg-amber-500/10 border-amber-500/30";
}

function buildAlphaMemo(profile: SignalProfileResponse): MemoInsight {
    const { composite, fired_signals, total_signals, category_summary, signals } = profile;
    const strength = composite.overall_strength;
    const firedPct = total_signals > 0 ? (fired_signals / total_signals) * 100 : 0;

    const signal: MemoInsight["signal"] = strength >= 0.65 ? "BULLISH" : strength <= 0.3 ? "BEARISH" : "NEUTRAL";
    const conviction: MemoInsight["conviction"] = strength >= 0.75 ? "HIGH" : strength >= 0.45 ? "MEDIUM" : "LOW";

    const activeCats = Object.entries(category_summary)
        .filter(([, v]) => (v.fired ?? 0) > 0)
        .sort((a, b) => (b[1].fired ?? 0) - (a[1].fired ?? 0));

    const dominant = composite.dominant_category
        ? (CATEGORY_CONFIG[composite.dominant_category]?.label || composite.dominant_category)
        : activeCats[0]?.[0] || "N/A";

    const topSignals = signals
        .filter((s) => s.fired)
        .sort((a, b) => {
            const order: Record<string, number> = { strong: 3, moderate: 2, weak: 1 };
            return (order[b.strength] ?? 0) - (order[a.strength] ?? 0);
        })
        .slice(0, 3);

    const narrative = `${fired_signals} de ${total_signals} señales Alpha activas (${firedPct.toFixed(0)}%). ` +
        `Fuerza Compuesta: ${(strength * 100).toFixed(0)}%. Categoría dominante: ${dominant}` +
        (composite.multi_category_bonus ? ` con bonus multi-estilo aplicado.` : `.`);

    const bullets: string[] = [];
    if (topSignals.length > 0) {
        bullets.push(`Señales más fuertes: ${topSignals.map((s) => s.signal_name).join(", ")}`);
    }
    if (activeCats.length > 0) {
        bullets.push(`Categorías activas: ${activeCats.map(([k, v]) => `${CATEGORY_CONFIG[k]?.label || k} (${v.fired}/${v.total})`).join(", ")}`);
    }
    if (composite.multi_category_bonus) {
        bullets.push("Bonus multi-categoría aplicado — señales diversificadas refuerzan la convicción");
    }

    const risks: string[] = [];
    if (firedPct < 30) risks.push(`Solo ${firedPct.toFixed(0)}% de señales activas — baja cobertura factorial`);
    if (activeCats.length <= 1) risks.push("Señales concentradas en una sola categoría — falta diversificación");
    const decayInfo = profile.composite_alpha?.decay;
    if (decayInfo && (decayInfo.freshness_level === "stale" || decayInfo.freshness_level === "expired")) {
        risks.push(`Señales con frescura "${decayInfo.freshness_level}" (${(decayInfo.average_freshness * 100).toFixed(0)}%) — considerar re-evaluación`);
    }

    return { title: "Research Memo — Alpha Signals", signal, conviction, narrative, bullets, risks };
}

// ── ScoreRing Component ────────────────────────────────────────────────────

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
    const filled = (displayed / 100) * circumference;
    const color = score >= 65 ? "#34d399" : score >= 35 ? "#fbbf24" : "#fb7185";

    return (
        <svg width={size} height={size} className="rotate-[-90deg]">
            <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#21262d" strokeWidth={4} />
            <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={color} strokeWidth={4} strokeDasharray={`${filled} ${circumference}`} strokeLinecap="round" />
            <text x={size / 2} y={size / 2 + 1} textAnchor="middle" dominantBaseline="middle" fill="white" fontSize={size * 0.25} fontWeight="900" style={{ transform: `rotate(90deg) translateX(0)`, transformOrigin: `${size / 2}px ${size / 2}px` }}>
                {displayed.toFixed(0)}
            </text>
        </svg>
    );
}

// ── Micro Card: Alpha Module ───────────────────────────────────────────────

function AlphaCategoryCard({ catKey, cfg, score, signals }: { catKey: string; cfg: any; score?: CategoryScore; signals: EvaluatedSignal[] }) {
    const hasFired = score && score.fired > 0;
    
    // Si no hay señales encendidas, renderizamos una tarjeta "dimmed"
    if (!hasFired) {
        return (
            <div className={`glass-card p-4 flex flex-col gap-3 border transition-colors border-[#30363d]/50 bg-[#161b22]/30 opacity-60`}>
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        {React.cloneElement(cfg.icon, { className: "text-gray-500" })}
                        <h3 className="text-xs font-black uppercase tracking-widest text-gray-500">{cfg.label}</h3>
                    </div>
                </div>
                <div className="flex items-center justify-center h-16 text-[10px] text-gray-500/70 font-mono italic">
                    Inactive (0 / {score?.total || 0})
                </div>
            </div>
        );
    }

    const isDominant = score.composite_strength > 0.6;
    const barColor = score.composite_strength > 0.6 ? "bg-emerald-500" : score.composite_strength > 0.3 ? "bg-yellow-500" : "bg-gray-500";

    return (
        <div className={`glass-card p-4 flex flex-col gap-3 border transition-colors ${cfg.border} hover:border-white/20 bg-[#161b22]/80`}>
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    {cfg.icon}
                    <h3 className="text-xs font-black uppercase tracking-widest text-gray-200">{cfg.label}</h3>
                </div>
                <div className="text-[9px] font-mono font-bold px-2 py-0.5 rounded border border-[#30363d] bg-[#0d1117] text-gray-400">
                    {score.fired} / {score.total} FIR
                </div>
            </div>

            {/* Fired Signals List */}
            <div className="flex-1 flex flex-col gap-1.5 mt-1 min-h-[64px]">
                {signals.slice(0, 3).map((sig, idx) => (
                    <div key={idx} className="flex flex-col gap-0.5 bg-[#0d1117]/50 rounded p-1.5 border border-white/5">
                        <div className="flex justify-between items-start w-full gap-2">
                            <span className="text-[9px] text-gray-300 leading-tight line-clamp-1">{sig.description}</span>
                            <span className={`text-[7px] font-black uppercase px-1 rounded flex-shrink-0 ${STRENGTH_STYLE[sig.strength] || ""}`}>
                                {sig.strength}
                            </span>
                        </div>
                    </div>
                ))}
                {signals.length > 3 && (
                    <span className="text-[8px] text-gray-500 text-center uppercase tracking-widest mt-0.5">
                        + {signals.length - 3} more
                    </span>
                )}
            </div>

            {/* Category Strength Bar */}
            <div className="mt-auto pt-2 border-t border-white/5">
                <div className="flex justify-between items-end mb-1">
                    <span className="text-[9px] text-gray-500 uppercase font-bold tracking-widest">Strength</span>
                    <span className="text-[10px] font-mono font-bold text-gray-300">{(score.composite_strength * 100).toFixed(0)}%</span>
                </div>
                <div className="relative h-1.5 bg-[#21262d] rounded-full overflow-hidden">
                    <div className={`absolute top-0 left-0 h-full rounded-full transition-all duration-1000 ${barColor}`} style={{ width: `${score.composite_strength * 100}%` }} />
                </div>
            </div>
        </div>
    );
}

// ── Main Interface ─────────────────────────────────────────────────────────

export interface UnifiedAlphaDashboardProps {
    profile: SignalProfileResponse | null;
    status: "idle" | "loading" | "done" | "error";
    error: string | null;
    onEvaluate?: () => void;
}

export default function UnifiedAlphaDashboard({
    profile,
    status,
    error,
    onEvaluate,
}: UnifiedAlphaDashboardProps) {

    if (status === "loading") {
        return (
            <div className="flex flex-col items-center justify-center py-8 gap-2 text-gray-500">
                <Loader2 size={20} className="animate-spin text-[#d4af37]" />
                <p className="text-[10px] font-bold uppercase tracking-widest">Evaluating Alpha Logic...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="mx-3 mt-2 p-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-[10px] flex items-center gap-1.5">
                <AlertTriangle size={12} />
                {error}
            </div>
        );
    }

    if (!profile) {
        return (
            <div className="flex flex-col items-center justify-center h-full px-4 py-8 text-center gap-2">
                <Radio size={24} className="text-[#30363d]" />
                <p className="text-[10px] text-gray-600 leading-relaxed font-mono">
                    Analyze a ticker to view its quantitative alpha signals
                </p>
                {onEvaluate && (
                    <button onClick={onEvaluate} className="text-[9px] font-bold text-[#d4af37] border border-[#d4af37]/30 bg-[#d4af37]/10 px-3 py-1.5 rounded-lg hover:border-[#d4af37] transition-all uppercase tracking-widest mt-2">
                        Evaluate Signals
                    </button>
                )}
            </div>
        );
    }

    const { composite, composite_alpha } = profile;
    const allCategories = ["value", "quality", "growth", "momentum", "volatility", "flow", "event", "macro"];

    // Evaluate high-level action base on overall strength
    let actionTxt = "NEUTRAL";
    if (composite.overall_strength >= 0.65) actionTxt = "BULLISH";
    else if (composite.overall_strength <= 0.3) actionTxt = "BEARISH";

    const alphaMemo: MemoInsight = profile.alpha_memo
        ? {
              title: "Research Memo — Alpha Signals",
              signal: (profile.alpha_memo.signal as MemoInsight["signal"]) || "NEUTRAL",
              conviction: (profile.alpha_memo.conviction as MemoInsight["conviction"]) || "LOW",
              narrative: profile.alpha_memo.narrative,
              bullets: profile.alpha_memo.key_data || [],
              risks: profile.alpha_memo.risk_factors || [],
          }
        : buildAlphaMemo(profile);

    return (
        <div className="space-y-4" style={{ animation: "fadeSlideIn 0.4s ease both" }}>
            
            {/* 1. TOP HEADER: Radar & Logic Flow */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                
                {/* 1A. Alpha Radar Chart */}
                <div className="glass-card flex flex-col relative md:col-span-1 border border-[#30363d] overflow-hidden min-h-[256px]">
                    <AlphaRadarChart data={composite_alpha} />
                </div>

                {/* 1B. Actionable Logic Flow */}
                <div className="glass-card p-5 border border-[#30363d] flex flex-col justify-center md:col-span-2 relative min-h-[256px] overflow-hidden">
                    <div className="absolute top-0 right-0 w-64 h-64 bg-[#d4af37]/5 blur-3xl rounded-full translate-x-1/2 -translate-y-1/2 pointer-events-none" />
                    
                    <div className="flex items-center justify-between absolute top-4 left-5 right-5">
                       <h3 className="text-[9px] font-black uppercase tracking-widest text-gray-500">
                           Institutional Alpha Logic Walkthrough
                       </h3>
                       {composite_alpha?.decay && (
                           <div className="scale-75 origin-top-right">
                               <FreshnessBadge decay={composite_alpha.decay} />
                           </div>
                       )}
                    </div>

                    <div className="mt-6 flex flex-col sm:flex-row items-center gap-6 justify-between w-full">
                        
                        {/* Step 1: Feature Coverage */}
                        <div className="flex flex-col items-center text-center flex-1">
                            <div className="w-10 h-10 rounded-full bg-blue-500/10 border border-blue-500/20 flex items-center justify-center mb-2">
                                <Activity className="text-blue-400" size={16} />
                            </div>
                            <span className="text-[9px] text-gray-500 font-black uppercase tracking-wide">Coverage</span>
                            <span className="text-xs font-mono text-gray-300 mt-1">{profile.fired_signals}/{profile.total_signals} Fired</span>
                        </div>

                        <div className="w-8 h-px bg-[#30363d] hidden sm:block" />

                        {/* Step 2: Factor Bias */}
                        <div className="flex flex-col items-center text-center flex-1">
                            <div className="w-10 h-10 rounded-full bg-purple-500/10 border border-purple-500/20 flex items-center justify-center mb-2">
                                {composite.dominant_category ? CATEGORY_CONFIG[composite.dominant_category.toLowerCase()]?.icon || <Target className="text-purple-400" size={16} /> : <Target className="text-purple-400" size={16} />}
                            </div>
                            <span className="text-[9px] text-gray-500 font-black uppercase tracking-wide">Dominant</span>
                            <span className={`text-xs font-black uppercase tracking-widest mt-1 ${composite.dominant_category ? CATEGORY_CONFIG[composite.dominant_category.toLowerCase()]?.color : "text-gray-300"}`}>
                                {composite.dominant_category ? CATEGORY_CONFIG[composite.dominant_category.toLowerCase()]?.label : "N/A"}
                            </span>
                        </div>

                        <div className="w-8 h-px bg-[#30363d] hidden sm:block" />

                        {/* Step 3: Synthesis */}
                        <div className="flex flex-col items-center text-center flex-1">
                            <div className={`w-12 h-12 rounded-full flex items-center justify-center mb-2 ${signalBg(actionTxt)}`}>
                                {actionTxt === "BULLISH" ? <TrendingUp className={signalColor(actionTxt)} size={20} /> : 
                                actionTxt === "BEARISH" ? <TrendingDown className={signalColor(actionTxt)} size={20} /> : 
                                <Minus className={signalColor(actionTxt)} size={20} />}
                            </div>
                            <span className="text-[9px] text-gray-500 font-black uppercase tracking-wide">Action</span>
                            <span className={`text-sm font-black uppercase tracking-widest mt-1 ${signalColor(actionTxt)}`}>{actionTxt}</span>
                        </div>

                        {/* Final Composite Score */}
                        <div className="flex-1 flex justify-end pl-6 sm:border-l border-[#30363d]">
                            <div className="flex flex-col items-end">
                                <span className="text-[9px] text-gray-500 font-black uppercase tracking-widest mb-1.5 text-right w-full text-[#d4af37]">CASE composite</span>
                                <div className="flex items-center gap-3">
                                    <ScoreRing score={composite_alpha?.score ?? (composite.overall_strength * 100)} size={70} />
                                </div>
                                <span className="text-[10px] text-gray-400 font-mono mt-1 w-full text-right">Extracted</span>
                            </div>
                        </div>

                    </div>
                </div>
            </div>

            {/* 2. MIDDLE GRID: Alpha Strategy Modules */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {allCategories.map((catKey) => {
                    const cfg = CATEGORY_CONFIG[catKey];
                    const catScore = profile.category_summary[catKey];
                    const firedSignals = catScore
                        ? profile.signals.filter((s) => s.category.toLowerCase() === catKey && s.fired)
                        : [];

                    return (
                        <AlphaCategoryCard key={catKey} catKey={catKey} cfg={cfg} score={catScore} signals={firedSignals} />
                    );
                })}
            </div>

            {/* 3. BOTTOM ZONE: Research Memo */}
            <ResearchMemoInsight memo={alphaMemo} />

        </div>
    );
}
