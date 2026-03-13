"use client";

import { TrendingUp, Activity, Zap, BarChart3, Layers, Brain, Target, AlertTriangle, Clock } from "lucide-react";
import { TechnicalAnalysisResult } from "@/hooks/useTechnicalAnalysis";
import GlossaryTooltip from "./GlossaryTooltip";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function statusColor(status: string): string {
    const s = status.toUpperCase();
    if (s.includes("STRONG_BULL") || s === "STRONG") return "text-green-400";
    if (s.includes("BULL") || s === "RISING" || s === "ABOVE") return "text-green-400";
    if (s.includes("STRONG_BEAR")) return "text-red-400";
    if (s.includes("BEAR") || s === "FALLING" || s === "BELOW") return "text-red-400";
    if (s === "OVERSOLD") return "text-blue-400";
    if (s === "OVERBOUGHT") return "text-orange-400";
    return "text-gray-400";
}

function statusBg(status: string): string {
    const s = status.toUpperCase();
    if (s.includes("STRONG_BULL")) return "bg-green-500/20 border-green-500/40";
    if (s.includes("BULL") || s === "RISING") return "bg-green-500/10 border-green-500/25";
    if (s.includes("STRONG_BEAR")) return "bg-red-500/20 border-red-500/40";
    if (s.includes("BEAR") || s === "FALLING") return "bg-red-500/10 border-red-500/25";
    if (s === "OVERSOLD") return "bg-blue-500/10 border-blue-500/25";
    if (s === "OVERBOUGHT") return "bg-orange-500/10 border-orange-500/25";
    return "bg-gray-500/10 border-gray-500/20";
}

function signalColor(signal: string): string {
    if (signal === "STRONG_BUY") return "text-green-300";
    if (signal === "BUY") return "text-green-400";
    if (signal === "STRONG_SELL") return "text-red-300";
    if (signal === "SELL") return "text-red-400";
    return "text-gray-400";
}

function ScoreBar({ value, label }: { value: number; label: string }) {
    const pct = (value / 10) * 100;
    const color =
        value >= 7 ? "bg-green-500" : value >= 5 ? "bg-[#d4af37]" : "bg-red-500";
    return (
        <div className="space-y-1">
            <div className="flex justify-between items-center">
                <span className="text-[9px] text-gray-500 uppercase tracking-widest font-bold">
                    {label}
                </span>
                <span className="text-[10px] font-mono tabular-nums text-gray-300">{value.toFixed(1)}</span>
            </div>
            <div className="h-1 bg-[#21262d] rounded-full overflow-hidden">
                <div
                    className={`h-full rounded-full transition-all duration-500 ${color}`}
                    style={{ width: `${pct}%` }}
                />
            </div>
        </div>
    );
}

// ─── Module Cards ─────────────────────────────────────────────────────────────

function TrendCard({ data }: { data: TechnicalAnalysisResult }) {
    const t = data.indicators.trend;
    const score = data.summary.subscores.trend;
    const status = data.summary.trend_status;
    return (
        <div className={`glass-card p-4 border flex flex-col gap-3 ${statusBg(status)}`}>
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <TrendingUp size={14} className={statusColor(status)} />
                    <span className="text-[10px] font-black uppercase tracking-widest text-gray-400">Trend</span>
                </div>
                <span className={`text-[9px] font-black px-1.5 py-0.5 rounded border uppercase ${statusBg(status)} ${statusColor(status)}`}>
                    {status.replace("_", " ")}
                </span>
            </div>

            <div className="text-2xl font-black text-white">{score.toFixed(1)}<span className="text-xs font-normal text-gray-600">/10</span></div>

            <div className="space-y-1.5 text-[9px]">
                <div className="flex justify-between">
                    <span className="text-gray-600"><GlossaryTooltip term="SMA" label="SMA 50" /></span>
                    <span className={`font-mono font-bold tabular-nums ${statusColor(t.price_vs_sma50)}`}>{t.price_vs_sma50}</span>
                </div>
                <div className="flex justify-between">
                    <span className="text-gray-600"><GlossaryTooltip term="SMA" label="SMA 200" /></span>
                    <span className={`font-mono font-bold tabular-nums ${statusColor(t.price_vs_sma200)}`}>{t.price_vs_sma200}</span>
                </div>
                <div className="flex justify-between">
                    <span className="text-gray-600"><GlossaryTooltip term="MACD" label="MACD Cross" /></span>
                    <span className={`font-bold ${statusColor(t.macd_crossover)}`}>{t.macd_crossover}</span>
                </div>
                {t.golden_cross && (
                    <span className="text-[8px] bg-green-500/10 text-green-400 border border-green-500/20 px-1.5 py-0.5 rounded font-black uppercase tracking-wider">
                        ✦ Golden Cross
                    </span>
                )}
                {t.death_cross && (
                    <span className="text-[8px] bg-red-500/10 text-red-400 border border-red-500/20 px-1.5 py-0.5 rounded font-black uppercase tracking-wider">
                        ✦ Death Cross
                    </span>
                )}
            </div>
        </div>
    );
}

function MomentumCard({ data }: { data: TechnicalAnalysisResult }) {
    const m = data.indicators.momentum;
    const score = data.summary.subscores.momentum;
    const status = data.summary.momentum_status;
    const rsiPct = (m.rsi / 100) * 100;
    return (
        <div className={`glass-card p-4 border flex flex-col gap-3 ${statusBg(status)}`}>
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Activity size={14} className={statusColor(status)} />
                    <span className="text-[10px] font-black uppercase tracking-widest text-gray-400">Momentum</span>
                </div>
                <span className={`text-[9px] font-black px-1.5 py-0.5 rounded border uppercase ${statusBg(status)} ${statusColor(status)}`}>
                    {status.replace("_", " ")}
                </span>
            </div>

            <div className="text-2xl font-black text-white">{score.toFixed(1)}<span className="text-xs font-normal text-gray-600">/10</span></div>

            {/* RSI gauge */}
            <div className="space-y-1">
                <div className="flex justify-between text-[9px]">
                    <span className="text-gray-600">RSI (14)</span>
                    <span className={`font-mono font-bold tabular-nums ${statusColor(m.rsi_zone)}`}>{m.rsi.toFixed(1)}</span>
                </div>
                <div className="relative h-2 bg-[#21262d] rounded-full overflow-hidden">
                    <div className="absolute inset-y-0 left-[30%] right-[30%] bg-gray-700/30" />
                    <div
                        className="h-full rounded-full transition-all duration-500 bg-[#d4af37]"
                        style={{ width: `${rsiPct}%` }}
                    />
                    <div className="absolute top-0 left-[30%] h-full w-px bg-red-500/30" />
                    <div className="absolute top-0 left-[70%] h-full w-px bg-red-500/30" />
                </div>
                <div className="flex justify-between text-[7px] text-gray-700">
                    <span>0 Oversold</span><span>70 Overbought 100</span>
                </div>
            </div>

            <div className="space-y-1 text-[9px]">
                <div className="flex justify-between">
                    <span className="text-gray-600">RSI Zone</span>
                    <span className={`font-bold ${statusColor(m.rsi_zone)}`}>{m.rsi_zone}</span>
                </div>
                <div className="flex justify-between">
                    <span className="text-gray-600"><GlossaryTooltip term="Stochastic" label="Stoch %K" /></span>
                    <span className={`font-mono font-bold tabular-nums ${statusColor(m.stochastic_zone)}`}>{m.stochastic_k.toFixed(1)}</span>
                </div>
            </div>
        </div>
    );
}

function VolatilityCard({ data }: { data: TechnicalAnalysisResult }) {
    const v = data.indicators.volatility;
    const score = data.summary.subscores.volatility;
    const condition = data.summary.volatility_condition;
    return (
        <div className={`glass-card p-4 border flex flex-col gap-3 ${statusBg(condition)}`}>
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Zap size={14} className="text-yellow-400" />
                    <span className="text-[10px] font-black uppercase tracking-widest text-gray-400">Volatility</span>
                </div>
                <span className="text-[9px] font-black px-1.5 py-0.5 rounded border uppercase bg-yellow-500/10 border-yellow-500/20 text-yellow-400">
                    {condition}
                </span>
            </div>

            <div className="text-2xl font-black text-white">{score.toFixed(1)}<span className="text-xs font-normal text-gray-600">/10</span></div>

            <div className="space-y-1.5 text-[9px]">
                <div className="flex justify-between">
                    <span className="text-gray-600"><GlossaryTooltip term="Bollinger Bands" label="BB Position" /></span>
                    <span className="font-bold text-gray-300">{v.bb_position.replace("_", " ")}</span>
                </div>
                <div className="flex justify-between">
                    <span className="text-gray-600">BB Width</span>
                    <span className="font-mono tabular-nums text-gray-300">{v.bb_width.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                    <span className="text-gray-600"><GlossaryTooltip term="ATR" label="ATR" /></span>
                    <span className="font-mono tabular-nums text-gray-300">{v.atr.toFixed(2)} ({(v.atr_pct * 100).toFixed(1)}%)</span>
                </div>
            </div>
        </div>
    );
}

function VolumeCard({ data }: { data: TechnicalAnalysisResult }) {
    const v = data.indicators.volume;
    const score = data.summary.subscores.volume;
    const strength = data.summary.volume_strength;
    return (
        <div className={`glass-card p-4 border flex flex-col gap-3 ${statusBg(strength)}`}>
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <BarChart3 size={14} className="text-blue-400" />
                    <span className="text-[10px] font-black uppercase tracking-widest text-gray-400">Volume</span>
                </div>
                <span className={`text-[9px] font-black px-1.5 py-0.5 rounded border uppercase ${statusBg(v.obv_trend)} ${statusColor(v.obv_trend)}`}>
                    OBV {v.obv_trend}
                </span>
            </div>

            <div className="text-2xl font-black text-white">{score.toFixed(1)}<span className="text-xs font-normal text-gray-600">/10</span></div>

            <div className="space-y-1.5 text-[9px]">
                <div className="flex justify-between">
                    <span className="text-gray-600">Vol/Avg20</span>
                    <span className={`font-mono font-bold ${v.volume_vs_avg_20 >= 1.5 ? "text-green-400" : v.volume_vs_avg_20 < 0.7 ? "text-red-400" : "text-gray-300"}`}>
                        {v.volume_vs_avg_20.toFixed(2)}×
                    </span>
                </div>
                <div className="flex justify-between">
                    <span className="text-gray-600">Strength</span>
                    <span className={`font-bold ${statusColor(strength)}`}>{strength}</span>
                </div>
            </div>
        </div>
    );
}

function StructureCard({ data }: { data: TechnicalAnalysisResult }) {
    const s = data.indicators.structure;
    const score = data.summary.subscores.structure;
    const dir = s.breakout_direction;
    const ms = (s as any).market_structure as string | undefined;
    const patterns = ((s as any).patterns || []) as string[];
    const levelStrength = ((s as any).level_strength || {}) as Record<string, { touches: number; strong: boolean }>;
    return (
        <div className={`glass-card p-4 border flex flex-col gap-3 ${statusBg(dir)}`}>
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Layers size={14} className={statusColor(dir)} />
                    <span className="text-[10px] font-black uppercase tracking-widest text-gray-400">Structure</span>
                </div>
                <span className={`text-[9px] font-black px-1.5 py-0.5 rounded border uppercase ${statusBg(dir)} ${statusColor(dir)}`}>
                    {dir}
                </span>
            </div>

            <div className="text-2xl font-black text-white">{score.toFixed(1)}<span className="text-xs font-normal text-gray-600">/10</span></div>

            {/* V2: Market Structure badge */}
            {ms && ms !== "MIXED" && (
                <span className={`text-[8px] font-black px-2 py-0.5 rounded border uppercase tracking-wider self-start ${ms === "HH_HL" ? "bg-green-500/10 border-green-500/30 text-green-400" :
                        "bg-red-500/10 border-red-500/30 text-red-400"
                    }`}>
                    {ms === "HH_HL" ? "↗ HH / HL" : "↘ LH / LL"}
                </span>
            )}

            {/* V2: Pattern badges */}
            {patterns.length > 0 && (
                <div className="flex flex-wrap gap-1">
                    {patterns.map((p: string) => (
                        <span key={p} className={`text-[7px] font-black px-1.5 py-0.5 rounded border uppercase ${p.includes("BOTTOM") || p.includes("HIGHER") ? "bg-green-500/10 border-green-500/30 text-green-400" :
                                "bg-red-500/10 border-red-500/30 text-red-400"
                            }`}>
                            {p.replace(/_/g, " ")}
                        </span>
                    ))}
                </div>
            )}

            <div className="space-y-1.5 text-[9px]">
                <div className="flex justify-between">
                    <span className="text-gray-600">Breakout Prob</span>
                    <span className={`font-bold ${statusColor(dir)}`}>{data.summary.breakout_probability}</span>
                </div>
                {s.nearest_resistance && (
                    <div className="flex justify-between">
                        <span className="text-gray-600"><GlossaryTooltip term="Resistance" label="Resistance" /></span>
                        <span className="font-mono text-red-400">${s.nearest_resistance.toFixed(2)}{s.distance_to_resistance_pct != null ? ` (+${s.distance_to_resistance_pct.toFixed(1)}%)` : ""}</span>
                    </div>
                )}
                {s.nearest_support && (
                    <div className="flex justify-between">
                        <span className="text-gray-600"><GlossaryTooltip term="Support" label="Support" /></span>
                        <span className="font-mono text-green-400">${s.nearest_support.toFixed(2)}{s.distance_to_support_pct != null ? ` (-${s.distance_to_support_pct.toFixed(1)}%)` : ""}</span>
                    </div>
                )}
            </div>

            {/* V2: Level Strength */}
            {Object.keys(levelStrength).length > 0 && (
                <div className="flex flex-wrap gap-1">
                    {Object.entries(levelStrength).map(([level, info]) => (
                        <span key={level} className={`text-[7px] px-1.5 py-0.5 rounded border ${info.strong ? "border-yellow-500/40 bg-yellow-500/10" : "border-[#30363d] bg-[#161b22]"
                            }`}>
                            <span className="text-gray-400">${level}</span>
                            <span className={`ml-0.5 font-bold ${info.strong ? "text-yellow-400" : "text-gray-600"}`}>
                                {info.touches}×
                            </span>
                            {info.strong && <span className="ml-0.5 text-yellow-500">★</span>}
                        </span>
                    ))}
                </div>
            )}
        </div>
    );
}

// ─── Main IndicatorGrid component ─────────────────────────────────────────────

interface IndicatorGridProps {
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

export default function IndicatorGrid({ data, technicalMemo }: IndicatorGridProps) {
    const { summary } = data;

    return (
        <div className="space-y-6" style={{ animation: "fadeSlideIn 0.4s ease both" }}>

            {/* ── Score Header ────────────────────────────────────────────────────── */}
            <div className="glass-card p-5 border-[#30363d] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div>
                    <p className="text-[9px] font-black uppercase tracking-widest text-gray-500 mb-1">
                        Technical Score
                    </p>
                    <div className="flex items-baseline gap-2">
                        <span className={`text-5xl font-black ${signalColor(summary.signal)}`}>
                            {summary.technical_score.toFixed(1)}
                        </span>
                        <span className="text-gray-600 text-sm">/10</span>
                    </div>
                </div>

                <div className="flex flex-col items-start sm:items-end gap-2">
                    <div className="flex items-center gap-2">
                        <span className={`text-sm font-black px-3 py-1 rounded-lg border uppercase tracking-wider ${statusBg(summary.signal)} ${signalColor(summary.signal)}`}>
                            {summary.signal.replace("_", " ")}
                        </span>
                        <span className="text-[9px] font-bold text-gray-500 px-2 py-1 rounded border border-[#30363d] bg-[#161b22]">
                            {summary.signal_strength}
                        </span>
                        {summary.confirmation_level && (
                            <span className={`text-[8px] font-black px-2 py-0.5 rounded border uppercase tracking-wider ${
                                summary.confirmation_level === "HIGH" ? "bg-green-500/10 border-green-500/30 text-green-400" :
                                summary.confirmation_level === "MEDIUM" ? "bg-yellow-500/10 border-yellow-500/30 text-yellow-400" :
                                    "bg-gray-500/10 border-gray-500/30 text-gray-400"
                            }`}>
                                ◎ {summary.confirmation_level} CONF
                            </span>
                        )}
                    </div>
                    {/* Regime badges */}
                    {data.regime?.trend_regime && (
                        <div className="flex items-center gap-2">
                            <span className={`text-[8px] font-black px-2 py-0.5 rounded border uppercase tracking-wider ${data.regime.trend_regime === "TRENDING" ? "bg-green-500/10 border-green-500/30 text-green-400" :
                                    data.regime.trend_regime === "RANGING" ? "bg-blue-500/10 border-blue-500/30 text-blue-400" :
                                        data.regime.trend_regime === "VOLATILE" ? "bg-red-500/10 border-red-500/30 text-red-400" :
                                            "bg-gray-500/10 border-gray-500/30 text-gray-400"
                                }`}>
                                ◆ {data.regime.trend_regime}
                            </span>
                            <span className={`text-[8px] font-black px-2 py-0.5 rounded border uppercase tracking-wider ${data.regime.volatility_regime === "COMPRESSION" ? "bg-yellow-500/10 border-yellow-500/30 text-yellow-400" :
                                    data.regime.volatility_regime === "EXPANSION" ? "bg-orange-500/10 border-orange-500/30 text-orange-400" :
                                        data.regime.volatility_regime === "MEAN_REVERTING" ? "bg-purple-500/10 border-purple-500/30 text-purple-400" :
                                            "bg-gray-500/10 border-gray-500/30 text-gray-400"
                                }`}>
                                ◆ {data.regime.volatility_regime?.replace("_", " ")}
                            </span>
                            <span className="text-[7px] font-mono text-gray-600">ADX {data.regime.adx?.toFixed(1)}</span>
                        </div>
                    )}
                    <div className="flex gap-4 text-[9px] text-gray-600">
                        <span>Trend: <b className={statusColor(summary.trend_status)}>{summary.trend_status.replace(/_/g, " ")}</b></span>
                        <span>Momentum: <b className={statusColor(summary.momentum_status)}>{summary.momentum_status.replace(/_/g, " ")}</b></span>
                    </div>
                </div>
            </div>

            {/* ── TradingView Rating (reference) ──────────────────────────────── */}
            {data.tradingview_rating && (
                <div className="glass-card p-4 border-[#30363d]">
                    <p className="text-[9px] font-black uppercase tracking-widest text-gray-500 mb-3">
                        TradingView Rating <span className="text-gray-700 font-normal">(26 indicators)</span>
                    </p>
                    <div className="grid grid-cols-3 gap-3">
                        {[
                            { label: "Overall", data: data.tradingview_rating },
                            { label: "Oscillators", data: data.tradingview_rating?.oscillators },
                            { label: "Moving Avgs", data: data.tradingview_rating?.moving_averages },
                        ].map(({ label, data: d }) => {
                            const rec = d?.recommendation || "UNKNOWN";
                            const buy = d?.buy || 0;
                            const sell = d?.sell || 0;
                            const neutral = d?.neutral || 0;
                            const total = buy + sell + neutral || 1;
                            const recColor = rec.includes("BUY") ? "text-green-400" : rec.includes("SELL") ? "text-red-400" : "text-gray-400";
                            return (
                                <div key={label} className="text-center">
                                    <p className="text-[8px] text-gray-600 uppercase tracking-widest mb-1">{label}</p>
                                    <p className={`text-xs font-black uppercase ${recColor}`}>{rec.replace("_", " ")}</p>
                                    <div className="flex h-1.5 rounded-full overflow-hidden mt-1.5 bg-[#21262d]">
                                        {buy > 0 && <div className="bg-green-500 transition-all" style={{ width: `${(buy / total) * 100}%` }} />}
                                        {neutral > 0 && <div className="bg-gray-500 transition-all" style={{ width: `${(neutral / total) * 100}%` }} />}
                                        {sell > 0 && <div className="bg-red-500 transition-all" style={{ width: `${(sell / total) * 100}%` }} />}
                                    </div>
                                    <div className="flex justify-between text-[7px] mt-0.5 text-gray-700">
                                        <span className="text-green-600">{buy}B</span>
                                        <span>{neutral}N</span>
                                        <span className="text-red-600">{sell}S</span>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* ── Subscore bars ────────────────────────────────────────────────────── */}
            <div className="glass-card p-4 border-[#30363d]">
                <p className="text-[9px] font-black uppercase tracking-widest text-gray-500 mb-4">Module Scores</p>
                <div className="space-y-3">
                    <ScoreBar value={summary.subscores.trend} label="Trend" />
                    <ScoreBar value={summary.subscores.momentum} label="Momentum" />
                    <ScoreBar value={summary.subscores.volatility} label="Volatility" />
                    <ScoreBar value={summary.subscores.volume} label="Volume" />
                    <ScoreBar value={summary.subscores.structure} label="Structure" />
                </div>
                {summary.strongest_module && (
                    <div className="flex items-center gap-3 mt-3 pt-3 border-t border-[#30363d]/50 text-[8px]">
                        <span className="text-gray-600">Strongest: <b className="text-green-400 uppercase">{summary.strongest_module}</b></span>
                        <span className="text-gray-600">Weakest: <b className="text-red-400 uppercase">{summary.weakest_module}</b></span>
                        {summary.technical_confidence != null && (
                            <span className="text-gray-600 ml-auto font-mono">Confidence: <b className="text-gray-300">{(summary.technical_confidence * 100).toFixed(0)}%</b></span>
                        )}
                    </div>
                )}
            </div>

            {/* ── Evidence Trail ────────────────────────────────────────────────────── */}
            {summary.evidence && Object.values(summary.evidence).some((v: any) => Array.isArray(v) && v.length > 0) && (
                <div className="glass-card p-4 border-[#30363d]">
                    <p className="text-[9px] font-black uppercase tracking-widest text-gray-500 mb-3">Deterministic Evidence Trail</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
                        {["trend", "momentum", "volatility", "volume", "structure"].map((mod) => {
                            const ev = (summary.evidence?.[mod] || []) as string[];
                            if (!ev.length) return null;
                            return (
                                <div key={mod} className="p-2.5 rounded-lg bg-[#161b22] border border-[#30363d]">
                                    <p className="text-[8px] font-black uppercase tracking-widest text-gray-500 mb-1.5">{mod}</p>
                                    <ul className="space-y-0.5">
                                        {ev.map((e, i) => (
                                            <li key={i} className="text-[8px] text-gray-400 flex items-start gap-1">
                                                <span className="text-[#d4af37] mt-0.5">▸</span>
                                                <span>{e}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* ── 5 module cards ───────────────────────────────────────────────────── */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
                <TrendCard data={data} />
                <MomentumCard data={data} />
                <VolatilityCard data={data} />
                <VolumeCard data={data} />
                <StructureCard data={data} />
            </div>

            {/* ── MTF Heatmap ────────────────────────────────────────────────────── */}
            {data.mtf?.timeframe_scores && (
                <div className="glass-card p-4 border-[#30363d]">
                    <div className="flex items-center justify-between mb-3">
                        <p className="text-[9px] font-black uppercase tracking-widest text-gray-500">
                            Multi-Timeframe Analysis
                        </p>
                        <div className="flex items-center gap-2">
                            <span className={`text-[8px] font-black px-2 py-0.5 rounded border uppercase ${data.mtf.agreement_level === "STRONG" ? "bg-green-500/10 border-green-500/30 text-green-400" :
                                    data.mtf.agreement_level === "MODERATE" ? "bg-yellow-500/10 border-yellow-500/30 text-yellow-400" :
                                        "bg-red-500/10 border-red-500/30 text-red-400"
                                }`}>
                                {data.mtf.agreement_level} ({data.mtf.agreement_count}/4)
                            </span>
                            <span className={`text-sm font-black ${signalColor(data.mtf.mtf_signal)}`}>
                                {data.mtf.mtf_aggregate.toFixed(1)}
                            </span>
                        </div>
                    </div>
                    <div className="grid grid-cols-4 gap-2">
                        {(data.mtf.timeframe_scores as any[]).map((tf: any) => {
                            const bg = tf.score >= 7 ? "bg-green-500/15 border-green-500/30" :
                                tf.score >= 5 ? "bg-yellow-500/10 border-yellow-500/25" :
                                    "bg-red-500/10 border-red-500/25";
                            return (
                                <div key={tf.timeframe} className={`rounded-lg border p-3 text-center ${bg}`}>
                                    <p className="text-[8px] font-black uppercase tracking-wider text-gray-400 mb-1">
                                        {tf.timeframe}
                                    </p>
                                    <p className={`text-xl font-black ${tf.score >= 7 ? "text-green-400" : tf.score >= 5 ? "text-yellow-400" : "text-red-400"
                                        }`}>
                                        {tf.score.toFixed(1)}
                                    </p>
                                    <div className="flex justify-center gap-1 mt-1">
                                        <span className={`text-[6px] font-bold uppercase ${statusColor(tf.trend)}`}>
                                            {tf.trend?.replace(/_/g, " ")}
                                        </span>
                                    </div>
                                    <p className="text-[7px] text-gray-600 mt-0.5">{tf.signal?.replace("_", " ")}</p>
                                </div>
                            );
                        })}
                    </div>
                    {data.mtf.bonus_applied !== 0 && (
                        <p className="text-[7px] text-gray-600 mt-2 text-right">
                            Agreement adjustment: <b className={`${data.mtf.bonus_applied > 0 ? "text-green-500" : "text-red-500"}`}>
                                {data.mtf.bonus_applied > 0 ? "+" : ""}{data.mtf.bonus_applied}
                            </b>
                        </p>
                    )}
                </div>
            )}

            {/* ── Technical Analyst Memo (LLM Interpretation) ───────────────────── */}
            {technicalMemo && (() => {
                const signalBadge = (sig: string) => {
                    const s = sig.toUpperCase();
                    if (s === "BULLISH") return "bg-green-500/15 border-green-500/30 text-green-400";
                    if (s === "BEARISH") return "bg-red-500/15 border-red-500/30 text-red-400";
                    return "bg-gray-500/10 border-gray-500/30 text-gray-400";
                };
                const convictionDot = (c: string) => {
                    const v = c.toUpperCase();
                    if (v === "HIGH") return "text-green-400";
                    if (v === "MEDIUM") return "text-yellow-400";
                    return "text-gray-500";
                };

                const OPINIONS = [
                    { key: "trend" as const, label: "Tendencia", icon: <TrendingUp size={11} />, color: "text-blue-400" },
                    { key: "momentum" as const, label: "Momentum", icon: <Activity size={11} />, color: "text-green-400" },
                    { key: "volatility" as const, label: "Volatilidad", icon: <Zap size={11} />, color: "text-yellow-400" },
                    { key: "volume" as const, label: "Volumen", icon: <BarChart3 size={11} />, color: "text-blue-300" },
                    { key: "structure" as const, label: "Estructura", icon: <Layers size={11} />, color: "text-orange-400" },
                ];

                return (
                    <div className="glass-card p-5 border-[#30363d]" style={{ animation: "fadeSlideIn 0.5s ease both" }}>
                        {/* Header */}
                        <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-2">
                                <Brain size={16} className="text-purple-400" />
                                <p className="text-[10px] font-black uppercase tracking-widest text-gray-400">
                                    Technical Analyst
                                    <span className="text-gray-700 font-normal ml-1">(AI Committee)</span>
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
                            <p className="text-[11px] text-gray-300 leading-relaxed">{technicalMemo.consensus}</p>
                        </div>

                        {/* TradingView Cross-Validation */}
                        {technicalMemo.tradingview_comparison && (
                            <div className="mb-5 p-3 rounded-lg bg-[#131722]/80 border border-[#2962ff]/20 flex items-start gap-2.5">
                                <span className="text-[10px] font-black text-[#2962ff] whitespace-nowrap mt-0.5">TV</span>
                                <p className="text-[10px] text-gray-400 leading-relaxed">{technicalMemo.tradingview_comparison}</p>
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
                                        <p className="text-[9px] text-gray-400 leading-relaxed flex-1">{op.narrative}</p>
                                        {op.key_data.length > 0 && (
                                            <div className="flex flex-wrap gap-1 mt-auto pt-1 border-t border-[#30363d]/50">
                                                {op.key_data.map((d, i) => (
                                                    <span key={i} className="text-[7px] bg-[#21262d] text-gray-500 px-1.5 py-0.5 rounded font-mono">
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
                                <p className="text-[10px] text-gray-400 leading-relaxed">{technicalMemo.key_levels}</p>
                            </div>
                            <div className="p-3 rounded-lg bg-[#161b22] border border-[#30363d]">
                                <div className="flex items-center gap-1.5 mb-1.5">
                                    <Clock size={10} className="text-emerald-400" />
                                    <span className="text-[8px] font-black uppercase tracking-widest text-emerald-400">Timing</span>
                                </div>
                                <p className="text-[10px] text-gray-400 leading-relaxed">{technicalMemo.timing}</p>
                            </div>
                        </div>

                        {/* Risk Factors */}
                        {technicalMemo.risk_factors.length > 0 && (
                            <div className="p-3 rounded-lg bg-red-500/5 border border-red-500/15">
                                <div className="flex items-center gap-1.5 mb-2">
                                    <AlertTriangle size={10} className="text-red-400" />
                                    <span className="text-[8px] font-black uppercase tracking-widest text-red-400">Riesgos Técnicos</span>
                                </div>
                                <ul className="space-y-1">
                                    {technicalMemo.risk_factors.map((risk, i) => (
                                        <li key={i} className="text-[10px] text-gray-500 flex items-start gap-1.5">
                                            <span className="text-red-500 mt-0.5">▸</span>
                                            <span>{risk}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </div>
                );
            })()}

            {/* ── Footer meta ──────────────────────────────────────────────────────── */}
            <div className="flex items-center justify-between text-[8px] text-gray-700 px-1">
                <span>
                    Source: <b className="text-gray-500">yfinance + tradingview-ta</b>
                </span>
                <span>
                    {data.from_cache ? "⚡ Cached" : "Live"} ·{" "}
                    {data.processing_time_ms != null ? `${data.processing_time_ms}ms` : "—"} ·{" "}
                    {new Date(data.timestamp).toLocaleTimeString()}
                </span>
            </div>
        </div>
    );
}
