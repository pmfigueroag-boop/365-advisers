"use client";

/**
 * ScoreRing.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Small circular score indicator. Extracted from VerdictHero for reuse.
 */

interface ScoreRingProps {
    value: number;
    max?: number;
    size?: number;
    label: string;
    color?: string;
}

export default function ScoreRing({ value, max = 10, size = 56, label, color }: ScoreRingProps) {
    const pct = Math.min(value / max, 1);
    const r = (size - 6) / 2;
    const c = 2 * Math.PI * r;
    const offset = c * (1 - pct);

    const autoColor = value / max >= 0.7 ? "#22c55e" : value / max >= 0.4 ? "#d4af37" : "#ef4444";
    const strokeColor = color ?? autoColor;

    return (
        <div className="flex flex-col items-center gap-1">
            <div className="relative">
                <svg width={size} height={size} className="-rotate-90">
                    <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#21262d" strokeWidth={3} />
                    <circle
                        cx={size / 2} cy={size / 2} r={r}
                        fill="none" stroke={strokeColor} strokeWidth={3}
                        strokeLinecap="round"
                        strokeDasharray={c} strokeDashoffset={offset}
                        style={{ transition: "stroke-dashoffset 0.8s ease" }}
                    />
                </svg>
                <span
                    className="absolute inset-0 flex items-center justify-center font-black"
                    style={{ fontSize: size * 0.3, fontFamily: "var(--font-data)", color: strokeColor }}
                >
                    {value.toFixed(1)}
                </span>
            </div>
            <span className="text-[8px] font-black uppercase tracking-widest text-gray-600">{label}</span>
        </div>
    );
}
