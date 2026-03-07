"use client";

/**
 * SourceStatusStrip.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Horizontal bar of small source indicators showing which data sources
 * contributed to the current analysis.
 *
 * Colors: green=available, yellow=stale/partial, gray=unavailable
 */

import { Database, Globe, TrendingUp, FileText, BarChart3, Radio, Wallet, Newspaper } from "lucide-react";

interface SourceStatusStripProps {
    sources: Record<string, string>;
}

const SOURCE_META: Record<string, { label: string; icon: any }> = {
    market_data: { label: "Market", icon: TrendingUp },
    macro: { label: "FRED", icon: BarChart3 },
    institutional: { label: "Instit.", icon: Wallet },
    sentiment: { label: "Sentiment", icon: Newspaper },
    options: { label: "Options", icon: Radio },
    etf_flows: { label: "ETF", icon: Database },
    filing_events: { label: "EDGAR", icon: FileText },
    geopolitical: { label: "GDELT", icon: Globe },
};

const STATUS_COLORS: Record<string, { dot: string; text: string }> = {
    available: { dot: "#22C55E", text: "#A7F3D0" },
    stale: { dot: "#F59E0B", text: "#FDE68A" },
    partial: { dot: "#F59E0B", text: "#FDE68A" },
    unavailable: { dot: "#4B5563", text: "#6B7280" },
    error: { dot: "#EF4444", text: "#FCA5A5" },
};

export default function SourceStatusStrip({ sources }: SourceStatusStripProps) {
    const entries = Object.entries(sources);
    if (entries.length === 0) return null;

    return (
        <div
            style={{
                display: "flex",
                flexWrap: "wrap" as const,
                gap: 6,
                padding: "6px 0",
            }}
        >
            {entries.map(([key, status]) => {
                const meta = SOURCE_META[key] || { label: key, icon: Database };
                const colors = STATUS_COLORS[status] || STATUS_COLORS.unavailable;
                const Icon = meta.icon;

                return (
                    <span
                        key={key}
                        title={`${meta.label}: ${status}`}
                        style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 4,
                            fontSize: 10,
                            fontWeight: 600,
                            color: colors.text,
                            padding: "2px 8px 2px 6px",
                            borderRadius: 6,
                            background: "rgba(30, 41, 59, 0.6)",
                            border: "1px solid rgba(148, 163, 184, 0.08)",
                        }}
                    >
                        <span
                            style={{
                                width: 6,
                                height: 6,
                                borderRadius: "50%",
                                background: colors.dot,
                                boxShadow: `0 0 4px ${colors.dot}50`,
                                flexShrink: 0,
                            }}
                        />
                        <Icon size={10} style={{ opacity: 0.7 }} />
                        {meta.label}
                    </span>
                );
            })}
        </div>
    );
}
