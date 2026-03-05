"use client";

import React from "react";
import { Clock, TimerOff, Sparkles, AlertTriangle } from "lucide-react";
import type { DecayInfo } from "@/hooks/useAlphaSignals";

// ── Freshness config ──────────────────────────────────────────────────────────

const FRESHNESS_CONFIG: Record<
    string,
    { label: string; color: string; bg: string; border: string; icon: React.ReactNode; glow: string }
> = {
    fresh: {
        label: "Fresh Signals",
        color: "text-emerald-400",
        bg: "bg-emerald-500/10",
        border: "border-emerald-500/30",
        icon: <Sparkles size={10} />,
        glow: "shadow-[0_0_6px_rgba(52,211,153,0.25)]",
    },
    aging: {
        label: "Aging Signals",
        color: "text-yellow-400",
        bg: "bg-yellow-500/10",
        border: "border-yellow-500/30",
        icon: <Clock size={10} />,
        glow: "shadow-[0_0_6px_rgba(250,204,21,0.20)]",
    },
    stale: {
        label: "Stale Signals",
        color: "text-orange-400",
        bg: "bg-orange-500/10",
        border: "border-orange-500/30",
        icon: <AlertTriangle size={10} />,
        glow: "shadow-[0_0_6px_rgba(251,146,60,0.20)]",
    },
    expired: {
        label: "Expired Signals",
        color: "text-red-400",
        bg: "bg-red-500/10",
        border: "border-red-500/30",
        icon: <TimerOff size={10} />,
        glow: "shadow-[0_0_6px_rgba(248,113,113,0.25)]",
    },
};

// ── Component ─────────────────────────────────────────────────────────────────

interface FreshnessBadgeProps {
    decay: DecayInfo;
    compact?: boolean;
}

export default function FreshnessBadge({ decay, compact = false }: FreshnessBadgeProps) {
    if (!decay.applied) return null;

    const cfg = FRESHNESS_CONFIG[decay.freshness_level] || FRESHNESS_CONFIG.fresh;
    const pct = Math.round(decay.average_freshness * 100);

    if (compact) {
        return (
            <span
                className={`inline-flex items-center gap-0.5 text-[7px] font-bold uppercase px-1.5 py-0.5 rounded border ${cfg.color} ${cfg.bg} ${cfg.border} ${cfg.glow}`}
                title={`Signal Freshness: ${pct}% (${decay.freshness_level})`}
            >
                {cfg.icon}
                {pct}%
            </span>
        );
    }

    return (
        <div
            className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg border transition-all ${cfg.border} ${cfg.bg} ${cfg.glow}`}
        >
            {/* Icon + Label */}
            <div className={`flex items-center gap-1 ${cfg.color}`}>
                {cfg.icon}
                <span className="text-[8px] font-bold uppercase tracking-wider">
                    {cfg.label}
                </span>
            </div>

            {/* Freshness bar */}
            <div className="flex-1 h-1 rounded-full bg-[#30363d] overflow-hidden">
                <div
                    className={`h-full rounded-full transition-all duration-700 ${pct >= 80 ? "bg-emerald-500" :
                            pct >= 50 ? "bg-yellow-500" :
                                pct >= 20 ? "bg-orange-500" :
                                    "bg-red-500"
                        }`}
                    style={{ width: `${pct}%` }}
                />
            </div>

            {/* Percentage */}
            <span className={`text-[10px] font-mono font-black ${cfg.color}`}>
                {pct}%
            </span>

            {/* Expired count */}
            {decay.expired_signals > 0 && (
                <span className="text-[7px] font-bold text-red-400/70 bg-red-500/10 px-1 rounded border border-red-500/20">
                    {decay.expired_signals} expired
                </span>
            )}
        </div>
    );
}
