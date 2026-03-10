"use client";

/**
 * SectorHeatmap.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Horizontal bar chart showing sector opportunity scores.
 */

import { BarChart3 } from "lucide-react";
import InfoTooltip from "@/components/shared/InfoTooltip";
import type { RankedItem } from "@/hooks/useMarketRadar";

interface SectorHeatmapProps {
    globalRanking: RankedItem[];
    onSectorClick?: (sector: string) => void;
    className?: string;
}

interface SectorData {
    sector: string;
    avgScore: number;
    count: number;
}

export default function SectorHeatmap({ globalRanking, onSectorClick, className = "" }: SectorHeatmapProps) {
    // Aggregate by sector
    const sectorMap: Record<string, { total: number; count: number }> = {};
    for (const item of globalRanking) {
        const s = item.sector || "Unknown";
        if (!sectorMap[s]) sectorMap[s] = { total: 0, count: 0 };
        sectorMap[s].total += (item.composite_score ?? (item as any).uos ?? 0);
        sectorMap[s].count += 1;
    }

    const sectors: SectorData[] = Object.entries(sectorMap)
        .map(([sector, { total, count }]) => ({ sector, avgScore: total / count, count }))
        .sort((a, b) => b.avgScore - a.avgScore)
        .slice(0, 10);

    const maxScore = Math.max(...sectors.map((s) => s.avgScore), 1);

    function barColor(score: number) {
        const pct = score / maxScore;
        if (pct >= 0.75) return "from-emerald-500 to-green-400";
        if (pct >= 0.50) return "from-blue-500 to-cyan-400";
        if (pct >= 0.25) return "from-yellow-500 to-amber-400";
        return "from-red-500 to-rose-400";
    }

    if (sectors.length === 0) {
        return (
            <div className={`glass-card p-5 border-[#30363d] ${className}`}>
                <div className="flex items-center gap-2 mb-3">
                    <BarChart3 size={12} className="text-[#d4af37]" />
                    <InfoTooltip text="Average opportunity score by sector. Identifies sectors with the best investment opportunities in your universe." position="bottom">
                        <span className="text-[9px] font-black uppercase tracking-widest text-gray-400">Sector Opportunities</span>
                    </InfoTooltip>
                </div>
                <p className="text-xs text-gray-600">No ranking data. Run a scan first.</p>
            </div>
        );
    }

    return (
        <div className={`glass-card p-5 border-[#30363d] ${className}`}>
            <div className="flex items-center gap-2 mb-4">
                <BarChart3 size={12} className="text-[#d4af37]" />
                <span className="text-[9px] font-black uppercase tracking-widest text-gray-400">Sector Opportunities</span>
            </div>

            <div className="space-y-2.5">
                {sectors.map((s) => (
                    <button
                        key={s.sector}
                        onClick={() => onSectorClick?.(s.sector)}
                        className="w-full flex items-center gap-3 group hover:bg-[#161b22] p-1 -mx-1 rounded transition-colors"
                    >
                        <span className="text-[10px] text-gray-400 w-20 text-right truncate group-hover:text-gray-200 transition-colors">
                            {s.sector}
                        </span>
                        <div className="flex-1 bg-[#161b22] rounded-full h-2 overflow-hidden">
                            <div
                                className={`h-full rounded-full bg-gradient-to-r ${barColor(s.avgScore)} transition-all duration-500`}
                                style={{ width: `${(s.avgScore / maxScore) * 100}%` }}
                            />
                        </div>
                        <span className="text-[10px] font-mono font-bold text-gray-300 w-8 text-right">
                            {s.avgScore.toFixed(1)}
                        </span>
                        <span className="text-[8px] text-gray-600 w-4">({s.count})</span>
                    </button>
                ))}
            </div>
        </div>
    );
}
