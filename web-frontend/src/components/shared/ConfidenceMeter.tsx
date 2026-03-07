"use client";

/**
 * ConfidenceMeter.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Compact horizontal confidence meter bar with percentage label.
 * Reusable across Terminal, Ideas, and Deep Analysis views.
 */

interface ConfidenceMeterProps {
    value: number;        // 0-100
    label?: string;
    size?: "sm" | "md";
    className?: string;
}

export default function ConfidenceMeter({
    value,
    label = "Confidence",
    size = "md",
    className = "",
}: ConfidenceMeterProps) {
    const pct = Math.min(Math.max(value, 0), 100);

    const barColor = pct >= 75
        ? "from-emerald-500 to-green-400"
        : pct >= 50
            ? "from-blue-500 to-cyan-400"
            : pct >= 25
                ? "from-yellow-500 to-amber-400"
                : "from-red-500 to-rose-400";

    const textColor = pct >= 75
        ? "text-emerald-400"
        : pct >= 50
            ? "text-blue-400"
            : pct >= 25
                ? "text-yellow-400"
                : "text-red-400";

    const isSm = size === "sm";

    return (
        <div className={`${className}`}>
            <div className="flex items-center justify-between mb-1">
                <span className={`font-black uppercase tracking-widest text-gray-500 ${isSm ? "text-[8px]" : "text-[9px]"}`}>
                    {label}
                </span>
                <span className={`font-black font-mono ${textColor} ${isSm ? "text-[9px]" : "text-[11px]"}`}>
                    {pct.toFixed(0)}%
                </span>
            </div>
            <div className={`w-full bg-[#161b22] rounded-full overflow-hidden ${isSm ? "h-1" : "h-1.5"}`}>
                <div
                    className={`h-full rounded-full bg-gradient-to-r ${barColor} transition-all duration-700`}
                    style={{ width: `${pct}%` }}
                />
            </div>
        </div>
    );
}
