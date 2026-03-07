"use client";

/**
 * ScenarioAnalysisPanel.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Bull / Base / Bear scenario projections for the portfolio.
 */

import { GitBranch, TrendingUp, Minus, TrendingDown } from "lucide-react";

interface ScenarioPanelProps {
    bullReturn?: number;
    baseReturn?: number;
    bearReturn?: number;
    className?: string;
}

interface ScenarioRowProps {
    label: string;
    value: number;
    icon: React.ReactNode;
    color: string;
    barColor: string;
}

function ScenarioRow({ label, value, icon, color, barColor }: ScenarioRowProps) {
    const abs = Math.abs(value);
    const maxRange = 30; // visual scale
    const barWidth = Math.min((abs / maxRange) * 100, 100);

    return (
        <div className="flex items-center gap-3 p-3 bg-[#161b22] rounded-xl border border-[#30363d]">
            <span className={`flex-shrink-0 ${color}`}>{icon}</span>
            <div className="flex-1">
                <p className="text-[9px] font-black uppercase tracking-wider text-gray-500 mb-1">{label}</p>
                <div className="w-full bg-[#0d1117] rounded-full h-1.5 overflow-hidden">
                    <div
                        className={`h-full rounded-full ${barColor} transition-all duration-500`}
                        style={{ width: `${barWidth}%` }}
                    />
                </div>
            </div>
            <span className={`text-sm font-black ${color}`} style={{ fontFamily: "var(--font-data)" }}>
                {value >= 0 ? "+" : ""}{value.toFixed(1)}%
            </span>
        </div>
    );
}

export default function ScenarioAnalysisPanel({ bullReturn, baseReturn, bearReturn, className = "" }: ScenarioPanelProps) {
    return (
        <div className={`glass-card p-5 border-[#30363d] ${className}`}>
            <div className="flex items-center gap-2 mb-4">
                <GitBranch size={12} className="text-[#d4af37]" />
                <span className="text-[9px] font-black uppercase tracking-widest text-gray-400">Scenario Analysis</span>
            </div>

            <div className="space-y-2.5">
                {bullReturn != null && (
                    <ScenarioRow label="Bull Case" value={bullReturn} icon={<TrendingUp size={14} />} color="text-green-400" barColor="bg-green-500" />
                )}
                {baseReturn != null && (
                    <ScenarioRow label="Base Case" value={baseReturn} icon={<Minus size={14} />} color="text-blue-400" barColor="bg-blue-500" />
                )}
                {bearReturn != null && (
                    <ScenarioRow label="Bear Case" value={bearReturn} icon={<TrendingDown size={14} />} color="text-red-400" barColor="bg-red-500" />
                )}
            </div>

            {bullReturn == null && baseReturn == null && bearReturn == null && (
                <p className="text-xs text-gray-600 text-center py-4">No scenario data available</p>
            )}
        </div>
    );
}
