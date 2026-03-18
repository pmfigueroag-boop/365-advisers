"use client";

import React from "react";
import { Activity, Target, Network, BoxSelect, AlertTriangle, Radio } from "lucide-react";
import type { SignalProfileResponse } from "@/hooks/useAlphaSignals";
import ScoreHistoryChart from "../ScoreHistoryChart";
import CompositeAlphaGauge from "../CompositeAlphaGauge";
import ResearchMemoInsight from "./ResearchMemoInsight";
import type { MemoInsight } from "./ResearchMemoInsight";

export interface UnifiedEvidenceDashboardProps {
    profile: SignalProfileResponse | null;
    ticker: string;
}

export default function UnifiedEvidenceDashboard({
    profile,
    ticker,
}: UnifiedEvidenceDashboardProps) {
    if (!profile) {
        return (
            <div className="flex flex-col items-center justify-center py-20 text-center gap-2">
                <Radio size={24} className="text-[#30363d]" />
                <p className="text-[10px] text-gray-600 font-mono">No alpha profile available for evidence</p>
            </div>
        );
    }

    const ca = profile.composite_alpha;

    // ── Generate Memo ──────────────────────────────────────────────────────────
    const evidenceMemo: MemoInsight = (() => {
        if (profile.evidence_memo) {
            return {
                title: "Research Memo — Evidence",
                signal: (profile.evidence_memo.signal as "BULLISH" | "BEARISH" | "NEUTRAL") || "NEUTRAL",
                conviction: (profile.evidence_memo.conviction as "HIGH" | "MEDIUM" | "LOW") || "LOW",
                narrative: profile.evidence_memo.narrative,
                bullets: profile.evidence_memo.key_data || [],
                risks: profile.evidence_memo.risk_factors || [],
            };
        }

        // Determistic fallback
        if (!ca) {
            return { title: "Research Memo — Evidence", signal: "NEUTRAL", conviction: "LOW", narrative: "Insufficient data.", bullets: [], risks: [] };
        }

        const caseScore = ca.score;
        const subscores = ca.subscores || {};
        const sortedSubs = Object.entries(subscores).sort((a, b) => (b[1].score ?? 0) - (a[1].score ?? 0));
        const strongest = sortedSubs[0];
        const weakest = sortedSubs[sortedSubs.length - 1];

        const signal: "BULLISH" | "BEARISH" | "NEUTRAL" = caseScore >= 65 ? "BULLISH" : caseScore <= 35 ? "BEARISH" : "NEUTRAL";
        const conviction: "HIGH" | "MEDIUM" | "LOW" = caseScore >= 75 ? "HIGH" : caseScore >= 45 ? "MEDIUM" : "LOW";

        const narrative =
            `CASE Composite Score: ${caseScore.toFixed(0)}/100 (Environment: ${ca.environment}). ` +
            `${ca.active_categories} categorías activas` +
            (ca.convergence_bonus > 0 ? ` con bonus de convergencia +${ca.convergence_bonus.toFixed(1)}.` : ".") +
            (ca.cross_category_conflicts?.length > 0 ? ` ${ca.cross_category_conflicts.length} conflictos detectados.` : "");

        const bullets: string[] = [];
        if (strongest) bullets.push(`Categoría más fuerte: ${strongest[0]} (score ${strongest[1].score?.toFixed(0) ?? "N/A"})`);
        if (weakest && weakest !== strongest) bullets.push(`Categoría más débil: ${weakest[0]} (score ${weakest[1].score?.toFixed(0) ?? "N/A"})`);
        if (ca.convergence_bonus > 0) bullets.push(`Bonus de convergencia: +${ca.convergence_bonus.toFixed(1)} puntos asignados`);

        const risks: string[] = [];
        if (ca.cross_category_conflicts?.length > 0) risks.push(`Conflictos detectados: ${ca.cross_category_conflicts.join(", ")}`);
        if (ca.active_categories <= 2) risks.push("Pocas categorías activas — el score depende de muy pocos factores");
        if (ca.decay && (ca.decay.freshness_level === "stale" || ca.decay.freshness_level === "expired")) {
            risks.push(`Señales con nivel iterativo "${ca.decay.freshness_level}"`);
        }

        return { title: "Research Memo — Evidence", signal, conviction, narrative, bullets, risks };
    })();

    return (
        <div className="space-y-4" style={{ animation: "fadeSlideIn 0.4s ease both" }}>
            
            {/* 1. TOP ROW: Logic Flow & History Chart */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                
                {/* Logic Flow */}
                <div className="glass-card p-5 border border-[#30363d] col-span-1 min-h-[250px] flex flex-col justify-center relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/5 blur-2xl rounded-full" />
                    
                    <h3 className="text-[9px] font-black uppercase tracking-widest text-gray-500 mb-6 absolute top-4 left-5">
                        CASE Factor Evidence Flow
                    </h3>

                    {ca ? (
                        <div className="flex flex-col gap-5 mt-4">
                            <div className="flex items-center gap-4">
                                <div className="w-10 h-10 rounded-full border border-blue-500/20 bg-blue-500/10 flex items-center justify-center shrink-0">
                                    <BoxSelect size={14} className="text-blue-400" />
                                </div>
                                <div>
                                    <p className="text-[9px] text-gray-500 font-black uppercase tracking-widest">Active Categories</p>
                                    <p className="text-xl font-mono font-black text-white">{ca.active_categories} / 8</p>
                                </div>
                            </div>
                            <div className="flex items-center gap-4">
                                <div className="w-10 h-10 rounded-full border border-green-500/20 bg-green-500/10 flex items-center justify-center shrink-0">
                                    <Network size={14} className="text-green-400" />
                                </div>
                                <div>
                                    <p className="text-[9px] text-gray-500 font-black uppercase tracking-widest">Convergence Bonus</p>
                                    <p className="text-xl font-mono font-black text-green-400">+{ca.convergence_bonus.toFixed(1)}</p>
                                </div>
                            </div>
                            <div className="flex items-center gap-4">
                                <div className={`w-10 h-10 rounded-full border flex items-center justify-center shrink-0 ${ca.cross_category_conflicts.length > 0 ? "border-orange-500/20 bg-orange-500/10" : "border-gray-500/20 bg-gray-500/10"}`}>
                                    <AlertTriangle size={14} className={ca.cross_category_conflicts.length > 0 ? "text-orange-400" : "text-gray-500"} />
                                </div>
                                <div>
                                    <p className="text-[9px] text-gray-500 font-black uppercase tracking-widest">Detected Conflicts</p>
                                    <p className={`text-xl font-mono font-black ${ca.cross_category_conflicts.length > 0 ? "text-orange-400" : "text-gray-500"}`}>
                                        {ca.cross_category_conflicts.length}
                                    </p>
                                </div>
                            </div>
                        </div>
                    ) : (
                        <p className="text-xs text-center text-gray-500">Wait for CASE synthesis...</p>
                    )}
                </div>

                {/* Score History Chart */}
                <div className="glass-card flex flex-col md:col-span-2 border border-[#30363d] min-h-[250px] relative overflow-hidden">
                    {/* The ScoreHistoryChart naturally brings its own padding and titles. We wrap it or just render it. */}
                    {ticker && (
                        <div className="h-full w-full absolute inset-0">
                            <ScoreHistoryChart ticker={ticker} />
                        </div>
                    )}
                </div>

            </div>

            {/* 2. MIDDLE GRID: Composite Alpha Gauge (Breakdown) */}
            {ca && (
                <div className="w-full">
                    <CompositeAlphaGauge data={ca} />
                </div>
            )}

            {/* 3. BOTTOM ZONE: Research Memo */}
            <ResearchMemoInsight memo={evidenceMemo} />

        </div>
    );
}
