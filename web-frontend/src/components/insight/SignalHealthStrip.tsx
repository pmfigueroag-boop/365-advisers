"use client";

/**
 * SignalHealthStrip.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Compact horizontal strip showing overall signal health, CASE score,
 * and active category count. Designed for the Terminal sidebar.
 */

import { Activity, Gauge, Layers, Clock } from "lucide-react";
import type { SignalProfileResponse } from "@/hooks/useAlphaSignals";

interface SignalHealthStripProps {
    profile: SignalProfileResponse | null;
    className?: string;
}

export default function SignalHealthStrip({ profile, className = "" }: SignalHealthStripProps) {
    if (!profile) return null;

    const firedPct = profile.total_signals > 0
        ? Math.round((profile.fired_signals / profile.total_signals) * 100)
        : 0;

    const caseScore = profile.composite_alpha?.score ?? null;
    const environment = profile.composite_alpha?.environment ?? null;
    const activeCats = profile.composite_alpha?.active_categories ?? 0;
    const decay = profile.composite_alpha?.decay;

    const healthLevel = firedPct >= 60 ? "Good" : firedPct >= 40 ? "Moderate" : "Low";
    const healthColor = firedPct >= 60 ? "text-green-400" : firedPct >= 40 ? "text-yellow-400" : "text-red-400";
    const barColor = firedPct >= 60 ? "from-green-500 to-emerald-400" : firedPct >= 40 ? "from-yellow-500 to-amber-400" : "from-red-500 to-rose-400";

    return (
        <div className={`glass-card p-4 border-[#30363d] space-y-4 ${className}`}>
            <div className="flex items-center gap-2 mb-1">
                <Activity size={12} className="text-emerald-400" />
                <span className="text-[10px] font-black uppercase tracking-widest text-gray-400">
                    Signal Health
                </span>
            </div>

            {/* Overall health */}
            <div>
                <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[9px] text-gray-600 uppercase">Overall</span>
                    <span className={`text-[10px] font-black ${healthColor}`}>{healthLevel}</span>
                </div>
                <div className="w-full bg-[#161b22] rounded-full h-1.5 overflow-hidden">
                    <div
                        className={`h-full rounded-full bg-gradient-to-r ${barColor} transition-all duration-700`}
                        style={{ width: `${firedPct}%` }}
                    />
                </div>
                <p className="text-[9px] font-mono text-gray-600 mt-1">
                    {profile.fired_signals}/{profile.total_signals} signals active ({firedPct}%)
                </p>
            </div>

            {/* CASE Score */}
            {caseScore != null && (
                <div>
                    <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center gap-1.5">
                            <Gauge size={10} className="text-[#d4af37]" />
                            <span className="text-[9px] text-gray-600 uppercase">CASE</span>
                        </div>
                        <span className="text-sm font-black font-mono text-[#d4af37]">
                            {caseScore.toFixed(0)}
                        </span>
                    </div>
                    <div className="w-full bg-[#161b22] rounded-full h-1.5 overflow-hidden">
                        <div
                            className="h-full rounded-full bg-gradient-to-r from-[#d4af37] to-[#e8c84a] transition-all duration-700"
                            style={{ width: `${Math.min(caseScore, 100)}%` }}
                        />
                    </div>
                    {environment && (
                        <p className="text-[9px] font-mono text-gray-600 mt-1 capitalize">
                            Environment: {environment}
                        </p>
                    )}
                </div>
            )}

            {/* Active categories */}
            {activeCats > 0 && (
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                        <Layers size={10} className="text-blue-400" />
                        <span className="text-[9px] text-gray-600 uppercase">Categories</span>
                    </div>
                    <span className="text-[10px] font-mono font-bold text-gray-300">
                        {activeCats} active
                    </span>
                </div>
            )}

            {/* Freshness */}
            {decay && (
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                        <Clock size={10} className="text-purple-400" />
                        <span className="text-[9px] text-gray-600 uppercase">Freshness</span>
                    </div>
                    <span className={`text-[10px] font-black uppercase ${decay.freshness_level === "fresh" ? "text-green-400" :
                        decay.freshness_level === "aging" ? "text-yellow-400" :
                            decay.freshness_level === "stale" ? "text-orange-400" : "text-red-400"
                        }`}>
                        {decay.freshness_level}
                    </span>
                </div>
            )}
        </div>
    );
}
