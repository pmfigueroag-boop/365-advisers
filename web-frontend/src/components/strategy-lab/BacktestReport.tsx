"use client";

/**
 * BacktestReport.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Strategy Backtest Report — metrics, equity curve, drawdown, regime
 * performance, cost analysis, scorecard, and walk-forward panel.
 */

import { useState, useCallback, useEffect, useRef } from "react";
import {
    ArrowLeft,
    Play,
    TrendingUp,
    TrendingDown,
    BarChart3,
    Activity,
    AlertTriangle,
    Award,
    DollarSign,
    Loader2,
    ChevronDown,
    ChevronUp,
    RefreshCw,
    Target,
    Shield,
    Zap,
    Clock,
} from "lucide-react";

// ── Types ──────────────────────────────────────────────────────────────────

interface EquityCurvePoint {
    date: string;
    portfolio_value: number;
    benchmark_value?: number | null;
    drawdown: number;
    regime: string;
}

interface CostBreakdown {
    total_cost_usd: number;
    total_cost_bps: number;
    avg_cost_per_trade_bps: number;
    commission_total: number;
    spread_total: number;
    slippage_total: number;
    impact_total: number;
}

interface WalkForwardFold {
    fold: number;
    train_start: string;
    train_end: string;
    test_start: string;
    test_end: string;
    sharpe: number;
    return_pct: number;
    max_drawdown: number;
}

interface BacktestData {
    strategy_name?: string;
    metrics: Record<string, number>;
    equity_curve: EquityCurvePoint[];
    trades: Array<{ date: string; ticker: string; action: string; weight: number; cost_bps: number; reason: string }>;
    cost_breakdown: CostBreakdown;
    regime_analysis?: Record<string, { sharpe: number; return_pct: number; count: number }>;
    scorecard?: { score: number; grade: string; breakdown: Record<string, number> };
    walk_forward?: { folds: WalkForwardFold[]; verdict: string; stability: number };
}

interface BacktestReportProps {
    strategyId: string;
    onBack: () => void;
}

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Metric Card ────────────────────────────────────────────────────────────

function MetricCard({ label, value, suffix, positive, icon }: {
    label: string; value: string; suffix?: string; positive?: boolean | null; icon?: React.ReactNode;
}) {
    const color = positive === true ? "text-green-400" : positive === false ? "text-red-400" : "text-[#d4af37]";
    return (
        <div className="glass-card border-[#30363d] rounded-xl p-3 text-center">
            <div className="text-[9px] font-bold uppercase tracking-widest text-gray-500 mb-1 flex items-center justify-center gap-1">
                {icon}
                {label}
            </div>
            <div className={`text-lg font-black font-mono ${color}`}>
                {value}
                {suffix && <span className="text-[10px] text-gray-500 ml-0.5">{suffix}</span>}
            </div>
        </div>
    );
}

// ── Mini Equity Chart (CSS-based sparkline) ────────────────────────────────

function EquitySparkline({ points }: { points: EquityCurvePoint[] }) {
    if (!points.length) return null;
    const values = points.map((p) => p.portfolio_value);
    const benchValues = points.map((p) => p.benchmark_value ?? 0);
    const hasBench = benchValues.some((v) => v > 0);
    const allValues = [...values, ...(hasBench ? benchValues : [])];
    const min = Math.min(...allValues);
    const max = Math.max(...allValues);
    const range = max - min || 1;
    const height = 120;
    const width = 100;

    const toY = (v: number) => height - ((v - min) / range) * height;
    const pathD = values
        .map((v, i) => `${(i / (values.length - 1)) * width},${toY(v)}`)
        .join(" L ");
    const benchD = hasBench
        ? benchValues.map((v, i) => `${(i / (benchValues.length - 1)) * width},${toY(v)}`).join(" L ")
        : "";

    // Regime colors at bottom
    const regimeColors: Record<string, string> = {
        bull: "#22c55e", bear: "#ef4444", high_vol: "#f97316",
        low_vol: "#3b82f6", range: "#6b7280", unknown: "#374151",
    };

    return (
        <div className="glass-card border-[#30363d] rounded-2xl p-4">
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-2 flex items-center gap-1">
                <TrendingUp size={11} /> Equity Curve
            </h4>
            <div className="relative">
                <svg viewBox={`0 0 ${width} ${height + 8}`} className="w-full" style={{ height: "160px" }} preserveAspectRatio="none">
                    {/* Regime bars at bottom */}
                    {points.map((p, i) => (
                        <rect
                            key={i}
                            x={(i / (points.length - 1)) * width}
                            y={height}
                            width={width / points.length + 0.5}
                            height={8}
                            fill={regimeColors[p.regime] ?? regimeColors.unknown}
                            opacity={0.5}
                        />
                    ))}
                    {/* Benchmark line */}
                    {hasBench && (
                        <polyline
                            points={benchD}
                            fill="none" stroke="#6b7280" strokeWidth="0.6"
                            strokeDasharray="2,1" opacity={0.6}
                        />
                    )}
                    {/* Portfolio line */}
                    <polyline
                        points={`M ${pathD}`}
                        fill="none" stroke="#d4af37" strokeWidth="1"
                    />
                </svg>
                {/* Legend */}
                <div className="flex gap-3 mt-2 text-[9px] text-gray-500">
                    <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-[#d4af37] inline-block" /> Portfolio</span>
                    {hasBench && <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-gray-500 inline-block border-dashed" /> Benchmark</span>}
                </div>
            </div>
        </div>
    );
}

// ── Drawdown Chart ─────────────────────────────────────────────────────────

function DrawdownChart({ points }: { points: EquityCurvePoint[] }) {
    if (!points.length) return null;
    const drawdowns = points.map((p) => p.drawdown);
    const maxDD = Math.min(...drawdowns);
    const range = Math.abs(maxDD) || 0.01;
    const height = 60;
    const width = 100;

    const pathD = drawdowns
        .map((d, i) => `${(i / (drawdowns.length - 1)) * width},${height - (Math.abs(d) / range) * height}`)
        .join(" L ");

    return (
        <div className="glass-card border-[#30363d] rounded-2xl p-4">
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-2 flex items-center gap-1">
                <TrendingDown size={11} /> Drawdown
            </h4>
            <svg viewBox={`0 0 ${width} ${height}`} className="w-full" style={{ height: "80px" }} preserveAspectRatio="none">
                <polyline
                    points={`M ${pathD}`}
                    fill="none" stroke="#ef4444" strokeWidth="0.8" opacity={0.8}
                />
                <line x1="0" y1={height} x2={width} y2={height} stroke="#30363d" strokeWidth="0.3" />
            </svg>
            <div className="text-[10px] text-red-400 font-mono mt-1">
                Max: {(maxDD * 100).toFixed(1)}%
            </div>
        </div>
    );
}

// ── Regime Performance Table ───────────────────────────────────────────────

function RegimePerformance({ data }: { data: Record<string, { sharpe: number; return_pct: number; count: number }> }) {
    const regimeColors: Record<string, string> = {
        bull: "text-green-400", bear: "text-red-400", high_vol: "text-orange-400",
        low_vol: "text-blue-400", range: "text-gray-400",
    };

    return (
        <div className="glass-card border-[#30363d] rounded-2xl p-4">
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-3 flex items-center gap-1">
                <Activity size={11} /> Regime Performance
            </h4>
            <div className="space-y-2">
                {Object.entries(data).map(([regime, metrics]) => (
                    <div key={regime} className="flex items-center gap-3 text-xs">
                        <span className={`font-bold uppercase w-16 ${regimeColors[regime] ?? "text-gray-400"}`}>
                            {regime.replace("_", " ")}
                        </span>
                        <div className="flex-1">
                            <div className="flex items-center gap-2">
                                <div className="flex-1 bg-[#1a1a2e] rounded-full h-2 overflow-hidden">
                                    <div
                                        className={`h-full rounded-full ${metrics.sharpe > 0 ? "bg-green-500" : "bg-red-500"}`}
                                        style={{ width: `${Math.min(Math.abs(metrics.sharpe) / 3 * 100, 100)}%` }}
                                    />
                                </div>
                                <span className="font-mono text-[10px] text-gray-400 w-12 text-right">
                                    SR {metrics.sharpe.toFixed(2)}
                                </span>
                            </div>
                        </div>
                        <span className={`font-mono text-[10px] w-14 text-right ${metrics.return_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                            {metrics.return_pct >= 0 ? "+" : ""}{(metrics.return_pct * 100).toFixed(1)}%
                        </span>
                        <span className="font-mono text-[9px] text-gray-600 w-8">
                            n={metrics.count}
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
}

// ── Scorecard Gauge ────────────────────────────────────────────────────────

function ScorecardGauge({ score, grade, breakdown }: {
    score: number; grade: string; breakdown: Record<string, number>;
}) {
    const gradeColors: Record<string, string> = {
        "A+": "text-emerald-400", A: "text-green-400", "A-": "text-green-400",
        "B+": "text-lime-400", B: "text-yellow-400", "B-": "text-yellow-500",
        "C+": "text-orange-400", C: "text-orange-500", "C-": "text-red-400",
        D: "text-red-500", F: "text-red-600",
    };
    const angle = (score / 100) * 180;

    return (
        <div className="glass-card border-[#30363d] rounded-2xl p-4 text-center">
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-3 flex items-center justify-center gap-1">
                <Award size={11} /> Scorecard
            </h4>
            {/* Gauge arc */}
            <div className="relative w-32 h-16 mx-auto mb-2 overflow-hidden">
                <svg viewBox="0 0 100 50" className="w-full">
                    <path d="M 5 50 A 45 45 0 0 1 95 50" fill="none" stroke="#30363d" strokeWidth="6" strokeLinecap="round" />
                    <path
                        d="M 5 50 A 45 45 0 0 1 95 50" fill="none" stroke="#d4af37" strokeWidth="6" strokeLinecap="round"
                        strokeDasharray={`${(angle / 180) * 141.3} 141.3`}
                    />
                </svg>
                <div className="absolute inset-0 flex items-end justify-center pb-0">
                    <span className={`text-2xl font-black ${gradeColors[grade] ?? "text-gray-300"}`}>{grade}</span>
                </div>
            </div>
            <p className="text-lg font-mono font-bold text-[#d4af37]">{score.toFixed(0)}<span className="text-[10px] text-gray-500">/100</span></p>

            {/* Breakdown */}
            {Object.keys(breakdown).length > 0 && (
                <div className="mt-3 space-y-1 text-left">
                    {Object.entries(breakdown).map(([key, val]) => (
                        <div key={key} className="flex items-center gap-2 text-[10px]">
                            <span className="text-gray-500 w-24 truncate capitalize">{key.replace(/_/g, " ")}</span>
                            <div className="flex-1 bg-[#1a1a2e] rounded-full h-1.5 overflow-hidden">
                                <div className="h-full bg-[#d4af37] rounded-full" style={{ width: `${val}%` }} />
                            </div>
                            <span className="font-mono text-gray-400 w-8 text-right">{val}</span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

// ── Cost Analysis ──────────────────────────────────────────────────────────

function CostAnalysis({ costs }: { costs: CostBreakdown }) {
    const rows = [
        { label: "Commission", value: costs.commission_total, icon: <DollarSign size={10} /> },
        { label: "Spread", value: costs.spread_total, icon: <BarChart3 size={10} /> },
        { label: "Slippage", value: costs.slippage_total, icon: <AlertTriangle size={10} /> },
        { label: "Market Impact", value: costs.impact_total, icon: <Activity size={10} /> },
    ];

    return (
        <div className="glass-card border-[#30363d] rounded-2xl p-4">
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-3 flex items-center gap-1">
                <DollarSign size={11} /> Cost Analysis
            </h4>
            <div className="grid grid-cols-2 gap-2 mb-3">
                <div className="bg-[#161b22] rounded-xl p-2 text-center">
                    <p className="text-[9px] text-gray-500">Total Cost</p>
                    <p className="text-sm font-mono font-bold text-orange-400">{costs.total_cost_bps.toFixed(1)} bps</p>
                </div>
                <div className="bg-[#161b22] rounded-xl p-2 text-center">
                    <p className="text-[9px] text-gray-500">Avg Per Trade</p>
                    <p className="text-sm font-mono font-bold text-gray-300">{costs.avg_cost_per_trade_bps.toFixed(1)} bps</p>
                </div>
            </div>
            <div className="space-y-1.5">
                {rows.map((r) => (
                    <div key={r.label} className="flex items-center gap-2 text-[10px]">
                        <span className="text-gray-600">{r.icon}</span>
                        <span className="text-gray-400 flex-1">{r.label}</span>
                        <span className="font-mono text-gray-300">${r.value.toFixed(0)}</span>
                    </div>
                ))}
            </div>
        </div>
    );
}

// ── Walk-Forward Panel ─────────────────────────────────────────────────────

function WalkForwardPanel({ data }: { data: { folds: WalkForwardFold[]; verdict: string; stability: number } }) {
    const [expanded, setExpanded] = useState(false);

    const verdictColors: Record<string, string> = {
        pass: "text-green-400", marginal: "text-yellow-400", fail: "text-red-400",
    };

    return (
        <div className="glass-card border-[#30363d] rounded-2xl p-4">
            <button
                onClick={() => setExpanded(!expanded)}
                className="w-full flex items-center justify-between text-[10px] font-bold uppercase tracking-widest text-gray-500"
            >
                <span className="flex items-center gap-1"><Shield size={11} /> Walk-Forward Validation</span>
                <div className="flex items-center gap-2">
                    <span className={`text-xs font-black ${verdictColors[data.verdict] ?? "text-gray-400"}`}>
                        {data.verdict.toUpperCase()}
                    </span>
                    <span className="text-[10px] font-mono text-gray-500">
                        Stability: {(data.stability * 100).toFixed(0)}%
                    </span>
                    {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                </div>
            </button>
            {expanded && (
                <div className="mt-3 space-y-1">
                    <div className="grid grid-cols-6 text-[9px] text-gray-500 font-bold uppercase tracking-wider px-2 pb-1 border-b border-[#30363d]">
                        <span>Fold</span><span>Train</span><span>Test</span><span className="text-right">Sharpe</span><span className="text-right">Return</span><span className="text-right">MaxDD</span>
                    </div>
                    {data.folds.map((f) => (
                        <div key={f.fold} className="grid grid-cols-6 text-[10px] px-2 py-1 rounded-lg hover:bg-white/5">
                            <span className="font-mono text-gray-400">#{f.fold}</span>
                            <span className="text-gray-500">{f.train_start.slice(0, 7)}</span>
                            <span className="text-gray-500">{f.test_start.slice(0, 7)}</span>
                            <span className={`text-right font-mono ${f.sharpe > 0 ? "text-green-400" : "text-red-400"}`}>
                                {f.sharpe.toFixed(2)}
                            </span>
                            <span className={`text-right font-mono ${f.return_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                                {(f.return_pct * 100).toFixed(1)}%
                            </span>
                            <span className="text-right font-mono text-red-400">
                                {(f.max_drawdown * 100).toFixed(1)}%
                            </span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

// ── Trades Table ───────────────────────────────────────────────────────────

function TradesTable({ trades }: { trades: BacktestData["trades"] }) {
    const [showAll, setShowAll] = useState(false);
    const visible = showAll ? trades : trades.slice(0, 10);

    return (
        <div className="glass-card border-[#30363d] rounded-2xl p-4">
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-3 flex items-center gap-1">
                <Zap size={11} /> Trade Activity
                <span className="text-gray-600 font-mono ml-1">({trades.length} trades)</span>
            </h4>
            <div className="space-y-1">
                <div className="grid grid-cols-6 text-[9px] text-gray-500 font-bold uppercase tracking-wider px-2 pb-1 border-b border-[#30363d]">
                    <span>Date</span><span>Ticker</span><span>Action</span><span className="text-right">Weight</span><span className="text-right">Cost</span><span>Reason</span>
                </div>
                {visible.map((t, i) => (
                    <div key={i} className="grid grid-cols-6 text-[10px] px-2 py-1 rounded-lg hover:bg-white/5">
                        <span className="font-mono text-gray-500">{t.date.slice(0, 10)}</span>
                        <span className="font-bold text-gray-300">{t.ticker}</span>
                        <span className={t.action === "buy" ? "text-green-400" : "text-red-400"}>{t.action}</span>
                        <span className="text-right font-mono text-gray-400">{(t.weight * 100).toFixed(1)}%</span>
                        <span className="text-right font-mono text-orange-400">{t.cost_bps.toFixed(1)}bp</span>
                        <span className="text-gray-600 truncate">{t.reason}</span>
                    </div>
                ))}
            </div>
            {trades.length > 10 && (
                <button onClick={() => setShowAll(!showAll)} className="mt-2 text-[10px] text-[#d4af37] hover:underline">
                    {showAll ? "Show less" : `Show all ${trades.length} trades`}
                </button>
            )}
        </div>
    );
}

// ── Main Component ─────────────────────────────────────────────────────────

export default function BacktestReport({ strategyId, onBack }: BacktestReportProps) {
    const [data, setData] = useState<BacktestData | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const ranRef = useRef(false);

    const runBacktest = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`${API}/lab/research`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    strategy_id: strategyId,
                    mode: "backtest",
                    run_backtest: true,
                    initial_capital: 1_000_000,
                }),
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const result = await res.json();

            // Normalize the response — the backend may nest differently
            const bt = result.backtest ?? result;
            setData({
                strategy_name: result.strategy_name ?? bt.strategy_name ?? "Strategy",
                metrics: bt.metrics ?? {},
                equity_curve: bt.equity_curve ?? [],
                trades: bt.trades ?? [],
                cost_breakdown: bt.cost_breakdown ?? { total_cost_usd: 0, total_cost_bps: 0, avg_cost_per_trade_bps: 0, commission_total: 0, spread_total: 0, slippage_total: 0, impact_total: 0 },
                regime_analysis: bt.regime_analysis ?? undefined,
                scorecard: bt.scorecard ?? undefined,
                walk_forward: bt.walk_forward ?? undefined,
            });
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : "Backtest failed";
            setError(msg);
        } finally {
            setLoading(false);
        }
    }, [strategyId]);

    useEffect(() => {
        if (!ranRef.current && strategyId) {
            ranRef.current = true;
            runBacktest();
        }
    }, [strategyId, runBacktest]);

    // ── Loading state ───────────────────────────────────────────────────
    if (loading) {
        return (
            <div className="space-y-4">
                <button onClick={onBack} className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-[#d4af37] transition-colors">
                    <ArrowLeft size={14} /> Back to Lab
                </button>
                <div className="glass-card border-[#30363d] rounded-2xl p-12 text-center">
                    <Loader2 size={32} className="text-[#d4af37] animate-spin mx-auto mb-3" />
                    <p className="text-sm text-gray-400 font-bold">Running Backtest…</p>
                    <p className="text-[11px] text-gray-600 mt-1">Signal replay → Entry/Exit → Sizing → Portfolio → Costs → Metrics → Regime → Benchmark</p>
                </div>
            </div>
        );
    }

    // ── Error state ─────────────────────────────────────────────────────
    if (error) {
        return (
            <div className="space-y-4">
                <button onClick={onBack} className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-[#d4af37] transition-colors">
                    <ArrowLeft size={14} /> Back to Lab
                </button>
                <div className="glass-card border-red-900/50 rounded-2xl p-8 text-center">
                    <AlertTriangle size={32} className="text-red-400 mx-auto mb-3" />
                    <p className="text-sm text-red-400 font-bold mb-1">Backtest Failed</p>
                    <p className="text-[11px] text-gray-500">{error}</p>
                    <button onClick={runBacktest} className="mt-4 flex items-center gap-1.5 mx-auto px-4 py-2 rounded-xl text-xs border border-[#d4af37]/40 text-[#d4af37] hover:bg-[#d4af37]/10 transition-all">
                        <RefreshCw size={12} /> Retry
                    </button>
                </div>
            </div>
        );
    }

    if (!data) return null;

    // ── Extract metrics ─────────────────────────────────────────────────
    const m = data.metrics;
    const totalReturn = m.total_return ?? m.return ?? 0;
    const cagr = m.cagr ?? m.annualized_return ?? 0;
    const sharpe = m.sharpe ?? m.sharpe_ratio ?? 0;
    const sortino = m.sortino ?? m.sortino_ratio ?? 0;
    const maxDD = m.max_drawdown ?? m.max_dd ?? 0;
    const calmar = m.calmar ?? 0;
    const ir = m.information_ratio ?? 0;
    const winRate = m.win_rate ?? 0;
    const profitFactor = m.profit_factor ?? 0;
    const volatility = m.volatility ?? m.annual_volatility ?? 0;

    return (
        <div className="space-y-4">
            {/* ── Toolbar ── */}
            <div className="flex items-center justify-between">
                <button onClick={onBack} className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-[#d4af37] transition-colors">
                    <ArrowLeft size={14} /> Back to Lab
                </button>
                <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500">{data.strategy_name}</span>
                    <button onClick={runBacktest} className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[10px] border border-[#30363d] text-gray-400 hover:text-[#d4af37] hover:border-[#d4af37]/40 transition-all">
                        <Play size={10} /> Re-run
                    </button>
                </div>
            </div>

            {/* ── Summary Metrics ── */}
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-2">
                <MetricCard label="Total Return" value={`${(totalReturn * 100).toFixed(1)}%`} positive={totalReturn > 0} icon={<TrendingUp size={9} />} />
                <MetricCard label="CAGR" value={`${(cagr * 100).toFixed(1)}%`} positive={cagr > 0} icon={<Target size={9} />} />
                <MetricCard label="Sharpe" value={sharpe.toFixed(2)} positive={sharpe > 0.5 ? true : sharpe < 0 ? false : null} icon={<BarChart3 size={9} />} />
                <MetricCard label="Sortino" value={sortino.toFixed(2)} positive={sortino > 0.5 ? true : sortino < 0 ? false : null} icon={<Shield size={9} />} />
                <MetricCard label="Max DD" value={`${(maxDD * 100).toFixed(1)}%`} positive={false} icon={<TrendingDown size={9} />} />
                <MetricCard label="Volatility" value={`${(volatility * 100).toFixed(1)}%`} positive={null} icon={<Activity size={9} />} />
                <MetricCard label="Calmar" value={calmar.toFixed(2)} positive={calmar > 1 ? true : null} />
                <MetricCard label="Info Ratio" value={ir.toFixed(2)} positive={ir > 0 ? true : ir < 0 ? false : null} />
                <MetricCard label="Win Rate" value={`${(winRate * 100).toFixed(0)}%`} positive={winRate > 0.5 ? true : null} icon={<Zap size={9} />} />
                <MetricCard label="Profit Factor" value={profitFactor.toFixed(2)} positive={profitFactor > 1 ? true : profitFactor < 1 ? false : null} icon={<DollarSign size={9} />} />
            </div>

            {/* ── Charts Row ── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <EquitySparkline points={data.equity_curve} />
                <DrawdownChart points={data.equity_curve} />
            </div>

            {/* ── Regime + Scorecard + Costs ── */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                {data.regime_analysis && <RegimePerformance data={data.regime_analysis} />}
                {data.scorecard && (
                    <ScorecardGauge
                        score={data.scorecard.score}
                        grade={data.scorecard.grade}
                        breakdown={data.scorecard.breakdown}
                    />
                )}
                <CostAnalysis costs={data.cost_breakdown} />
            </div>

            {/* ── Walk-Forward ── */}
            {data.walk_forward && <WalkForwardPanel data={data.walk_forward} />}

            {/* ── Trades ── */}
            {data.trades.length > 0 && <TradesTable trades={data.trades} />}
        </div>
    );
}
