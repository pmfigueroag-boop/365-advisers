"use client";

/**
 * AllocationChart.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Visual Core/Satellite allocation chart for Portfolio Intelligence.
 */

import { PieChart, Target } from "lucide-react";

interface AllocationEntry {
    ticker: string;
    allocation: number;
    type: "core" | "satellite";
}

interface AllocationChartProps {
    entries: AllocationEntry[];
    className?: string;
}

function allocationColor(type: string, idx: number) {
    if (type === "core") {
        const coreColors = ["bg-[#d4af37]", "bg-[#b8962e]", "bg-[#9a7d26]", "bg-[#7c641e]"];
        return coreColors[idx % coreColors.length];
    }
    const satColors = ["bg-blue-500", "bg-cyan-500", "bg-purple-500", "bg-pink-500"];
    return satColors[idx % satColors.length];
}

export default function AllocationChart({ entries, className = "" }: AllocationChartProps) {
    const totalAllocation = entries.reduce((sum, e) => sum + e.allocation, 0);
    const coreEntries = entries.filter((e) => e.type === "core");
    const satEntries = entries.filter((e) => e.type === "satellite");
    const cashReserve = Math.max(0, 100 - totalAllocation);

    if (entries.length === 0) {
        return (
            <div className={`glass-card p-5 border-[#30363d] ${className}`}>
                <div className="flex items-center gap-2 mb-3">
                    <PieChart size={12} className="text-[#d4af37]" />
                    <span className="text-[9px] font-black uppercase tracking-widest text-gray-400">Allocation</span>
                </div>
                <p className="text-xs text-gray-600 text-center py-8">No positions configured</p>
            </div>
        );
    }

    return (
        <div className={`glass-card p-5 border-[#30363d] ${className}`}>
            <div className="flex items-center gap-2 mb-4">
                <PieChart size={12} className="text-[#d4af37]" />
                <span className="text-[9px] font-black uppercase tracking-widest text-gray-400">Core / Satellite Allocation</span>
            </div>

            {/* Allocation bar */}
            <div className="w-full h-6 rounded-full bg-[#161b22] overflow-hidden flex mb-4">
                {entries.map((e, i) => (
                    <div
                        key={e.ticker}
                        className={`h-full ${allocationColor(e.type, i)} transition-all duration-500`}
                        style={{ width: `${e.allocation}%` }}
                        title={`${e.ticker}: ${e.allocation.toFixed(1)}%`}
                    />
                ))}
                {cashReserve > 0 && (
                    <div
                        className="h-full bg-[#30363d]"
                        style={{ width: `${cashReserve}%` }}
                        title={`Cash: ${cashReserve.toFixed(1)}%`}
                    />
                )}
            </div>

            {/* Legend */}
            <div className="grid grid-cols-2 gap-4">
                {/* Core */}
                <div>
                    <div className="flex items-center gap-1.5 mb-2">
                        <Target size={10} className="text-[#d4af37]" />
                        <span className="text-[8px] font-black uppercase tracking-widest text-gray-500">Core</span>
                        <span className="text-[8px] font-mono text-gray-600 ml-auto">
                            {coreEntries.reduce((s, e) => s + e.allocation, 0).toFixed(1)}%
                        </span>
                    </div>
                    <div className="space-y-1.5">
                        {coreEntries.map((e, i) => (
                            <div key={e.ticker} className="flex items-center gap-2">
                                <span className={`w-2 h-2 rounded-full ${allocationColor("core", i)}`} />
                                <span className="text-[10px] font-bold text-gray-300">{e.ticker}</span>
                                <span className="text-[9px] font-mono text-gray-500 ml-auto">{e.allocation.toFixed(1)}%</span>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Satellite */}
                <div>
                    <div className="flex items-center gap-1.5 mb-2">
                        <Target size={10} className="text-blue-400" />
                        <span className="text-[8px] font-black uppercase tracking-widest text-gray-500">Satellite</span>
                        <span className="text-[8px] font-mono text-gray-600 ml-auto">
                            {satEntries.reduce((s, e) => s + e.allocation, 0).toFixed(1)}%
                        </span>
                    </div>
                    <div className="space-y-1.5">
                        {satEntries.map((e, i) => (
                            <div key={e.ticker} className="flex items-center gap-2">
                                <span className={`w-2 h-2 rounded-full ${allocationColor("satellite", i)}`} />
                                <span className="text-[10px] font-bold text-gray-300">{e.ticker}</span>
                                <span className="text-[9px] font-mono text-gray-500 ml-auto">{e.allocation.toFixed(1)}%</span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Total */}
            <div className="flex items-center justify-between mt-4 pt-3 border-t border-[#30363d]">
                <span className="text-[9px] text-gray-600">Total Allocated</span>
                <span className="text-sm font-black text-white" style={{ fontFamily: "var(--font-data)" }}>
                    {totalAllocation.toFixed(1)}%
                </span>
            </div>
        </div>
    );
}
