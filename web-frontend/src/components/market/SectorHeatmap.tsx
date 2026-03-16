"use client";

/**
 * SectorHeatmap.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Horizontal bar chart showing sector opportunity scores.
 * P1 Fix: Single gold-based color scale + average marker + legend.
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
    const avgScore = sectors.length > 0
        ? sectors.reduce((sum, s) => sum + s.avgScore, 0) / sectors.length
        : 0;

    // Single gold-based bar color with opacity variation
    function barOpacity(score: number) {
        const pct = score / maxScore;
        return Math.max(0.3, pct);
    }

    if (sectors.length === 0) {
        return (
            <div className={`glass-card p-5 border-[#30363d] ${className}`}>
                <div className="flex items-center gap-2 mb-3">
                    <BarChart3 size={12} className="text-[#d4af37]" />
                    <InfoTooltip text="Average opportunity score by sector. Identifies sectors with the best investment opportunities in your universe." position="bottom">
                        <span className="text-[10px] font-black uppercase tracking-widest text-gray-400">Sector Opportunities</span>
                    </InfoTooltip>
                </div>
                <p className="text-xs text-gray-600">No ranking data. Run a scan first.</p>
            </div>
        );
    }

    return (
        <div className={`glass-card p-5 border-[#30363d] ${className}`}>
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <BarChart3 size={12} className="text-[#d4af37]" />
                    <span className="text-[10px] font-black uppercase tracking-widest text-gray-400">Sector Opportunities</span>
                </div>
                {/* Legend */}
                <div className="flex items-center gap-3 text-[10px] text-gray-500">
                    <span className="flex items-center gap-1">
                        <span className="w-2 h-2 rounded-sm" style={{ background: 'rgba(212, 175, 55, 0.5)' }} />
                        Score
                    </span>
                    <span className="flex items-center gap-1">
                        <span className="w-3 h-px bg-[#d4af37]/60" style={{ borderTop: '1px dashed rgba(212,175,55,0.6)' }} />
                        Avg
                    </span>
                </div>
            </div>

            <div className="space-y-2.5">
                {sectors.map((s) => (
                    <button
                        key={s.sector}
                        onClick={() => onSectorClick?.(s.sector)}
                        className="w-full flex items-center gap-3 group hover:bg-[#161b22] p-1 -mx-1 rounded transition-colors"
                    >
                        <span className="text-[11px] text-gray-400 w-24 text-right truncate group-hover:text-gray-200 transition-colors">
                            {s.sector}
                        </span>
                        <div className="flex-1 bg-[#161b22] rounded-full h-2.5 overflow-hidden relative">
                            {/* Average marker */}
                            <div
                                className="absolute top-0 bottom-0 w-px z-10"
                                style={{
                                    left: `${(avgScore / maxScore) * 100}%`,
                                    borderLeft: '1px dashed rgba(212,175,55,0.5)',
                                }}
                            />
                            {/* Score bar */}
                            <div
                                className="h-full rounded-full transition-all duration-500"
                                style={{
                                    width: `${(s.avgScore / maxScore) * 100}%`,
                                    background: `rgba(212, 175, 55, ${barOpacity(s.avgScore)})`,
                                }}
                            />
                        </div>
                        <span className="text-[11px] font-mono font-bold text-gray-300 w-8 text-right tabular-nums">
                            {s.avgScore.toFixed(1)}
                        </span>
                        <span className="text-[10px] text-gray-600 w-5 tabular-nums">({s.count})</span>
                    </button>
                ))}
            </div>

            {/* Bottom scale */}
            <div className="flex items-center justify-between mt-3 pt-2 border-t border-[#30363d]/50">
                <span className="text-[10px] text-gray-600">0</span>
                <span className="text-[10px] text-[#d4af37]/60 font-mono">◆ Avg: {avgScore.toFixed(1)}</span>
                <span className="text-[10px] text-gray-600">{maxScore.toFixed(1)}</span>
            </div>
        </div>
    );
}
