"use client";

/**
 * InvestmentStory.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Level 2 — Investment Story.
 *
 * Answers the question: "Why?" in 30 seconds.
 * Shows: thesis, catalysts, risks, technical context, market regime.
 */

import { useState } from "react";
import {
    Lightbulb,
    AlertTriangle,
    TrendingUp,
    TrendingDown,
    Activity,
    BarChart3,
    Globe,
    ChevronDown,
    ChevronUp,
    FileText,
    Newspaper,
} from "lucide-react";
import type { CombinedState } from "@/hooks/useCombinedStream";

// ─── Sub-tab type ─────────────────────────────────────────────────────────────

type StoryTab = "thesis" | "catalysts" | "risks" | "technical" | "regime";

const TABS: { id: StoryTab; label: string; icon: React.ReactNode }[] = [
    { id: "thesis", label: "Thesis", icon: <Lightbulb size={12} /> },
    { id: "catalysts", label: "Catalysts", icon: <TrendingUp size={12} /> },
    { id: "risks", label: "Risks", icon: <AlertTriangle size={12} /> },
    { id: "technical", label: "Technical", icon: <Activity size={12} /> },
    { id: "regime", label: "Regime", icon: <Globe size={12} /> },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function TechBadge({ label, value, color }: { label: string; value: string; color: string }) {
    return (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#161b22] border border-[#30363d]">
            <span className="text-[9px] font-black uppercase tracking-widest text-gray-600">{label}</span>
            <span className={`text-xs font-mono font-bold ${color}`}>{value}</span>
        </div>
    );
}

// ─── Component ────────────────────────────────────────────────────────────────

interface InvestmentStoryProps {
    combined: CombinedState;
}

export default function InvestmentStory({ combined }: InvestmentStoryProps) {
    const [activeTab, setActiveTab] = useState<StoryTab>("thesis");
    const [expanded, setExpanded] = useState(true);

    const { decision, technical, committee, agentMemos, researchMemo } = combined;
    const cio = decision?.cio_memo;

    if (!cio && !committee && agentMemos.length === 0) return null;

    // Extract technical context
    const techSummary = technical?.summary;
    const techScore = techSummary?.technical_score ?? 0;
    const trend = techSummary?.signal ?? "—";
    const rsi = technical?.indicators?.momentum?.rsi ?? 0;
    const macdCross = technical?.indicators?.trend?.macd_crossover ?? "NEUTRAL";

    return (
        <div className="glass-card border-[#30363d] overflow-hidden">
            {/* Section header */}
            <button
                onClick={() => setExpanded(v => !v)}
                className="w-full flex items-center justify-between px-6 py-4 hover:bg-white/[0.02] transition-colors"
            >
                <div className="flex items-center gap-2">
                    <BarChart3 size={14} className="text-[#d4af37]" />
                    <span className="text-xs font-black uppercase tracking-widest text-[#d4af37]">Investment Story</span>
                </div>
                {expanded ? <ChevronUp size={14} className="text-gray-600" /> : <ChevronDown size={14} className="text-gray-600" />}
            </button>

            {expanded && (
                <div className="border-t border-[#30363d]">
                    {/* Tab bar */}
                    <div className="flex gap-1 px-4 pt-3 pb-0 overflow-x-auto">
                        {TABS.map((tab) => (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id)}
                                className={`flex items-center gap-1.5 px-3 py-2 rounded-t-lg text-[10px] font-black uppercase tracking-widest transition-all flex-shrink-0 ${activeTab === tab.id
                                    ? "text-[#d4af37] bg-[#161b22] border border-[#30363d] border-b-transparent"
                                    : "text-gray-600 hover:text-gray-400"
                                    }`}
                            >
                                {tab.icon}
                                {tab.label}
                            </button>
                        ))}
                    </div>

                    {/* Tab content */}
                    <div className="px-6 py-5 min-h-[120px]" style={{ animation: "fadeSlideIn 0.3s ease both" }}>
                        {/* Thesis */}
                        {activeTab === "thesis" && (
                            <div className="space-y-4">
                                {cio?.thesis_summary ? (
                                    <p className="text-sm text-gray-300 leading-relaxed">{cio.thesis_summary}</p>
                                ) : committee?.consensus_narrative ? (
                                    <p className="text-sm text-gray-300 leading-relaxed">{committee.consensus_narrative}</p>
                                ) : (
                                    <p className="text-sm text-gray-600 italic">Thesis will appear when analysis completes...</p>
                                )}
                                {cio?.valuation_view && (
                                    <div className="pl-3 border-l-2 border-[#d4af37]/30">
                                        <span className="text-[9px] font-black uppercase tracking-widest text-gray-600 block mb-1">Valuation View</span>
                                        <p className="text-xs text-gray-400 leading-relaxed">{cio.valuation_view}</p>
                                    </div>
                                )}
                                {cio?.filing_context && (
                                    <div className="pl-3 border-l-2 border-blue-500/30">
                                        <span className="text-[9px] font-black uppercase tracking-widest text-gray-600 flex items-center gap-1 mb-1">
                                            <FileText size={9} /> Contexto de Filings
                                        </span>
                                        <p className="text-xs text-gray-400 leading-relaxed">{cio.filing_context}</p>
                                    </div>
                                )}
                                {cio?.geopolitical_context && (
                                    <div className="pl-3 border-l-2 border-purple-500/30">
                                        <span className="text-[9px] font-black uppercase tracking-widest text-gray-600 flex items-center gap-1 mb-1">
                                            <Globe size={9} /> Contexto Geopolítico
                                        </span>
                                        <p className="text-xs text-gray-400 leading-relaxed">{cio.geopolitical_context}</p>
                                    </div>
                                )}
                                {cio?.macro_environment && (
                                    <div className="pl-3 border-l-2 border-teal-500/30">
                                        <span className="text-[9px] font-black uppercase tracking-widest text-gray-600 flex items-center gap-1 mb-1">
                                            <BarChart3 size={9} /> Entorno Macro
                                        </span>
                                        <p className="text-xs text-gray-400 leading-relaxed">{cio.macro_environment}</p>
                                    </div>
                                )}
                                {cio?.sentiment_context && (
                                    <div className="pl-3 border-l-2 border-pink-500/30">
                                        <span className="text-[9px] font-black uppercase tracking-widest text-gray-600 flex items-center gap-1 mb-1">
                                            <Newspaper size={9} /> Contexto de Sentimiento
                                        </span>
                                        <p className="text-xs text-gray-400 leading-relaxed">{cio.sentiment_context}</p>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Catalysts */}
                        {activeTab === "catalysts" && (
                            <div className="space-y-2">
                                {(cio?.key_catalysts && cio.key_catalysts.length > 0) ? (
                                    cio.key_catalysts.map((cat, i) => (
                                        <div key={i} className="flex items-start gap-2.5 py-1.5">
                                            <TrendingUp size={12} className="text-green-400 mt-0.5 flex-shrink-0" />
                                            <p className="text-sm text-gray-300 leading-relaxed">{cat}</p>
                                        </div>
                                    ))
                                ) : (
                                    <p className="text-sm text-gray-600 italic">No catalysts identified yet...</p>
                                )}
                            </div>
                        )}

                        {/* Risks */}
                        {activeTab === "risks" && (
                            <div className="space-y-2">
                                {(cio?.key_risks && cio.key_risks.length > 0) ? (
                                    cio.key_risks.map((risk, i) => (
                                        <div key={i} className="flex items-start gap-2.5 py-1.5">
                                            <AlertTriangle size={12} className="text-red-400 mt-0.5 flex-shrink-0" />
                                            <p className="text-sm text-gray-300 leading-relaxed">{risk}</p>
                                        </div>
                                    ))
                                ) : (
                                    <p className="text-sm text-gray-600 italic">No risks identified yet...</p>
                                )}
                            </div>
                        )}

                        {/* Technical context */}
                        {activeTab === "technical" && (
                            <div className="space-y-4">
                                {cio?.technical_context && (
                                    <p className="text-sm text-gray-300 leading-relaxed">{cio.technical_context}</p>
                                )}
                                <div className="flex flex-wrap gap-2">
                                    <TechBadge
                                        label="Score"
                                        value={techScore.toFixed(1)}
                                        color={techScore > 7.0 ? "text-green-400" : techScore > 4.0 ? "text-yellow-400" : "text-red-400"}
                                    />
                                    <TechBadge
                                        label="Trend"
                                        value={trend.toUpperCase()}
                                        color={trend.toLowerCase().includes("bull") ? "text-green-400" : trend.toLowerCase().includes("bear") ? "text-red-400" : "text-yellow-400"}
                                    />
                                    <TechBadge
                                        label="RSI"
                                        value={rsi.toFixed(0)}
                                        color={rsi > 70 ? "text-red-400" : rsi < 30 ? "text-green-400" : "text-gray-300"}
                                    />
                                    <TechBadge
                                        label="MACD"
                                        value={macdCross}
                                        color={macdCross === "BULLISH" ? "text-green-400" : macdCross === "BEARISH" ? "text-red-400" : "text-yellow-400"}
                                    />
                                </div>
                            </div>
                        )}

                        {/* Regime */}
                        {activeTab === "regime" && (
                            <div className="space-y-3">
                                {committee ? (
                                    <>
                                        <div className="flex items-center gap-3">
                                            <span className="text-[9px] font-black uppercase tracking-widest text-gray-600">Committee Score</span>
                                            <span className="text-lg font-black font-mono text-[#d4af37]">{committee.score?.toFixed(1) ?? "—"}</span>
                                        </div>
                                        <div className="flex items-center gap-3">
                                            <span className="text-[9px] font-black uppercase tracking-widest text-gray-600">Final Verdict</span>
                                            <span className="text-sm font-bold text-gray-300">{committee.signal ?? "—"}</span>
                                        </div>
                                        {committee.consensus_narrative && (
                                            <p className="text-xs text-gray-400 leading-relaxed mt-2">{committee.consensus_narrative}</p>
                                        )}
                                    </>
                                ) : (
                                    <p className="text-sm text-gray-600 italic">Committee verdict pending...</p>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
