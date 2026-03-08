"use client";

/**
 * BottomPanel.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Universal bottom analytics panel for the 365 Advisers Terminal.
 * Displays view-adaptive metrics, tables, and charts.
 * Collapsible with toggle chevron.
 */

import { useState, type ReactNode } from "react";
import {
    ChevronDown,
    ChevronUp,
    Activity,
} from "lucide-react";
import type { ViewId } from "../navigation/TopNav";

// ─── Types ────────────────────────────────────────────────────────────────

export interface BottomMetric {
    icon: ReactNode;
    label: string;
    value: string | number;
    className?: string;
}

interface BottomPanelProps {
    title: string;
    subtitle?: string;
    metrics?: BottomMetric[];
    /** Optional custom content (tables, charts) */
    children?: ReactNode;
}

// ─── Component ────────────────────────────────────────────────────────────

export default function BottomPanel({
    title,
    subtitle,
    metrics = [],
    children,
}: BottomPanelProps) {
    const [collapsed, setCollapsed] = useState(false);

    return (
        <div className={`lab-bottom-panel ${collapsed ? "lab-bottom-panel-collapsed" : ""}`}>
            {/* Toggle bar */}
            <button
                onClick={() => setCollapsed(!collapsed)}
                className="lab-bottom-toggle"
            >
                <div className="lab-bottom-toggle-left">
                    <Activity size={11} className="text-[#d4af37]" />
                    <span className="lab-bottom-toggle-title">{title}</span>
                    {subtitle && (
                        <span className="lab-bottom-toggle-badge">{subtitle}</span>
                    )}
                </div>
                {collapsed ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>

            {/* Expandable content */}
            {!collapsed && (
                <div className="lab-bottom-content">
                    {metrics.length > 0 && (
                        <div className="lab-bottom-metrics-strip">
                            {metrics.map((m, i) => (
                                <div key={i} className={`lab-bottom-metric ${m.className ?? ""}`}>
                                    {m.icon}
                                    <div>
                                        <span className="lab-bottom-metric-label">{m.label}</span>
                                        <span className="lab-bottom-metric-value">{m.value}</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                    {children}
                </div>
            )}
        </div>
    );
}
