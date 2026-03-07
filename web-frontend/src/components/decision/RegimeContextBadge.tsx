"use client";

/**
 * RegimeContextBadge.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Displays the current market regime context as a compact institutional badge.
 * Shows regime label + descriptive icon with semantic coloring.
 */

import { TrendingUp, TrendingDown, Minus, Waves, AlertTriangle } from "lucide-react";

interface RegimeContextBadgeProps {
    regime?: string | null;
    className?: string;
}

const REGIME_MAP: Record<string, { label: string; color: string; bg: string; border: string; icon: React.ReactNode }> = {
    bull: { label: "Bull Market", color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/25", icon: <TrendingUp size={12} /> },
    bullish: { label: "Bullish", color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/25", icon: <TrendingUp size={12} /> },
    bear: { label: "Bear Market", color: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/25", icon: <TrendingDown size={12} /> },
    bearish: { label: "Bearish", color: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/25", icon: <TrendingDown size={12} /> },
    sideways: { label: "Sideways", color: "text-yellow-400", bg: "bg-yellow-500/10", border: "border-yellow-500/25", icon: <Minus size={12} /> },
    neutral: { label: "Neutral", color: "text-gray-400", bg: "bg-gray-500/10", border: "border-gray-500/25", icon: <Minus size={12} /> },
    volatile: { label: "High Volatility", color: "text-orange-400", bg: "bg-orange-500/10", border: "border-orange-500/25", icon: <Waves size={12} /> },
    crisis: { label: "Crisis", color: "text-red-500", bg: "bg-red-500/15", border: "border-red-500/30", icon: <AlertTriangle size={12} /> },
};

export default function RegimeContextBadge({ regime, className = "" }: RegimeContextBadgeProps) {
    if (!regime) return null;

    const key = regime.toLowerCase().replace(/[_\s-]+/g, "");
    const cfg = Object.entries(REGIME_MAP).find(([k]) => key.includes(k))?.[1]
        ?? { label: regime, color: "text-gray-400", bg: "bg-gray-500/10", border: "border-gray-500/25", icon: <Minus size={12} /> };

    return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-black uppercase tracking-wider border ${cfg.color} ${cfg.bg} ${cfg.border} ${className}`}>
            {cfg.icon}
            {cfg.label}
        </span>
    );
}
