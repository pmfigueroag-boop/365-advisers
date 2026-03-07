"use client";

/**
 * KeyCatalystsPanel.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Displays key catalysts and risks from the CIO memo.
 */

import { Zap, AlertTriangle } from "lucide-react";
import type { CIOMemo } from "@/hooks/useCombinedStream";

interface KeyCatalystsPanelProps {
    cioMemo: CIOMemo | null;
    className?: string;
}

export default function KeyCatalystsPanel({ cioMemo, className = "" }: KeyCatalystsPanelProps) {
    if (!cioMemo) return null;

    const catalysts = cioMemo.key_catalysts ?? [];
    const risks = cioMemo.key_risks ?? [];

    if (catalysts.length === 0 && risks.length === 0) return null;

    return (
        <div className={`glass-card p-5 border-[#30363d] ${className}`}>
            {/* Catalysts */}
            {catalysts.length > 0 && (
                <div className="mb-4">
                    <div className="flex items-center gap-2 mb-3">
                        <Zap size={12} className="text-emerald-400" />
                        <span className="text-[9px] font-black uppercase tracking-widest text-gray-400">
                            Key Catalysts
                        </span>
                    </div>
                    <div className="space-y-2">
                        {catalysts.map((cat, i) => (
                            <div key={i} className="flex items-start gap-2">
                                <span className="text-emerald-500 mt-0.5 text-[10px]">●</span>
                                <p className="text-[11px] text-gray-300 leading-relaxed">{cat}</p>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Risks */}
            {risks.length > 0 && (
                <div className={catalysts.length > 0 ? "pt-3 border-t border-[#30363d]" : ""}>
                    <div className="flex items-center gap-2 mb-3">
                        <AlertTriangle size={12} className="text-red-400" />
                        <span className="text-[9px] font-black uppercase tracking-widest text-gray-400">
                            Key Risks
                        </span>
                    </div>
                    <div className="space-y-2">
                        {risks.map((risk, i) => (
                            <div key={i} className="flex items-start gap-2">
                                <span className="text-red-500 mt-0.5 text-[10px]">●</span>
                                <p className="text-[11px] text-gray-400 leading-relaxed">{risk}</p>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
