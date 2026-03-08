"use client";

/**
 * LabStatusBar.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Terminal-style status bar at the bottom of the Lab Shell.
 * Shows: current view, strategy count, shortcut hint, connection status.
 * Bloomberg/VS Code inspired bottom strip.
 */

import {
    Wifi,
    WifiOff,
    Command,
    Clock,
} from "lucide-react";
import type { LabSubView, StrategyItem } from "@/hooks/useStrategyLab";

interface LabStatusBarProps {
    activeView: LabSubView;
    strategies: StrategyItem[];
    selectedStrategyId?: string | null;
}

const VIEW_LABELS: Record<LabSubView, string> = {
    home: "LAB HOME",
    builder: "STRATEGY BUILDER",
    backtest: "BACKTEST REPORT",
    compare: "STRATEGY COMPARE",
    portfolio: "PORTFOLIO BUILDER",
};

export default function LabStatusBar({
    activeView,
    strategies,
    selectedStrategyId,
}: LabStatusBarProps) {
    const selected = strategies.find((s) => s.strategy_id === selectedStrategyId);
    const now = new Date();
    const timeStr = now.toLocaleTimeString("en-US", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
    });

    return (
        <div className="lab-status-bar">
            {/* Left section */}
            <div className="lab-status-section">
                <span className="lab-status-view">{VIEW_LABELS[activeView]}</span>
                {selected && (
                    <span className="lab-status-strategy">
                        {selected.name} · v{selected.version}
                    </span>
                )}
            </div>

            {/* Center section */}
            <div className="lab-status-section">
                <span className="lab-status-count">
                    {strategies.length} strategies
                </span>
                <span className="lab-status-dot">·</span>
                <span className="lab-status-count">
                    {strategies.filter((s) => s.sharpe_ratio != null).length} backtested
                </span>
            </div>

            {/* Right section */}
            <div className="lab-status-section">
                <span className="lab-status-hint">
                    <Command size={9} />K palette
                </span>
                <span className="lab-status-dot">·</span>
                <span className="lab-status-hint">
                    ⇧1-5 nav
                </span>
                <span className="lab-status-dot">·</span>
                <span className="lab-status-time">
                    <Clock size={9} />
                    {timeStr}
                </span>
                <Wifi size={9} className="lab-status-conn" />
            </div>
        </div>
    );
}
