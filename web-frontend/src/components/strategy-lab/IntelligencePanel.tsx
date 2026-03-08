"use client";

/**
 * IntelligencePanel.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Right intelligence panel for the Strategy Lab.
 * Shows AI Assistant chat, context-aware insights, warnings, and regime context.
 * Collapsible with a toggle button. Integrates AssistantChatPanel.
 */

import { useState } from "react";
import {
    Brain,
    ChevronRight,
    ChevronLeft,
    Lightbulb,
    AlertTriangle,
    BarChart3,
    TrendingUp,
    MessageSquare,
    Target,
    Zap,
} from "lucide-react";
import type { LabSubView } from "@/hooks/useStrategyLab";
import type { StrategyItem } from "@/hooks/useStrategyLab";
import AssistantChatPanel from "./AssistantChatPanel";

interface IntelligencePanelProps {
    activeView: LabSubView;
    strategies?: StrategyItem[];
    selectedStrategyId?: string | null;
}

// ── Context-aware insight generation ─────────────────────────────────────

interface InsightItem {
    type: "info" | "warn" | "success";
    text: string;
}

function deriveInsights(
    view: LabSubView,
    strategies: StrategyItem[],
    selectedId: string | null,
): InsightItem[] {
    const insights: InsightItem[] = [];

    if (view === "home") {
        const total = strategies.length;
        if (total === 0) {
            insights.push({ type: "info", text: "Create your first strategy to get started" });
        } else {
            const backtested = strategies.filter((s) => s.lifecycle_state === "backtested").length;
            const live = strategies.filter((s) => s.lifecycle_state === "live").length;
            if (total > 0) {
                insights.push({ type: "info", text: `${total} strategies, ${backtested} backtested, ${live} live` });
            }
            const bestSharpe = strategies
                .filter((s) => s.sharpe_ratio != null)
                .sort((a, b) => (b.sharpe_ratio ?? 0) - (a.sharpe_ratio ?? 0))[0];
            if (bestSharpe) {
                insights.push({
                    type: "success",
                    text: `Top Sharpe: ${bestSharpe.name} (${bestSharpe.sharpe_ratio?.toFixed(2)})`,
                });
            }
            const drafts = strategies.filter((s) => s.lifecycle_state === "draft").length;
            if (drafts > 2) {
                insights.push({
                    type: "warn",
                    text: `${drafts} draft strategies — consider backtesting them`,
                });
            }
        }
    } else if (view === "builder") {
        const selected = strategies.find((s) => s.strategy_id === selectedId);
        if (selected) {
            insights.push({ type: "info", text: `Editing: ${selected.name} v${selected.version}` });
            if (selected.lifecycle_state === "draft") {
                insights.push({ type: "warn", text: "Strategy is in draft — backtest before promoting" });
            }
        } else {
            insights.push({ type: "info", text: "Configure signals, rules, and risk parameters" });
        }
    } else if (view === "backtest") {
        insights.push({ type: "info", text: "Review equity curves, drawdowns, and trade logs" });
        insights.push({ type: "warn", text: "Past performance ≠ future results" });
    } else if (view === "compare") {
        const comparable = strategies.filter((s) => s.sharpe_ratio != null).length;
        insights.push({
            type: comparable >= 2 ? "success" : "warn",
            text: comparable >= 2
                ? `${comparable} strategies with results available to compare`
                : "Need ≥2 backtested strategies to compare",
        });
    } else if (view === "portfolio") {
        insights.push({ type: "info", text: "Combine strategies with allocation optimization" });
        insights.push({ type: "info", text: "Low inter-strategy correlation improves diversification" });
    }

    return insights;
}

// ── Main Component ──────────────────────────────────────────────────────

export default function IntelligencePanel({
    activeView,
    strategies = [],
    selectedStrategyId = null,
}: IntelligencePanelProps) {
    const [collapsed, setCollapsed] = useState(false);
    const [activeTab, setActiveTab] = useState<"insights" | "chat">("insights");

    const insights = deriveInsights(activeView, strategies, selectedStrategyId);

    // Build chat context from current state
    const chatContext = {
        active_view: activeView,
        strategy_id: selectedStrategyId,
        strategy_count: strategies.length,
    };

    if (collapsed) {
        return (
            <div className="lab-intel-collapsed">
                <button
                    onClick={() => setCollapsed(false)}
                    className="lab-intel-toggle"
                    title="Show Intelligence Panel"
                >
                    <ChevronLeft size={12} />
                    <Brain size={14} />
                </button>
            </div>
        );
    }

    return (
        <aside className="lab-intel-panel">
            {/* Header */}
            <div className="lab-intel-header">
                <div className="lab-intel-header-left">
                    <Brain size={14} className="text-[#d4af37]" />
                    <span className="lab-intel-title">Intelligence</span>
                </div>
                <button
                    onClick={() => setCollapsed(true)}
                    className="lab-intel-toggle-btn"
                    title="Hide Intelligence Panel"
                >
                    <ChevronRight size={12} />
                </button>
            </div>

            {/* Tab switcher */}
            <div className="lab-intel-tabs">
                <button
                    onClick={() => setActiveTab("insights")}
                    className={`lab-intel-tab ${activeTab === "insights" ? "lab-intel-tab-active" : ""}`}
                >
                    <Lightbulb size={10} />
                    Insights
                </button>
                <button
                    onClick={() => setActiveTab("chat")}
                    className={`lab-intel-tab ${activeTab === "chat" ? "lab-intel-tab-active" : ""}`}
                >
                    <MessageSquare size={10} />
                    AI Chat
                </button>
            </div>

            <div className="lab-nav-separator" />

            {activeTab === "insights" ? (
                <>
                    {/* Context-aware Insights */}
                    <section className="lab-intel-section">
                        <div className="lab-intel-section-header">
                            <Target size={11} />
                            <span>CONTEXT ({activeView.toUpperCase()})</span>
                        </div>
                        <div className="lab-intel-insights">
                            {insights.map((item, i) => (
                                <div
                                    key={i}
                                    className={`lab-intel-insight-item ${item.type === "warn"
                                            ? "lab-intel-insight-warn"
                                            : item.type === "success"
                                                ? "lab-intel-insight-success"
                                                : "lab-intel-insight-info"
                                        }`}
                                >
                                    {item.type === "warn" ? (
                                        <AlertTriangle size={10} />
                                    ) : item.type === "success" ? (
                                        <TrendingUp size={10} />
                                    ) : (
                                        <Lightbulb size={10} />
                                    )}
                                    <span>{item.text}</span>
                                </div>
                            ))}
                        </div>
                    </section>

                    {/* Regime Context */}
                    <section className="lab-intel-section">
                        <div className="lab-intel-section-header">
                            <BarChart3 size={11} />
                            <span>REGIME CONTEXT</span>
                        </div>
                        <div className="lab-intel-regime">
                            <div className="lab-intel-regime-badge lab-intel-regime-bull">
                                BULL
                            </div>
                            <span className="lab-intel-regime-action">Full Exposure</span>
                        </div>
                    </section>

                    {/* Quick Stats */}
                    {strategies.length > 0 && (
                        <section className="lab-intel-section">
                            <div className="lab-intel-section-header">
                                <Zap size={11} />
                                <span>QUICK STATS</span>
                            </div>
                            <div className="lab-intel-stats">
                                <div className="lab-intel-stat">
                                    <span className="lab-intel-stat-value">{strategies.length}</span>
                                    <span className="lab-intel-stat-label">Strategies</span>
                                </div>
                                <div className="lab-intel-stat">
                                    <span className="lab-intel-stat-value">
                                        {strategies.filter((s) => s.sharpe_ratio != null).length}
                                    </span>
                                    <span className="lab-intel-stat-label">Backtested</span>
                                </div>
                                <div className="lab-intel-stat">
                                    <span className="lab-intel-stat-value">
                                        {strategies.filter((s) => s.lifecycle_state === "live").length}
                                    </span>
                                    <span className="lab-intel-stat-label">Live</span>
                                </div>
                            </div>
                        </section>
                    )}
                </>
            ) : (
                /* AI Chat tab */
                <div className="lab-intel-chat-wrapper">
                    <AssistantChatPanel
                        sessionId={`lab-${activeView}`}
                        context={chatContext}
                    />
                </div>
            )}
        </aside>
    );
}
