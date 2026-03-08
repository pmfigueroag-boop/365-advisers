"use client";

/**
 * BottomAnalyticsPanel.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Bottom analytics strip for the Strategy Lab terminal.
 * Displays view-adaptive metrics derived from real lab state:
 *   - Home    → Summary dashboard strip (strategy counts, best Sharpe, lifecycle dist)
 *   - Builder → Signal & rule count for active strategy
 *   - Backtest→ Key performance metrics from last backtest
 *   - Compare → Strategy-by-strategy metric comparison row
 *   - Portfolio→ Allocation + risk metrics
 * Collapsible with a toggle chevron.
 */

import { useState, useMemo } from "react";
import {
    ChevronDown,
    ChevronUp,
    Activity,
    TrendingUp,
    BarChart3,
    Clock,
    Target,
    Shield,
    Layers,
    Zap,
    AlertTriangle,
    Briefcase,
} from "lucide-react";
import type { LabSubView, StrategyItem } from "@/hooks/useStrategyLab";

interface BottomAnalyticsPanelProps {
    activeView: LabSubView;
    strategies: StrategyItem[];
    selectedStrategyId?: string | null;
}

// ── Title per view ────────────────────────────────────────────────────────

const VIEW_TITLES: Record<LabSubView, string> = {
    home: "Lab Overview",
    builder: "Strategy Config",
    backtest: "Performance Summary",
    compare: "Comparison Matrix",
    portfolio: "Portfolio Metrics",
};

// ── Derived metrics helper ────────────────────────────────────────────────

function useLabMetrics(strategies: StrategyItem[]) {
    return useMemo(() => {
        const total = strategies.length;
        const byLifecycle = strategies.reduce<Record<string, number>>((acc, s) => {
            acc[s.lifecycle_state] = (acc[s.lifecycle_state] || 0) + 1;
            return acc;
        }, {});
        const withSharpe = strategies.filter((s) => s.sharpe_ratio != null);
        const bestSharpe = withSharpe.length > 0
            ? withSharpe.reduce((best, s) => (s.sharpe_ratio ?? 0) > (best.sharpe_ratio ?? 0) ? s : best)
            : null;
        const avgSharpe = withSharpe.length > 0
            ? withSharpe.reduce((sum, s) => sum + (s.sharpe_ratio ?? 0), 0) / withSharpe.length
            : null;
        const categories = [...new Set(strategies.map((s) => s.category).filter(Boolean))];

        return {
            total,
            byLifecycle,
            backtested: withSharpe.length,
            bestSharpe,
            avgSharpe,
            categories,
            drafts: byLifecycle["draft"] ?? 0,
            live: byLifecycle["live"] ?? 0,
            retired: byLifecycle["retired"] ?? 0,
        };
    }, [strategies]);
}

// ── Main component ────────────────────────────────────────────────────────

export default function BottomAnalyticsPanel({
    activeView,
    strategies,
    selectedStrategyId = null,
}: BottomAnalyticsPanelProps) {
    const [collapsed, setCollapsed] = useState(false);
    const metrics = useLabMetrics(strategies);
    const selectedStrategy = strategies.find((s) => s.strategy_id === selectedStrategyId);

    return (
        <div className={`lab-bottom-panel ${collapsed ? "lab-bottom-panel-collapsed" : ""}`}>
            {/* Toggle bar */}
            <button
                onClick={() => setCollapsed(!collapsed)}
                className="lab-bottom-toggle"
            >
                <div className="lab-bottom-toggle-left">
                    <Activity size={11} className="text-[#d4af37]" />
                    <span className="lab-bottom-toggle-title">
                        {VIEW_TITLES[activeView]}
                    </span>
                    {/* Quick summary in toggle bar */}
                    {activeView === "home" && metrics.total > 0 && (
                        <span className="lab-bottom-toggle-badge">
                            {metrics.total} strategies
                        </span>
                    )}
                    {activeView === "builder" && selectedStrategy && (
                        <span className="lab-bottom-toggle-badge">
                            {selectedStrategy.name} · v{selectedStrategy.version}
                        </span>
                    )}
                </div>
                {collapsed ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>

            {/* Expandable content */}
            {!collapsed && (
                <div className="lab-bottom-content">

                    {/* ═══ HOME: Lab Overview Dashboard ═══ */}
                    {activeView === "home" && (
                        <div className="lab-bottom-metrics-strip">
                            <div className="lab-bottom-metric">
                                <BarChart3 size={12} className="text-[#d4af37]" />
                                <div>
                                    <span className="lab-bottom-metric-label">Total Strategies</span>
                                    <span className="lab-bottom-metric-value">{metrics.total}</span>
                                </div>
                            </div>
                            <div className="lab-bottom-metric">
                                <TrendingUp size={12} className="text-emerald-400" />
                                <div>
                                    <span className="lab-bottom-metric-label">Best Sharpe</span>
                                    <span className="lab-bottom-metric-value">
                                        {metrics.bestSharpe?.sharpe_ratio?.toFixed(2) ?? "—"}
                                    </span>
                                </div>
                            </div>
                            <div className="lab-bottom-metric">
                                <Activity size={12} className="text-blue-400" />
                                <div>
                                    <span className="lab-bottom-metric-label">Backtested</span>
                                    <span className="lab-bottom-metric-value">{metrics.backtested}</span>
                                </div>
                            </div>
                            <div className="lab-bottom-metric">
                                <Zap size={12} className="text-emerald-400" />
                                <div>
                                    <span className="lab-bottom-metric-label">Live</span>
                                    <span className="lab-bottom-metric-value">{metrics.live}</span>
                                </div>
                            </div>
                            <div className="lab-bottom-metric">
                                <Clock size={12} className="text-purple-400" />
                                <div>
                                    <span className="lab-bottom-metric-label">Avg Sharpe</span>
                                    <span className="lab-bottom-metric-value">
                                        {metrics.avgSharpe?.toFixed(2) ?? "—"}
                                    </span>
                                </div>
                            </div>
                            <div className="lab-bottom-metric">
                                <Layers size={12} className="text-orange-400" />
                                <div>
                                    <span className="lab-bottom-metric-label">Categories</span>
                                    <span className="lab-bottom-metric-value">{metrics.categories.length}</span>
                                </div>
                            </div>
                            {metrics.drafts > 2 && (
                                <div className="lab-bottom-metric lab-bottom-metric-warn">
                                    <AlertTriangle size={12} className="text-yellow-400" />
                                    <div>
                                        <span className="lab-bottom-metric-label">Drafts</span>
                                        <span className="lab-bottom-metric-value">{metrics.drafts}</span>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {/* ═══ BUILDER: Strategy Config Summary ═══ */}
                    {activeView === "builder" && (
                        selectedStrategy ? (
                            <div className="lab-bottom-metrics-strip">
                                <div className="lab-bottom-metric">
                                    <Target size={12} className="text-[#d4af37]" />
                                    <div>
                                        <span className="lab-bottom-metric-label">Category</span>
                                        <span className="lab-bottom-metric-value lab-bottom-metric-text">
                                            {selectedStrategy.category?.replace("_", " ") ?? "—"}
                                        </span>
                                    </div>
                                </div>
                                <div className="lab-bottom-metric">
                                    <Shield size={12} className="text-blue-400" />
                                    <div>
                                        <span className="lab-bottom-metric-label">Lifecycle</span>
                                        <span className="lab-bottom-metric-value lab-bottom-metric-text">
                                            {selectedStrategy.lifecycle_state}
                                        </span>
                                    </div>
                                </div>
                                <div className="lab-bottom-metric">
                                    <Activity size={12} className="text-purple-400" />
                                    <div>
                                        <span className="lab-bottom-metric-label">Version</span>
                                        <span className="lab-bottom-metric-value">v{selectedStrategy.version}</span>
                                    </div>
                                </div>
                                {selectedStrategy.sharpe_ratio != null && (
                                    <div className="lab-bottom-metric">
                                        <TrendingUp size={12} className="text-emerald-400" />
                                        <div>
                                            <span className="lab-bottom-metric-label">Last Sharpe</span>
                                            <span className="lab-bottom-metric-value">
                                                {selectedStrategy.sharpe_ratio.toFixed(2)}
                                            </span>
                                        </div>
                                    </div>
                                )}
                                {selectedStrategy.tags?.length > 0 && (
                                    <div className="lab-bottom-metric">
                                        <Layers size={12} className="text-orange-400" />
                                        <div>
                                            <span className="lab-bottom-metric-label">Tags</span>
                                            <span className="lab-bottom-metric-value lab-bottom-metric-text">
                                                {selectedStrategy.tags.slice(0, 3).join(", ")}
                                            </span>
                                        </div>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="lab-bottom-preview">
                                <div className="lab-bottom-preview-placeholder">
                                    <TrendingUp size={16} className="text-gray-600" />
                                    <span>Select or create a strategy to see configuration details</span>
                                </div>
                            </div>
                        )
                    )}

                    {/* ═══ BACKTEST: Performance Summary ═══ */}
                    {activeView === "backtest" && (
                        selectedStrategy ? (
                            <div className="lab-bottom-metrics-strip">
                                <div className="lab-bottom-metric">
                                    <Target size={12} className="text-[#d4af37]" />
                                    <div>
                                        <span className="lab-bottom-metric-label">Strategy</span>
                                        <span className="lab-bottom-metric-value lab-bottom-metric-text">
                                            {selectedStrategy.name}
                                        </span>
                                    </div>
                                </div>
                                {selectedStrategy.sharpe_ratio != null && (
                                    <div className="lab-bottom-metric">
                                        <TrendingUp size={12} className={selectedStrategy.sharpe_ratio > 0 ? "text-emerald-400" : "text-red-400"} />
                                        <div>
                                            <span className="lab-bottom-metric-label">Sharpe Ratio</span>
                                            <span className="lab-bottom-metric-value">
                                                {selectedStrategy.sharpe_ratio.toFixed(2)}
                                            </span>
                                        </div>
                                    </div>
                                )}
                                <div className="lab-bottom-metric">
                                    <Shield size={12} className="text-blue-400" />
                                    <div>
                                        <span className="lab-bottom-metric-label">State</span>
                                        <span className="lab-bottom-metric-value lab-bottom-metric-text">
                                            {selectedStrategy.lifecycle_state}
                                        </span>
                                    </div>
                                </div>
                                <div className="lab-bottom-metric">
                                    <Clock size={12} className="text-purple-400" />
                                    <div>
                                        <span className="lab-bottom-metric-label">Last Run</span>
                                        <span className="lab-bottom-metric-value lab-bottom-metric-text">
                                            {selectedStrategy.last_backtest
                                                ? new Date(selectedStrategy.last_backtest).toLocaleDateString()
                                                : "Never"}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="lab-bottom-preview">
                                <div className="lab-bottom-preview-placeholder">
                                    <Activity size={16} className="text-gray-600" />
                                    <span>Select a strategy to view backtest performance summary</span>
                                </div>
                            </div>
                        )
                    )}

                    {/* ═══ COMPARE: Strategy Comparison Row ═══ */}
                    {activeView === "compare" && (
                        metrics.backtested >= 2 ? (
                            <div className="lab-bottom-table-wrapper">
                                <table className="lab-bottom-table">
                                    <thead>
                                        <tr>
                                            <th>Strategy</th>
                                            <th>Category</th>
                                            <th>Sharpe</th>
                                            <th>State</th>
                                            <th>Version</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {strategies
                                            .filter((s) => s.sharpe_ratio != null)
                                            .sort((a, b) => (b.sharpe_ratio ?? 0) - (a.sharpe_ratio ?? 0))
                                            .slice(0, 5)
                                            .map((s) => (
                                                <tr key={s.strategy_id}>
                                                    <td className="lab-bottom-table-name">{s.name}</td>
                                                    <td>{s.category?.replace("_", " ") ?? "—"}</td>
                                                    <td className={(s.sharpe_ratio ?? 0) > 0 ? "lab-bottom-table-positive" : "lab-bottom-table-negative"}>
                                                        {s.sharpe_ratio?.toFixed(2)}
                                                    </td>
                                                    <td>{s.lifecycle_state}</td>
                                                    <td>v{s.version}</td>
                                                </tr>
                                            ))}
                                    </tbody>
                                </table>
                            </div>
                        ) : (
                            <div className="lab-bottom-preview">
                                <div className="lab-bottom-preview-placeholder">
                                    <BarChart3 size={16} className="text-gray-600" />
                                    <span>Need ≥2 backtested strategies to populate comparison matrix</span>
                                </div>
                            </div>
                        )
                    )}

                    {/* ═══ PORTFOLIO: Portfolio Summary ═══ */}
                    {activeView === "portfolio" && (
                        metrics.total >= 2 ? (
                            <div className="lab-bottom-metrics-strip">
                                <div className="lab-bottom-metric">
                                    <Briefcase size={12} className="text-[#d4af37]" />
                                    <div>
                                        <span className="lab-bottom-metric-label">Available</span>
                                        <span className="lab-bottom-metric-value">{metrics.total}</span>
                                    </div>
                                </div>
                                <div className="lab-bottom-metric">
                                    <Layers size={12} className="text-blue-400" />
                                    <div>
                                        <span className="lab-bottom-metric-label">Categories</span>
                                        <span className="lab-bottom-metric-value">{metrics.categories.length}</span>
                                    </div>
                                </div>
                                <div className="lab-bottom-metric">
                                    <TrendingUp size={12} className="text-emerald-400" />
                                    <div>
                                        <span className="lab-bottom-metric-label">Best Sharpe</span>
                                        <span className="lab-bottom-metric-value">
                                            {metrics.bestSharpe?.sharpe_ratio?.toFixed(2) ?? "—"}
                                        </span>
                                    </div>
                                </div>
                                <div className="lab-bottom-metric">
                                    <Activity size={12} className="text-purple-400" />
                                    <div>
                                        <span className="lab-bottom-metric-label">Backtested</span>
                                        <span className="lab-bottom-metric-value">{metrics.backtested}/{metrics.total}</span>
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="lab-bottom-preview">
                                <div className="lab-bottom-preview-placeholder">
                                    <Briefcase size={16} className="text-gray-600" />
                                    <span>Need ≥2 strategies to build a portfolio</span>
                                </div>
                            </div>
                        )
                    )}

                </div>
            )}
        </div>
    );
}
