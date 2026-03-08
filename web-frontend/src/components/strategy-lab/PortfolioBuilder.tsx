"use client";

/**
 * PortfolioBuilder.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Multi-strategy portfolio construction — weight editor, correlation matrix,
 * risk attribution, simulation, and Brinson attribution.
 */

import { useState, useCallback, useMemo } from "react";
import {
    ArrowLeft,
    Play,
    Plus,
    Trash2,
    Loader2,
    Briefcase,
    BarChart3,
    PieChart,
    Activity,
    Shield,
    TrendingUp,
    AlertTriangle,
    RefreshCw,
    Check,
    Scale,
} from "lucide-react";

// ── Types ──────────────────────────────────────────────────────────────────

interface StrategyOption {
    strategy_id: string;
    name: string;
    category: string;
    config?: Record<string, unknown>;
}

interface PortfolioEntry {
    strategy_id: string;
    name: string;
    weight: number; // 0-1
}

interface SimulationResult {
    portfolio_metrics: Record<string, number>;
    strategy_contributions: Array<{ name: string; return_contribution: number; risk_contribution: number }>;
    correlation_matrix: Record<string, Record<string, number>>;
    attribution: {
        allocation_effect: number;
        selection_effect: number;
        interaction_effect: number;
        sector_attribution: Record<string, { portfolio_weight: number; benchmark_weight: number; total_contribution: number }>;
    };
}

interface PortfolioBuilderProps {
    strategies: StrategyOption[];
    onBack: () => void;
}

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const STRATEGY_COLORS = [
    "#d4af37", "#3b82f6", "#22c55e", "#ef4444", "#a855f7",
    "#f97316", "#06b6d4", "#ec4899",
];

const ALLOCATION_METHODS = [
    { value: "equal", label: "Equal Weight" },
    { value: "risk_parity", label: "Risk Parity" },
    { value: "max_sharpe", label: "Max Sharpe" },
    { value: "min_variance", label: "Min Variance" },
    { value: "custom", label: "Custom" },
];

// ── Weight Editor ──────────────────────────────────────────────────────────

function WeightEditor({
    entries, onUpdate, onRemove,
}: {
    entries: PortfolioEntry[];
    onUpdate: (idx: number, weight: number) => void;
    onRemove: (idx: number) => void;
}) {
    const totalWeight = entries.reduce((s, e) => s + e.weight, 0);
    const isValid = Math.abs(totalWeight - 1) < 0.01;

    return (
        <div className="space-y-2">
            {entries.map((entry, i) => (
                <div key={entry.strategy_id} className="flex items-center gap-3 p-3 rounded-xl bg-[#161b22] border border-[#30363d]">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: STRATEGY_COLORS[i % STRATEGY_COLORS.length] }} />
                    <span className="text-xs font-bold text-gray-300 flex-1 truncate">{entry.name}</span>
                    <input
                        type="range" min={0} max={100} step={1}
                        value={Math.round(entry.weight * 100)}
                        onChange={(e) => onUpdate(i, parseInt(e.target.value) / 100)}
                        className="w-24 accent-[#d4af37] h-1"
                    />
                    <span className="text-xs font-mono text-[#d4af37] w-12 text-right">
                        {(entry.weight * 100).toFixed(0)}%
                    </span>
                    <button onClick={() => onRemove(i)} className="p-1 text-gray-600 hover:text-red-400 transition-colors">
                        <Trash2 size={12} />
                    </button>
                </div>
            ))}

            {/* Total bar */}
            <div className="flex items-center gap-2 px-3 py-2 rounded-xl border border-[#30363d]/50">
                <Scale size={12} className={isValid ? "text-green-400" : "text-yellow-400"} />
                <span className="text-[10px] text-gray-500 flex-1">Total Weight</span>
                <div className="w-24 bg-[#1a1a2e] rounded-full h-2 overflow-hidden">
                    <div
                        className={`h-full rounded-full transition-all ${isValid ? "bg-green-500" : totalWeight > 1 ? "bg-red-500" : "bg-yellow-500"}`}
                        style={{ width: `${Math.min(totalWeight * 100, 100)}%` }}
                    />
                </div>
                <span className={`text-xs font-mono w-12 text-right ${isValid ? "text-green-400" : "text-yellow-400"}`}>
                    {(totalWeight * 100).toFixed(0)}%
                </span>
            </div>
        </div>
    );
}

// ── Pie Chart (CSS) ────────────────────────────────────────────────────────

function AllocationPie({ entries }: { entries: PortfolioEntry[] }) {
    const total = entries.reduce((s, e) => s + e.weight, 0) || 1;
    let cumulative = 0;

    const gradientStops = entries.map((e, i) => {
        const start = (cumulative / total) * 360;
        cumulative += e.weight;
        const end = (cumulative / total) * 360;
        return `${STRATEGY_COLORS[i % STRATEGY_COLORS.length]} ${start}deg ${end}deg`;
    });

    return (
        <div className="glass-card border-[#30363d] rounded-2xl p-4">
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-3 flex items-center gap-1">
                <PieChart size={11} /> Allocation
            </h4>
            <div className="flex items-center gap-4">
                <div
                    className="w-20 h-20 rounded-full shrink-0"
                    style={{
                        background: entries.length > 0
                            ? `conic-gradient(${gradientStops.join(", ")})`
                            : "#30363d",
                    }}
                />
                <div className="space-y-1 flex-1">
                    {entries.map((e, i) => (
                        <div key={e.strategy_id} className="flex items-center gap-2 text-[10px]">
                            <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: STRATEGY_COLORS[i % STRATEGY_COLORS.length] }} />
                            <span className="text-gray-400 truncate flex-1">{e.name}</span>
                            <span className="font-mono text-gray-300">{(e.weight * 100).toFixed(0)}%</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}

// ── Correlation Matrix ─────────────────────────────────────────────────────

function CorrelationMatrix({ matrix, names }: { matrix: Record<string, Record<string, number>>; names: string[] }) {
    const corrColor = (v: number) => {
        if (v >= 0.7) return "text-red-400 bg-red-400/10";
        if (v >= 0.3) return "text-orange-400 bg-orange-400/10";
        if (v >= -0.3) return "text-gray-400 bg-gray-700/30";
        return "text-green-400 bg-green-400/10";
    };

    return (
        <div className="glass-card border-[#30363d] rounded-2xl p-4 overflow-x-auto">
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-3 flex items-center gap-1">
                <Activity size={11} /> Strategy Correlation
            </h4>
            <table className="w-full text-[10px]">
                <thead>
                    <tr>
                        <th className="text-left py-1 px-2 text-gray-600"></th>
                        {names.map((n, i) => (
                            <th key={n} className="py-1 px-2 font-bold text-center" style={{ color: STRATEGY_COLORS[i % STRATEGY_COLORS.length] }}>
                                {n.slice(0, 8)}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {names.map((row, ri) => (
                        <tr key={row}>
                            <td className="py-1 px-2 font-bold" style={{ color: STRATEGY_COLORS[ri % STRATEGY_COLORS.length] }}>
                                {row.slice(0, 8)}
                            </td>
                            {names.map((col) => {
                                const val = matrix[row]?.[col] ?? 0;
                                return (
                                    <td key={col} className={`py-1 px-2 text-center font-mono rounded ${corrColor(val)}`}>
                                        {val.toFixed(2)}
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

// ── Risk Attribution ───────────────────────────────────────────────────────

function RiskAttribution({ contributions }: {
    contributions: Array<{ name: string; return_contribution: number; risk_contribution: number }>;
}) {
    return (
        <div className="glass-card border-[#30363d] rounded-2xl p-4">
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-3 flex items-center gap-1">
                <Shield size={11} /> Risk & Return Contribution
            </h4>
            <div className="space-y-2">
                {contributions.map((c, i) => (
                    <div key={c.name} className="space-y-1">
                        <div className="flex items-center gap-2 text-[10px]">
                            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: STRATEGY_COLORS[i % STRATEGY_COLORS.length] }} />
                            <span className="text-gray-300 font-bold flex-1">{c.name}</span>
                        </div>
                        <div className="grid grid-cols-2 gap-2 pl-4">
                            <div className="flex items-center gap-1">
                                <span className="text-[9px] text-gray-500 w-12">Return</span>
                                <div className="flex-1 bg-[#1a1a2e] rounded-full h-1.5 overflow-hidden">
                                    <div className="h-full bg-green-500 rounded-full" style={{ width: `${Math.abs(c.return_contribution) * 100}%` }} />
                                </div>
                                <span className={`text-[9px] font-mono w-12 text-right ${c.return_contribution >= 0 ? "text-green-400" : "text-red-400"}`}>
                                    {(c.return_contribution * 100).toFixed(1)}%
                                </span>
                            </div>
                            <div className="flex items-center gap-1">
                                <span className="text-[9px] text-gray-500 w-12">Risk</span>
                                <div className="flex-1 bg-[#1a1a2e] rounded-full h-1.5 overflow-hidden">
                                    <div className="h-full bg-orange-500 rounded-full" style={{ width: `${Math.abs(c.risk_contribution) * 100}%` }} />
                                </div>
                                <span className="text-[9px] font-mono text-orange-400 w-12 text-right">
                                    {(c.risk_contribution * 100).toFixed(1)}%
                                </span>
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

// ── Brinson Attribution Panel ──────────────────────────────────────────────

function BrinsonAttribution({ attribution }: { attribution: SimulationResult["attribution"] }) {
    const effects = [
        { label: "Allocation", value: attribution.allocation_effect, color: "text-blue-400" },
        { label: "Selection", value: attribution.selection_effect, color: "text-green-400" },
        { label: "Interaction", value: attribution.interaction_effect, color: "text-purple-400" },
    ];

    return (
        <div className="glass-card border-[#30363d] rounded-2xl p-4">
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-3 flex items-center gap-1">
                <BarChart3 size={11} /> Brinson Attribution
            </h4>
            <div className="grid grid-cols-3 gap-3 mb-4">
                {effects.map((e) => (
                    <div key={e.label} className="bg-[#161b22] rounded-xl p-3 text-center">
                        <p className="text-[9px] text-gray-500 mb-1">{e.label}</p>
                        <p className={`text-lg font-black font-mono ${e.color}`}>
                            {(e.value * 100).toFixed(1)}%
                        </p>
                    </div>
                ))}
            </div>
            {/* Sector breakdown */}
            {Object.keys(attribution.sector_attribution ?? {}).length > 0 && (
                <div className="space-y-1">
                    <p className="text-[9px] text-gray-500 font-bold uppercase">By Sector</p>
                    {Object.entries(attribution.sector_attribution).map(([sector, data]) => (
                        <div key={sector} className="flex items-center gap-2 text-[10px]">
                            <span className="text-gray-400 w-20 truncate capitalize">{sector}</span>
                            <div className="flex-1 bg-[#1a1a2e] rounded-full h-1.5 overflow-hidden">
                                <div
                                    className={`h-full rounded-full ${data.total_contribution >= 0 ? "bg-green-500" : "bg-red-500"}`}
                                    style={{ width: `${Math.min(Math.abs(data.total_contribution) * 1000, 100)}%` }}
                                />
                            </div>
                            <span className={`font-mono w-14 text-right ${data.total_contribution >= 0 ? "text-green-400" : "text-red-400"}`}>
                                {(data.total_contribution * 100).toFixed(2)}%
                            </span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

// ── Portfolio Metrics Summary ──────────────────────────────────────────────

function PortfolioMetrics({ metrics }: { metrics: Record<string, number> }) {
    const items = [
        { key: "portfolio_return", label: "Return", format: "pct" },
        { key: "portfolio_sharpe", label: "Sharpe", format: "dec" },
        { key: "portfolio_volatility", label: "Volatility", format: "pct" },
        { key: "portfolio_max_drawdown", label: "Max DD", format: "pct" },
        { key: "diversification_ratio", label: "Diversification", format: "dec" },
    ];

    return (
        <div className="grid grid-cols-5 gap-2">
            {items.map((item) => {
                const val = metrics[item.key] ?? metrics[item.key.replace("portfolio_", "")] ?? 0;
                const isPos = item.key.includes("drawdown") ? false : val > 0;
                return (
                    <div key={item.key} className="glass-card border-[#30363d] rounded-xl p-3 text-center">
                        <p className="text-[9px] font-bold uppercase tracking-widest text-gray-500 mb-1">{item.label}</p>
                        <p className={`text-lg font-black font-mono ${isPos ? "text-green-400" : item.key.includes("drawdown") ? "text-red-400" : "text-[#d4af37]"}`}>
                            {item.format === "pct" ? `${(val * 100).toFixed(1)}%` : val.toFixed(2)}
                        </p>
                    </div>
                );
            })}
        </div>
    );
}

// ── Main Component ─────────────────────────────────────────────────────────

export default function PortfolioBuilder({ strategies, onBack }: PortfolioBuilderProps) {
    const [entries, setEntries] = useState<PortfolioEntry[]>([]);
    const [method, setMethod] = useState("equal");
    const [result, setResult] = useState<SimulationResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const available = useMemo(
        () => strategies.filter((s) => !entries.some((e) => e.strategy_id === s.strategy_id)),
        [strategies, entries],
    );

    const addStrategy = useCallback((s: StrategyOption) => {
        setEntries((prev) => {
            const next = [...prev, { strategy_id: s.strategy_id, name: s.name, weight: 0 }];
            // Auto equal-weight on add
            const w = 1 / next.length;
            return next.map((e) => ({ ...e, weight: w }));
        });
    }, []);

    const removeEntry = useCallback((idx: number) => {
        setEntries((prev) => {
            const next = prev.filter((_, i) => i !== idx);
            if (next.length > 0) {
                const w = 1 / next.length;
                return next.map((e) => ({ ...e, weight: w }));
            }
            return next;
        });
    }, []);

    const updateWeight = useCallback((idx: number, weight: number) => {
        setEntries((prev) => prev.map((e, i) => i === idx ? { ...e, weight } : e));
    }, []);

    const applyMethod = useCallback(() => {
        if (entries.length === 0) return;
        if (method === "equal") {
            const w = 1 / entries.length;
            setEntries((prev) => prev.map((e) => ({ ...e, weight: w })));
        }
        // Other methods would require backend calculation
    }, [method, entries.length]);

    const runSimulation = useCallback(async () => {
        if (entries.length < 2) return;
        setLoading(true);
        setError(null);
        try {
            const portfolioConfig = {
                strategies: entries.map((e) => ({
                    strategy_id: e.strategy_id,
                    name: e.name,
                    weight: e.weight,
                    config: strategies.find((s) => s.strategy_id === e.strategy_id)?.config ?? {},
                })),
                allocation_method: method,
            };

            const res = await fetch(`${API}/lab/portfolio/simulate`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(portfolioConfig),
            });

            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            setResult({
                portfolio_metrics: data.portfolio_metrics ?? data.metrics ?? {},
                strategy_contributions: data.strategy_contributions ?? entries.map((e) => ({
                    name: e.name,
                    return_contribution: (data.metrics?.total_return ?? 0) * e.weight,
                    risk_contribution: e.weight,
                })),
                correlation_matrix: data.correlation_matrix ?? {},
                attribution: data.attribution ?? {
                    allocation_effect: 0, selection_effect: 0, interaction_effect: 0, sector_attribution: {},
                },
            });
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : "Simulation failed";
            setError(msg);
        } finally {
            setLoading(false);
        }
    }, [entries, method, strategies]);

    return (
        <div className="space-y-4">
            {/* ── Toolbar ── */}
            <div className="flex items-center justify-between">
                <button onClick={onBack} className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-[#d4af37] transition-colors">
                    <ArrowLeft size={14} /> Back to Lab
                </button>
                <div className="flex gap-2">
                    <select
                        value={method}
                        onChange={(e) => { setMethod(e.target.value); }}
                        className="bg-[#161b22] border border-[#30363d] rounded-xl px-3 py-2 text-xs text-gray-300 focus:outline-none focus:border-[#d4af37]"
                    >
                        {ALLOCATION_METHODS.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
                    </select>
                    <button onClick={applyMethod} className="px-3 py-2 rounded-xl text-xs border border-[#30363d] text-gray-400 hover:text-[#d4af37] hover:border-[#d4af37]/40 transition-all">
                        Apply
                    </button>
                    <button
                        onClick={runSimulation}
                        disabled={entries.length < 2 || loading}
                        className="flex items-center gap-1.5 bg-gradient-to-r from-[#d4af37] to-[#e8c84a] text-black font-bold px-4 py-2 rounded-xl text-xs hover:brightness-110 transition-all disabled:opacity-40"
                    >
                        {loading ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
                        Simulate
                    </button>
                </div>
            </div>

            {/* ── Strategy Selector + Weights ── */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                {/* Left: Available strategies */}
                <div className="glass-card border-[#30363d] rounded-2xl p-4">
                    <h4 className="text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-3 flex items-center gap-1">
                        <Plus size={11} /> Add Strategies
                    </h4>
                    {available.length === 0 ? (
                        <p className="text-[11px] text-gray-600">All strategies added.</p>
                    ) : (
                        <div className="space-y-1">
                            {available.map((s) => (
                                <button
                                    key={s.strategy_id}
                                    onClick={() => addStrategy(s)}
                                    className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-left text-gray-400 hover:text-[#d4af37] hover:bg-[#d4af37]/5 transition-all"
                                >
                                    <Plus size={10} /> {s.name}
                                    <span className="text-[8px] text-gray-600 capitalize ml-auto">{s.category?.replace("_", " ")}</span>
                                </button>
                            ))}
                        </div>
                    )}
                </div>

                {/* Center: Weight editor */}
                <div className="lg:col-span-2 glass-card border-[#30363d] rounded-2xl p-4">
                    <h4 className="text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-3 flex items-center gap-1">
                        <Briefcase size={11} /> Portfolio Weights
                    </h4>
                    {entries.length === 0 ? (
                        <p className="text-[11px] text-gray-600 py-4 text-center">Add strategies from the left panel.</p>
                    ) : (
                        <WeightEditor entries={entries} onUpdate={updateWeight} onRemove={removeEntry} />
                    )}
                </div>
            </div>

            {/* ── Allocation Pie ── */}
            {entries.length > 0 && <AllocationPie entries={entries} />}

            {/* ── Error ── */}
            {error && (
                <div className="glass-card border-red-900/50 rounded-xl px-4 py-2 text-red-400 text-xs flex items-center gap-2">
                    <AlertTriangle size={12} /> {error}
                    <button onClick={runSimulation} className="ml-auto text-[#d4af37] hover:underline flex items-center gap-1">
                        <RefreshCw size={10} /> Retry
                    </button>
                </div>
            )}

            {/* ── Loading ── */}
            {loading && (
                <div className="glass-card border-[#30363d] rounded-2xl p-8 text-center">
                    <Loader2 size={24} className="text-[#d4af37] animate-spin mx-auto mb-2" />
                    <p className="text-sm text-gray-400">Simulating portfolio…</p>
                </div>
            )}

            {/* ── Results ── */}
            {result && !loading && (
                <>
                    {/* Portfolio metrics */}
                    <PortfolioMetrics metrics={result.portfolio_metrics} />

                    {/* Contributions + Correlation */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        <RiskAttribution contributions={result.strategy_contributions} />
                        {Object.keys(result.correlation_matrix).length > 0 && (
                            <CorrelationMatrix
                                matrix={result.correlation_matrix}
                                names={entries.map((e) => e.name)}
                            />
                        )}
                    </div>

                    {/* Brinson Attribution */}
                    {(result.attribution.allocation_effect !== 0 ||
                        result.attribution.selection_effect !== 0) && (
                            <BrinsonAttribution attribution={result.attribution} />
                        )}
                </>
            )}
        </div>
    );
}
