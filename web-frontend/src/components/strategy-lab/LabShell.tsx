"use client";

/**
 * LabShell.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * 4-zone layout wrapper for the Strategy Lab terminal.
 *
 * Zones:
 *   ┌──────┬──────────────────────┬──────────┐
 *   │ LEFT │   CENTRAL WORKSPACE  │  RIGHT   │
 *   │ NAV  │   (children)         │  INTEL   │
 *   ├──────┴──────────────────────┴──────────┤
 *   │           BOTTOM ANALYTICS             │
 *   └────────────────────────────────────────┘
 *
 * Each panel is collapsible. Central workspace flexes to fill.
 * Integrates keyboard shortcuts + command palette.
 */

import { useState, useCallback } from "react";
import type { LabSubView, StrategyItem } from "@/hooks/useStrategyLab";
import { useLabShortcuts } from "@/hooks/useLabShortcuts";
import LabNavPanel from "./LabNavPanel";
import IntelligencePanel from "./IntelligencePanel";
import BottomAnalyticsPanel from "./BottomAnalyticsPanel";
import CommandPalette from "./CommandPalette";
import LabStatusBar from "./LabStatusBar";

interface LabShellProps {
    activeView: LabSubView;
    onNavigate: (view: LabSubView) => void;
    strategyName?: string;
    strategies?: StrategyItem[];
    selectedStrategyId?: string | null;
    onNewStrategy?: () => void;
    onOpenStrategy?: (id: string) => void;
    children: React.ReactNode;
}

export default function LabShell({
    activeView,
    onNavigate,
    strategyName,
    strategies = [],
    selectedStrategyId = null,
    onNewStrategy,
    onOpenStrategy,
    children,
}: LabShellProps) {
    const [paletteOpen, setPaletteOpen] = useState(false);

    const togglePalette = useCallback(() => setPaletteOpen((p) => !p), []);
    const closePalette = useCallback(() => setPaletteOpen(false), []);

    // Global keyboard shortcuts
    useLabShortcuts({
        onNavigate,
        onTogglePalette: togglePalette,
        onEscape: closePalette,
    });

    return (
        <div className="lab-shell" style={{ animation: "fadeSlideIn 0.3s ease both" }}>
            {/* Left Navigation */}
            <LabNavPanel
                activeView={activeView}
                onNavigate={onNavigate}
                strategyName={strategyName}
            />

            {/* Main content area (center + right stacked vertically with bottom) */}
            <div className="lab-shell-main">
                {/* Top row: Center + Right */}
                <div className="lab-shell-workspace">
                    {/* Central Workspace */}
                    <main className="lab-shell-center">
                        {children}
                    </main>

                    {/* Right Intelligence Panel */}
                    <IntelligencePanel
                        activeView={activeView}
                        strategies={strategies}
                        selectedStrategyId={selectedStrategyId}
                    />
                </div>

                {/* Bottom Analytics Panel */}
                <BottomAnalyticsPanel
                    activeView={activeView}
                    strategies={strategies}
                    selectedStrategyId={selectedStrategyId}
                />

                {/* Status Bar */}
                <LabStatusBar
                    activeView={activeView}
                    strategies={strategies}
                    selectedStrategyId={selectedStrategyId}
                />
            </div>

            {/* Command Palette overlay */}
            <CommandPalette
                open={paletteOpen}
                onClose={closePalette}
                onNavigate={(v) => {
                    onNavigate(v);
                    closePalette();
                }}
                onNewStrategy={() => {
                    onNewStrategy?.();
                    closePalette();
                }}
                onOpenStrategy={(id) => {
                    onOpenStrategy?.(id);
                    closePalette();
                }}
                strategies={strategies}
            />
        </div>
    );
}
