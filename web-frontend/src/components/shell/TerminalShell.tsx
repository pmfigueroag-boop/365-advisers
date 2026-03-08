"use client";

/**
 * TerminalShell.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Universal 4-zone layout wrapper for ALL 365 Advisers views.
 *
 * Zones:
 *   ┌──────┬──────────────────────┬──────────┐
 *   │ LEFT │   CENTRAL WORKSPACE  │  RIGHT   │
 *   │ NAV  │   (children)         │  INTEL   │
 *   ├──────┴──────────────────────┴──────────┤
 *   │           BOTTOM ANALYTICS             │
 *   ├────────────────────────────────────────┤
 *   │           STATUS BAR                   │
 *   └────────────────────────────────────────┘
 *
 * Each panel receives contextual content from the active view.
 * Strategy Lab already used this pattern; now all views share it.
 */

import type { ReactNode } from "react";
import type { ViewId } from "../navigation/TopNav";
import LeftNavPanel, { type SubNavItem } from "./LeftNavPanel";
import RightIntelPanel, { type IntelInsight, type IntelSection } from "./RightIntelPanel";
import BottomPanel, { type BottomMetric } from "./BottomPanel";
import GlobalStatusBar from "./GlobalStatusBar";

// ─── Types ────────────────────────────────────────────────────────────────

interface TerminalShellProps {
    activeView: ViewId;
    children: ReactNode;

    // Left Nav
    subNavItems?: SubNavItem[];
    activeSubNav?: string;
    onSubNavChange?: (id: string) => void;
    subNavContextLabel?: string;
    subNavContextValue?: string;

    // Watchlist
    watchlistItems?: Array<{ ticker: string; name?: string; lastSignal?: string; lastScore?: number }>;
    activeTicker?: string;
    onTickerSelect?: (ticker: string) => void;

    // Right Intel
    insights?: IntelInsight[];
    intelSections?: IntelSection[];
    intelChildren?: ReactNode;

    // Bottom Panel
    bottomTitle?: string;
    bottomSubtitle?: string;
    bottomMetrics?: BottomMetric[];
    bottomChildren?: ReactNode;

    // Status Bar
    regime?: "bull" | "bear" | "neutral" | "volatile";
    activeSignals?: number;
    lastUpdate?: string;
    statusItems?: Array<{ label: string; value: string }>;
}

export default function TerminalShell({
    activeView,
    children,
    // Left Nav
    subNavItems = [],
    activeSubNav,
    onSubNavChange,
    subNavContextLabel,
    subNavContextValue,
    // Watchlist
    watchlistItems = [],
    activeTicker,
    onTickerSelect,
    // Right Intel
    insights = [],
    intelSections = [],
    intelChildren,
    // Bottom Panel
    bottomTitle = "Analytics",
    bottomSubtitle,
    bottomMetrics = [],
    bottomChildren,
    // Status Bar
    regime = "bull",
    activeSignals,
    lastUpdate,
    statusItems = [],
}: TerminalShellProps) {
    return (
        <div className="terminal-shell" style={{ animation: "fadeSlideIn 0.3s ease both" }}>
            {/* Left Navigation */}
            <LeftNavPanel
                activeView={activeView}
                subNavConfig={
                    subNavItems.length > 0
                        ? {
                            items: subNavItems,
                            contextLabel: subNavContextLabel,
                            contextValue: subNavContextValue,
                        }
                        : undefined
                }
                activeSubNav={activeSubNav}
                onSubNavChange={onSubNavChange}
                watchlistItems={watchlistItems}
                activeTicker={activeTicker}
                onTickerSelect={onTickerSelect}
            />

            {/* Main content area (center + right stacked with bottom) */}
            <div className="terminal-shell-main">
                {/* Top row: Center + Right */}
                <div className="terminal-shell-workspace">
                    {/* Central Workspace */}
                    <main className="terminal-shell-center">
                        {children}
                    </main>

                    {/* Right Intelligence Panel */}
                    {(insights.length > 0 || intelSections.length > 0 || intelChildren) && (
                        <RightIntelPanel
                            activeView={activeView}
                            insights={insights}
                            sections={intelSections}
                        >
                            {intelChildren}
                        </RightIntelPanel>
                    )}
                </div>

                {/* Bottom Analytics Panel */}
                {(bottomMetrics.length > 0 || bottomChildren) && (
                    <BottomPanel
                        title={bottomTitle}
                        subtitle={bottomSubtitle}
                        metrics={bottomMetrics}
                    >
                        {bottomChildren}
                    </BottomPanel>
                )}

                {/* Status Bar */}
                <GlobalStatusBar
                    activeView={activeView}
                    regime={regime}
                    activeSignals={activeSignals}
                    lastUpdate={lastUpdate}
                    activeTicker={activeTicker}
                    statusItems={statusItems}
                />
            </div>
        </div>
    );
}
