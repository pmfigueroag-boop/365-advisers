"use client";

import { TrendingUp, Activity, Zap, BarChart3, Layers, AlertCircle } from "lucide-react";
import { TechnicalAnalysisResult, TechnicalSummary } from "@/hooks/useTechnicalAnalysis";
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
                <span className="text-[10px] font-mono text-gray-300">{value.toFixed(1)}</span>
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
                    <span className={`font-mono font-bold ${statusColor(t.price_vs_sma50)}`}>{t.price_vs_sma50}</span>
                </div>
                <div className="flex justify-between">
                    <span className="text-gray-600"><GlossaryTooltip term="SMA" label="SMA 200" /></span>
                    <span className={`font-mono font-bold ${statusColor(t.price_vs_sma200)}`}>{t.price_vs_sma200}</span>
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
                    <span className={`font-mono font-bold ${statusColor(m.rsi_zone)}`}>{m.rsi.toFixed(1)}</span>
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
                    <span className={`font-mono font-bold ${statusColor(m.stochastic_zone)}`}>{m.stochastic_k.toFixed(1)}</span>
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
                    <span className="font-mono text-gray-300">{v.bb_width.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                    <span className="text-gray-600"><GlossaryTooltip term="ATR" label="ATR" /></span>
                    <span className="font-mono text-gray-300">{v.atr.toFixed(2)} ({(v.atr_pct * 100).toFixed(1)}%)</span>
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
        </div>
    );
}

// ─── Main IndicatorGrid component ─────────────────────────────────────────────

interface IndicatorGridProps {
    data: TechnicalAnalysisResult;
}

export default function IndicatorGrid({ data }: IndicatorGridProps) {
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
                    </div>
                    <div className="flex gap-4 text-[9px] text-gray-600">
                        <span>Trend: <b className={statusColor(summary.trend_status)}>{summary.trend_status.replace(/_/g, " ")}</b></span>
                        <span>Momentum: <b className={statusColor(summary.momentum_status)}>{summary.momentum_status.replace(/_/g, " ")}</b></span>
                    </div>
                </div>
            </div>

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
            </div>

            {/* ── 5 module cards ───────────────────────────────────────────────────── */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
                <TrendCard data={data} />
                <MomentumCard data={data} />
                <VolatilityCard data={data} />
                <VolumeCard data={data} />
                <StructureCard data={data} />
            </div>

            {/* ── Footer meta ──────────────────────────────────────────────────────── */}
            <div className="flex items-center justify-between text-[8px] text-gray-700 px-1">
                <span>
                    TV Recommendation: <b className="text-gray-500">{data.tv_recommendation}</b>
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
