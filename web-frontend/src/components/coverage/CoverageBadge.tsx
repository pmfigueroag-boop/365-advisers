"use client";

/**
 * CoverageBadge.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Small inline pill badge showing analysis completeness score.
 * Green ≥90, Blue ≥70, Amber ≥50, Red <50.
 */

import { ShieldCheck, ShieldAlert, Shield } from "lucide-react";

interface CoverageBadgeProps {
    completeness: number;
    label: string;
}

const TIERS = [
    { min: 90, color: "#22C55E", bg: "rgba(34, 197, 94, 0.12)", icon: ShieldCheck },
    { min: 70, color: "#3B82F6", bg: "rgba(59, 130, 246, 0.12)", icon: ShieldCheck },
    { min: 50, color: "#F59E0B", bg: "rgba(245, 158, 11, 0.12)", icon: ShieldAlert },
    { min: 0, color: "#EF4444", bg: "rgba(239, 68, 68, 0.12)", icon: Shield },
];

export default function CoverageBadge({ completeness, label }: CoverageBadgeProps) {
    const tier = TIERS.find((t) => completeness >= t.min) ?? TIERS[3];
    const Icon = tier.icon;

    return (
        <span
            title={`Analysis used ${label} data coverage (${completeness.toFixed(0)}%)`}
            style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: "0.04em",
                padding: "3px 8px",
                borderRadius: 10,
                background: tier.bg,
                color: tier.color,
                border: `1px solid ${tier.color}25`,
                cursor: "default",
                whiteSpace: "nowrap" as const,
            }}
        >
            <Icon size={11} />
            <span style={{ fontFamily: "var(--font-mono, monospace)" }}>
                {completeness.toFixed(0)}%
            </span>
            <span style={{ opacity: 0.8, textTransform: "uppercase" as const }}>
                {label}
            </span>
        </span>
    );
}
