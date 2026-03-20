"use client";

import React, { useState, useMemo } from "react";
import { BarChart3, Loader2, Play, TrendingUp, TrendingDown, Target, Zap, ChevronDown, ChevronRight, CheckCircle2, ChevronUp, Activity } from "lucide-react";
import { useBacktest } from "@/hooks/useBacktest";
import type { BacktestResult, BacktestTrade } from "@/hooks/useBacktest";
import ResearchMemoInsight from "./ResearchMemoInsight";
import type { MemoInsight } from "./ResearchMemoInsight";

interface UnifiedBacktestDashboardProps {
    ticker: string;
}

// ── Backtest Metric Definitions ─────────────────────────────────────────────

const BACKTEST_DEFS = [
    {
        metric: "Walk-Forward Evaluation",
        definition: "Recorre cada barra histórica y evalúa si la señal habría disparado en ese punto. Luego mide el retorno forward real a T+1, 5, 10, 20, 60 días. Usa cooldown (50% de la ventana) para evitar overlap de señales.",
    },
    {
        metric: "Win Rate",
        definition: "Porcentaje de señales que generaron retorno positivo en la ventana forward. Win Rate >55% con N>30 se considera estadísticamente significativo. >60% es excelente.",
    },
    {
        metric: "Sharpe Ratio",
        definition: "Retorno promedio / desviación estándar, anualizado. Mide el retorno ajustado por riesgo. Sharpe >1.0 = bueno, >2.0 = excelente. Se calcula por ventana (T+5, T+20, etc.).",
    },
    {
        metric: "Sortino Ratio",
        definition: "Similar al Sharpe pero solo penaliza la volatilidad a la baja (downside deviation). Más relevante que Sharpe cuando la distribución de retornos es asimétrica.",
    },
    {
        metric: "Alpha Decay Curve",
        definition: "Retorno excedente promedio para cada día 1..60 post-señal. Muestra cómo pierde poder predictivo la señal con el tiempo. El half-life es cuando el alpha cae al 50% del pico.",
    },
    {
        metric: "Profit Factor",
        definition: "Suma de ganancias / suma de pérdidas (en valor absoluto). PF >1.5 indica edge real. PF <1.0 = la señal destruye valor.",
    },
    {
        metric: "Excess Return (vs SPY)",
        definition: "Retorno de la señal menos el retorno del benchmark (SPY) en el mismo período. Excess positivo = la señal genera alpha sobre el mercado. Es la métrica más importante.",
    },
    {
        metric: "Calibration Suggestions",
        definition: "Sugerencias automáticas para ajustar thresholds, pesos, o half-life de señales basadas en evidencia del backtest. Generadas por el report_builder.",
    },
];

// ── Backtest Analyst Depth Component ────────────────────────────────────────

function BacktestAnalystDepth() {
    const [expanded, setExpanded] = useState(false);

    return (
        <div className="mt-4 pt-3 border-t border-[#30363d]/50">
            <button
                className="w-full flex items-center justify-between text-left group cursor-pointer"
                onClick={() => setExpanded(!expanded)}
                aria-expanded={expanded}
            >
                <span className="text-[9px] text-[#8b949e] font-bold uppercase tracking-widest group-hover:text-[#d4af37] transition-colors flex items-center gap-1.5">
                    <Activity size={10} /> Analyst Depth
                </span>
                <div className="flex items-center justify-center group-hover:bg-[#161b22] rounded p-0.5 transition-colors">
                    {expanded ? <ChevronUp size={12} className="text-[#d4af37]" /> : <ChevronDown size={12} className="text-[#8b949e] group-hover:text-[#d4af37]" />}
                </div>
            </button>

            {expanded && (
                <div className="mt-3 space-y-3 pt-3 border-t border-[#30363d]/30" style={{ animation: "fadeSlideIn 0.2s ease" }}>
                    <div className="bg-[#161b22] p-3 rounded-lg border border-[#30363d]/50">
                        <p className="text-[10px] text-[#c9d1d9] leading-relaxed font-serif italic border-l-2 border-[#d4af37]/40 pl-2">
                            "El Backtest Engine evalúa retrospectivamente si las señales Alpha habrían generado retorno real. Usa walk-forward evaluation con cooldown para evitar sesgo, y mide excess returns vs SPY."
                        </p>
                    </div>

                    <div>
                        <p className="text-[8px] text-[#d4af37] font-bold uppercase tracking-widest mb-2 flex items-center gap-1.5">
                            <Zap size={10} /> Métricas Explicadas
                        </p>
                        <div className="flex flex-col gap-2">
                            {BACKTEST_DEFS.map((d, idx) => (
                                <div key={idx} className="bg-[#0d1117] p-3 rounded border border-[#30363d]">
                                    <p className="text-[10px] font-black text-[#c9d1d9] mb-1 font-mono">{d.metric}</p>
                                    <p className="text-[9px] text-[#8b949e] leading-relaxed">{d.definition}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

function buildBacktestMemo(results: BacktestResult[], ticker: string): MemoInsight | null {
    if (results.length === 0) return null;

    const n = (v: unknown): number => (typeof v === "number" && !isNaN(v) ? v : 0);

    const avgWinRate = results.reduce((s, r) => s + n(r.win_rate), 0) / results.length;
    const avgReturn = results.reduce((s, r) => s + n(r.avg_return), 0) / results.length;
    const avgSharpe = results.reduce((s, r) => s + n(r.sharpe_ratio), 0) / results.length;
    const avgExcess = results.reduce((s, r) => s + n(r.excess_return), 0) / results.length;
    const totalSignals = results.reduce((s, r) => s + n(r.total_signals), 0);

    // Compute proper Profit Factor: sum(positive returns) / abs(sum(negative returns))
    const returns = results.map(r => n(r.avg_return));
    const totalGains = returns.filter(r => r > 0).reduce((s, r) => s + r, 0);
    const totalLosses = Math.abs(returns.filter(r => r < 0).reduce((s, r) => s + r, 0));
    const avgPF = totalLosses > 0 ? +(totalGains / totalLosses).toFixed(2) : (totalGains > 0 ? 999 : 0);

    const best = results.reduce((a, b) => n(a.avg_return) > n(b.avg_return) ? a : b);
    const worst = results.reduce((a, b) => n(a.avg_return) < n(b.avg_return) ? a : b);

    // Signal is BULLISH only if excess return vs SPY is positive
    const signal: MemoInsight["signal"] =
        avgWinRate >= 55 && avgExcess > 0 ? "BULLISH" :
        avgWinRate < 45 || avgExcess < -1 ? "BEARISH" : "NEUTRAL";
    const conviction: MemoInsight["conviction"] =
        totalSignals >= 10 && avgSharpe >= 0.5 ? "HIGH" :
        totalSignals >= 5 ? "MEDIUM" : "LOW";

    const narrative =
        `Backtest empírico sobre ${results.length} vectores atómicos con ${totalSignals} señales conjuntas evaluadas (ventana T+20). ` +
        `Win Rate ponderado: ${avgWinRate.toFixed(1)}%. ` +
        `Retorno promedio T+20: ${avgReturn >= 0 ? "+" : ""}${avgReturn.toFixed(2)}%. ` +
        `Excess Return vs SPY: ${avgExcess >= 0 ? "+" : ""}${avgExcess.toFixed(2)}%. ` +
        `Sharpe: ${avgSharpe.toFixed(2)}. PF: ${avgPF.toFixed(2)}.`;

    const bullets: string[] = [];
    bullets.push(`Alpha vs SPY (T+20): ${avgExcess >= 0 ? "+" : ""}${avgExcess.toFixed(2)}%`);
    bullets.push(`Vector líder: ${best.ticker || best.signal_id} (retorno ${n(best.avg_return) >= 0 ? "+" : ""}${n(best.avg_return).toFixed(2)}%)`);
    if (worst !== best) {
        bullets.push(`Módulo drag: ${worst.ticker || worst.signal_id} (retorno ${n(worst.avg_return) >= 0 ? "+" : ""}${n(worst.avg_return).toFixed(2)}%)`);
    }
    bullets.push(`Profit Factor: ${avgPF.toFixed(2)} (wins/losses ratio)`);

    const risks: string[] = [];
    if (totalSignals < 5) risks.push(`Validación estadística en riesgo: N-size = ${totalSignals} observaciones`);
    if (avgWinRate < 50) risks.push(`Sin Edge Estadístico: Win Rate ${avgWinRate.toFixed(1)}% < 50%`);
    if (avgSharpe < 0) risks.push(`Sharpe Negativo (${avgSharpe.toFixed(2)}): el sistema destruye valor ajustado por riesgo`);
    if (avgExcess < 0) risks.push(`Alpha Negativo vs SPY: las señales no superan al benchmark`);

    return { title: "Research Memo — Empirical Backtest", signal, conviction, narrative, bullets, risks };
}

export default function UnifiedBacktestDashboard({ ticker }: UnifiedBacktestDashboardProps) {
    const { results, status, error, run, backtestMemo: llmMemo } = useBacktest();
    const [period, setPeriod] = useState("2y");

    const handleRun = () => {
        if (ticker) run(ticker, { period });
    };

    const backtestMemo = useMemo(() => {
        if (llmMemo) {
            return {
                title: "Research Memo — Empirical Backtest",
                signal: (llmMemo.signal as "BULLISH" | "BEARISH" | "NEUTRAL") || "NEUTRAL",
                conviction: (llmMemo.conviction as "HIGH" | "MEDIUM" | "LOW") || "LOW",
                narrative: llmMemo.narrative,
                bullets: llmMemo.key_data || [],
                risks: llmMemo.risk_factors || [],
            };
        }
        return buildBacktestMemo(results, ticker);
    }, [llmMemo, results, ticker]);

    // Aggregate Calculations
    const n = (v: unknown): number => (typeof v === "number" && !isNaN(v) ? v : 0);
    const avgWinRate = results.length > 0 ? results.reduce((s, r) => s + n(r.win_rate), 0) / results.length : 0;
    const avgReturn = results.length > 0 ? results.reduce((s, r) => s + n(r.avg_return), 0) / results.length : 0;
    const avgSharpe = results.length > 0 ? results.reduce((s, r) => s + n(r.sharpe_ratio), 0) / results.length : 0;
    const totalSignals = results.reduce((s, r) => s + n(r.total_signals), 0);

    return (
        <div className="space-y-4" style={{ animation: "fadeSlideIn 0.4s ease both" }}>
            
            {/* 1. TOP ROW: Aggregate Logic Flow & Control Strip */}
            <div className="glass-card border border-[#30363d] relative overflow-hidden">
                <div className="absolute top-0 right-0 w-32 h-32 bg-[#d4af37]/5 blur-2xl rounded-full" />
                <div className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-6">
                    {/* Aggregate Flow */}
                    <div className="flex items-center gap-6 z-10 w-full md:w-auto">
                        <div className="flex flex-col gap-1">
                            <span className="text-[9px] font-black uppercase tracking-widest text-gray-500 mb-1 flex items-center gap-1.5"><Target size={10} className="text-[#d4af37]" /> Total Observations</span>
                            <p className="text-2xl font-black font-mono text-white leading-none">{totalSignals}</p>
                        </div>
                        
                        <div className="w-px h-10 bg-[#30363d] hidden sm:block" />
                        
                        <div className="flex flex-col gap-1">
                            <span className="text-[9px] font-black uppercase tracking-widest text-gray-500 mb-1">Blended Win Rate</span>
                            <p className={`text-xl font-black font-mono leading-none ${avgWinRate >= 50 ? "text-green-400" : "text-gray-400"}`}>
                                {avgWinRate.toFixed(1)}%
                            </p>
                        </div>

                        <div className="w-px h-10 bg-[#30363d] hidden sm:block" />

                        <div className="flex flex-col gap-1">
                            <span className="text-[9px] font-black uppercase tracking-widest text-gray-500 mb-1">Blended Sharpe</span>
                            <p className={`text-xl font-black font-mono leading-none ${avgSharpe >= 1 ? "text-blue-400" : avgSharpe > 0 ? "text-gray-300" : "text-gray-500"}`}>
                                {avgSharpe.toFixed(2)}
                            </p>
                        </div>
                    </div>

                    {/* Engine Controls */}
                    <div className="flex items-center gap-3 z-10 w-full md:w-auto mt-4 md:mt-0 pt-4 md:pt-0 border-t md:border-t-0 border-[#30363d]">
                        <div className="flex items-center gap-2 flex-1 md:flex-auto">
                            <span className="text-[9px] font-black uppercase tracking-widest text-gray-500 hidden sm:block">Timeframe</span>
                            <select
                                value={period}
                                onChange={(e) => setPeriod(e.target.value)}
                                className="bg-[#161b22] border border-[#30363d] rounded-lg text-[10px] uppercase font-bold tracking-wider px-3 py-2 text-gray-300 focus:outline-none focus:border-[#d4af37]/40 w-full sm:w-auto transition-colors"
                            >
                                <option value="6m">6 Months</option>
                                <option value="1y">1 Year</option>
                                <option value="2y">2 Years (Def)</option>
                                <option value="3y">3 Years</option>
                            </select>
                        </div>
                        
                        <button
                            onClick={handleRun}
                            disabled={status === "running" || !ticker}
                            className="flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg text-[10px] font-black uppercase tracking-wider bg-[#d4af37] text-black hover:bg-[#e8c84a] border border-transparent hover:shadow-[0_0_15px_rgba(212,175,55,0.3)] transition-all disabled:opacity-50 disabled:hover:shadow-none min-w-[130px]"
                        >
                            {status === "running" ? <Loader2 size={11} className="animate-spin" /> : <Play size={11} fill="currentColor" />}
                            Execute Engine
                        </button>
                    </div>
                </div>

                {/* Analyst Depth — full width below the flow row */}
                <div className="px-5 pb-5">
                    <BacktestAnalystDepth />
                </div>
            </div>

            {/* Error State */}
            {error && (
                <div className="p-4 bg-red-500/5 border border-red-500/20 rounded-xl flex items-center gap-3">
                    <Zap size={14} className="text-red-400 shrink-0" />
                    <p className="text-red-400 font-mono text-xs">{error}</p>
                </div>
            )}

            {/* Running Overlay Concept (or inline status) */}
            {status === "running" && results.length === 0 && (
                <div className="glass-card border border-[#30363d] p-12 flex flex-col items-center justify-center gap-4 text-[#d4af37]">
                    <Loader2 size={24} className="animate-spin" />
                    <span className="text-[10px] font-black uppercase tracking-widest">Executing Backtest Simulation for {ticker}…</span>
                </div>
            )}

            {/* Empty state */}
            {status === "idle" && results.length === 0 && (
                <div className="glass-card border border-[#30363d] flex flex-col items-center justify-center py-20 text-center">
                    <div className="w-12 h-12 rounded-full border border-[#30363d] flex items-center justify-center bg-[#161b22] mb-4">
                        <BarChart3 size={18} className="text-gray-600" />
                    </div>
                    <p className="text-[11px] font-black uppercase tracking-widest text-gray-500">Awaiting Simulation</p>
                    <p className="text-[10px] text-gray-600 mt-2 font-mono">Select a timeframe and execute the backtesting engine.</p>
                </div>
            )}

            {/* 2 & 3. MIDDLE GRID & AUDIT LOGS (Strategy Cards) */}
            {results.length > 0 && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {results.map((result, idx) => (
                        <StrategyPerformanceCard key={idx} result={result} />
                    ))}
                </div>
            )}

            {/* 4. BOTTOM ZONE: Research Memo Insight */}
            {backtestMemo && results.length > 0 && status !== "running" && (
                <div className="pt-2">
                    <ResearchMemoInsight memo={backtestMemo} />
                </div>
            )}
        </div>
    );
}

// ─── Subcomponents ─────────────────────────────────────────────────────────────

function StrategyPerformanceCard({ result }: { result: BacktestResult }) {
    const [showTrades, setShowTrades] = useState(false);

    const n = (v: unknown): number => (typeof v === "number" && !isNaN(v) ? v : 0);
    const wr = n(result.win_rate);
    const ar = n(result.avg_return);
    const sr = n(result.sharpe_ratio);
    const pf = n(result.profit_factor);

    const winColor = wr >= 60 ? "text-green-400" : wr >= 40 ? "text-yellow-400" : "text-gray-400";
    const barColor = wr >= 60 ? "bg-green-500" : wr >= 40 ? "bg-yellow-500" : "bg-gray-500";
    const returnColor = ar > 0 ? "text-green-400" : ar < 0 ? "text-red-400" : "text-gray-400";

    return (
        <div className="glass-card border-[#30363d] overflow-hidden flex flex-col">
            <div className="p-4 border-b border-[#30363d]">
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                        <CheckCircle2 size={12} className="text-blue-400" />
                        <h4 className="text-[11px] font-black uppercase tracking-widest text-gray-200 truncate pr-2">
                            {result.ticker || "STRATEGY"}
                        </h4>
                        {result.signal_id && (
                            <span className="text-[8px] font-mono font-bold text-gray-400 bg-[#161b22] border border-[#30363d] px-1.5 py-0.5 rounded uppercase">
                                {result.signal_id.replace(/^alpha_/i, "")}
                            </span>
                        )}
                    </div>
                    <span className="text-[9px] font-black uppercase tracking-widest text-[#d4af37] bg-[#d4af37]/10 px-2 py-0.5 rounded border border-[#d4af37]/20 shrink-0">
                        N: {n(result.total_signals)}
                    </span>
                </div>

                <div className="grid grid-cols-4 gap-2">
                    {/* Win Rate */}
                    <div className="bg-[#161b22]/50 rounded-lg p-2.5 border border-[#30363d] flex flex-col justify-between">
                        <p className="text-[8px] font-black uppercase tracking-widest text-gray-500 mb-1">Win Rate</p>
                        <p className={`text-base font-black font-mono leading-none ${winColor}`}>{wr.toFixed(1)}%</p>
                        <div className="w-full bg-[#0d1117] rounded-full h-0.5 mt-2 overflow-hidden">
                            <div className={`h-full rounded-full ${barColor}`} style={{ width: `${wr}%` }} />
                        </div>
                    </div>
                    {/* Avg Return */}
                    <div className="bg-[#161b22]/50 rounded-lg p-2.5 border border-[#30363d] flex flex-col justify-between">
                        <p className="text-[8px] font-black uppercase tracking-widest text-gray-500 mb-1">Avg Ret</p>
                        <p className={`text-base font-black font-mono leading-none ${returnColor}`}>
                            {ar > 0 ? "+" : ""}{ar.toFixed(2)}%
                        </p>
                        <p className="text-[7px] font-black uppercase tracking-widest text-gray-600 mt-2 truncate">Per Trade</p>
                    </div>
                    {/* Sharpe */}
                    <div className="bg-[#161b22]/50 rounded-lg p-2.5 border border-[#30363d] flex flex-col justify-between">
                        <p className="text-[8px] font-black uppercase tracking-widest text-gray-500 mb-1">Sharpe</p>
                        <p className="text-base font-black font-mono leading-none text-blue-400">{sr.toFixed(2)}</p>
                        <p className="text-[7px] font-black uppercase tracking-widest text-gray-600 mt-2 truncate">Ratio</p>
                    </div>
                    {/* Profit Factor */}
                    <div className="bg-[#161b22]/50 rounded-lg p-2.5 border border-[#30363d] flex flex-col justify-between">
                        <p className="text-[8px] font-black uppercase tracking-widest text-gray-500 mb-1">P.Factor</p>
                        <p className="text-base font-black font-mono leading-none text-purple-400">{pf.toFixed(2)}</p>
                        <p className="text-[7px] font-black uppercase tracking-widest text-gray-600 mt-2 truncate">Gross</p>
                    </div>
                </div>
            </div>

            {/* Trade History Toggle */}
            {result.trades && result.trades.length > 0 && (
                <button
                    onClick={() => setShowTrades(!showTrades)}
                    className="w-full flex items-center justify-between px-4 py-2 hover:bg-white/[0.02] transition-colors bg-[#0d1117]/30"
                >
                    <span className="text-[9px] font-black uppercase tracking-widest text-gray-500 group-hover:text-gray-300 transition-colors">
                        Institutional Trade Log ({result.trades.length})
                    </span>
                    {showTrades ? <ChevronDown size={12} className="text-gray-600" /> : <ChevronRight size={12} className="text-gray-600" />}
                </button>
            )}

            {/* Institutional Trade Log (Audit Style) */}
            {showTrades && result.trades && (
                <div className="bg-[#0d1117]/80 flex flex-col max-h-[250px] overflow-y-auto custom-scrollbar border-t border-[#30363d]">
                    {/* Header Row */}
                    <div className="flex items-center px-4 py-2 border-b border-[#30363d] bg-[#161b22]/50 sticky top-0 z-10">
                        <div className="w-[100px] text-[8px] font-black uppercase tracking-widest text-gray-500">Entry/Exit</div>
                        <div className="flex-1 min-w-0" />
                        <div className="w-[60px] text-right text-[8px] font-black uppercase tracking-widest text-gray-500">Days</div>
                        <div className="w-[70px] text-right text-[8px] font-black uppercase tracking-widest text-gray-500">Return</div>
                    </div>
                    {/* Rows */}
                    <div className="divide-y divide-[#30363d]/50">
                        {result.trades.map((trade, i) => (
                            <TradeTraceRow key={i} trade={trade} />
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

function TradeTraceRow({ trade }: { trade: BacktestTrade }) {
    const isPositive = trade.return_pct >= 0;
    const isStrong = trade.signal_strength === "strong";
    
    return (
        <div className="flex items-center px-4 py-2.5 hover:bg-white/[0.02] transition-colors group">
            {/* Dates (Entry/Exit Matrix) */}
            <div className="w-[110px] flex flex-col gap-0.5 shrink-0">
                <div className="flex items-center gap-1.5 opacity-60 group-hover:opacity-100 transition-opacity">
                    <TrendingUp size={8} className="text-blue-400" />
                    <span className="text-[9px] font-mono text-gray-400">{trade.entry_date}</span>
                </div>
                <div className="flex items-center gap-1.5 opacity-60 group-hover:opacity-100 transition-opacity">
                    <TrendingDown size={8} className="text-orange-400" />
                    <span className="text-[9px] font-mono text-gray-500">{trade.exit_date}</span>
                </div>
            </div>

            {/* Spacer */}
            <div className="flex-1 min-w-0 flex items-center justify-start pl-2">
                {trade.signal_strength && (
                    <span className={`text-[7px] font-black uppercase tracking-widest px-1.5 py-0.5 rounded border ${isStrong ? "text-green-400 bg-green-500/10 border-green-500/20" : "text-gray-500 bg-gray-500/10 border-gray-500/20"}`}>
                        {trade.signal_strength}
                    </span>
                )}
            </div>

            {/* Hold Days */}
            <div className="w-[50px] shrink-0 text-right">
                <span className="text-[10px] font-mono text-gray-500">{trade.holding_days}d</span>
            </div>

            {/* Return */}
            <div className="w-[70px] shrink-0 flex justify-end">
                <span className={`text-[11px] font-mono font-bold flex items-center justify-end gap-1 px-2 py-0.5 rounded ${isPositive ? "text-green-400 bg-green-500/5" : "text-red-400 bg-red-500/5"}`}>
                    {isPositive ? "+" : ""}{trade.return_pct.toFixed(2)}%
                </span>
            </div>
        </div>
    );
}
