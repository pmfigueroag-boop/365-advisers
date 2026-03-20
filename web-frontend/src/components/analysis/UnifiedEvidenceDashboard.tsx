"use client";

import React, { useState } from "react";
import { Activity, Target, Network, BoxSelect, AlertTriangle, Radio, ChevronDown, ChevronUp, Zap } from "lucide-react";
import type { SignalProfileResponse } from "@/hooks/useAlphaSignals";
import ScoreHistoryChart from "../ScoreHistoryChart";
import CompositeAlphaGauge from "../CompositeAlphaGauge";
import ResearchMemoInsight from "./ResearchMemoInsight";
import type { MemoInsight } from "./ResearchMemoInsight";

// ── Evidence Metric Definitions ──────────────────────────────────────────────

const EVIDENCE_DEFS = [
    {
        metric: "Active Categories",
        definition: "Número de las 8 categorías de señales Alpha que tienen al menos una señal disparada. Más categorías activas = evidencia más diversificada y robusta. Idealmente 4-6 para un perfil equilibrado.",
    },
    {
        metric: "Convergence Bonus",
        definition: "Bonus basado en la Entropía de Shannon (H). Mide qué tan uniformemente distribuida está la evidencia entre categorías. Un score de 60 repartido en 5 categorías es más robusto que 60 concentrado en 1-2. Máximo bonus: +6.0 puntos.",
    },
    {
        metric: "Cross-Category Conflicts",
        definition: "Conflictos entre categorías con direcciones opuestas (ej: Value vs Quality = trampa de valor, Momentum vs Macro = momentum contra vientos macro). Cada conflicto aplica una penalización proporcional a la intensidad (media geométrica de ambos scores), máx -20%.",
    },
    {
        metric: "CASE Composite Score",
        definition: "Score final 0-100 que sintetiza las 8 categorías ponderadas, después de aplicar: normalización sigmoid, agregación por categoría, resolución de conflictos, ponderación CASE, spread amplification (×1.4), y ajuste de régimen de mercado (SPY).",
    },
    {
        metric: "Signal Environment",
        definition: "Clasificación del score: Very Strong (≥80), Strong (≥60), Neutral (≥40), Weak (≥20), Negative (<20). Determina el tono general de la evidencia Alpha para la tesis de inversión.",
    },
    {
        metric: "Freshness/Decay",
        definition: "Las señales tienen un factor de decaimiento temporal. Señales antiguas pierden confianza exponencialmente (half-life 90 días). Señales expiradas se desactivan. El nivel de frescura (fresh/aging/stale/expired) indica la fiabilidad temporal.",
    },
];

// ── Evidence Analyst Depth Component ────────────────────────────────────────

function EvidenceAnalystDepth({ conflicts }: { conflicts: string[] }) {
    const [expanded, setExpanded] = useState(false);

    return (
        <div className="mt-4 pt-3 border-t border-[#30363d]/50">
            <button
                className="w-full flex items-center justify-between text-left group cursor-pointer"
                onClick={() => setExpanded(!expanded)}
                aria-expanded={expanded}
            >
                <span className="text-[9px] text-[#8b949e] font-bold uppercase tracking-widest group-hover:text-indigo-400 transition-colors flex items-center gap-1.5">
                    <Activity size={10} /> Analyst Depth
                </span>
                <div className="flex items-center justify-center group-hover:bg-[#161b22] rounded p-0.5 transition-colors">
                    {expanded ? <ChevronUp size={12} className="text-indigo-400" /> : <ChevronDown size={12} className="text-[#8b949e] group-hover:text-indigo-400" />}
                </div>
            </button>

            {expanded && (
                <div className="mt-3 space-y-3 pt-3 border-t border-[#30363d]/30" style={{ animation: "fadeSlideIn 0.2s ease" }}>
                    {/* Pipeline Description */}
                    <div className="bg-[#161b22] p-3 rounded-lg border border-[#30363d]/50">
                        <p className="text-[10px] text-[#c9d1d9] leading-relaxed font-serif italic border-l-2 border-indigo-500/40 pl-2">
                            "Evidence evalúa la robustez de la tesis Alpha. No genera nuevos datos — sintetiza la convergencia, diversificación, conflictos y frescura de las señales ya evaluadas."
                        </p>
                    </div>

                    {/* Metric Definitions */}
                    <div>
                        <p className="text-[8px] text-indigo-400 font-bold uppercase tracking-widest mb-2 flex items-center gap-1.5">
                            <Zap size={10} /> Métricas Explicadas
                        </p>
                        <div className="flex flex-col gap-2">
                            {EVIDENCE_DEFS.map((d, idx) => (
                                <div key={idx} className="bg-[#0d1117] p-3 rounded border border-[#30363d]">
                                    <p className="text-[10px] font-black text-[#c9d1d9] mb-1 font-mono">{d.metric}</p>
                                    <p className="text-[9px] text-[#8b949e] leading-relaxed">{d.definition}</p>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Active Conflicts Detail */}
                    {conflicts.length > 0 && (
                        <div>
                            <p className="text-[8px] text-orange-400 font-bold uppercase tracking-widest mb-2 flex items-center gap-1.5">
                                <AlertTriangle size={10} /> Conflictos Activos
                            </p>
                            <div className="flex flex-col gap-1.5">
                                {conflicts.map((c, i) => (
                                    <div key={i} className="flex items-center gap-2 bg-orange-500/5 p-2 rounded border border-orange-500/20">
                                        <AlertTriangle size={10} className="text-orange-400 flex-shrink-0" />
                                        <span className="text-[9px] text-orange-300/90 leading-tight">{c}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// ── Main Component ──────────────────────────────────────────────────────

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

                    {/* Analyst Depth */}
                    {ca && <EvidenceAnalystDepth conflicts={ca.cross_category_conflicts || []} />}
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
