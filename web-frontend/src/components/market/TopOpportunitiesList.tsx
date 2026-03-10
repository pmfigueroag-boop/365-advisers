"use client";

/**
 * TopOpportunitiesList.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Ranked list of top investment opportunities from the Ranking Engine.
 */

import { Trophy, TrendingUp } from "lucide-react";
import SignalBadge from "@/components/shared/SignalBadge";
import InfoTooltip from "@/components/shared/InfoTooltip";
import type { RankedItem } from "@/hooks/useMarketRadar";

interface TopOpportunitiesListProps {
    items: RankedItem[];
    onSelect?: (ticker: string) => void;
    limit?: number;
    className?: string;
}

function tierBadge(tier: string) {
    if (tier === "top") return "text-[#d4af37] bg-[#d4af37]/10 border-[#d4af37]/30";
    if (tier === "strong") return "text-green-400 bg-green-500/10 border-green-500/30";
    if (tier === "moderate") return "text-blue-400 bg-blue-500/10 border-blue-500/30";
    return "text-gray-400 bg-gray-500/10 border-gray-500/30";
}

export default function TopOpportunitiesList({ items, onSelect, limit = 10, className = "" }: TopOpportunitiesListProps) {
    const display = items.slice(0, limit);

    if (display.length === 0) {
        return (
            <div className={`glass-card p-5 border-[#30363d] ${className}`}>
                <div className="flex items-center gap-2 mb-3">
                    <Trophy size={12} className="text-[#d4af37]" />
                    <InfoTooltip text="Ranking of the best investment opportunities by composite score (fundamental + technical + alpha signals). Click an asset to analyze it." position="bottom">
                        <span className="text-[9px] font-black uppercase tracking-widest text-gray-400">Top Opportunities</span>
                    </InfoTooltip>
                </div>
                <p className="text-xs text-gray-600">Compute a ranking to see top opportunities.</p>
            </div>
        );
    }

    return (
        <div className={`glass-card p-5 border-[#30363d] ${className}`}>
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <Trophy size={12} className="text-[#d4af37]" />
                    <InfoTooltip text="Ranking of the best investment opportunities by composite score (fundamental + technical + alpha signals). Click an asset to analyze it." position="bottom">
                        <span className="text-[9px] font-black uppercase tracking-widest text-gray-400">Top Opportunities</span>
                    </InfoTooltip>
                </div>
                <span className="text-[8px] font-mono text-gray-600">{items.length} ranked</span>
            </div>

            <div className="space-y-1">
                {display.map((item, i) => (
                    <button
                        key={`${item.ticker}-${item.idea_type}-${i}`}
                        onClick={() => onSelect?.(item.ticker)}
                        className="w-full flex items-center gap-3 p-2.5 rounded-lg hover:bg-[#161b22] transition-colors group"
                    >
                        {/* Rank */}
                        <span className={`text-[11px] font-black w-5 text-center ${i < 3 ? "text-[#d4af37]" : "text-gray-600"}`}>
                            {item.rank ?? i + 1}
                        </span>

                        {/* Ticker + Name */}
                        <div className="flex-1 min-w-0 text-left">
                            <div className="flex items-center gap-2">
                                <span className="text-xs font-black text-white group-hover:text-[#d4af37] transition-colors" style={{ fontFamily: "var(--font-data)" }}>
                                    {item.ticker}
                                </span>
                                <span className={`text-[7px] font-black px-1.5 py-0.5 rounded border uppercase ${tierBadge(item.tier)}`}>
                                    {item.tier}
                                </span>
                            </div>
                            <p className="text-[9px] text-gray-600 truncate">{item.name ?? item.sector}</p>
                        </div>

                        {/* Score */}
                        <div className="text-right flex-shrink-0">
                            <p className="text-xs font-black text-white" style={{ fontFamily: "var(--font-data)" }}>
                                {(item.composite_score ?? (item as any).uos ?? 0).toFixed(1)}
                            </p>
                            <p className="text-[8px] text-gray-600">{item.idea_type}</p>
                        </div>

                        {/* Allocation */}
                        <div className="flex-shrink-0 w-12 text-right">
                            <p className="text-[10px] font-mono text-[#d4af37] font-bold">
                                {(item.suggested_allocation ?? (item as any).suggested_alloc_pct ?? 0).toFixed(1)}%
                            </p>
                        </div>
                    </button>
                ))}
            </div>
        </div>
    );
}
