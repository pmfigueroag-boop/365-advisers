"use client";

import { useMemo } from "react";
import { TrendingUp, Activity, Zap, BarChart3, Layers, Target, Clock, AlertTriangle, ArrowRight, ShieldCheck } from "lucide-react";
import { TechnicalAnalysisResult } from "@/hooks/useTechnicalAnalysis";
import GlossaryTooltip from "../GlossaryTooltip";
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from "recharts";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function statusColor(status: string): string {
    const s = status?.toUpperCase() || "";
    if (s.includes("STRONG_BULL") || s === "STRONG" || s === "CONFIRMED") return "text-emerald-400";
    if (s.includes("BULL") || s === "RISING" || s === "ABOVE") return "text-emerald-400";
    if (s.includes("STRONG_BEAR") || s === "DIVERGENT") return "text-rose-400";
    if (s.includes("BEAR") || s === "FALLING" || s === "BELOW") return "text-rose-400";
    if (s === "OVERSOLD") return "text-sky-400";
    if (s === "OVERBOUGHT") return "text-orange-400";
    return "text-slate-400";
}

function statusBg(status: string): string {
    const s = status?.toUpperCase() || "";
    if (s.includes("STRONG_BULL") || s === "CONFIRMED") return "bg-emerald-500/15 border-emerald-500/30";
    if (s.includes("BULL") || s === "RISING") return "bg-emerald-500/10 border-emerald-500/20";
    if (s.includes("STRONG_BEAR") || s === "DIVERGENT") return "bg-rose-500/15 border-rose-500/30";
    if (s.includes("BEAR") || s === "FALLING") return "bg-rose-500/10 border-rose-500/20";
    if (s === "OVERSOLD") return "bg-sky-500/10 border-sky-500/20";
    if (s === "OVERBOUGHT") return "bg-orange-500/10 border-orange-500/20";
    return "bg-slate-500/10 border-slate-500/20";
}

function signalColor(signal: string): string {
    if (signal === "STRONG_BUY") return "text-emerald-400";
    if (signal === "BUY") return "text-emerald-500";
    if (signal === "STRONG_SELL") return "text-rose-500";
    if (signal === "SELL") return "text-rose-400";
    return "text-slate-400";
}

// ─── Weights Map ─────────────────────────────────────────────────────────────

const REGIME_WEIGHT_PROFILES: Record<string, Record<string, number>> = {
    TRENDING: { trend: 0.35, momentum: 0.25, volatility: 0.15, volume: 0.15, structure: 0.10 },
    RANGING: { trend: 0.15, momentum: 0.30, volatility: 0.15, volume: 0.15, structure: 0.25 },
    VOLATILE: { trend: 0.20, momentum: 0.20, volatility: 0.30, volume: 0.20, structure: 0.10 },
    TRANSITIONING: { trend: 0.30, momentum: 0.25, volatility: 0.20, volume: 0.15, structure: 0.10 },
};

function getWeight(regime: string, module: string): number {
    const profile = REGIME_WEIGHT_PROFILES[regime?.toUpperCase()] || REGIME_WEIGHT_PROFILES["TRANSITIONING"];
    return (profile[module.toLowerCase()] || 0.2) * 100;
}

// ─── Shared UI Components ─────────────────────────────────────────────────────

function ScoreWeightBar({ score, weight, label }: { score: number; weight: number; label: string }) {
    const pct = (score / 10) * 100;
    const color = score >= 7 ? "bg-emerald-500" : score >= 4 ? "bg-[#d4af37]" : "bg-rose-500";
    
    return (
        <div className="space-y-1.5 mt-auto pt-3 border-t border-[#30363d]/50">
            <div className="flex justify-between items-end">
                <span className="text-[9px] text-slate-500 uppercase tracking-widest font-bold">
                    Score
                </span>
                <div className="flex items-baseline gap-1">
                    <span className="text-sm font-black text-slate-200">{score.toFixed(1)}</span>
                    <span className="text-[9px] text-slate-500">/10</span>
                </div>
            </div>
            {/* Split Progress bar: Score Top, Weight Bottom */}
            <div className="h-1.5 bg-[#161b22] rounded-full overflow-hidden flex flex-col gap-[1px]">
                <div className="h-full w-full bg-[#21262d]">
                    <div className={`h-full transition-all duration-500 ${color}`} style={{ width: `${pct}%` }} />
                </div>
            </div>
            <div className="flex justify-between items-center text-[8px] text-slate-500 font-mono tracking-widest uppercase mt-1">
                <span>Weight</span>
                <span className="text-[#d4af37]">{weight.toFixed(0)}%</span>
            </div>
        </div>
    );
}

// ─── Module Cards (Tactical Grid) ──────────────────────────────────────────────

function TactTrendCard({ data, weight }: { data: TechnicalAnalysisResult; weight: number }) {
    const t = data.indicators.trend;
    const score = data.summary.subscores.trend;
    const status = data.summary.trend_status;
    return (
        <div className={`glass-card p-4 border flex flex-col gap-3 ${statusBg(status)}`}>
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <TrendingUp size={14} className={statusColor(status)} />
                    <span className="text-[10px] font-black uppercase tracking-widest text-slate-300">Trend</span>
                </div>
                <span className={`text-[8px] font-black px-1.5 py-0.5 rounded border uppercase ${statusBg(status)} ${statusColor(status)}`}>
                    {status.replace("_", " ")}
                </span>
            </div>

            {/* Raw Data Data Array */}
            <div className="space-y-2 mt-1 text-[9px]">
                <div className="flex justify-between items-center p-1.5 rounded bg-[#161b22]/50 border border-[#30363d]/50">
                    <span className="text-slate-400 font-medium">SMA 50</span>
                    <span className={`font-mono font-bold ${statusColor(t.price_vs_sma50)}`}>
                        ${t.sma_50?.toFixed(2)} ({t.price_vs_sma50})
                    </span>
                </div>
                <div className="flex justify-between items-center p-1.5 rounded bg-[#161b22]/50 border border-[#30363d]/50">
                    <span className="text-slate-400 font-medium">SMA 200</span>
                    <span className={`font-mono font-bold ${statusColor(t.price_vs_sma200)}`}>
                        ${t.sma_200?.toFixed(2)} ({t.price_vs_sma200})
                    </span>
                </div>
                <div className="flex justify-between items-center p-1.5 rounded bg-[#161b22]/50 border border-[#30363d]/50">
                    <span className="text-slate-400 font-medium">MACD Signal</span>
                    <span className={`font-bold ${statusColor(t.macd_crossover)}`}>{t.macd_crossover}</span>
                </div>
                
                {t.golden_cross && (
                    <div className="mt-1 text-[8px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-1 rounded flex justify-center font-black uppercase tracking-wider">
                        ✦ Golden Cross Active
                    </div>
                )}
            </div>

            <ScoreWeightBar score={score} weight={weight} label="Trend Score" />
        </div>
    );
}

function TactMomentumCard({ data, weight }: { data: TechnicalAnalysisResult; weight: number }) {
    const m = data.indicators.momentum;
    const score = data.summary.subscores.momentum;
    const status = data.summary.momentum_status;
    const rsiPct = Math.max(0, Math.min(100, m.rsi));
    
    return (
        <div className={`glass-card p-4 border flex flex-col gap-3 ${statusBg(status)}`}>
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Activity size={14} className={statusColor(status)} />
                    <span className="text-[10px] font-black uppercase tracking-widest text-slate-300">Momentum</span>
                </div>
                <span className={`text-[8px] font-black px-1.5 py-0.5 rounded border uppercase ${statusBg(status)} ${statusColor(status)}`}>
                    {status.replace("_", " ")}
                </span>
            </div>

            <div className="space-y-4 mt-1">
                {/* RSI Visual Gauge */}
                <div className="space-y-1">
                    <div className="flex justify-between text-[9px] mb-1.5">
                        <span className="text-slate-400 font-medium">RSI (14)</span>
                        <span className={`font-mono font-bold ${statusColor(m.rsi_zone)}`}>{m.rsi.toFixed(1)}</span>
                    </div>
                    <div className="relative h-1.5 bg-[#21262d] rounded-full overflow-hidden">
                        <div className="absolute inset-y-0 left-[30%] right-[30%] bg-slate-700/20" />
                        <div
                            className={`absolute top-0 bottom-0 left-0 transition-all duration-500 ${m.rsi > 70 ? 'bg-orange-500' : m.rsi < 30 ? 'bg-sky-500' : 'bg-[#d4af37]'}`}
                            style={{ width: `${rsiPct}%` }}
                        />
                        <div className="absolute top-0 left-[30%] h-full w-[2px] bg-sky-500/50" />
                        <div className="absolute top-0 left-[70%] h-full w-[2px] bg-orange-500/50" />
                    </div>
                    <div className="flex justify-between text-[7px] text-slate-600 font-mono pt-0.5">
                        <span className="text-sky-500/70">OS 30</span>
                        <span className="text-orange-500/70">70 OB</span>
                    </div>
                </div>

                <div className="space-y-2 text-[9px]">
                    <div className="flex justify-between items-center p-1.5 rounded bg-[#161b22]/50 border border-[#30363d]/50">
                        <span className="text-slate-400 font-medium">Stochastic %K</span>
                        <span className={`font-mono font-bold ${statusColor(m.stochastic_zone)}`}>{m.stochastic_k.toFixed(1)}</span>
                    </div>
                    {m.divergence && m.divergence !== "NONE" && (
                        <div className={`p-1.5 rounded text-[8px] border font-bold uppercase tracking-wider text-center ${m.divergence === "BULLISH_DIV" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-rose-500/10 text-rose-400 border-rose-500/20"}`}>
                            {m.divergence.replace("_", " ")}
                        </div>
                    )}
                </div>
            </div>

            <ScoreWeightBar score={score} weight={weight} label="Momentum Score" />
        </div>
    );
}

function TactVolatilityCard({ data, weight }: { data: TechnicalAnalysisResult; weight: number }) {
    const v = data.indicators.volatility;
    const score = data.summary.subscores.volatility;
    const condition = data.summary.volatility_condition;
    return (
        <div className={`glass-card p-4 border flex flex-col gap-3 ${statusBg(condition)}`}>
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Zap size={14} className="text-yellow-400" />
                    <span className="text-[10px] font-black uppercase tracking-widest text-slate-300">Volatility</span>
                </div>
                <span className="text-[8px] font-black px-1.5 py-0.5 rounded border uppercase bg-yellow-500/10 border-yellow-500/20 text-yellow-400">
                    {condition}
                </span>
            </div>

            <div className="space-y-2 mt-1 text-[9px]">
                <div className="flex justify-between items-center p-1.5 rounded bg-[#161b22]/50 border border-[#30363d]/50">
                    <span className="text-slate-400 font-medium">BB Position</span>
                    <span className="font-bold text-slate-300">{v.bb_position.replace("_", " ")}</span>
                </div>
                <div className="flex justify-between items-center p-1.5 rounded bg-[#161b22]/50 border border-[#30363d]/50">
                    <span className="text-slate-400 font-medium">BB Width</span>
                    <span className="font-mono text-slate-300">{v.bb_width.toFixed(2)}</span>
                </div>
                <div className="flex justify-between items-center p-1.5 rounded bg-[#161b22]/50 border border-[#30363d]/50">
                    <span className="text-slate-400 font-medium">ATR</span>
                    <span className="font-mono text-slate-300">${v.atr.toFixed(2)} <span className="text-slate-500">({(v.atr_pct * 100).toFixed(1)}%)</span></span>
                </div>
            </div>

            <ScoreWeightBar score={score} weight={weight} label="Vol Score" />
        </div>
    );
}

function TactVolumeCard({ data, weight }: { data: TechnicalAnalysisResult; weight: number }) {
    const v = data.indicators.volume;
    const score = data.summary.subscores.volume;
    const strength = data.summary.volume_strength;
    return (
        <div className={`glass-card p-4 border flex flex-col gap-3 ${statusBg(strength)}`}>
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <BarChart3 size={14} className="text-sky-400" />
                    <span className="text-[10px] font-black uppercase tracking-widest text-slate-300">Volume</span>
                </div>
                <span className={`text-[8px] font-black px-1.5 py-0.5 rounded border uppercase ${statusBg(v.obv_trend)} ${statusColor(v.obv_trend)}`}>
                    OBV {v.obv_trend}
                </span>
            </div>

            <div className="space-y-2 mt-1 text-[9px]">
                <div className="flex justify-between items-center p-1.5 rounded bg-[#161b22]/50 border border-[#30363d]/50">
                    <span className="text-slate-400 font-medium">Vol vs Avg 20</span>
                    <span className={`font-mono font-bold ${v.volume_vs_avg_20 >= 1.5 ? "text-emerald-400" : v.volume_vs_avg_20 < 0.7 ? "text-rose-400" : "text-slate-300"}`}>
                        {v.volume_vs_avg_20.toFixed(2)}×
                    </span>
                </div>
                <div className="flex justify-between items-center p-1.5 rounded bg-[#161b22]/50 border border-[#30363d]/50">
                    <span className="text-slate-400 font-medium">Confirmation</span>
                    <span className={`font-bold ${statusColor(v.volume_price_confirmation || "")}`}>
                        {v.volume_price_confirmation || "NEUTRAL"}
                    </span>
                </div>
            </div>

            <ScoreWeightBar score={score} weight={weight} label="Volume Score" />
        </div>
    );
}

function TactStructureCard({ data, weight }: { data: TechnicalAnalysisResult; weight: number }) {
    const s = data.indicators.structure;
    const score = data.summary.subscores.structure;
    const dir = s.breakout_direction;
    const ms = (s as any).market_structure as string | undefined;
    
    return (
        <div className={`glass-card p-4 border flex flex-col gap-3 ${statusBg(dir)}`}>
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Layers size={14} className={statusColor(dir)} />
                    <span className="text-[10px] font-black uppercase tracking-widest text-slate-300">Structure</span>
                </div>
                <span className={`text-[8px] font-black px-1.5 py-0.5 rounded border uppercase ${statusBg(dir)} ${statusColor(dir)}`}>
                    {dir}
                </span>
            </div>

            <div className="space-y-2 mt-1 text-[9px]">
                {ms && ms !== "MIXED" && (
                    <div className={`flex justify-center p-1 rounded border text-[8px] font-black uppercase tracking-wider ${ms === "HH_HL" ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400" : "bg-rose-500/10 border-rose-500/30 text-rose-400"}`}>
                        {ms === "HH_HL" ? "↗ HH / HL (Uptrend)" : "↘ LH / LL (Downtrend)"}
                    </div>
                )}
                
                <div className="flex justify-between items-center p-1.5 rounded bg-[#161b22]/50 border border-[#30363d]/50">
                    <span className="text-slate-400 font-medium">Support</span>
                    <span className="font-mono text-emerald-400">
                        {s.nearest_support ? `$${s.nearest_support.toFixed(2)}` : "None"} 
                        {s.distance_to_support_pct && <span className="text-slate-500 text-[8px] ml-1">(-{s.distance_to_support_pct.toFixed(1)}%)</span>}
                    </span>
                </div>
                
                <div className="flex justify-between items-center p-1.5 rounded bg-[#161b22]/50 border border-[#30363d]/50">
                    <span className="text-slate-400 font-medium">Resistance</span>
                    <span className="font-mono text-rose-400">
                        {s.nearest_resistance ? `$${s.nearest_resistance.toFixed(2)}` : "None"}
                        {s.distance_to_resistance_pct && <span className="text-slate-500 text-[8px] ml-1">(+{s.distance_to_resistance_pct.toFixed(1)}%)</span>}
                    </span>
                </div>
            </div>

            <ScoreWeightBar score={score} weight={weight} label="Struct Score" />
        </div>
    );
}

// ─── Main Component ────────────────────────────────────────────────────────

interface UnifiedTacticalDashboardProps {
    data: TechnicalAnalysisResult;
    technicalMemo?: {
        trend: { signal: string; conviction: string; narrative: string; key_data: string[] };
        momentum: { signal: string; conviction: string; narrative: string; key_data: string[] };
        volatility: { signal: string; conviction: string; narrative: string; key_data: string[] };
        volume: { signal: string; conviction: string; narrative: string; key_data: string[] };
        structure: { signal: string; conviction: string; narrative: string; key_data: string[] };
        consensus: string;
        consensus_signal: string;
        consensus_conviction: string;
        tradingview_comparison: string;
        key_levels: string;
        timing: string;
        risk_factors: string[];
    } | null;
}

export default function UnifiedTacticalDashboard({ data, technicalMemo }: UnifiedTacticalDashboardProps) {
    const { summary, regime } = data;
    const trendRegime = regime?.trend_regime || "TRANSITIONING";

    // Build data for the Radar Chart
    const radarData = useMemo(() => {
        return [
            { subject: "Trend", score: summary.subscores.trend, fullMark: 10 },
            { subject: "Momentum", score: summary.subscores.momentum, fullMark: 10 },
            { subject: "Volatility", score: summary.subscores.volatility, fullMark: 10 },
            { subject: "Volume", score: summary.subscores.volume, fullMark: 10 },
            { subject: "Structure", score: summary.subscores.structure, fullMark: 10 },
        ];
    }, [summary.subscores]);

    return (
        <div className="space-y-4" style={{ animation: "fadeSlideIn 0.4s ease both" }}>
            {/* Dot Grid Background Overlay is applied via standard CSS in Tailwind global if needed, 
                or we can use minimal border styles to simulate it. */}
                
            {/* ── 1. ZONA SUPERIOR: Radial, Flow-Chart, Veredicto ────────────────── */}
            <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
                
                {/* 1A. Institutuional Radar Chart (Left Module) */}
                <div className="md:col-span-3 glass-card border-[#30363d] p-4 flex flex-col h-full bg-[#0d1117] relative overflow-hidden">
                    <div className="absolute inset-0 bg-[url('/img/dot_grid.png')] opacity-10 pointer-events-none" />
                    <p className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-2">
                        Institutional Radar
                    </p>
                    <div className="flex-1 w-full min-h-[160px] -ml-2">
                        <ResponsiveContainer width="100%" height="100%">
                            <RadarChart cx="50%" cy="50%" outerRadius="70%" data={radarData}>
                                <PolarGrid stroke="#30363d" />
                                <PolarAngleAxis dataKey="subject" tick={{ fill: '#8b949e', fontSize: 9, fontWeight: 700 }} />
                                <PolarRadiusAxis angle={30} domain={[0, 10]} stroke="#30363d" tick={false} axisLine={false} />
                                <Radar
                                    name="Score"
                                    dataKey="score"
                                    stroke={summary.signal.includes("BUY") ? "#10b981" : summary.signal.includes("SELL") ? "#f43f5e" : "#d4af37"}
                                    fill={summary.signal.includes("BUY") ? "#10b981" : summary.signal.includes("SELL") ? "#f43f5e" : "#d4af37"}
                                    fillOpacity={0.2}
                                />
                            </RadarChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* 1B. Actionable Flow Chart (Middle Module) */}
                <div className="md:col-span-6 glass-card border-[#30363d] p-5 flex flex-col justify-center bg-[#0d1117]/80">
                    <p className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-4">
                        Actionable Logic Flow
                    </p>
                    <div className="flex flex-col sm:flex-row items-center gap-2 w-full">
                        {/* Block 1: Regime */}
                        <div className="flex-1 flex flex-col items-center justify-center p-3 rounded-lg border border-[#30363d] bg-[#161b22] text-center w-full min-h-[70px]">
                            <span className="text-[8px] uppercase tracking-widest text-slate-500 mb-1">Regime Detected</span>
                            <span className={`text-[10px] font-black uppercase ${trendRegime === "TRENDING" ? "text-emerald-400" : "text-sky-400"}`}>
                                {trendRegime}
                            </span>
                        </div>
                        
                        <ArrowRight size={14} className="text-slate-600 rotate-90 sm:rotate-0 flex-shrink-0" />
                        
                        {/* Block 2: Structure / Bias */}
                        <div className="flex-1 flex flex-col items-center justify-center p-3 rounded-lg border border-[#30363d] bg-[#161b22] text-center w-full min-h-[70px]">
                            <span className="text-[8px] uppercase tracking-widest text-slate-500 mb-1">Bias & Zone</span>
                            <span className={`text-[10px] font-black uppercase ${statusColor(data.bias?.primary_bias || summary.signal)}`}>
                                {data.bias?.actionable_zone || summary.actionable_zone?.replace("_", " ") || "Wait"}
                            </span>
                        </div>
                        
                        <ArrowRight size={14} className="text-slate-600 rotate-90 sm:rotate-0 flex-shrink-0" />

                        {/* Block 3: Final Action */}
                        <div className={`flex-1 flex flex-col items-center justify-center p-3 rounded-lg border text-center w-full min-h-[70px] transition-colors ${statusBg(summary.signal)}`}>
                            <ShieldCheck size={14} className={`mb-1 ${signalColor(summary.signal)}`} />
                            <span className={`text-[11px] font-black uppercase tracking-wider ${signalColor(summary.signal)}`}>
                                {summary.signal.replace("_", " ")}
                            </span>
                        </div>
                    </div>
                </div>

                {/* 1C. 365 Master Score (Right Module) */}
                <div className={`md:col-span-3 glass-card border flex flex-col justify-center items-center p-6 text-center shadow-lg ${statusBg(summary.signal)}`}>
                    <p className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2">
                        Technical Score
                    </p>
                    <div className="flex items-start gap-1">
                        <span className={`text-6xl font-black tabular-nums tracking-tighter ${signalColor(summary.signal)} drop-shadow-md`}>
                            {summary.technical_score.toFixed(1)}
                        </span>
                        <span className="text-sm font-bold text-slate-500 mt-2">/10</span>
                    </div>
                    
                    <div className="mt-4 flex items-center justify-center gap-1.5 flex-wrap">
                        <span className="text-[8px] font-black text-slate-400 px-2 py-1 rounded border border-[#30363d] bg-[#161b22] uppercase tracking-wider">
                            {summary.signal_strength} STRENGTH
                        </span>
                        {summary.confirmation_level && (
                            <span className="text-[8px] font-black text-slate-400 px-2 py-1 rounded border border-[#30363d] bg-[#161b22] uppercase tracking-wider">
                                {summary.confirmation_level} CONF
                            </span>
                        )}
                    </div>
                </div>
            </div>

            {/* ── 2. ZONA CENTRAL: Grid Táctico de Componentes ──────────────────── */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
                <TactTrendCard data={data} weight={getWeight(trendRegime, "trend")} />
                <TactMomentumCard data={data} weight={getWeight(trendRegime, "momentum")} />
                <TactVolatilityCard data={data} weight={getWeight(trendRegime, "volatility")} />
                <TactVolumeCard data={data} weight={getWeight(trendRegime, "volume")} />
                <TactStructureCard data={data} weight={getWeight(trendRegime, "structure")} />
            </div>

            {/* ── 3. ZONA INFERIOR: MTF Heatmap ─────────────────────────────────── */}
            {data.mtf?.timeframe_scores && (
                <div className="glass-card p-5 border-[#30363d] bg-[#0d1117]">
                    <div className="flex items-center justify-between mb-4">
                        <p className="text-[10px] font-black uppercase tracking-widest text-slate-400">
                            Multi-Timeframe Heatmap (MTF)
                        </p>
                        <div className="flex items-center gap-3">
                            <span className={`text-[9px] font-black px-2.5 py-1 rounded border uppercase ${
                                data.mtf.agreement_level === "STRONG" ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-400" :
                                data.mtf.agreement_level === "MODERATE" ? "bg-yellow-500/15 border-yellow-500/30 text-yellow-400" :
                                "bg-rose-500/15 border-rose-500/30 text-rose-400"
                            }`}>
                                {data.mtf.agreement_level} AGMT ({data.mtf.agreement_count}/4)
                            </span>
                            <div className="flex items-center gap-1 text-[10px] font-mono">
                                <span className="text-slate-500 tracking-widest uppercase">MTF Score</span>
                                <span className={`font-black ml-1 text-sm ${signalColor(data.mtf.mtf_signal)}`}>
                                    {data.mtf.mtf_aggregate.toFixed(1)}
                                </span>
                            </div>
                        </div>
                    </div>
                    
                    {/* Heatmap Row */}
                    <div className="grid grid-cols-4 gap-3">
                        {(data.mtf.timeframe_scores as any[]).map((tf: any) => {
                            const isBull = tf.score >= 6;
                            const isBear = tf.score <= 4;
                            const hBg = isBull ? "bg-emerald-500/5 hover:bg-emerald-500/10 border-emerald-500/10" :
                                      isBear ? "bg-rose-500/5 hover:bg-rose-500/10 border-rose-500/10" :
                                      "bg-slate-800/50 hover:bg-slate-800 border-slate-700/50";
                            return (
                                <div key={tf.timeframe} className={`rounded-xl border p-4 flex flex-col items-center justify-center transition-colors ${hBg}`}>
                                    <p className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-1">
                                        {tf.timeframe}
                                    </p>
                                    <p className={`text-2xl font-black ${isBull ? "text-emerald-400" : isBear ? "text-rose-400" : "text-slate-300"}`}>
                                        {tf.score.toFixed(1)}
                                    </p>
                                    <div className="flex gap-2 mt-2">
                                        <div className="flex items-center gap-1">
                                            <span className={`w-1.5 h-1.5 rounded-full ${statusBg(tf.trend) ? statusColor(tf.trend).replace("text-", "bg-") : "bg-slate-500"}`} />
                                            <span className="text-[7px] font-bold text-slate-400 uppercase">TRD</span>
                                        </div>
                                        <div className="flex items-center gap-1">
                                            <span className={`w-1.5 h-1.5 rounded-full ${statusBg(tf.signal) ? statusColor(tf.signal).replace("text-", "bg-") : "bg-slate-500"}`} />
                                            <span className="text-[7px] font-bold text-slate-400 uppercase">MOM</span>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>

                    {data.mtf.bonus_applied !== 0 && (
                        <p className="text-[7px] text-slate-600 mt-2 text-right">
                            Agreement adjustment: <b className={`${data.mtf.bonus_applied > 0 ? "text-emerald-500" : "text-rose-500"}`}>
                                {data.mtf.bonus_applied > 0 ? "+" : ""}{data.mtf.bonus_applied}
                            </b>
                        </p>
                    )}
                </div>
            )}

            {/* ── 4. ZONA INFERIOR: Technical Analyst Memo (LLM Interpretation) ── */}
            {technicalMemo && (() => {
                const signalBadge = (sig: string) => {
                    const s = sig.toUpperCase();
                    if (s === "BULLISH") return "bg-emerald-500/15 border-emerald-500/30 text-emerald-400";
                    if (s === "BEARISH") return "bg-rose-500/15 border-rose-500/30 text-rose-400";
                    return "bg-slate-500/10 border-slate-500/30 text-slate-400";
                };
                const convictionDot = (c: string) => {
                    const v = c.toUpperCase();
                    if (v === "HIGH") return "text-emerald-400";
                    if (v === "MEDIUM") return "text-yellow-400";
                    return "text-slate-500";
                };

                const OPINIONS = [
                    { key: "trend" as const, label: "Tendencia", icon: <TrendingUp size={11} />, color: "text-sky-400" },
                    { key: "momentum" as const, label: "Momentum", icon: <Activity size={11} />, color: "text-emerald-400" },
                    { key: "volatility" as const, label: "Volatilidad", icon: <Zap size={11} />, color: "text-yellow-400" },
                    { key: "volume" as const, label: "Volumen", icon: <BarChart3 size={11} />, color: "text-sky-300" },
                    { key: "structure" as const, label: "Estructura", icon: <Layers size={11} />, color: "text-orange-400" },
                ];

                return (
                    <div className="glass-card p-5 border-[#30363d]" style={{ animation: "fadeSlideIn 0.5s ease both" }}>
                        {/* Header */}
                        <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-2">
                                <Activity size={16} className="text-purple-400" />
                                <p className="text-[10px] font-black uppercase tracking-widest text-slate-400">
                                    Technical Analyst
                                    <span className="text-slate-600 font-normal ml-1">(AI Committee)</span>
                                </p>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className={`text-[9px] font-black px-2 py-0.5 rounded border uppercase ${signalBadge(technicalMemo.consensus_signal)}`}>
                                    {technicalMemo.consensus_signal}
                                </span>
                                <span className={`text-[8px] font-bold ${convictionDot(technicalMemo.consensus_conviction)}`}>
                                    ● {technicalMemo.consensus_conviction}
                                </span>
                            </div>
                        </div>

                        {/* Consensus Thesis */}
                        <div className="mb-4 p-3 rounded-lg bg-purple-500/5 border border-purple-500/15">
                            <p className="text-[11px] text-slate-300 leading-relaxed">{technicalMemo.consensus}</p>
                        </div>

                        {/* TradingView Cross-Validation */}
                        {technicalMemo.tradingview_comparison && (
                            <div className="mb-5 p-3 rounded-lg bg-[#131722]/80 border border-[#2962ff]/20 flex items-start gap-2.5">
                                <span className="text-[10px] font-black text-[#2962ff] whitespace-nowrap mt-0.5">TV</span>
                                <p className="text-[10px] text-slate-400 leading-relaxed">{technicalMemo.tradingview_comparison}</p>
                            </div>
                        )}

                        {/* 5 Specialty Opinion Cards */}
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 mb-4">
                            {OPINIONS.map(({ key, label, icon, color }) => {
                                const op = technicalMemo[key];
                                return (
                                    <div key={key} className="p-3 rounded-lg bg-[#161b22] border border-[#30363d] flex flex-col gap-2">
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-1.5">
                                                <span className={color}>{icon}</span>
                                                <span className={`text-[8px] font-black uppercase tracking-widest ${color}`}>{label}</span>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-1.5">
                                            <span className={`text-[8px] font-black px-1.5 py-0.5 rounded border uppercase ${signalBadge(op.signal)}`}>
                                                {op.signal}
                                            </span>
                                            <span className={`text-[7px] font-bold ${convictionDot(op.conviction)}`}>
                                                ● {op.conviction}
                                            </span>
                                        </div>
                                        <p className="text-[9px] text-slate-400 leading-relaxed flex-1">{op.narrative}</p>
                                        {op.key_data.length > 0 && (
                                            <div className="flex flex-wrap gap-1 mt-auto pt-1 border-t border-[#30363d]/50">
                                                {op.key_data.map((d: string, i: number) => (
                                                    <span key={i} className="text-[7px] bg-[#21262d] text-slate-500 px-1.5 py-0.5 rounded font-mono">
                                                        {d}
                                                    </span>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>

                        {/* Key Levels + Timing */}
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
                            <div className="p-3 rounded-lg bg-[#161b22] border border-[#30363d]">
                                <div className="flex items-center gap-1.5 mb-1.5">
                                    <Target size={10} className="text-cyan-400" />
                                    <span className="text-[8px] font-black uppercase tracking-widest text-cyan-400">Niveles Clave</span>
                                </div>
                                <p className="text-[10px] text-slate-400 leading-relaxed">{technicalMemo.key_levels}</p>
                            </div>
                            <div className="p-3 rounded-lg bg-[#161b22] border border-[#30363d]">
                                <div className="flex items-center gap-1.5 mb-1.5">
                                    <Clock size={10} className="text-emerald-400" />
                                    <span className="text-[8px] font-black uppercase tracking-widest text-emerald-400">Timing</span>
                                </div>
                                <p className="text-[10px] text-slate-400 leading-relaxed">{technicalMemo.timing}</p>
                            </div>
                        </div>

                        {/* Risk Factors */}
                        {technicalMemo.risk_factors.length > 0 && (
                            <div className="p-3 rounded-lg bg-rose-500/5 border border-rose-500/15">
                                <div className="flex items-center gap-1.5 mb-2">
                                    <AlertTriangle size={10} className="text-rose-400" />
                                    <span className="text-[8px] font-black uppercase tracking-widest text-rose-400">Riesgos Técnicos</span>
                                </div>
                                <ul className="space-y-1">
                                    {technicalMemo.risk_factors.map((risk: string, i: number) => (
                                        <li key={i} className="text-[10px] text-slate-500 flex items-start gap-1.5">
                                            <span className="text-rose-500 mt-0.5">▸</span>
                                            <span>{risk}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </div>
                );
            })()}

            {/* Footer meta */}
            <div className="flex items-center justify-between text-[8px] text-slate-700 px-1">
                <span>
                    Source: <b className="text-slate-500">yfinance + TA-Lib AI</b>
                </span>
                {data.timestamp && (
                    <span>
                        {data.from_cache ? "⚡ Cached" : "Live"} ·{" "}
                        {data.processing_time_ms != null ? `${data.processing_time_ms}ms` : "—"} ·{" "}
                        {new Date(data.timestamp).toLocaleTimeString()}
                    </span>
                )}
            </div>

        </div>
    );
}
