"use client";

/**
 * RightIntelPanel.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Universal right intelligence panel for the 365 Advisers Terminal.
 * Shows context-aware insights, AI chat, and data relevant to the active view.
 * Collapsible with toggle button.
 */

import { useState, type ReactNode } from "react";
import {
    Brain,
    ChevronRight,
    ChevronLeft,
    Lightbulb,
    AlertTriangle,
    TrendingUp,
    BarChart3,
    Target,
} from "lucide-react";
import type { ViewId } from "../navigation/TopNav";

// ─── Types ────────────────────────────────────────────────────────────────

export interface IntelInsight {
    type: "info" | "warn" | "success";
    text: string;
}

export interface IntelSection {
    title: string;
    icon?: ReactNode;
    content: ReactNode;
}

interface RightIntelPanelProps {
    activeView: ViewId;
    insights?: IntelInsight[];
    sections?: IntelSection[];
    /** Optional custom children rendered below sections */
    children?: ReactNode;
}

// ─── Component ────────────────────────────────────────────────────────────

export default function RightIntelPanel({
    activeView,
    insights = [],
    sections = [],
    children,
}: RightIntelPanelProps) {
    const [collapsed, setCollapsed] = useState(false);

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

            <div className="lab-nav-separator" />

            {/* Context-aware Insights */}
            {insights.length > 0 && (
                <section className="lab-intel-section">
                    <div className="lab-intel-section-header">
                        <Target size={11} />
                        <span>CONTEXT</span>
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
            )}

            {/* Custom Sections */}
            {sections.map((section, i) => (
                <section key={i} className="lab-intel-section">
                    <div className="lab-intel-section-header">
                        {section.icon ?? <BarChart3 size={11} />}
                        <span>{section.title}</span>
                    </div>
                    {section.content}
                </section>
            ))}

            {/* Custom children */}
            {children}
        </aside>
    );
}
