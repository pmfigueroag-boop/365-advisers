"use client";

/**
 * LabNavPanel.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Left navigation sidebar for the Strategy Lab terminal.
 * Collapsed (56px icons-only) / Expanded (200px with labels).
 * Bloomberg-inspired vertical nav with gold active indicator.
 */

import { useState } from "react";
import {
    Home,
    Wrench,
    LineChart,
    GitCompare,
    Briefcase,
    FlaskConical,
    ChevronLeft,
    ChevronRight,
} from "lucide-react";
import type { LabSubView } from "@/hooks/useStrategyLab";

interface NavItem {
    id: LabSubView;
    label: string;
    icon: React.ReactNode;
    shortcut: string;
}

const NAV_ITEMS: NavItem[] = [
    { id: "home", label: "Lab Home", icon: <Home size={18} />, shortcut: "⇧1" },
    { id: "builder", label: "Builder", icon: <Wrench size={18} />, shortcut: "⇧2" },
    { id: "backtest", label: "Backtest", icon: <LineChart size={18} />, shortcut: "⇧3" },
    { id: "compare", label: "Compare", icon: <GitCompare size={18} />, shortcut: "⇧4" },
    { id: "portfolio", label: "Portfolio", icon: <Briefcase size={18} />, shortcut: "⇧5" },
];

interface LabNavPanelProps {
    activeView: LabSubView;
    onNavigate: (view: LabSubView) => void;
    strategyName?: string;
}

export default function LabNavPanel({ activeView, onNavigate, strategyName }: LabNavPanelProps) {
    const [expanded, setExpanded] = useState(false);

    return (
        <nav
            className="lab-nav-panel"
            style={{
                width: expanded ? 200 : 56,
                minWidth: expanded ? 200 : 56,
                transition: "width 200ms ease-out, min-width 200ms ease-out",
            }}
        >
            {/* Lab Branding */}
            <div className="lab-nav-brand">
                <div className="lab-nav-brand-icon">
                    <FlaskConical size={18} />
                </div>
                {expanded && (
                    <span className="lab-nav-brand-text">
                        Strategy Lab
                    </span>
                )}
            </div>

            {/* Strategy Context */}
            {expanded && strategyName && (
                <div className="lab-nav-context">
                    <span className="lab-nav-context-label">ACTIVE</span>
                    <span className="lab-nav-context-name">{strategyName}</span>
                </div>
            )}

            <div className="lab-nav-separator" />

            {/* Navigation Items */}
            <div className="lab-nav-items">
                {NAV_ITEMS.map((item) => {
                    const isActive = activeView === item.id;
                    return (
                        <button
                            key={item.id}
                            onClick={() => onNavigate(item.id)}
                            className={`lab-nav-item ${isActive ? "lab-nav-item-active" : ""}`}
                            title={!expanded ? `${item.label} (${item.shortcut})` : undefined}
                        >
                            {/* Active indicator bar */}
                            <div className={`lab-nav-indicator ${isActive ? "lab-nav-indicator-active" : ""}`} />
                            <div className="lab-nav-item-icon">
                                {item.icon}
                            </div>
                            {expanded && (
                                <>
                                    <span className="lab-nav-item-label">{item.label}</span>
                                    <span className="lab-nav-item-shortcut">{item.shortcut}</span>
                                </>
                            )}
                        </button>
                    );
                })}
            </div>

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
