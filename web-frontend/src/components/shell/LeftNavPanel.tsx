"use client";

/**
 * LeftNavPanel.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Universal left navigation sidebar for the 365 Advisers Terminal.
 * Renders context-aware sub-navigation items for each top-level view.
 * Collapsed (56px icons-only) / Expanded (200px with labels).
 * Bloomberg-inspired vertical nav with gold active indicator.
 */

import { useState } from "react";
import {
    Activity,
    ChevronLeft,
    ChevronRight,
    Monitor,
    Map,
    Lightbulb,
    Microscope,
    Briefcase,
    Brain,
    FlaskConical,
    Store,
    Sparkles,
    Star,
    TrendingUp,
    Rocket,
} from "lucide-react";
import type { ViewId } from "../navigation/TopNav";

// ─── Left Nav Context Config ──────────────────────────────────────────────

interface LeftNavContext {
    icon: React.ReactNode;
    label: string;
}

const VIEW_CONTEXT: Record<ViewId, LeftNavContext> = {
    terminal: { icon: <Monitor size={18} />, label: "Terminal" },
    market: { icon: <Map size={18} />, label: "Market Intel" },
    ideas: { icon: <Lightbulb size={18} />, label: "Idea Explorer" },
    analysis: { icon: <Microscope size={18} />, label: "Deep Analysis" },
    portfolio: { icon: <Briefcase size={18} />, label: "Portfolio" },
    system: { icon: <Brain size={18} />, label: "System Intel" },
    pilot: { icon: <Rocket size={18} />, label: "Pilot" },
    "strategy-lab": { icon: <FlaskConical size={18} />, label: "Strategy Lab" },
    marketplace: { icon: <Store size={18} />, label: "Marketplace" },
    "ai-assistant": { icon: <Sparkles size={18} />, label: "AI Assistant" },
    "alpha-engine": { icon: <Activity size={18} />, label: "Alpha Engine" },
};

// ─── Sub-navigation items per view ────────────────────────────────────────

export interface SubNavItem {
    id: string;
    label: string;
    icon: React.ReactNode;
    shortcut?: string;
}

interface SubNavConfig {
    items: SubNavItem[];
    contextLabel?: string;
    contextValue?: string;
}

// ─── Component Props ──────────────────────────────────────────────────────

interface LeftNavPanelProps {
    activeView: ViewId;
    subNavConfig?: SubNavConfig;
    activeSubNav?: string;
    onSubNavChange?: (id: string) => void;

    // Watchlist integration (bottom of nav)
    watchlistItems?: Array<{ ticker: string; name?: string; lastSignal?: string; lastScore?: number }>;
    activeTicker?: string;
    onTickerSelect?: (ticker: string) => void;
}

export default function LeftNavPanel({
    activeView,
    subNavConfig,
    activeSubNav,
    onSubNavChange,
    watchlistItems = [],
    activeTicker,
    onTickerSelect,
}: LeftNavPanelProps) {
    const [expanded, setExpanded] = useState(false);
    const context = VIEW_CONTEXT[activeView] ?? { icon: <Monitor size={18} />, label: activeView };

    return (
        <nav
            className="shell-nav-panel"
            style={{
                width: expanded ? 200 : 56,
                minWidth: expanded ? 200 : 56,
                transition: "width 200ms ease-out, min-width 200ms ease-out",
            }}
        >
            {/* View Branding */}
            <div className="lab-nav-brand">
                <div className="lab-nav-brand-icon">
                    {context.icon}
                </div>
                {expanded && (
                    <span className="lab-nav-brand-text">
                        {context.label}
                    </span>
                )}
            </div>

            {/* Context Info */}
            {expanded && subNavConfig?.contextLabel && (
                <div className="lab-nav-context">
                    <span className="lab-nav-context-label">{subNavConfig.contextLabel}</span>
                    <span className="lab-nav-context-name">{subNavConfig.contextValue ?? "—"}</span>
                </div>
            )}

            <div className="lab-nav-separator" />

            {/* Sub-Navigation Items */}
            {subNavConfig && subNavConfig.items.length > 0 && (
                <div className="lab-nav-items">
                    {subNavConfig.items.map((item) => {
                        const isActive = activeSubNav === item.id;
                        return (
                            <button
                                key={item.id}
                                onClick={() => onSubNavChange?.(item.id)}
                                className={`lab-nav-item ${isActive ? "lab-nav-item-active" : ""}`}
                                title={!expanded ? `${item.label}${item.shortcut ? ` (${item.shortcut})` : ""}` : undefined}
                            >
                                <div className={`lab-nav-indicator ${isActive ? "lab-nav-indicator-active" : ""}`} />
                                <div className="lab-nav-item-icon">
                                    {item.icon}
                                </div>
                                {expanded && (
                                    <>
                                        <span className="lab-nav-item-label">{item.label}</span>
                                        {item.shortcut && (
                                            <span className="lab-nav-item-shortcut">{item.shortcut}</span>
                                        )}
                                    </>
                                )}
                            </button>
                        );
                    })}
                </div>
            )}

            {/* Watchlist Section (contextual) */}
            {watchlistItems.length > 0 && (
                <>
                    <div className="lab-nav-separator" />
                    {expanded && (
                        <div className="shell-nav-watchlist-header">
                            <Star size={9} className="text-[#d4af37]" />
                            <span>WATCHLIST</span>
                        </div>
                    )}
                    <div className="shell-nav-watchlist">
                        {watchlistItems.slice(0, expanded ? 10 : 6).map((item) => {
                            const isActive = item.ticker === activeTicker;
                            const sigColor =
                                item.lastSignal === "BUY" ? "#22c55e" :
                                    item.lastSignal === "SELL" ? "#ef4444" :
                                        item.lastSignal === "HOLD" ? "#f59e0b" : "#6b7280";
                            return (
                                <button
                                    key={item.ticker}
                                    onClick={() => onTickerSelect?.(item.ticker)}
                                    className={`shell-nav-watchlist-item ${isActive ? "shell-nav-watchlist-item-active" : ""}`}
                                    title={!expanded ? `${item.ticker}${item.lastSignal ? ` — ${item.lastSignal}` : ""}` : undefined}
                                >
                                    <span className="shell-nav-watchlist-ticker">{item.ticker}</span>
                                    {expanded && (
                                        <>
                                            {item.lastScore != null && (
                                                <span className="shell-nav-watchlist-score">{item.lastScore.toFixed(1)}</span>
                                            )}
                                            {item.lastSignal && (
                                                <span
                                                    className="shell-nav-watchlist-signal"
                                                    style={{ color: sigColor }}
                                                >
                                                    {item.lastSignal}
                                                </span>
                                            )}
                                        </>
                                    )}
                                    {!expanded && item.lastSignal && (
                                        <div
                                            className="shell-nav-watchlist-dot"
                                            style={{ background: sigColor }}
                                        />
                                    )}
                                </button>
                            );
                        })}
                    </div>
                </>
            )}

            {/* Expand/Collapse Toggle */}
            <button
                onClick={() => setExpanded(!expanded)}
                className="lab-nav-toggle"
                title={expanded ? "Collapse" : "Expand"}
            >
                {expanded ? <ChevronLeft size={14} /> : <ChevronRight size={14} />}
            </button>
        </nav>
    );
}
