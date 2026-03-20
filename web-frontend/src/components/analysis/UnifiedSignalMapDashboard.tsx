"use client";

import React, { useState } from "react";
import { Radio, Shield, Zap, TrendingUp, Activity, BarChart3, Rocket, Globe, Clock, CheckCircle2, XCircle, ChevronDown, ChevronRight, ChevronUp } from "lucide-react";
import type { SignalProfileResponse, EvaluatedSignal, CategoryScore } from "@/hooks/useAlphaSignals";
import ResearchMemoInsight from "./ResearchMemoInsight";
import type { MemoInsight } from "./ResearchMemoInsight";

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
    value: <Shield size={14} className="text-emerald-400" />,
    quality: <Zap size={14} className="text-blue-400" />,
    momentum: <TrendingUp size={14} className="text-orange-400" />,
    volatility: <Activity size={14} className="text-yellow-400" />,
    flow: <BarChart3 size={14} className="text-cyan-400" />,
    event: <Radio size={14} className="text-purple-400" />,
    growth: <Rocket size={14} className="text-rose-400" />,
    macro: <Globe size={14} className="text-amber-400" />,
};

const CATEGORY_COLORS: Record<string, string> = {
    value: "bg-emerald-500",
    quality: "bg-blue-500",
    momentum: "bg-orange-500",
    volatility: "bg-yellow-500",
    flow: "bg-cyan-500",
    event: "bg-purple-500",
    growth: "bg-rose-500",
    macro: "bg-amber-500",
};

const STRENGTH_STYLES: Record<string, string> = {
    strong: "text-green-400 bg-green-500/10 border-green-500/20",
    moderate: "text-yellow-400 bg-yellow-500/10 border-yellow-500/20",
    weak: "text-gray-500 bg-gray-500/10 border-gray-500/20",
};

export interface UnifiedSignalMapDashboardProps {
    profile: SignalProfileResponse | null;
    ticker: string;
}

// ── Signal Map Definitions ───────────────────────────────────────────────

const SIGNAL_MAP_DEFS = [
    {
        metric: "Signal Origin Log",
        definition: "Registro de cuántas de las 68 señales Alpha registradas dispararon (cumplieron su condición threshold). Cada señal evalúa una variable específica (P/E, RSI, ROIC, etc.) contra un umbral predefinido.",
    },
    {
        metric: "Dominant Origin",
        definition: "La categoría de señales con mayor presencia activa. Indica dónde está concentrada la evidencia factorial. Quality = ventajas competitivas, Value = descuento, Momentum = inercia de precio.",
    },
    {
        metric: "Coverage Breadth",
        definition: "Porcentaje de señales activas vs total. Mide la amplitud de la evidencia. <15% = muy selectiva (pocas condiciones cumplidas). >50% = amplia cobertura (múltiples factores alineados).",
    },
    {
        metric: "Strength Level",
        definition: "Cada señal tiene un nivel de fuerza: STRONG (valor muy por encima del threshold), MODERATE (justo por encima), WEAK (marginal). Se determina comparando el valor con strong_threshold.",
    },
    {
        metric: "Active vs Inactive",
        definition: "Señales activas (FIRED) cumplieron su condición. Señales inactivas no la cumplieron — esto NO es negativo, solo indica que esa condición específica no aplica para este activo en este momento.",
    },
    {
        metric: "Category Coverage Bars",
        definition: "Las 8 micro-tarjetas muestran qué proporción de señales disparó en cada categoría. Una barra llena indica alta participación factorial. Tarjetas dimmed = 0 señales activas en esa categoría.",
    },
];

// ── Signal Map Analyst Depth ───────────────────────────────────────────

function SignalMapAnalystDepth() {
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
                    <div className="bg-[#161b22] p-3 rounded-lg border border-[#30363d]/50">
                        <p className="text-[10px] text-[#c9d1d9] leading-relaxed font-serif italic border-l-2 border-indigo-500/40 pl-2">
                            "Signal Map es la vista de auditoría granular. Muestra cada señal individual con su valor exacto, threshold, y fuerza. Permite verificar la trazabilidad de cada decisión del motor Alpha."
                        </p>
                    </div>

                    <div>
                        <p className="text-[8px] text-indigo-400 font-bold uppercase tracking-widest mb-2 flex items-center gap-1.5">
                            <Zap size={10} /> Conceptos Explicados
                        </p>
                        <div className="flex flex-col gap-2">
                            {SIGNAL_MAP_DEFS.map((d, idx) => (
                                <div key={idx} className="bg-[#0d1117] p-3 rounded border border-[#30363d]">
                                    <p className="text-[10px] font-black text-[#c9d1d9] mb-1 font-mono">{d.metric}</p>
                                    <p className="text-[9px] text-[#8b949e] leading-relaxed">{d.definition}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

export default function UnifiedSignalMapDashboard({ profile, ticker }: UnifiedSignalMapDashboardProps) {
    const [showInactive, setShowInactive] = useState(false);

    if (!profile) {
        return (
            <div className="flex flex-col items-center justify-center py-20 text-center gap-2">
                <Radio size={24} className="text-[#30363d]" />
                <p className="text-[10px] text-gray-600 font-mono">No alpha profile available for signal map</p>
            </div>
        );
    }

    const { signals, category_summary, composite } = profile;
    const allCategories = ["value", "quality", "growth", "momentum", "volatility", "flow", "event", "macro"];
    const firedSignals = signals.filter((s) => s.fired);
    const notFired = signals.filter((s) => !s.fired);

    // ── Generate Memo ────────────────────────────────────────────────────────
    const signalMapMemo: MemoInsight = (() => {
        if (profile.signal_map_memo) {
            return {
                title: "Research Memo — Signal Map",
                signal: (profile.signal_map_memo.signal as "BULLISH" | "BEARISH" | "NEUTRAL") || "NEUTRAL",
                conviction: (profile.signal_map_memo.conviction as "HIGH" | "MEDIUM" | "LOW") || "LOW",
                narrative: profile.signal_map_memo.narrative,
                bullets: profile.signal_map_memo.key_data || [],
                risks: profile.signal_map_memo.risk_factors || [],
            };
        }

        const firedPct = signals.length > 0 ? (firedSignals.length / signals.length) * 100 : 0;
        const signal: "BULLISH" | "BEARISH" | "NEUTRAL" = firedPct >= 55 ? "BULLISH" : firedPct <= 25 ? "BEARISH" : "NEUTRAL";
        const conviction: "HIGH" | "MEDIUM" | "LOW" = firedPct >= 70 ? "HIGH" : firedPct >= 40 ? "MEDIUM" : "LOW";

        const sortedCats = Object.entries(category_summary)
            .filter(([, v]) => (v.fired ?? 0) > 0)
            .sort((a, b) => (b[1].fired ?? 0) - (a[1].fired ?? 0));

        const strongSignals = firedSignals.filter((s) => s.strength === "strong");

        const narrative = `${ticker}: ${firedSignals.length} de ${signals.length} señales activas (${firedPct.toFixed(0)}%). ` +
            (sortedCats.length > 0 ? `Categoría dominante en volumen: ${sortedCats[0][0]}. ` : "") +
            (strongSignals.length > 0 ? `Registrando ${strongSignals.length} convicciones fuertes.` : "Sin confirmaciones fuertes.");

        const bullets: string[] = [];
        if (strongSignals.length > 0) bullets.push(`Señales fuertes: ${strongSignals.slice(0, 3).map((s) => s.signal_name).join(", ")}`);
        bullets.push(`Cobertura factorial: ${sortedCats.length} de 8 categorías iluminadas`);
        
        const risks: string[] = [];
        if (firedPct < 25) risks.push("Muy baja participación de factores");
        if (sortedCats.length <= 1) risks.push("Concentración crítica: posible falso positivo por falta de convergencia transversal");
        if (firedSignals.length > 0 && firedSignals.every((s) => s.strength === "weak")) risks.push("Toda la cobertura activa es 'weak'");

        return { title: "Research Memo — Signal Map", signal, conviction, narrative, bullets, risks };
    })();

    return (
        <div className="space-y-4" style={{ animation: "fadeSlideIn 0.4s ease both" }}>
            
            {/* 1. TOP ROW: Logic Flow Summary */}
            <div className="glass-card border border-[#30363d] relative overflow-hidden">
                <div className="absolute top-0 left-0 w-32 h-32 bg-purple-500/5 blur-2xl rounded-full" />
                <div className="p-5 flex flex-col sm:flex-row items-center justify-between gap-6">
                    <div className="flex flex-col gap-1 z-10 w-full sm:w-auto">
                        <h3 className="text-[9px] font-black uppercase tracking-widest text-gray-500 mb-2">Alpha Signal Origin Log</h3>
                        <div className="flex items-end gap-2">
                            <span className="text-3xl font-black font-mono text-white leading-none">{firedSignals.length}</span>
                            <span className="text-[10px] text-gray-600 font-bold uppercase tracking-widest pb-1">/ {signals.length} Fired</span>
                        </div>
                    </div>

                    <div className="hidden sm:block w-px h-12 bg-[#30363d]" />

                    <div className="flex flex-col gap-1 z-10 w-full sm:w-auto">
                        <span className="text-[9px] font-black uppercase tracking-widest text-gray-500 mb-2">Dominant Origin</span>
                        <div className="flex items-center gap-2">
                            {composite.dominant_category && CATEGORY_ICONS[composite.dominant_category.toLowerCase()]}
                            <span className={`text-[11px] font-black uppercase tracking-widest ${composite.dominant_category ? "text-gray-300" : "text-gray-600"}`}>
                                {composite.dominant_category || "N/A"}
                            </span>
                        </div>
                    </div>

                    <div className="hidden sm:block w-px h-12 bg-[#30363d]" />

                    <div className="flex flex-col gap-1 z-10 w-full sm:w-auto">
                        <span className="text-[9px] font-black uppercase tracking-widest text-gray-500 mb-2">Coverage Breadth</span>
                        <span className="text-lg font-mono font-black text-gray-300 leading-none">
                            {(signals.length > 0 ? (firedSignals.length / signals.length) * 100 : 0).toFixed(0)}%
                        </span>
                    </div>
                </div>

                {/* Analyst Depth — full width below the flow row */}
                <div className="px-5 pb-5">
                    <SignalMapAnalystDepth />
                </div>
            </div>

            {/* 2. MIDDLE GRID: Category Coverage Micro-Cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                {allCategories.map((catKey) => {
                    const summary = category_summary[catKey];
                    const total = summary?.total || 0;
                    const fired = summary?.fired || 0;
                    const firedPct = total > 0 ? (fired / total) * 100 : 0;
                    const colorClass = CATEGORY_COLORS[catKey] || "bg-gray-500";
                    const isDimmed = fired === 0;

                    return (
                        <div key={catKey} className={`glass-card p-3 border transition-colors ${isDimmed ? "border-[#30363d]/50 bg-[#161b22]/30 opacity-60" : "border-[#30363d]"}`}>
                            <div className="flex items-center justify-between mb-3">
                                <div className="flex items-center gap-2">
                                    {(() => {
                                        const iconEl = CATEGORY_ICONS[catKey] as React.ReactElement<{ className?: string }>;
                                        return React.cloneElement(iconEl, { className: isDimmed ? "text-gray-600" : iconEl.props.className });
                                    })()}
                                    <span className="text-[9px] font-black uppercase tracking-wider text-gray-400">{catKey}</span>
                                </div>
                                <span className="text-[10px] font-mono font-bold text-gray-500">{fired}/{total}</span>
                            </div>
                            <div className="w-full h-1 bg-[#161b22] rounded-full overflow-hidden">
                                <div className={`h-full rounded-full transition-all duration-700 ${colorClass}`} style={{ width: `${firedPct}%` }} />
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* 3. LOWER SECTION: Institutional Audit Log */}
            <div className="glass-card border border-[#30363d] overflow-hidden flex flex-col">
                <div className="px-5 py-3 border-b border-[#30363d] bg-[#0d1117]/50 flex items-center gap-2">
                    <CheckCircle2 size={12} className="text-purple-400" />
                    <h3 className="text-[10px] font-black uppercase tracking-widest text-gray-300">
                        Active Alpha Trace Log ({firedSignals.length})
                    </h3>
                </div>
                
                {firedSignals.length > 0 ? (
                    <div className="divide-y divide-[#30363d]/50 max-h-[400px] overflow-y-auto custom-scrollbar">
                        {firedSignals.map((sig, idx) => (
                            <div key={sig.signal_id || idx} className="flex items-center gap-4 px-5 py-3 hover:bg-white/[0.02] transition-colors group">
                                <div className="flex items-center justify-center w-6 shrink-0">
                                    {CATEGORY_ICONS[sig.category.toLowerCase()] || <Radio size={12} className="text-gray-500" />}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <p className="text-[11px] font-bold text-white truncate">{sig.signal_name}</p>
                                    <p className="text-[9px] text-gray-500 font-mono mt-0.5 line-clamp-1">{sig.description}</p>
                                </div>
                                {sig.value !== null && (
                                    <div className="shrink-0 w-16 text-right">
                                        <p className="text-[9px] text-gray-600 font-black uppercase tracking-widest">Value</p>
                                        <p className="text-[11px] font-mono text-gray-300">{typeof sig.value === "number" ? sig.value.toFixed(2) : String(sig.value)}</p>
                                    </div>
                                )}
                                <div className="shrink-0 w-20 flex justify-end">
                                    <span className={`text-[8px] font-black uppercase tracking-widest px-2 py-0.5 rounded border ${STRENGTH_STYLES[sig.strength] || ""}`}>
                                        {sig.strength}
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="p-8 text-center">
                        <p className="text-xs text-gray-600 font-mono">No active signals found in the current timeframe.</p>
                    </div>
                )}

                {/* Collapsible Inactive Signals */}
                {notFired.length > 0 && (
                    <div className="border-t border-[#30363d]">
                        <button
                            onClick={() => setShowInactive(!showInactive)}
                            className="w-full flex items-center justify-between px-5 py-3 hover:bg-white/[0.02] transition-colors"
                        >
                            <div className="flex items-center gap-2 opacity-60">
                                <XCircle size={12} className="text-gray-500" />
                                <span className="text-[10px] font-black uppercase tracking-widest text-gray-500">
                                    Inactive Signals ({notFired.length})
                                </span>
                            </div>
                            {showInactive ? <ChevronDown size={14} className="text-gray-600" /> : <ChevronRight size={14} className="text-gray-600" />}
                        </button>
                        
                        {showInactive && (
                            <div className="divide-y divide-[#30363d]/30 bg-[#0d1117]/30 max-h-[300px] overflow-y-auto custom-scrollbar border-t border-[#30363d]/50">
                                {notFired.map((sig, idx) => (
                                    <div key={sig.signal_id || idx} className="flex items-center gap-4 px-5 py-2.5 opacity-40 hover:opacity-100 transition-opacity">
                                        <div className="flex items-center justify-center w-6 shrink-0">
                                            <Clock size={12} className="text-gray-600" />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-[10px] font-bold text-gray-400 truncate">{sig.signal_name}</p>
                                        </div>
                                        <div className="shrink-0 text-right">
                                            <span className="text-[8px] font-black uppercase tracking-widest text-gray-600">{sig.category}</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* 4. BOTTOM ZONE: Research Memo */}
            <ResearchMemoInsight memo={signalMapMemo} />

        </div>
    );
}
