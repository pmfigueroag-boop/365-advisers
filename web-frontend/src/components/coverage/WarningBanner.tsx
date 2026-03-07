"use client";

/**
 * WarningBanner.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Contextual amber warning bar shown when critical data sources are missing
 * or degraded. Expandable to show all messages.
 */

import { useState } from "react";
import { AlertTriangle, ChevronDown, ChevronRight } from "lucide-react";

interface WarningBannerProps {
    messages: string[];
    unavailable: string[];
}

export default function WarningBanner({ messages, unavailable }: WarningBannerProps) {
    const [expanded, setExpanded] = useState(false);

    // Don't render if nothing to warn about
    if (messages.length === 0 && unavailable.length === 0) return null;

    const headline =
        unavailable.length > 0
            ? `${unavailable.length} data source${unavailable.length > 1 ? "s" : ""} unavailable`
            : messages[0] || "Partial coverage detected";

    return (
        <div
            style={{
                background: "rgba(245, 158, 11, 0.08)",
                border: "1px solid rgba(245, 158, 11, 0.2)",
                borderRadius: 8,
                padding: "8px 12px",
                marginBottom: 4,
            }}
        >
            <div
                onClick={() => messages.length > 1 && setExpanded(!expanded)}
                style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    cursor: messages.length > 1 ? "pointer" : "default",
                }}
            >
                <AlertTriangle size={14} style={{ color: "#F59E0B", flexShrink: 0 }} />
                <span
                    style={{
                        fontSize: 11,
                        color: "#FDE68A",
                        fontWeight: 600,
                        flex: 1,
                    }}
                >
                    {headline}
                </span>

                {messages.length > 1 && (
                    <span style={{ display: "flex", alignItems: "center", gap: 2, color: "#F59E0B", fontSize: 10 }}>
                        {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                        {messages.length} details
                    </span>
                )}
            </div>

            {expanded && messages.length > 1 && (
                <div style={{ marginTop: 6, paddingLeft: 22 }}>
                    {messages.map((msg, i) => (
                        <div
                            key={i}
                            style={{
                                fontSize: 10,
                                color: "#FDE68A",
                                opacity: 0.8,
                                padding: "2px 0",
                            }}
                        >
                            • {msg}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
