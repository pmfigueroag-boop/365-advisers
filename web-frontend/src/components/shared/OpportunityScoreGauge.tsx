"use client";

/**
 * OpportunityScoreGauge.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Reusable circular gauge for displaying opportunity scores (0-10).
 * Used in Terminal, Ideas, and Deep Analysis views.
 */

interface OpportunityScoreGaugeProps {
    score: number;
    max?: number;
    size?: number;
    label?: string;
    showLabel?: boolean;
    className?: string;
}

export default function OpportunityScoreGauge({
    score,
    max = 10,
    size = 90,
    label = "Opportunity",
    showLabel = true,
    className = "",
}: OpportunityScoreGaugeProps) {
    const pct = Math.min(score / max, 1);
    const radius = (size - 10) / 2;
    const circumference = 2 * Math.PI * radius;
    const strokeDashoffset = circumference * (1 - pct);

    // Color based on score
    const color = score >= 7 ? "#00d4aa" : score >= 5 ? "#d4af37" : score >= 3 ? "#f59e0b" : "#ff4757";
    const bgGlow = score >= 7 ? "shadow-emerald-500/15" : score >= 5 ? "shadow-yellow-500/10" : "shadow-orange-500/10";

    return (
        <div className={`flex flex-col items-center gap-1.5 ${className}`}>
            <div className={`relative shadow-lg ${bgGlow} rounded-full`}>
                <svg width={size} height={size} className="-rotate-90">
                    {/* Background track */}
                    <circle
                        cx={size / 2}
                        cy={size / 2}
                        r={radius}
                        fill="none"
                        stroke="#21262d"
                        strokeWidth={4}
                    />
                    {/* Score arc */}
                    <circle
                        cx={size / 2}
                        cy={size / 2}
                        r={radius}
                        fill="none"
                        stroke={color}
                        strokeWidth={4}
                        strokeLinecap="round"
                        strokeDasharray={circumference}
                        strokeDashoffset={strokeDashoffset}
                        style={{ transition: "stroke-dashoffset 1s ease, stroke 0.5s ease" }}
                    />
                </svg>
                {/* Center value */}
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className="font-black text-white" style={{ fontSize: size * 0.28, fontFamily: "var(--font-data)", color }}>
                        {score.toFixed(1)}
                    </span>
                    <span className="text-gray-600" style={{ fontSize: Math.max(7, size * 0.09) }}>
                        / {max}
                    </span>
                </div>
            </div>
            {showLabel && (
                <span className="text-[9px] font-black uppercase tracking-widest text-gray-500">{label}</span>
            )}
        </div>
    );
}
