"use client";

/**
 * GlobalStatusBar.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Terminal-style status bar at the bottom of the Shell.
 * Shows: current view, system status, keyboard hints, live clock.
 * Bloomberg/VS Code inspired bottom strip.
 */

import { useState, useEffect } from "react";
import {
    Wifi,
    Command,
    Clock,
    Activity,
    TrendingUp,
    Radio,
    Database,
    Shield,
} from "lucide-react";
import type { ViewId } from "../navigation/TopNav";

// ─── Types ────────────────────────────────────────────────────────────────

interface GlobalStatusBarProps {
    activeView: ViewId;
    /** Market regime */
    regime?: "bull" | "bear" | "neutral" | "volatile";
    /** Active signals count */
    activeSignals?: number;
    /** Last data update timestamp */
    lastUpdate?: string;
    /** Active ticker */
    activeTicker?: string;
    /** Custom status items */
    statusItems?: Array<{ label: string; value: string }>;
    /** Data source coverage e.g. "6/6" */
    dataCoverage?: string;
    /** System health: green/yellow/red */
    systemHealth?: "green" | "yellow" | "red";
}

// ─── View Labels ──────────────────────────────────────────────────────────

const VIEW_LABELS: Record<ViewId, string> = {
    terminal: "INVESTMENT TERMINAL",
    market: "MARKET INTELLIGENCE",
    ideas: "IDEA EXPLORER",
    analysis: "DEEP ANALYSIS",
    portfolio: "PORTFOLIO INTELLIGENCE",
    system: "SYSTEM INTELLIGENCE",
    pilot: "PILOT COMMAND CENTER",
    "strategy-lab": "STRATEGY LAB",
    marketplace: "STRATEGY MARKETPLACE",
    "ai-assistant": "AI ASSISTANT",
    "alpha-engine": "ALPHA ENGINE",
};

const REGIME_STYLES: Record<string, { bg: string; color: string; label: string }> = {
    bull: { bg: "rgba(34,197,94,0.12)", color: "#22c55e", label: "BULL" },
    bear: { bg: "rgba(239,68,68,0.12)", color: "#ef4444", label: "BEAR" },
    neutral: { bg: "rgba(107,114,128,0.12)", color: "#9ca3af", label: "NEUTRAL" },
    volatile: { bg: "rgba(245,158,11,0.12)", color: "#f59e0b", label: "VOLATILE" },
};

const HEALTH_COLORS: Record<string, string> = {
    green: "#22c55e",
    yellow: "#f59e0b",
    red: "#ef4444",
};

export default function GlobalStatusBar({
    activeView,
    regime = "bull",
    activeSignals,
    lastUpdate,
    activeTicker,
    statusItems = [],
    dataCoverage,
    systemHealth = "green",
}: GlobalStatusBarProps) {
    // Live clock — updates every minute
    const [timeStr, setTimeStr] = useState(() =>
        new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false })
    );

    useEffect(() => {
        const interval = setInterval(() => {
            setTimeStr(new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false }));
        }, 60_000);
        return () => clearInterval(interval);
    }, []);

    const regimeStyle = REGIME_STYLES[regime] ?? REGIME_STYLES.neutral;
    const healthColor = HEALTH_COLORS[systemHealth] ?? HEALTH_COLORS.green;

    return (
        <div className="lab-status-bar">
            {/* Left section */}
            <div className="lab-status-section">
                <span className="lab-status-view">{VIEW_LABELS[activeView]}</span>
                {activeTicker && (
                    <span className="lab-status-strategy">
                        {activeTicker}
                    </span>
                )}
            </div>

            {/* Center section */}
            <div className="lab-status-section">
                {/* Regime Badge */}
                <span
                    className="shell-status-regime"
                    style={{ background: regimeStyle.bg, color: regimeStyle.color }}
                >
                    <TrendingUp size={8} />
                    {regimeStyle.label}
                </span>

                {activeSignals != null && (
                    <>
                        <span className="lab-status-dot">·</span>
                        <span className="lab-status-count">
                            <Radio size={8} /> {activeSignals} signals
                        </span>
                    </>
                )}

                {dataCoverage && (
                    <>
                        <span className="lab-status-dot">·</span>
                        <span className="lab-status-count">
                            <Database size={8} /> {dataCoverage} Sources
                        </span>
                    </>
                )}

                {/* System health dot */}
                <span className="lab-status-dot">·</span>
                <span className="lab-status-count" style={{ display: "flex", alignItems: "center", gap: 3 }}>
                    <span style={{ width: 6, height: 6, borderRadius: "50%", background: healthColor, display: "inline-block", boxShadow: `0 0 6px ${healthColor}` }} />
                    <Shield size={8} />
                </span>

                {lastUpdate && (
                    <>
                        <span className="lab-status-dot">·</span>
                        <span className="lab-status-count">
                            Last: {lastUpdate}
                        </span>
                    </>
                )}

                {statusItems.map((item, i) => (
                    <span key={i} className="lab-status-count">
                        <span className="lab-status-dot">·</span>
                        {item.label}: {item.value}
                    </span>
                ))}
            </div>

            {/* Right section */}
            <div className="lab-status-section">
                <span className="lab-status-hint">
                    <Command size={9} />K palette
                </span>
                <span className="lab-status-dot">·</span>
                <span className="lab-status-hint">
                    Alt+1-9 nav
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

