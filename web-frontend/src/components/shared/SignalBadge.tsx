"use client";

/**
 * SignalBadge.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Compact signal badge (BUY / SELL / HOLD / NEUTRAL) with semantic coloring.
 * Extracted from AnalysisWidgets for reuse across the app.
 */

interface SignalBadgeProps {
    signal: string;
    size?: "xs" | "sm" | "md";
    className?: string;
}

const SIGNAL_CONFIG: Record<string, { color: string; bg: string; border: string }> = {
    BUY: { color: "text-green-400", bg: "bg-green-500/12", border: "border-green-500/30" },
    "STRONG BUY": { color: "text-green-300", bg: "bg-green-500/15", border: "border-green-500/40" },
    SELL: { color: "text-red-400", bg: "bg-red-500/12", border: "border-red-500/30" },
    "STRONG SELL": { color: "text-red-300", bg: "bg-red-500/15", border: "border-red-500/40" },
    HOLD: { color: "text-yellow-400", bg: "bg-yellow-500/12", border: "border-yellow-500/30" },
    NEUTRAL: { color: "text-gray-400", bg: "bg-gray-500/12", border: "border-gray-500/30" },
};

const SIZE_CLASSES = {
    xs: "text-[7px] px-1 py-0.5",
    sm: "text-[8px] px-1.5 py-0.5",
    md: "text-[9px] px-2 py-0.5",
};

export default function SignalBadge({ signal, size = "sm", className = "" }: SignalBadgeProps) {
    const key = signal.toUpperCase();
    const cfg = SIGNAL_CONFIG[key] ?? SIGNAL_CONFIG.NEUTRAL;

    return (
        <span className={`inline-flex items-center font-black uppercase tracking-wider rounded border ${cfg.color} ${cfg.bg} ${cfg.border} ${SIZE_CLASSES[size]} ${className}`}>
            {key}
        </span>
    );
}
