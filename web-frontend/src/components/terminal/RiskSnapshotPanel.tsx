"use client";

/**
 * RiskSnapshotPanel.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Compact risk summary: risk level, crowding, volatility context.
 */

import { Shield, AlertTriangle, Activity, BarChart3 } from "lucide-react";
import type { PositionSizing } from "@/hooks/useCombinedStream";
import type { TechnicalAnalysisResult } from "@/hooks/useTechnicalAnalysis";
import type { CrowdingAssessment } from "@/hooks/useCrowding";

interface RiskSnapshotPanelProps {
    positionSizing: PositionSizing | null;
    technical: TechnicalAnalysisResult | null;
    crowding?: CrowdingAssessment | null;
    className?: string;
}

function riskColor(level: string) {
    const l = level.toLowerCase();
    if (l.includes("low")) return "text-green-400";
    if (l.includes("moderate")) return "text-yellow-400";
    if (l.includes("high")) return "text-orange-400";
    if (l.includes("extreme")) return "text-red-400";
    return "text-gray-400";
}

export default function RiskSnapshotPanel({ positionSizing, technical, crowding, className = "" }: RiskSnapshotPanelProps) {
    const riskLevel = positionSizing?.risk_level ?? null;
    const atrPct = technical?.indicators?.volatility?.atr_pct;
    const crowdingLevel = crowding?.risk_level ?? null;
    const crowdingScore = crowding?.crowding_score ?? null;

    if (!riskLevel && !atrPct && !crowdingLevel) return null;

    return (
        <div className={`glass-card p-5 border-[#30363d] ${className}`}>
            <div className="flex items-center gap-2 mb-4">
                <Shield size={12} className="text-red-400" />
                <span className="text-[9px] font-black uppercase tracking-widest text-gray-400">
                    Risk Snapshot
                </span>
            </div>

            <div className="space-y-3">
                {/* Overall Risk */}
                {riskLevel && (
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5">
                            <AlertTriangle size={10} className="text-gray-600" />
                            <span className="text-[9px] uppercase text-gray-600">Risk Level</span>
                        </div>
                        <span className={`text-[10px] font-black uppercase ${riskColor(riskLevel)}`}>
                            {riskLevel}
                        </span>
                    </div>
                )}

                {/* Crowding */}
                {crowdingLevel && (
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5">
                            <BarChart3 size={10} className="text-gray-600" />
                            <span className="text-[9px] uppercase text-gray-600">Crowding</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className={`text-[10px] font-black uppercase ${riskColor(crowdingLevel)}`}>
                                {crowdingLevel}
                            </span>
                            {crowdingScore != null && (
                                <span className="text-[8px] font-mono text-gray-600">({crowdingScore.toFixed(0)})</span>
                            )}
                        </div>
                    </div>
                )}

                {/* Volatility */}
                {atrPct != null && (
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5">
                            <Activity size={10} className="text-gray-600" />
                            <span className="text-[9px] uppercase text-gray-600">Volatility (ATR)</span>
                        </div>
                        <span className={`text-[10px] font-mono font-bold ${atrPct > 3 ? "text-red-400" : atrPct > 1.5 ? "text-yellow-400" : "text-green-400"}`}>
                            {atrPct.toFixed(2)}%
                        </span>
                    </div>
                )}

                {/* Risk Adjustment */}
                {positionSizing?.risk_adjustment != null && (
                    <div className="flex items-center justify-between">
                        <span className="text-[9px] uppercase text-gray-600">Size Adjustment</span>
                        <span className="text-[10px] font-mono text-gray-400">
                            {positionSizing.risk_adjustment > 0 ? "+" : ""}{(positionSizing.risk_adjustment * 100).toFixed(0)}%
                        </span>
                    </div>
                )}
            </div>
        </div>
    );
}
