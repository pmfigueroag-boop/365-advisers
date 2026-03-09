"use client";

import { useMemo } from "react";
import {
    Rocket,
    Play,
    SkipForward,
    RefreshCw,
    Activity,
    TrendingUp,
    TrendingDown,
    AlertTriangle,
    CheckCircle,
    Clock,
    BarChart3,
    Zap,
    Shield,
    Target,
    ArrowUp,
    ArrowDown,
    Briefcase,
} from "lucide-react";
import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    Tooltip,
    ResponsiveContainer,
    CartesianGrid,
} from "recharts";
import { usePilot } from "@/hooks/usePilot";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const fmt = (n: number, decimals = 1) => n.toFixed(decimals);
const fmtPct = (n: number) => (n >= 0 ? `+${(n * 100).toFixed(2)}%` : `${(n * 100).toFixed(2)}%`);
const fmtUSD = (n: number) => `$${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;

const phaseLabel: Record<string, string> = {
    setup: "Setup",
    observation: "Observation",
    paper_trading: "Paper Trading",
    evaluation: "Evaluation",
    completed: "Completed",
};

const phaseColor: Record<string, string> = {
    setup: "text-blue-400",
    observation: "text-yellow-400",
    paper_trading: "text-green-400",
    evaluation: "text-purple-400",
    completed: "text-gray-400",
};

const severityIcon: Record<string, React.ReactNode> = {
    info: <Activity className="w-3.5 h-3.5 text-blue-400" />,
    warning: <AlertTriangle className="w-3.5 h-3.5 text-yellow-400" />,
    critical: <Shield className="w-3.5 h-3.5 text-red-400" />,
};

const severityBg: Record<string, string> = {
    info: "border-blue-500/30 bg-blue-500/5",
    warning: "border-yellow-500/30 bg-yellow-500/5",
    critical: "border-red-500/30 bg-red-500/10",
};

const CHART_COLORS: Record<string, { stroke: string; fill: string }> = {
    research: { stroke: "#d4af37", fill: "rgba(212,175,55,0.15)" },
    strategy: { stroke: "#4ade80", fill: "rgba(74,222,128,0.12)" },
    benchmark: { stroke: "#60a5fa", fill: "rgba(96,165,250,0.12)" },
};

// ─── Component ────────────────────────────────────────────────────────────────

export default function PilotDashboardView() {
    const pilot = usePilot();

    // ── No pilot state ────────────────────────────────────────────────────
    if (pilot.status === "no_pilot" || (!pilot.dashboard && pilot.status !== "loading")) {
        return (
            <div className="flex flex-col items-center justify-center py-24 space-y-6">
                <div className="ambient-glow">
                    <div className="premium-card p-10 text-center space-y-5">
                        <Rocket className="w-16 h-16 mx-auto text-[var(--gold)]" style={{ filter: "drop-shadow(0 0 20px rgba(212,175,55,0.5))" }} />
                        <h2 className="text-2xl font-bold text-white">Pilot Command Center</h2>
                        <p className="text-[var(--text-secondary)] max-w-md">
                            Initialize a new pilot deployment to validate the system with 3 portfolios:
                            Research, Strategy, and Benchmark.
                        </p>
                        <div className="flex gap-3 justify-center">
                            <div className="glass-card px-4 py-2 text-sm">
                                <span className="text-[var(--gold)]">12</span> <span className="text-[var(--text-secondary)]">weeks</span>
                            </div>
                            <div className="glass-card px-4 py-2 text-sm">
                                <span className="text-[var(--gold)]">3</span> <span className="text-[var(--text-secondary)]">portfolios</span>
                            </div>
                            <div className="glass-card px-4 py-2 text-sm">
                                <span className="text-[var(--gold)]">$1M</span> <span className="text-[var(--text-secondary)]">paper</span>
                            </div>
                        </div>
                        <button
                            onClick={pilot.initializePilot}
                            className="px-6 py-3 rounded-lg font-semibold text-black"
                            style={{ background: "linear-gradient(135deg, var(--gold), #f0d060)", boxShadow: "0 0 20px rgba(212,175,55,0.4)" }}
                        >
                            <Rocket className="w-4 h-4 inline mr-2" />
                            Initialize Pilot
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    // ── Loading ───────────────────────────────────────────────────────────
    if (pilot.status === "loading" && !pilot.dashboard) {
        return (
            <div className="flex items-center justify-center py-24">
                <RefreshCw className="w-8 h-8 text-[var(--gold)] animate-spin" />
                <span className="ml-3 text-[var(--text-secondary)]">Loading pilot data...</span>
            </div>
        );
    }

    const d = pilot.dashboard!;
    const ps = d.pilot_status;

    return (
        <div className="space-y-5 bg-grid" style={{ animation: "fadeSlideIn 0.3s ease both" }}>
            {/* ── Header Bar ──────────────────────────────────────────────── */}
            <div className="glass-card p-4 flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <Rocket className="w-6 h-6 text-[var(--gold)]" />
                    <div>
                        <h1 className="text-lg font-bold text-white">PILOT COMMAND CENTER</h1>
                        <p className="text-xs text-[var(--text-secondary)]">
                            Week {ps.current_week} of {ps.total_weeks} •{" "}
                            <span className={phaseColor[ps.phase] || "text-white"}>
                                {phaseLabel[ps.phase] || ps.phase}
                            </span>
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    {/* Health badge */}
                    <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium ${d.health.critical_alerts_count > 0
                        ? "bg-red-500/20 text-red-400 border border-red-500/30"
                        : d.health.warning_alerts_count > 0
                            ? "bg-yellow-500/20 text-yellow-400 border border-yellow-500/30"
                            : "bg-green-500/20 text-green-400 border border-green-500/30"
                        }`}>
                        <CheckCircle className="w-3 h-3" />
                        {d.health.critical_alerts_count > 0 ? "DEGRADED" : d.health.warning_alerts_count > 0 ? "WARNING" : "HEALTHY"}
                    </div>
                    {/* Actions */}
                    <button onClick={pilot.runDailyCycle} className="p-2 rounded-lg border border-[var(--border-subtle)] hover:border-[var(--gold)] transition-colors" title="Run Daily Cycle">
                        <Play className="w-4 h-4 text-[var(--gold)]" />
                    </button>
                    <button onClick={pilot.advancePhase} className="p-2 rounded-lg border border-[var(--border-subtle)] hover:border-[var(--gold)] transition-colors" title="Advance Phase">
                        <SkipForward className="w-4 h-4 text-[var(--text-secondary)]" />
                    </button>
                    <button onClick={() => pilot.refresh()} className="p-2 rounded-lg border border-[var(--border-subtle)] hover:border-[var(--gold)] transition-colors" title="Refresh">
                        <RefreshCw className={`w-4 h-4 text-[var(--text-secondary)] ${pilot.status === "loading" ? "animate-spin" : ""}`} />
                    </button>
                </div>
            </div>

            {/* ── Key Metrics Row ─────────────────────────────────────────── */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <MetricCard label="Trading Days" value={String(ps.total_trading_days)} icon={<Clock className="w-4 h-4" />} />
                <MetricCard label="Signals Evaluated" value={ps.total_signals_evaluated.toLocaleString()} icon={<Zap className="w-4 h-4" />} />
                <MetricCard label="Alerts" value={String(ps.total_alerts_generated)} icon={<AlertTriangle className="w-4 h-4" />} color={ps.total_alerts_generated > 0 ? "text-yellow-400" : undefined} />
                <MetricCard label="Pipeline" value={d.health.pipeline_status.toUpperCase()} icon={<Activity className="w-4 h-4" />} color={d.health.pipeline_status === "complete" ? "text-green-400" : undefined} />
            </div>

            {/* ── Equity Curve Charts ─────────────────────────────────────── */}
            <div className="glass-card p-5">
                <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-4">
                    <TrendingUp className="w-4 h-4 text-[var(--gold)]" />
                    EQUITY CURVES
                </h3>
                <EquityCurveCharts equityCurves={d.equity_curves} />
            </div>

            {/* ── Main Grid — Portfolios / Leaderboards ───────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                {/* Left 2/3: Positions table + Portfolio performance */}
                <div className="lg:col-span-2 space-y-5">
                    {/* Positions Detail Table */}
                    <PositionsTable positions={d.positions} />

                    {/* Portfolio Metrics Grid */}
                    <div className="glass-card p-5">
                        <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-4">
                            <BarChart3 className="w-4 h-4 text-[var(--gold)]" />
                            PORTFOLIO PERFORMANCE
                        </h3>
                        {d.portfolio_metrics.length > 0 ? (
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr className="text-[var(--text-secondary)] border-b border-[var(--border-subtle)]">
                                            <th className="text-left py-2 px-3">Portfolio</th>
                                            <th className="text-right py-2 px-3">Return</th>
                                            <th className="text-right py-2 px-3">Alpha</th>
                                            <th className="text-right py-2 px-3">Sharpe</th>
                                            <th className="text-right py-2 px-3">Volatility</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {d.portfolio_metrics.map((pm: any, i: number) => (
                                            <tr key={i} className="border-b border-[var(--border-subtle)]/30">
                                                <td className="py-2.5 px-3 text-white font-medium capitalize">{pm.portfolio_type}</td>
                                                <td className={`py-2.5 px-3 text-right ${pm.total_return >= 0 ? "text-green-400" : "text-red-400"}`}>{fmtPct(pm.total_return)}</td>
                                                <td className={`py-2.5 px-3 text-right ${pm.alpha_vs_benchmark >= 0 ? "text-green-400" : "text-red-400"}`}>{fmtPct(pm.alpha_vs_benchmark)}</td>
                                                <td className="py-2.5 px-3 text-right text-white">{fmt(pm.sharpe_ratio, 2)}</td>
                                                <td className="py-2.5 px-3 text-right text-[var(--text-secondary)]">{fmtPct(pm.annualized_volatility)}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        ) : (
                            <p className="text-sm text-[var(--text-secondary)] text-center py-6">Run a daily cycle to generate portfolio metrics</p>
                        )}
                    </div>
                </div>

                {/* Right 1/3: Leaderboards + Alerts */}
                <div className="space-y-5">
                    {/* Signal Leaderboard */}
                    <div className="glass-card p-5">
                        <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-3">
                            <Zap className="w-4 h-4 text-[var(--gold)]" />
                            SIGNAL LEADERBOARD
                        </h3>
                        {d.signal_leaderboard.length > 0 ? (
                            <div className="space-y-2">
                                {d.signal_leaderboard.slice(0, 8).map((s: any, i: number) => (
                                    <div key={i} className="flex items-center justify-between text-xs">
                                        <div className="flex items-center gap-2">
                                            <span className="text-[var(--gold)] font-mono w-4">{s.rank}</span>
                                            <span className="text-white truncate max-w-[120px]">{s.signal_name}</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="text-green-400 font-mono">{(s.hit_rate * 100).toFixed(0)}%</span>
                                            <span className="text-[var(--text-secondary)] font-mono">{s.total_firings}×</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <p className="text-xs text-[var(--text-secondary)] text-center py-3">No signal data yet</p>
                        )}
                    </div>

                    {/* Strategy Leaderboard */}
                    <div className="glass-card p-5">
                        <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-3">
                            <Target className="w-4 h-4 text-[var(--gold)]" />
                            STRATEGY LEADERBOARD
                        </h3>
                        {d.strategy_leaderboard.length > 0 ? (
                            <div className="space-y-3">
                                {d.strategy_leaderboard.map((s: any, i: number) => (
                                    <div key={i} className="glass-card p-3">
                                        <div className="flex items-center justify-between mb-1.5">
                                            <span className="text-white text-sm font-medium">{s.strategy_name}</span>
                                            <span className="text-xs text-[var(--text-secondary)]">{s.category}</span>
                                        </div>
                                        <div className="flex items-center gap-4 text-xs">
                                            <span className="text-[var(--gold)]">Sharpe {fmt(s.sharpe_ratio, 2)}</span>
                                            <span className="text-red-400">DD {fmtPct(s.max_drawdown)}</span>
                                            <span className="text-green-400">Q{fmt(s.quality_score, 0)}</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <p className="text-xs text-[var(--text-secondary)] text-center py-3">No strategy data yet</p>
                        )}
                    </div>

                    {/* Recent Alerts */}
                    <div className="glass-card p-5">
                        <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-3">
                            <AlertTriangle className="w-4 h-4 text-yellow-400" />
                            RECENT ALERTS
                            {d.recent_alerts.length > 0 && (
                                <span className="ml-auto text-xs text-[var(--text-secondary)]">{d.recent_alerts.length}</span>
                            )}
                        </h3>
                        {d.recent_alerts.length > 0 ? (
                            <div className="space-y-2 max-h-[240px] overflow-y-auto pr-1">
                                {d.recent_alerts.slice(0, 8).map((a: any) => (
                                    <div key={a.id} className={`p-2.5 rounded-lg border text-xs ${severityBg[a.severity]}`}>
                                        <div className="flex items-center gap-1.5 mb-0.5">
                                            {severityIcon[a.severity]}
                                            <span className="text-white font-medium">{a.title}</span>
                                        </div>
                                        {a.message && <p className="text-[var(--text-secondary)] ml-5 line-clamp-2">{a.message}</p>}
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="flex items-center gap-2 text-xs text-green-400 py-2">
                                <CheckCircle className="w-3.5 h-3.5" />
                                No alerts — all systems nominal
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* ── System Health Bar ───────────────────────────────────────── */}
            <div className="glass-card p-4 flex flex-wrap items-center gap-6 text-xs">
                <HealthDot label="Pipeline" ok={d.health.pipeline_status === "complete"} value={d.health.pipeline_status} />
                <HealthDot label="Data" ok={d.health.data_fresh} value={d.health.data_fresh ? "FRESH" : "STALE"} />
                <HealthDot label="Strategies" ok={d.health.active_strategies_count >= d.health.target_strategies_count} value={`${d.health.active_strategies_count}/${d.health.target_strategies_count}`} />
                <HealthDot label="Uptime" ok={d.health.uptime_pct >= 99} value={`${d.health.uptime_pct.toFixed(1)}%`} />
                <HealthDot label="Alerts" ok={d.health.critical_alerts_count === 0} value={`${d.health.critical_alerts_count} critical`} />
                {d.health.last_run_duration_seconds > 0 && (
                    <span className="text-[var(--text-secondary)]">
                        Last run: {d.health.last_run_duration_seconds.toFixed(1)}s
                    </span>
                )}
                {ps.last_daily_run && (
                    <span className="text-[var(--text-secondary)] ml-auto">
                        Last cycle: {new Date(ps.last_daily_run).toLocaleString()}
                    </span>
                )}
            </div>
        </div>
    );
}

// ─── Equity Curve Charts ────────────────────────────────────────────────────

function EquityCurveCharts({ equityCurves }: { equityCurves: Record<string, any[]> }) {
    const portfolioTypes = ["research", "strategy", "benchmark"] as const;
    const labels: Record<string, string> = { research: "Research", strategy: "Strategy", benchmark: "Benchmark" };

    // Build combined chart data for overlay
    const combinedData = useMemo(() => {
        const dateMap = new Map<string, Record<string, number>>();
        for (const ptype of portfolioTypes) {
            const curve = equityCurves[ptype] || [];
            curve.forEach((pt: any, idx: number) => {
                const dateKey = pt.date ? new Date(pt.date).toLocaleDateString("en-US", { month: "short", day: "numeric" }) : `Day ${idx + 1}`;
                const existing = dateMap.get(dateKey) || {};
                existing[ptype] = pt.nav;
                dateMap.set(dateKey, existing);
            });
        }
        return Array.from(dateMap.entries()).map(([date, vals]) => ({ date, ...vals }));
    }, [equityCurves]);

    const hasData = combinedData.length > 0;

    return (
        <div className="space-y-4">
            {/* Summary cards */}
            <div className="grid grid-cols-3 gap-3">
                {portfolioTypes.map((ptype) => {
                    const curve = equityCurves[ptype] || [];
                    const latest = curve[curve.length - 1];
                    const nav = latest?.nav || 1_000_000;
                    const cumReturn = latest?.cumulative_return || 0;
                    const isPositive = cumReturn >= 0;
                    const color = CHART_COLORS[ptype];
                    return (
                        <div key={ptype} className="glass-card p-3 text-center" style={{ borderColor: color.stroke + "40" }}>
                            <div className="text-xs text-[var(--text-secondary)] uppercase mb-0.5 font-medium">{labels[ptype]}</div>
                            <div className="text-lg font-bold text-white">{fmtUSD(nav)}</div>
                            <div className={`text-sm font-medium ${isPositive ? "text-green-400" : "text-red-400"}`}>
                                {isPositive ? <ArrowUp className="w-3 h-3 inline" /> : <ArrowDown className="w-3 h-3 inline" />}
                                {fmtPct(cumReturn)}
                            </div>
                            <div className="text-[10px] text-[var(--text-secondary)] mt-0.5">{curve.length} days</div>
                        </div>
                    );
                })}
            </div>

            {/* Overlaid area chart */}
            {hasData && combinedData.length >= 2 ? (
                <div className="h-[220px] -mx-2">
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={combinedData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                            <defs>
                                {portfolioTypes.map((ptype) => (
                                    <linearGradient key={ptype} id={`gradient_${ptype}`} x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor={CHART_COLORS[ptype].stroke} stopOpacity={0.3} />
                                        <stop offset="95%" stopColor={CHART_COLORS[ptype].stroke} stopOpacity={0} />
                                    </linearGradient>
                                ))}
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                            <XAxis
                                dataKey="date"
                                tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }}
                                axisLine={{ stroke: "rgba(255,255,255,0.08)" }}
                                tickLine={false}
                            />
                            <YAxis
                                tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }}
                                axisLine={{ stroke: "rgba(255,255,255,0.08)" }}
                                tickLine={false}
                                tickFormatter={(v: number) => `$${(v / 1_000_000).toFixed(2)}M`}
                                domain={["auto", "auto"]}
                            />
                            <Tooltip
                                contentStyle={{
                                    backgroundColor: "rgba(10,10,15,0.95)",
                                    border: "1px solid rgba(212,175,55,0.3)",
                                    borderRadius: "8px",
                                    fontSize: "12px",
                                    color: "#fff",
                                }}
                                formatter={(value: any, name: any) => [fmtUSD(Number(value)), labels[name] || name]}
                                labelStyle={{ color: "rgba(255,255,255,0.5)", fontSize: "11px" }}
                            />
                            {portfolioTypes.map((ptype) => (
                                <Area
                                    key={ptype}
                                    type="monotone"
                                    dataKey={ptype}
                                    stroke={CHART_COLORS[ptype].stroke}
                                    strokeWidth={2}
                                    fill={`url(#gradient_${ptype})`}
                                    dot={false}
                                    activeDot={{ r: 3, strokeWidth: 2, fill: CHART_COLORS[ptype].stroke }}
                                />
                            ))}
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            ) : (
                <div className="text-center py-8 text-[var(--text-secondary)] text-sm">
                    Run 2+ daily cycles to see equity curve chart
                </div>
            )}
        </div>
    );
}

// ─── Positions Table ─────────────────────────────────────────────────────────

function PositionsTable({ positions }: { positions: Record<string, any[]> }) {
    const portfolioTypes = ["research", "strategy", "benchmark"] as const;
    const labels: Record<string, string> = { research: "Research", strategy: "Strategy", benchmark: "Benchmark" };
    const iconColors: Record<string, string> = { research: "#d4af37", strategy: "#4ade80", benchmark: "#60a5fa" };

    const hasAnyPositions = portfolioTypes.some((pt) => (positions[pt] || []).length > 0);

    if (!hasAnyPositions) {
        return (
            <div className="glass-card p-5">
                <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-3">
                    <Briefcase className="w-4 h-4 text-[var(--gold)]" />
                    PORTFOLIO POSITIONS
                </h3>
                <p className="text-sm text-[var(--text-secondary)] text-center py-6">Run a daily cycle to populate positions</p>
            </div>
        );
    }

    return (
        <div className="glass-card p-5">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-4">
                <Briefcase className="w-4 h-4 text-[var(--gold)]" />
                PORTFOLIO POSITIONS
            </h3>
            <div className="space-y-4">
                {portfolioTypes.map((ptype) => {
                    const pos = positions[ptype] || [];
                    if (pos.length === 0) return null;

                    // Sort by weight descending
                    const sorted = [...pos].sort((a, b) => (b.weight || 0) - (a.weight || 0));

                    return (
                        <div key={ptype}>
                            <div className="flex items-center gap-2 mb-2">
                                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: iconColors[ptype] }} />
                                <span className="text-xs font-semibold text-white uppercase">{labels[ptype]}</span>
                                <span className="text-[10px] text-[var(--text-secondary)]">{sorted.length} positions</span>
                            </div>
                            <div className="overflow-x-auto">
                                <table className="w-full text-xs">
                                    <thead>
                                        <tr className="text-[var(--text-secondary)] border-b border-[var(--border-subtle)]">
                                            <th className="text-left py-1.5 px-2">Ticker</th>
                                            <th className="text-right py-1.5 px-2">Weight</th>
                                            <th className="text-right py-1.5 px-2">Shares</th>
                                            <th className="text-right py-1.5 px-2">Price</th>
                                            <th className="text-right py-1.5 px-2">P&L</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {sorted.map((p: any, i: number) => {
                                            const pnl = (p.pnl_pct || 0) * 100;
                                            return (
                                                <tr key={p.ticker || i} className="border-b border-[var(--border-subtle)]/20 hover:bg-white/[0.02] transition-colors">
                                                    <td className="py-1.5 px-2 font-mono font-semibold text-white">{p.ticker}</td>
                                                    <td className="py-1.5 px-2 text-right font-mono text-[var(--text-secondary)]">{((p.weight || 0) * 100).toFixed(1)}%</td>
                                                    <td className="py-1.5 px-2 text-right font-mono text-[var(--text-secondary)]">{(p.shares || 0).toFixed(1)}</td>
                                                    <td className="py-1.5 px-2 text-right font-mono text-white">${(p.price || 0).toFixed(2)}</td>
                                                    <td className={`py-1.5 px-2 text-right font-mono font-medium ${pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                                                        {pnl >= 0 ? "+" : ""}{pnl.toFixed(2)}%
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function MetricCard({ label, value, icon, color }: { label: string; value: string; icon: React.ReactNode; color?: string }) {
    return (
        <div className="glass-card p-4 text-center">
            <div className="flex items-center justify-center gap-1.5 mb-1.5 text-[var(--gold)]">{icon}</div>
            <div className={`text-xl font-bold ${color || "text-white"}`}>{value}</div>
            <div className="text-xs text-[var(--text-secondary)] mt-0.5">{label}</div>
        </div>
    );
}

function HealthDot({ label, ok, value }: { label: string; ok: boolean; value: string }) {
    return (
        <div className="flex items-center gap-1.5">
            <div className={`w-2 h-2 rounded-full ${ok ? "bg-green-400" : "bg-red-400"}`} style={{ boxShadow: ok ? "0 0 6px rgba(74,222,128,0.6)" : "0 0 6px rgba(248,113,113,0.6)" }} />
            <span className="text-[var(--text-secondary)]">{label}</span>
            <span className={`font-medium ${ok ? "text-green-400" : "text-red-400"}`}>{value}</span>
        </div>
    );
}
