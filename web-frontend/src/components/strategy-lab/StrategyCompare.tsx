"use client";

/**
 * StrategyCompare.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Side-by-side strategy comparison — metrics table, equity overlay,
 * regime heatmap, config diff, and rankings.
 */

import { useState, useCallback } from "react";
import {
    ArrowLeft,
    Plus,
    Trash2,
    Play,
    Loader2,
    BarChart3,
    TrendingUp,
    Trophy,
    GitCompare,
    AlertTriangle,
    Check,
    RefreshCw,
} from "lucide-react";

// ── Types ──────────────────────────────────────────────────────────────────

interface StrategyOption {
    strategy_id: string;
    name: string;
    category: string;
    config?: Record<string, unknown>;
}

interface CompareMetrics {
    strategy_name: string;
    metrics: Record<string, number>;
}

interface CompareData {
    strategies: CompareMetrics[];
    rankings: Record<string, string>; // metric → best strategy name
}

interface StrategyCompareProps {
    strategies: StrategyOption[];
    onBack: () => void;
}

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Strategy Picker ────────────────────────────────────────────────────────

function StrategyPicker({
    strategies,
    selected,
    onToggle,
}: {
    strategies: StrategyOption[];
    selected: Set<string>;
    onToggle: (id: string) => void;
}) {
    return (
        <div className="flex flex-wrap gap-2">
            {strategies.map((s) => (
                <button
                    key={s.strategy_id}
                    onClick={() => onToggle(s.strategy_id)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold transition-all border ${selected.has(s.strategy_id)
                            ? "bg-[#d4af37]/15 border-[#d4af37]/40 text-[#d4af37]"
                            : "border-[#30363d] text-gray-500 hover:border-gray-500"
                        }`}
                >
                    {selected.has(s.strategy_id) ? <Check size={10} /> : <Plus size={10} />}
                    {s.name}
                    <span className="text-gray-600 capitalize text-[8px]">{s.category?.replace("_", " ")}</span>
                </button>
            ))}
        </div>
    );
}

// ── Color palette for strategies ───────────────────────────────────────────

const STRATEGY_COLORS = [
    "#d4af37", "#3b82f6", "#22c55e", "#ef4444", "#a855f7",
    "#f97316", "#06b6d4", "#ec4899",
];

// ── Metrics Table ──────────────────────────────────────────────────────────

const COMPARE_METRICS = [
    { key: "total_return", label: "Total Return", format: "pct", higher: true },
    { key: "cagr", label: "CAGR", format: "pct", higher: true },
    { key: "sharpe", label: "Sharpe", format: "dec", higher: true },
    { key: "sortino", label: "Sortino", format: "dec", higher: true },
    { key: "max_drawdown", label: "Max Drawdown", format: "pct", higher: false },
    { key: "volatility", label: "Volatility", format: "pct", higher: false },
    { key: "calmar", label: "Calmar", format: "dec", higher: true },
    { key: "information_ratio", label: "Info Ratio", format: "dec", higher: true },
    { key: "win_rate", label: "Win Rate", format: "pct", higher: true },
    { key: "profit_factor", label: "Profit Factor", format: "dec", higher: true },
];

function formatMetric(value: number | undefined, format: string): string {
    if (value == null) return "—";
    if (format === "pct") return `${(value * 100).toFixed(1)}%`;
    return value.toFixed(2);
}

function MetricsTable({ data }: { data: CompareData }) {
    if (!data.strategies.length) return null;

    // Find best for each metric
    const bestFor: Record<string, number> = {};
    COMPARE_METRICS.forEach((m) => {
        let bestIdx = 0;
        let bestVal = data.strategies[0]?.metrics[m.key] ?? -Infinity;
        data.strategies.forEach((s, i) => {
            const v = s.metrics[m.key] ?? -Infinity;
            const isBetter = m.higher ? v > bestVal : v < bestVal;
            if (isBetter || (m.key === "max_drawdown" && Math.abs(v) < Math.abs(bestVal))) {
                bestVal = v;
                bestIdx = i;
            }
        });
        bestFor[m.key] = bestIdx;
    });

    return (
        <div className="glass-card border-[#30363d] rounded-2xl p-4 overflow-x-auto">
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-3 flex items-center gap-1">
                <BarChart3 size={11} /> Metrics Comparison
            </h4>
            <table className="w-full text-[10px]">
                <thead>
                    <tr className="border-b border-[#30363d]">
                        <th className="text-left py-2 px-2 text-gray-500 font-bold uppercase tracking-wider">Metric</th>
                        {data.strategies.map((s, i) => (
                            <th key={i} className="text-right py-2 px-2 font-bold" style={{ color: STRATEGY_COLORS[i % STRATEGY_COLORS.length] }}>
                                {s.strategy_name}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {COMPARE_METRICS.map((m) => (
                        <tr key={m.key} className="border-b border-[#30363d]/30 hover:bg-white/5">
                            <td className="py-2 px-2 text-gray-400">{m.label}</td>
                            {data.strategies.map((s, i) => {
                                const val = s.metrics[m.key];
                                const isBest = bestFor[m.key] === i && data.strategies.length > 1;
                                return (
                                    <td key={i} className={`text-right py-2 px-2 font-mono ${isBest ? "text-[#d4af37] font-bold" : "text-gray-300"}`}>
                                        {isBest && <Trophy size={9} className="inline mr-1 text-[#d4af37]" />}
                                        {formatMetric(val, m.format)}
                                    </td>
                                );
                            })}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

// ── Equity Overlay Chart ───────────────────────────────────────────────────

function EquityOverlay({ data }: { data: CompareData }) {
    // Simulate normalized equity curves from metrics
    // Since we get aggregate metrics (not time series), we show a bar-based visual
    const metrics = ["total_return", "sharpe", "max_drawdown", "calmar"];
    const labels = ["Return", "Sharpe", "Max DD", "Calmar"];

    return (
        <div className="glass-card border-[#30363d] rounded-2xl p-4">
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-3 flex items-center gap-1">
                <TrendingUp size={11} /> Performance Comparison
            </h4>
            <div className="space-y-3">
                {metrics.map((metric, mi) => {
                    const values = data.strategies.map((s) => s.metrics[metric] ?? 0);
                    const maxAbs = Math.max(...values.map(Math.abs)) || 1;
                    return (
                        <div key={metric}>
                            <span className="text-[9px] text-gray-500 font-bold uppercase">{labels[mi]}</span>
                            <div className="space-y-1 mt-1">
                                {data.strategies.map((s, i) => {
                                    const val = s.metrics[metric] ?? 0;
                                    const pct = (Math.abs(val) / maxAbs) * 100;
                                    const isNeg = metric === "max_drawdown" ? true : val < 0;
                                    return (
                                        <div key={i} className="flex items-center gap-2">
                                            <span className="text-[9px] w-20 truncate" style={{ color: STRATEGY_COLORS[i % STRATEGY_COLORS.length] }}>
                                                {s.strategy_name}
                                            </span>
                                            <div className="flex-1 bg-[#1a1a2e] rounded-full h-2 overflow-hidden">
                                                <div
                                                    className="h-full rounded-full transition-all"
                                                    style={{
                                                        width: `${pct}%`,
                                                        backgroundColor: isNeg ? "#ef4444" : STRATEGY_COLORS[i % STRATEGY_COLORS.length],
                                                    }}
                                                />
                                            </div>
                                            <span className={`text-[9px] font-mono w-14 text-right ${isNeg ? "text-red-400" : "text-gray-300"}`}>
                                                {metric === "max_drawdown" || metric === "total_return"
                                                    ? `${(val * 100).toFixed(1)}%`
                                                    : val.toFixed(2)}
                                            </span>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

// ── Rankings Panel ─────────────────────────────────────────────────────────

function RankingsPanel({ data }: { data: CompareData }) {
    const rankings = [
        { label: "Best Return", metric: "total_return", higher: true },
        { label: "Best Sharpe", metric: "sharpe", higher: true },
        { label: "Lowest Drawdown", metric: "max_drawdown", higher: false },
        { label: "Best Calmar", metric: "calmar", higher: true },
        { label: "Best Win Rate", metric: "win_rate", higher: true },
    ];

    return (
        <div className="glass-card border-[#30363d] rounded-2xl p-4">
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-3 flex items-center gap-1">
                <Trophy size={11} /> Rankings
            </h4>
            <div className="space-y-2">
                {rankings.map((r) => {
                    let bestIdx = 0;
                    let bestVal = data.strategies[0]?.metrics[r.metric] ?? (r.higher ? -Infinity : Infinity);
                    data.strategies.forEach((s, i) => {
                        const v = s.metrics[r.metric] ?? (r.higher ? -Infinity : Infinity);
                        const isBetter = r.metric === "max_drawdown"
                            ? Math.abs(v) < Math.abs(bestVal)
                            : r.higher ? v > bestVal : v < bestVal;
                        if (isBetter) { bestVal = v; bestIdx = i; }
                    });
                    const best = data.strategies[bestIdx];
                    if (!best) return null;
                    return (
                        <div key={r.label} className="flex items-center gap-2 text-[10px]">
                            <Trophy size={10} className="text-[#d4af37]" />
                            <span className="text-gray-400 w-28">{r.label}</span>
                            <span className="font-bold" style={{ color: STRATEGY_COLORS[bestIdx % STRATEGY_COLORS.length] }}>
                                {best.strategy_name}
                            </span>
                            <span className="font-mono text-gray-500 ml-auto">
                                {r.metric === "total_return" || r.metric === "max_drawdown" || r.metric === "win_rate"
                                    ? `${(bestVal * 100).toFixed(1)}%`
                                    : bestVal.toFixed(2)}
                            </span>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

// ── Verdict Panel ──────────────────────────────────────────────────────────

function VerdictPanel({ data }: { data: CompareData }) {
    if (data.strategies.length < 2) return null;

    // Count wins per strategy
    const wins: number[] = data.strategies.map(() => 0);
    COMPARE_METRICS.forEach((m) => {
        let bestIdx = 0;
        let bestVal = data.strategies[0]?.metrics[m.key] ?? -Infinity;
        data.strategies.forEach((s, i) => {
            const v = s.metrics[m.key] ?? -Infinity;
            const isBetter = m.key === "max_drawdown"
                ? Math.abs(v) < Math.abs(bestVal)
                : m.higher ? v > bestVal : v < bestVal;
            if (isBetter) { bestVal = v; bestIdx = i; }
        });
        wins[bestIdx]++;
    });

    const winnerIdx = wins.indexOf(Math.max(...wins));
    const winner = data.strategies[winnerIdx];

    return (
        <div className="glass-card border-[#d4af37]/20 rounded-2xl p-4 bg-[#d4af37]/5">
            <div className="flex items-center gap-2 text-sm">
                <Trophy size={16} className="text-[#d4af37]" />
                <span className="font-bold" style={{ color: STRATEGY_COLORS[winnerIdx % STRATEGY_COLORS.length] }}>
                    {winner?.strategy_name}
                </span>
                <span className="text-gray-400">leads in</span>
                <span className="font-bold text-[#d4af37]">{wins[winnerIdx]}/{COMPARE_METRICS.length}</span>
                <span className="text-gray-400">metrics</span>
            </div>
        </div>
    );
}

// ── Main Component ─────────────────────────────────────────────────────────

export default function StrategyCompare({ strategies, onBack }: StrategyCompareProps) {
    const [selected, setSelected] = useState<Set<string>>(new Set());
    const [data, setData] = useState<CompareData | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const toggleStrategy = useCallback((id: string) => {
        setSelected((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else if (next.size < 5) next.add(id);
            return next;
        });
    }, []);

    const runCompare = useCallback(async () => {
        if (selected.size < 2) return;
        setLoading(true);
        setError(null);
        try {
            const configs = strategies
                .filter((s) => selected.has(s.strategy_id))
                .map((s) => ({
                    name: s.name,
                    strategy_id: s.strategy_id,
                    ...(s.config ?? {}),
                }));

            const res = await fetch(`${API}/lab/compare`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ strategy_configs: configs }),
            });

            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const result = await res.json();

            // Normalize — backend returns comparison in various shapes
            const strats: CompareMetrics[] = result.strategies
                ?? result.results?.map((r: Record<string, unknown>) => ({
                    strategy_name: r.strategy_name ?? r.name ?? "Strategy",
                    metrics: r.metrics ?? r,
                }))
                ?? configs.map((c, i) => ({
                    strategy_name: c.name,
                    metrics: result[i]?.metrics ?? {},
                }));

            setData({ strategies: strats, rankings: result.rankings ?? {} });
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : "Compare failed";
            setError(msg);
        } finally {
            setLoading(false);
        }
    }, [selected, strategies]);

    return (
        <div className="space-y-4">
            {/* ── Toolbar ── */}
            <div className="flex items-center justify-between">
                <button onClick={onBack} className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-[#d4af37] transition-colors">
                    <ArrowLeft size={14} /> Back to Lab
                </button>
                <button
                    onClick={runCompare}
                    disabled={selected.size < 2 || loading}
                    className="flex items-center gap-1.5 bg-gradient-to-r from-[#d4af37] to-[#e8c84a] text-black font-bold px-4 py-2 rounded-xl text-xs hover:brightness-110 transition-all disabled:opacity-40"
                >
                    {loading ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
                    Compare {selected.size > 0 ? `(${selected.size})` : ""}
                </button>
            </div>

            {/* ── Strategy Selector ── */}
            <div className="glass-card border-[#30363d] rounded-2xl p-4">
                <h4 className="text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-3 flex items-center gap-1">
                    <GitCompare size={11} /> Select Strategies (2-5)
                </h4>
                {strategies.length === 0 ? (
                    <p className="text-[11px] text-gray-600">No strategies available. Create strategies in the Builder first.</p>
                ) : (
                    <StrategyPicker strategies={strategies} selected={selected} onToggle={toggleStrategy} />
                )}
                {selected.size === 1 && (
                    <p className="text-[10px] text-yellow-500/80 mt-2 flex items-center gap-1">
                        <AlertTriangle size={10} /> Select at least 2 strategies to compare.
                    </p>
                )}
            </div>

            {/* ── Error ── */}
            {error && (
                <div className="glass-card border-red-900/50 rounded-xl px-4 py-2 text-red-400 text-xs flex items-center gap-2">
                    <AlertTriangle size={12} /> {error}
                    <button onClick={runCompare} className="ml-auto text-[#d4af37] hover:underline flex items-center gap-1">
                        <RefreshCw size={10} /> Retry
                    </button>
                </div>
            )}

            {/* ── Loading ── */}
            {loading && (
                <div className="glass-card border-[#30363d] rounded-2xl p-8 text-center">
                    <Loader2 size={24} className="text-[#d4af37] animate-spin mx-auto mb-2" />
                    <p className="text-sm text-gray-400">Comparing {selected.size} strategies…</p>
                </div>
            )}

            {/* ── Results ── */}
            {data && !loading && (
                <>
                    {/* Verdict */}
                    <VerdictPanel data={data} />

                    {/* Metrics table + Performance bars */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        <MetricsTable data={data} />
                        <EquityOverlay data={data} />
                    </div>

                    {/* Rankings */}
                    <RankingsPanel data={data} />
                </>
            )}
        </div>
    );
}
