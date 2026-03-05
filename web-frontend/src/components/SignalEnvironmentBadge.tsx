"use client";

import React from "react";
import { Sparkles, CheckCircle, Minus, ChevronDown, XCircle } from "lucide-react";

// ── Environment badge configuration ──────────────────────────────────────────

const ENV_CONFIG: Record<
    string,
    {
        color: string;
        bg: string;
        border: string;
        icon: React.ReactNode;
        short: string;
    }
> = {
    "Very Strong Opportunity": {
        color: "text-green-400",
        bg: "bg-green-500/15",
        border: "border-green-500/40",
        icon: <Sparkles size={10} />,
        short: "Very Strong",
    },
    "Strong Opportunity": {
        color: "text-emerald-400",
        bg: "bg-emerald-500/12",
        border: "border-emerald-500/30",
        icon: <CheckCircle size={10} />,
        short: "Strong",
    },
    Neutral: {
        color: "text-yellow-400",
        bg: "bg-yellow-500/12",
        border: "border-yellow-500/30",
        icon: <Minus size={10} />,
        short: "Neutral",
    },
    Weak: {
        color: "text-orange-400",
        bg: "bg-orange-500/12",
        border: "border-orange-500/30",
        icon: <ChevronDown size={10} />,
        short: "Weak",
    },
    "Negative Signal Environment": {
        color: "text-red-400",
        bg: "bg-red-500/12",
        border: "border-red-500/30",
        icon: <XCircle size={10} />,
        short: "Negative",
    },
};

// ── Component ────────────────────────────────────────────────────────────────

interface SignalEnvironmentBadgeProps {
    environment: string;
    score?: number;
    /** Compact mode: just icon + short label */
    compact?: boolean;
}

export default function SignalEnvironmentBadge({
    environment,
    score,
    compact = false,
}: SignalEnvironmentBadgeProps) {
    const cfg = ENV_CONFIG[environment] || ENV_CONFIG["Neutral"];

    if (compact) {
        return (
            <span
                className={`inline-flex items-center gap-1 text-[7px] font-black uppercase tracking-wider px-1.5 py-0.5 rounded border ${cfg.color} ${cfg.bg} ${cfg.border}`}
                title={`${environment}${score != null ? ` (${score.toFixed(0)})` : ""}`}
            >
                {cfg.icon}
                {cfg.short}
            </span>
        );
    }

    return (
        <span
            className={`inline-flex items-center gap-1.5 text-[8px] font-black uppercase tracking-wider px-2 py-1 rounded-md border ${cfg.color} ${cfg.bg} ${cfg.border}`}
        >
            {cfg.icon}
            <span>{cfg.short}</span>
            {score != null && (
                <span className="font-mono text-[9px] opacity-80">{score.toFixed(0)}</span>
            )}
        </span>
    );
}
