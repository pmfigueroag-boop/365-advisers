"use client";

/**
 * SignalClusterPanel.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Shows the count of active signals by category cluster.
 */

import { Radio } from "lucide-react";
import InfoTooltip from "@/components/shared/InfoTooltip";
import type { RankedItem } from "@/hooks/useMarketRadar";

interface SignalClusterPanelProps {
    ranking: RankedItem[];
    className?: string;
}

const CLUSTER_COLORS: Record<string, string> = {
    value: "bg-emerald-500",
    quality: "bg-blue-500",
    momentum: "bg-purple-500",
    growth: "bg-rose-500",
    technical: "bg-cyan-500",
    sentiment: "bg-pink-500",
    risk: "bg-orange-500",
    macro: "bg-amber-500",
};

export default function SignalClusterPanel({ ranking, className = "" }: SignalClusterPanelProps) {
    // Count by idea_type (strategy)
    const clusters: Record<string, number> = {};
    for (const item of ranking) {
        const t = (item.idea_type || "unknown").toLowerCase();
        clusters[t] = (clusters[t] ?? 0) + 1;
    }

    const entries = Object.entries(clusters)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 8);

    const maxCount = Math.max(...entries.map(([, c]) => c), 1);

    return (
        <div className={`glass-card p-5 border-[#30363d] ${className}`}>
            <div className="flex items-center gap-2 mb-4">
                <Radio size={12} className="text-purple-400" />
                <InfoTooltip text="Asset grouping by dominant signal type (value, quality, momentum, growth, etc.). Shows which strategies have the most active opportunities." position="bottom">
                    <span className="text-[9px] font-black uppercase tracking-widest text-gray-400">Signal Clusters</span>
                </InfoTooltip>
            </div>

            {entries.length === 0 ? (
                <p className="text-xs text-gray-600">No cluster data available.</p>
            ) : (
                <div className="space-y-2.5">
                    {entries.map(([type, count]) => (
                        <div key={type} className="flex items-center gap-3">
                            <span className={`w-2 h-2 rounded-full flex-shrink-0 ${CLUSTER_COLORS[type] ?? "bg-gray-500"}`} />
                            <span className="text-[10px] text-gray-400 w-20 capitalize truncate">{type}</span>
                            <div className="flex-1 bg-[#161b22] rounded-full h-1.5 overflow-hidden">
                                <div
                                    className={`h-full rounded-full ${CLUSTER_COLORS[type] ?? "bg-gray-500"} transition-all duration-500`}
                                    style={{ width: `${(count / maxCount) * 100}%`, opacity: 0.7 }}
                                />
                            </div>
                            <span className="text-[10px] font-mono font-bold text-gray-300 w-6 text-right">{count}</span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
