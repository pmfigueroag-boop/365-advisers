"use client";

/**
 * StrategyLabView.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Strategy Lab — quantitative research environment.
 *
 * Phase 1: Lab Home with strategy cards, templates, and leaderboard.
 * Future phases will add Builder, Backtest, Compare, Portfolio sub-views.
 */

import { useState, useCallback } from "react";
import {
    FlaskConical,
    Plus,
    Copy,
    Trash2,
    RefreshCw,
    Loader2,
    ChevronRight,
    TrendingUp,
    Shield,
    Target,
    Zap,
    Award,
    BarChart3,
    Layers,
    Sparkles,
} from "lucide-react";
import ErrorBoundary from "@/components/ErrorBoundary";
import StrategyBuilder from "@/components/strategy-lab/StrategyBuilder";
import BacktestReport from "@/components/strategy-lab/BacktestReport";
import StrategyCompare from "@/components/strategy-lab/StrategyCompare";
import PortfolioBuilder from "@/components/strategy-lab/PortfolioBuilder";
import LabShell from "@/components/strategy-lab/LabShell";
import { useStrategyLab, LabSubView, StrategyItem, TemplateItem } from "@/hooks/useStrategyLab";

// ── Lifecycle badge colors ────────────────────────────────────────────────

const LIFECYCLE_COLORS: Record<string, { bg: string; text: string }> = {
    draft: { bg: "bg-gray-700/50", text: "text-gray-300" },
    research: { bg: "bg-blue-900/40", text: "text-blue-300" },
    backtested: { bg: "bg-purple-900/40", text: "text-purple-300" },
    validated: { bg: "bg-green-900/40", text: "text-green-300" },
    paper: { bg: "bg-yellow-900/40", text: "text-yellow-300" },
    live: { bg: "bg-emerald-900/40", text: "text-emerald-300" },
    paused: { bg: "bg-orange-900/40", text: "text-orange-300" },
    retired: { bg: "bg-red-900/40", text: "text-red-300" },
};

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
    momentum: <TrendingUp size={14} />,
    value: <Target size={14} />,
    quality: <Shield size={14} />,
    multi_factor: <Layers size={14} />,
    event_driven: <Zap size={14} />,
    thematic: <Sparkles size={14} />,
    low_vol: <BarChart3 size={14} />,
};

// SUB_TABS moved to LabNavPanel — vertical sidebar navigation

// ── Strategy Card ─────────────────────────────────────────────────────────

function StrategyCard({
    strategy,
    onOpen,
    onClone,
    onDelete,
}: {
    strategy: StrategyItem;
    onOpen: () => void;
    onClone: () => void;
    onDelete: () => void;
}) {
    const lifecycle = LIFECYCLE_COLORS[strategy.lifecycle_state] ?? LIFECYCLE_COLORS.draft;
    const icon = CATEGORY_ICONS[strategy.category] ?? <FlaskConical size={14} />;

    return (
        <div
            className="glass-card border-[#30363d] rounded-2xl p-4 hover:border-[#d4af37]/40 transition-all cursor-pointer group"
            onClick={onOpen}
        >
            {/* Header */}
            <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                    <div className="p-1.5 rounded-lg bg-[#d4af37]/10 text-[#d4af37]">
                        {icon}
                    </div>
                    <div>
                        <h3 className="text-sm font-bold text-gray-200 group-hover:text-[#d4af37] transition-colors">
                            {strategy.name}
                        </h3>
                        <p className="text-[10px] text-gray-600 capitalize">{strategy.category?.replace("_", " ")}</p>
                    </div>
                </div>
                <span className={`text-[9px] font-mono uppercase px-2 py-0.5 rounded-full ${lifecycle.bg} ${lifecycle.text}`}>
                    {strategy.lifecycle_state}
                </span>
            </div>

            {/* Description */}
            {strategy.description && (
                <p className="text-[11px] text-gray-500 mb-3 line-clamp-2">{strategy.description}</p>
            )}

            {/* Metrics row */}
            <div className="flex items-center gap-3 text-[10px] text-gray-500 mb-3">
                {strategy.sharpe_ratio != null && (
                    <span className="flex items-center gap-1">
                        <TrendingUp size={10} className={strategy.sharpe_ratio > 0 ? "text-green-400" : "text-red-400"} />
                        Sharpe {strategy.sharpe_ratio.toFixed(2)}
                    </span>
                )}
                <span className="font-mono">v{strategy.version}</span>
                {strategy.tags?.length > 0 && (
                    <span className="text-[#d4af37]/60">
                        {strategy.tags.slice(0, 2).join(", ")}
                    </span>
                )}
            </div>

            {/* Actions */}
            <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                    onClick={(e) => { e.stopPropagation(); onClone(); }}
                    className="p-1.5 rounded-lg text-gray-500 hover:text-[#d4af37] hover:bg-[#d4af37]/10 transition-all"
                    title="Clone"
                >
                    <Copy size={12} />
                </button>
                <button
                    onClick={(e) => { e.stopPropagation(); onDelete(); }}
                    className="p-1.5 rounded-lg text-gray-500 hover:text-red-400 hover:bg-red-400/10 transition-all"
                    title="Delete"
                >
                    <Trash2 size={12} />
                </button>
            </div>
        </div>
    );
}

// ── Template Card ─────────────────────────────────────────────────────────

function TemplateCard({
    template,
    onUse,
}: {
    template: TemplateItem;
    onUse: () => void;
}) {
    const icon = CATEGORY_ICONS[template.category] ?? <FlaskConical size={14} />;

    return (
        <button
            onClick={onUse}
            className="glass-card border-[#30363d] rounded-2xl p-4 text-left hover:border-[#d4af37]/40 transition-all group"
        >
            <div className="flex items-center gap-2 mb-2">
                <div className="p-1.5 rounded-lg bg-[#d4af37]/10 text-[#d4af37]">
                    {icon}
                </div>
                <span className="text-sm font-bold text-gray-300 group-hover:text-[#d4af37] transition-colors">
                    {template.name}
                </span>
            </div>
            <p className="text-[10px] text-gray-600 line-clamp-2">
                {template.description || `${template.category} strategy template`}
            </p>
            <div className="flex items-center gap-1 mt-2 text-[9px] text-[#d4af37]/60 opacity-0 group-hover:opacity-100 transition-opacity">
                <ChevronRight size={10} />
                Use template
            </div>
        </button>
    );
}

// ── Lab Home Sub-View ─────────────────────────────────────────────────────

function LabHome({
    strategies,
    templates,
    recommendations,
    loading,
    onNewStrategy,
    onOpenStrategy,
    onCloneStrategy,
    onDeleteStrategy,
    onUseTemplate,
    onRefresh,
}: {
    strategies: StrategyItem[];
    templates: TemplateItem[];
    recommendations: Array<{ name: string; reason: string; expected_sharpe?: number }>;
    loading: boolean;
    onNewStrategy: () => void;
    onOpenStrategy: (id: string) => void;
    onCloneStrategy: (id: string) => void;
    onDeleteStrategy: (id: string) => void;
    onUseTemplate: (t: TemplateItem) => void;
    onRefresh: () => void;
}) {
    return (
        <div className="space-y-6">
            {/* ── Actions Bar ── */}
            <div className="flex items-center justify-between">
                <div className="flex gap-2">
                    <button
                        onClick={onNewStrategy}
                        className="flex items-center gap-2 bg-gradient-to-r from-[#d4af37] to-[#e8c84a] text-black font-bold px-4 py-2 rounded-xl text-xs hover:brightness-110 transition-all shadow-[0_0_16px_-4px_rgba(212,175,55,0.3)]"
                    >
                        <Plus size={14} />
                        New Strategy
                    </button>
                </div>
                <button
                    onClick={onRefresh}
                    disabled={loading}
                    className="p-2 rounded-xl text-gray-500 hover:text-[#d4af37] hover:bg-[#d4af37]/10 transition-all disabled:opacity-40"
                    title="Refresh"
                >
                    {loading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                </button>
            </div>

            {/* ── Strategy Cards Grid ── */}
            <section>
                <h3 className="text-xs font-black uppercase tracking-widest text-gray-400 mb-3 flex items-center gap-2">
                    <FlaskConical size={12} className="text-[#d4af37]" />
                    Your Strategies
                    <span className="text-[10px] font-mono text-gray-600">({strategies.length})</span>
                </h3>

                {strategies.length === 0 ? (
                    <div className="glass-card border-[#30363d] rounded-2xl p-8 text-center">
                        <FlaskConical size={32} className="text-gray-700 mx-auto mb-3" />
                        <p className="text-sm text-gray-500 mb-1">No strategies yet</p>
                        <p className="text-[11px] text-gray-600">Create one from scratch or pick a template below.</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                        {strategies.map((s) => (
                            <StrategyCard
                                key={s.strategy_id}
                                strategy={s}
                                onOpen={() => onOpenStrategy(s.strategy_id)}
                                onClone={() => onCloneStrategy(s.strategy_id)}
                                onDelete={() => onDeleteStrategy(s.strategy_id)}
                            />
                        ))}
                    </div>
                )}
            </section>

            {/* ── Templates ── */}
            {templates.length > 0 && (
                <section>
                    <h3 className="text-xs font-black uppercase tracking-widest text-gray-400 mb-3 flex items-center gap-2">
                        <Sparkles size={12} className="text-purple-400" />
                        Strategy Templates
                    </h3>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                        {templates.map((t, i) => (
                            <TemplateCard key={i} template={t} onUse={() => onUseTemplate(t)} />
                        ))}
                    </div>
                </section>
            )}

            {/* ── Leaderboard / Recommendations ── */}
            {recommendations.length > 0 && (
                <section>
                    <h3 className="text-xs font-black uppercase tracking-widest text-gray-400 mb-3 flex items-center gap-2">
                        <Award size={12} className="text-yellow-400" />
                        Recommended for Current Regime
                    </h3>
                    <div className="glass-card border-[#30363d] rounded-2xl divide-y divide-[#30363d]/50">
                        {recommendations.map((rec, i) => (
                            <div key={i} className="flex items-center justify-between px-4 py-3">
                                <div className="flex items-center gap-3">
                                    <span className="text-[11px] font-mono text-[#d4af37] w-5">{i + 1}.</span>
                                    <div>
                                        <p className="text-sm font-semibold text-gray-300">{rec.name}</p>
                                        <p className="text-[10px] text-gray-600">{rec.reason}</p>
                                    </div>
                                </div>
                                {rec.expected_sharpe != null && (
                                    <span className="text-[10px] font-mono text-green-400">
                                        SR {rec.expected_sharpe.toFixed(2)}
                                    </span>
                                )}
                            </div>
                        ))}
                    </div>
                </section>
            )}
        </div>
    );
}









// ── Main View ─────────────────────────────────────────────────────────────

export default function StrategyLabView() {
    const lab = useStrategyLab();
    const [newStrategyModal, setNewStrategyModal] = useState(false);
    const [newName, setNewName] = useState("");
    const [newDesc, setNewDesc] = useState("");

    const handleCreateStrategy = useCallback(async () => {
        if (!newName.trim()) return;
        const id = await lab.createStrategy(newName.trim(), newDesc.trim());
        if (id) {
            setNewStrategyModal(false);
            setNewName("");
            setNewDesc("");
            lab.openBuilder(id);
        }
    }, [newName, newDesc, lab]);

    const handleUseTemplate = useCallback(async (t: TemplateItem) => {
        const id = await lab.createStrategy(t.name, t.description || `${t.category} strategy`, t.config);
        if (id) {
            lab.openBuilder(id);
        }
    }, [lab]);

    const handleClone = useCallback((strategyId: string) => {
        const strategy = lab.strategies.find((s) => s.strategy_id === strategyId);
        const cloneName = `${strategy?.name ?? "Strategy"} (copy)`;
        lab.cloneStrategy(strategyId, cloneName);
    }, [lab]);

    // Derive active strategy name for LabShell context
    const activeStrategyName = lab.selectedStrategyId
        ? lab.strategies.find((s) => s.strategy_id === lab.selectedStrategyId)?.name
        : undefined;

    return (
        <LabShell
            activeView={lab.subView}
            onNavigate={lab.setSubView}
            strategyName={activeStrategyName}
            strategies={lab.strategies}
            selectedStrategyId={lab.selectedStrategyId}
            onNewStrategy={() => setNewStrategyModal(true)}
            onOpenStrategy={(id) => lab.openBuilder(id)}
        >
            {/* ── Error banner ── */}
            {lab.error && (
                <div className="glass-card border-red-900/50 rounded-xl px-4 py-2 text-red-400 text-xs mb-4">
                    {lab.error}
                </div>
            )}

            {/* ── Sub-View Router ── */}
            <ErrorBoundary>
                {lab.subView === "home" && (
                    <LabHome
                        strategies={lab.strategies}
                        templates={lab.templates}
                        recommendations={lab.recommendations}
                        loading={lab.loading}
                        onNewStrategy={() => setNewStrategyModal(true)}
                        onOpenStrategy={(id) => lab.openBuilder(id)}
                        onCloneStrategy={handleClone}
                        onDeleteStrategy={lab.deactivateStrategy}
                        onUseTemplate={handleUseTemplate}
                        onRefresh={lab.refresh}
                    />
                )}
                {lab.subView === "builder" && (
                    <StrategyBuilder
                        strategyId={lab.selectedStrategyId}
                        initialConfig={lab.strategies.find((s) => s.strategy_id === lab.selectedStrategyId)?.config}
                        onBack={() => lab.setSubView("home")}
                        onSave={async (name, desc, config) => {
                            if (lab.selectedStrategyId) {
                                // Update existing
                                const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
                                try {
                                    await fetch(`${API}/lab/strategies/${lab.selectedStrategyId}`, {
                                        method: "PUT",
                                        headers: { "Content-Type": "application/json" },
                                        body: JSON.stringify(config),
                                    });
                                    await lab.refresh();
                                    return lab.selectedStrategyId;
                                } catch { return null; }
                            } else {
                                return await lab.createStrategy(name, desc, config);
                            }
                        }}
                        onRunBacktest={(id) => {
                            lab.setSelectedStrategyId(id);
                            lab.setSubView("backtest");
                        }}
                    />
                )}
                {lab.subView === "backtest" && lab.selectedStrategyId && (
                    <BacktestReport
                        strategyId={lab.selectedStrategyId}
                        onBack={() => lab.setSubView("home")}
                    />
                )}
                {lab.subView === "backtest" && !lab.selectedStrategyId && (
                    <div className="glass-card border-[#30363d] rounded-2xl p-8 text-center">
                        <BarChart3 size={32} className="text-gray-700 mx-auto mb-3" />
                        <p className="text-sm text-gray-400 font-bold mb-1">No Strategy Selected</p>
                        <p className="text-[11px] text-gray-600">Select a strategy from Lab Home or Builder to run a backtest.</p>
                    </div>
                )}
                {lab.subView === "compare" && (
                    <StrategyCompare
                        strategies={lab.strategies.map((s) => ({
                            strategy_id: s.strategy_id,
                            name: s.name,
                            category: s.category,
                            config: s.config,
                        }))}
                        onBack={() => lab.setSubView("home")}
                    />
                )}
                {lab.subView === "portfolio" && (
                    <PortfolioBuilder
                        strategies={lab.strategies.map((s) => ({
                            strategy_id: s.strategy_id,
                            name: s.name,
                            category: s.category,
                            config: s.config,
                        }))}
                        onBack={() => lab.setSubView("home")}
                    />
                )}
            </ErrorBoundary>

            {/* ── New Strategy Modal ── */}
            {newStrategyModal && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className="glass-card border-[#30363d] rounded-2xl p-6 w-full max-w-md space-y-4">
                        <h3 className="text-sm font-black uppercase tracking-widest text-gray-300">
                            New Strategy
                        </h3>
                        <input
                            type="text"
                            placeholder="Strategy name"
                            value={newName}
                            onChange={(e) => setNewName(e.target.value)}
                            onKeyDown={(e) => e.key === "Enter" && handleCreateStrategy()}
                            className="w-full bg-[#161b22] border border-[#30363d] px-4 py-2 rounded-xl text-sm focus:outline-none focus:border-[#d4af37] focus:ring-2 focus:ring-[#d4af37]/15 transition-all placeholder:text-gray-600"
                            autoFocus
                        />
                        <textarea
                            placeholder="Description (optional)"
                            value={newDesc}
                            onChange={(e) => setNewDesc(e.target.value)}
                            rows={2}
                            className="w-full bg-[#161b22] border border-[#30363d] px-4 py-2 rounded-xl text-sm focus:outline-none focus:border-[#d4af37] focus:ring-2 focus:ring-[#d4af37]/15 transition-all placeholder:text-gray-600 resize-none"
                        />
                        <div className="flex gap-2 justify-end">
                            <button
                                onClick={() => { setNewStrategyModal(false); setNewName(""); setNewDesc(""); }}
                                className="px-4 py-2 rounded-xl text-xs text-gray-400 hover:text-gray-200 hover:bg-white/5 transition-all"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleCreateStrategy}
                                disabled={!newName.trim() || lab.loading}
                                className="flex items-center gap-2 bg-gradient-to-r from-[#d4af37] to-[#e8c84a] text-black font-bold px-4 py-2 rounded-xl text-xs hover:brightness-110 transition-all disabled:opacity-50"
                            >
                                {lab.loading ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
                                Create
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </LabShell>
    );
}
