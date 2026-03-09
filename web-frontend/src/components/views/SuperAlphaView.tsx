"use client";

import { useState, useEffect } from "react";
import {
    TrendingUp,
    TrendingDown,
    Activity,
    Shield,
    Zap,
    BarChart3,
    Target,
    AlertTriangle,
    ChevronDown,
    ChevronRight,
    ArrowUpRight,
    ArrowDownRight,
    Minus,
    Loader2,
    RefreshCw,
} from "lucide-react";

// ─── Types ──────────────────────────────────────────────────────────────────

interface FactorVariable {
    name: string;
    raw_value: number | null;
    z_score: number | null;
    weight: number;
    weighted_contribution: number;
}

interface FactorScore {
    factor: string;
    score: number;
    percentile: number | null;
    variables: FactorVariable[];
    signals: string[];
    data_quality: number;
}

interface AssetProfile {
    ticker: string;
    composite_alpha_score: number;
    tier: string;
    rank: number | null;
    percentile: number | null;
    value: FactorScore;
    momentum: FactorScore;
    quality: FactorScore;
    size: FactorScore;
    volatility: FactorScore;
    sentiment: FactorScore;
    macro: FactorScore;
    event: FactorScore;
    convergence_bonus: number;
    volatility_adjustment: number;
    factor_agreement: number;
    top_drivers: string[];
}

interface Alert {
    alert_type: string;
    ticker: string | null;
    severity: string;
    headline: string;
    detail: string;
}

interface DashboardData {
    ranking: {
        rankings: AssetProfile[];
        universe_size: number;
        top_alpha: string[];
        bottom_alpha: string[];
        market_regime: string;
    };
    alerts: Alert[];
    heatmap: { ticker: string; exposures: Record<string, number> }[];
    regime: string;
}

// ─── Helper Components ──────────────────────────────────────────────────────

function ScoreBadge({ score, size = "md" }: { score: number; size?: "sm" | "md" | "lg" }) {
    const color =
        score >= 70 ? "text-emerald-400 bg-emerald-400/10 border-emerald-400/20" :
            score >= 50 ? "text-blue-400 bg-blue-400/10 border-blue-400/20" :
                score >= 30 ? "text-amber-400 bg-amber-400/10 border-amber-400/20" :
                    "text-red-400 bg-red-400/10 border-red-400/20";

    const sizes = {
        sm: "text-[9px] px-1.5 py-0.5",
        md: "text-xs px-2 py-1",
        lg: "text-sm px-3 py-1.5 font-bold",
    };

    return (
        <span className={`${color} ${sizes[size]} rounded-lg border font-mono font-bold`}>
            {score.toFixed(1)}
        </span>
    );
}

function TierBadge({ tier }: { tier: string }) {
    const configs: Record<string, { bg: string; text: string; glow: string }> = {
        "Alpha Elite": { bg: "bg-gradient-to-r from-[#d4af37]/20 to-[#e8c84a]/10", text: "text-[#d4af37]", glow: "shadow-[0_0_12px_-2px_rgba(212,175,55,0.3)]" },
        "Strong Alpha": { bg: "bg-emerald-500/10", text: "text-emerald-400", glow: "" },
        "Moderate Alpha": { bg: "bg-blue-500/10", text: "text-blue-400", glow: "" },
        "Neutral": { bg: "bg-gray-500/10", text: "text-gray-400", glow: "" },
        "Weak": { bg: "bg-amber-500/10", text: "text-amber-400", glow: "" },
        "Avoid": { bg: "bg-red-500/10", text: "text-red-400", glow: "" },
    };
    const c = configs[tier] || configs["Neutral"];
    return (
        <span className={`${c.bg} ${c.text} ${c.glow} text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md border border-current/10`}>
            {tier}
        </span>
    );
}

function FactorBar({ name, score }: { name: string; score: number }) {
    const color =
        score >= 70 ? "bg-emerald-500" :
            score >= 50 ? "bg-blue-500" :
                score >= 30 ? "bg-amber-500" :
                    "bg-red-500";

    return (
        <div className="flex items-center gap-2 text-[10px]">
            <span className="w-20 text-gray-500 font-mono uppercase tracking-wider">{name}</span>
            <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
                <div
                    className={`h-full ${color} rounded-full transition-all duration-700`}
                    style={{ width: `${Math.min(score, 100)}%` }}
                />
            </div>
            <span className="w-8 text-right font-mono text-gray-400">{score.toFixed(0)}</span>
        </div>
    );
}

// ─── Radar Chart (SVG) ──────────────────────────────────────────────────────

function RadarChart({ exposures }: { exposures: Record<string, number> }) {
    const factors = Object.keys(exposures);
    const n = factors.length;
    if (n === 0) return null;

    const cx = 120, cy = 120, r = 90;
    const angleStep = (2 * Math.PI) / n;

    const points = factors.map((f, i) => {
        const angle = i * angleStep - Math.PI / 2;
        const val = (exposures[f] || 0) / 100;
        return {
            x: cx + r * val * Math.cos(angle),
            y: cy + r * val * Math.sin(angle),
            lx: cx + (r + 16) * Math.cos(angle),
            ly: cy + (r + 16) * Math.sin(angle),
            label: f,
        };
    });

    const polygon = points.map(p => `${p.x},${p.y}`).join(" ");

    // Grid circles
    const gridCircles = [0.25, 0.5, 0.75, 1.0].map((pct) => (
        <circle
            key={pct}
            cx={cx} cy={cy} r={r * pct}
            fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="0.5"
        />
    ));

    // Axes
    const axes = factors.map((_, i) => {
        const angle = i * angleStep - Math.PI / 2;
        return (
            <line
                key={i}
                x1={cx} y1={cy}
                x2={cx + r * Math.cos(angle)} y2={cy + r * Math.sin(angle)}
                stroke="rgba(255,255,255,0.06)" strokeWidth="0.5"
            />
        );
    });

    return (
        <svg viewBox="0 0 240 240" className="w-full max-w-[280px] mx-auto">
            {gridCircles}
            {axes}
            <polygon
                points={polygon}
                fill="rgba(212, 175, 55, 0.12)"
                stroke="#d4af37"
                strokeWidth="1.5"
                strokeLinejoin="round"
            />
            {points.map((p, i) => (
                <g key={i}>
                    <circle cx={p.x} cy={p.y} r="3" fill="#d4af37" />
                    <text
                        x={p.lx} y={p.ly}
                        fill="rgba(255,255,255,0.5)"
                        fontSize="7"
                        textAnchor="middle"
                        dominantBaseline="middle"
                        fontFamily="monospace"
                    >
                        {p.label}
                    </text>
                </g>
            ))}
        </svg>
    );
}

// ─── Main Component ─────────────────────────────────────────────────────────

export default function SuperAlphaView() {
    const [data, setData] = useState<DashboardData | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [expandedTicker, setExpandedTicker] = useState<string | null>(null);
    const [sortBy, setSortBy] = useState<string>("composite");

    const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

    const fetchDashboard = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`${API}/super-alpha/dashboard`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const json = await res.json();
            setData(json);
        } catch (err: any) {
            setError(err.message || "Failed to load");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchDashboard(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

    // Sort rankings
    const sortedRankings = data?.ranking?.rankings?.slice().sort((a, b) => {
        if (sortBy === "composite") return b.composite_alpha_score - a.composite_alpha_score;
        const factorA = (a as any)[sortBy]?.score ?? 0;
        const factorB = (b as any)[sortBy]?.score ?? 0;
        return factorB - factorA;
    }) || [];

    const regime = data?.ranking?.market_regime ?? "unknown";
    const regimeConfig: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
        expansion: { label: "Expansion", color: "text-emerald-400", icon: <TrendingUp size={14} /> },
        neutral: { label: "Neutral", color: "text-blue-400", icon: <Minus size={14} /> },
        slowdown: { label: "Slowdown", color: "text-amber-400", icon: <TrendingDown size={14} /> },
        contraction: { label: "Contraction", color: "text-red-400", icon: <TrendingDown size={14} /> },
        unknown: { label: "Loading", color: "text-gray-400", icon: <Activity size={14} /> },
    };
    const rc = regimeConfig[regime] || regimeConfig.unknown;

    return (
        <div className="space-y-4 min-h-[600px]">
            {/* ── Header ── */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-lg font-black tracking-tighter gold-gradient flex items-center gap-2">
                        <Zap size={18} className="text-[#d4af37]" />
                        Super Alpha Engine
                    </h2>
                    <p className="text-[10px] text-gray-500 font-mono uppercase tracking-widest mt-0.5">
                        8-Factor Quantitative Scoring · Institutional Alpha Detection
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    {/* Regime Badge */}
                    <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl glass-card border border-[#30363d] ${rc.color}`}>
                        {rc.icon}
                        <span className="text-[10px] font-mono font-bold uppercase tracking-wider">{rc.label}</span>
                    </div>
                    <button
                        onClick={fetchDashboard}
                        disabled={loading}
                        className="p-2 rounded-xl text-gray-500 hover:text-[#d4af37] hover:bg-[#d4af37]/10 transition-all disabled:opacity-40"
                    >
                        {loading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                    </button>
                </div>
            </div>

            {error && (
                <div className="text-sm text-red-400 bg-red-400/10 border border-red-400/20 px-4 py-2 rounded-xl">
                    ⚠ {error}
                </div>
            )}

            {loading && !data && (
                <div className="flex items-center justify-center py-20 text-gray-500 gap-2">
                    <Loader2 size={18} className="animate-spin" />
                    <span className="text-sm">Loading alpha universe…</span>
                </div>
            )}

            {data && (
                <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
                    {/* ── Left: Ranking Table (3 cols) ── */}
                    <div className="xl:col-span-3 space-y-3">
                        {/* Sort Controls */}
                        <div className="flex items-center gap-2 text-[10px] font-mono text-gray-500 uppercase tracking-wider">
                            <span>Sort by:</span>
                            {["composite", "value", "momentum", "quality", "size", "volatility", "sentiment", "macro", "event"].map(s => (
                                <button
                                    key={s}
                                    onClick={() => setSortBy(s)}
                                    className={`px-2 py-0.5 rounded-md transition-all ${sortBy === s
                                        ? "bg-[#d4af37]/15 text-[#d4af37] border border-[#d4af37]/20"
                                        : "hover:text-gray-300"
                                        }`}
                                >
                                    {s}
                                </button>
                            ))}
                        </div>

                        {/* Ranking Cards */}
                        <div className="space-y-2">
                            {sortedRankings.map((asset, idx) => {
                                const isExpanded = expandedTicker === asset.ticker;
                                const factors = [
                                    { name: "Value", score: asset.value.score },
                                    { name: "Momentum", score: asset.momentum.score },
                                    { name: "Quality", score: asset.quality.score },
                                    { name: "Size", score: asset.size.score },
                                    { name: "Volatility", score: asset.volatility.score },
                                    { name: "Sentiment", score: asset.sentiment.score },
                                    { name: "Macro", score: asset.macro.score },
                                    { name: "Event", score: asset.event.score },
                                ];

                                return (
                                    <div
                                        key={asset.ticker}
                                        className="glass-card border border-[#30363d] rounded-xl overflow-hidden transition-all hover:border-[#d4af37]/20"
                                    >
                                        {/* Main Row */}
                                        <button
                                            onClick={() => setExpandedTicker(isExpanded ? null : asset.ticker)}
                                            className="w-full flex items-center gap-4 px-4 py-3 text-left hover:bg-white/[0.02] transition-colors"
                                        >
                                            {/* Rank */}
                                            <div className="w-8 text-center">
                                                <span className={`text-sm font-bold font-mono ${idx < 3 ? "text-[#d4af37]" : "text-gray-500"}`}>
                                                    #{asset.rank ?? idx + 1}
                                                </span>
                                            </div>

                                            {/* Ticker + Tier */}
                                            <div className="w-32">
                                                <div className="text-sm font-bold text-white">{asset.ticker}</div>
                                                <TierBadge tier={asset.tier} />
                                            </div>

                                            {/* CAS */}
                                            <div className="w-20">
                                                <div className="text-[9px] text-gray-500 font-mono uppercase mb-0.5">CAS</div>
                                                <ScoreBadge score={asset.composite_alpha_score} size="lg" />
                                            </div>

                                            {/* Factor Mini Bars */}
                                            <div className="flex-1 grid grid-cols-4 gap-x-4 gap-y-1">
                                                {factors.map(f => (
                                                    <FactorBar key={f.name} name={f.name} score={f.score} />
                                                ))}
                                            </div>

                                            {/* Expand Icon */}
                                            <div className="text-gray-500">
                                                {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                                            </div>
                                        </button>

                                        {/* Expanded Detail */}
                                        {isExpanded && (
                                            <div className="border-t border-[#30363d] px-4 py-4 bg-[#0a0d14]/50">
                                                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                                                    {/* Radar Chart */}
                                                    <div className="flex flex-col items-center gap-2">
                                                        <h4 className="text-[10px] font-mono text-gray-500 uppercase tracking-wider">Factor Exposure</h4>
                                                        <RadarChart exposures={
                                                            factors.reduce((acc, f) => ({ ...acc, [f.name]: f.score }), {} as Record<string, number>)
                                                        } />
                                                    </div>

                                                    {/* Score Breakdown */}
                                                    <div className="space-y-2">
                                                        <h4 className="text-[10px] font-mono text-gray-500 uppercase tracking-wider">Score Decomposition</h4>
                                                        <div className="space-y-1.5">
                                                            {factors.map(f => (
                                                                <div key={f.name} className="flex items-center justify-between text-xs">
                                                                    <span className="text-gray-400">{f.name}</span>
                                                                    <ScoreBadge score={f.score} size="sm" />
                                                                </div>
                                                            ))}
                                                            <div className="border-t border-[#30363d] pt-1.5 mt-2">
                                                                <div className="flex items-center justify-between text-xs">
                                                                    <span className="text-gray-300 font-bold">Convergence Bonus</span>
                                                                    <span className="text-[#d4af37] font-mono">+{asset.convergence_bonus.toFixed(1)}</span>
                                                                </div>
                                                                <div className="flex items-center justify-between text-xs">
                                                                    <span className="text-gray-300 font-bold">Vol Adjustment</span>
                                                                    <span className={`font-mono ${asset.volatility_adjustment < 0 ? "text-red-400" : "text-emerald-400"}`}>
                                                                        {asset.volatility_adjustment >= 0 ? "+" : ""}{asset.volatility_adjustment.toFixed(1)}
                                                                    </span>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </div>

                                                    {/* Top Drivers + Signals */}
                                                    <div className="space-y-3">
                                                        <div>
                                                            <h4 className="text-[10px] font-mono text-gray-500 uppercase tracking-wider mb-1">Top Drivers</h4>
                                                            <div className="space-y-1">
                                                                {asset.top_drivers.map((d, i) => (
                                                                    <div key={i} className="flex items-center gap-1.5 text-xs text-gray-300">
                                                                        <ArrowUpRight size={10} className="text-[#d4af37]" />
                                                                        {d}
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        </div>
                                                        <div>
                                                            <h4 className="text-[10px] font-mono text-gray-500 uppercase tracking-wider mb-1">Factor Agreement</h4>
                                                            <div className="flex items-center gap-2 text-xs text-gray-400">
                                                                <Target size={12} className="text-[#d4af37]" />
                                                                {asset.factor_agreement}/8 factors above 60
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* ── Right: Alerts + Intelligence (1 col) ── */}
                    <div className="space-y-4">
                        {/* Alert Feed */}
                        <div className="glass-card border border-[#30363d] rounded-xl p-4">
                            <h3 className="text-[10px] font-mono text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                                <AlertTriangle size={12} className="text-amber-400" />
                                Alpha Alerts
                                <span className="ml-auto text-[#d4af37] font-bold">{data.alerts?.length ?? 0}</span>
                            </h3>
                            <div className="space-y-2 max-h-[400px] overflow-y-auto">
                                {(data.alerts || []).slice(0, 15).map((alert, i) => {
                                    const sevColor =
                                        alert.severity === "critical" ? "border-red-500/30 bg-red-500/5" :
                                            alert.severity === "high" ? "border-amber-500/30 bg-amber-500/5" :
                                                "border-[#30363d] bg-white/[0.02]";
                                    const dotColor =
                                        alert.severity === "critical" ? "bg-red-500" :
                                            alert.severity === "high" ? "bg-amber-500" :
                                                "bg-blue-500";

                                    return (
                                        <div key={i} className={`border rounded-lg p-2.5 ${sevColor}`}>
                                            <div className="flex items-start gap-2">
                                                <span className={`w-1.5 h-1.5 rounded-full mt-1 flex-shrink-0 ${dotColor}`} />
                                                <div>
                                                    <div className="text-[10px] font-bold text-gray-200 leading-snug">{alert.headline}</div>
                                                    <div className="text-[9px] text-gray-500 mt-0.5 leading-snug">{alert.detail}</div>
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })}
                                {(!data.alerts || data.alerts.length === 0) && (
                                    <div className="text-center text-xs text-gray-600 py-4">No active alerts</div>
                                )}
                            </div>
                        </div>

                        {/* Universe Stats */}
                        <div className="glass-card border border-[#30363d] rounded-xl p-4">
                            <h3 className="text-[10px] font-mono text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                                <BarChart3 size={12} className="text-blue-400" />
                                Universe Stats
                            </h3>
                            <div className="space-y-2">
                                <div className="flex justify-between text-xs">
                                    <span className="text-gray-500">Assets Ranked</span>
                                    <span className="text-white font-mono">{data.ranking.universe_size}</span>
                                </div>
                                <div className="flex justify-between text-xs">
                                    <span className="text-gray-500">Top Alpha</span>
                                    <span className="text-emerald-400 font-mono">{data.ranking.top_alpha.join(", ") || "—"}</span>
                                </div>
                                <div className="flex justify-between text-xs">
                                    <span className="text-gray-500">Bottom Alpha</span>
                                    <span className="text-red-400 font-mono">{data.ranking.bottom_alpha.join(", ") || "—"}</span>
                                </div>
                                <div className="flex justify-between text-xs">
                                    <span className="text-gray-500">Market Regime</span>
                                    <span className={`font-mono font-bold ${rc.color}`}>{rc.label}</span>
                                </div>
                            </div>
                        </div>

                        {/* Top Radar */}
                        {sortedRankings.length > 0 && (
                            <div className="glass-card border border-[#30363d] rounded-xl p-4">
                                <h3 className="text-[10px] font-mono text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                                    <Shield size={12} className="text-[#d4af37]" />
                                    Top Asset Profile
                                </h3>
                                <div className="text-center text-sm font-bold text-white mb-1">{sortedRankings[0].ticker}</div>
                                <RadarChart exposures={{
                                    Value: sortedRankings[0].value.score,
                                    Momentum: sortedRankings[0].momentum.score,
                                    Quality: sortedRankings[0].quality.score,
                                    Size: sortedRankings[0].size.score,
                                    Volatility: sortedRankings[0].volatility.score,
                                    Sentiment: sortedRankings[0].sentiment.score,
                                    Macro: sortedRankings[0].macro.score,
                                    Event: sortedRankings[0].event.score,
                                }} />
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
