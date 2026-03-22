"use client";

/**
 * ConvergenceMap.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Decision Convergence Map — visual flowchart showing how all analysis
 * layers converge into the CIO's final investment decision.
 *
 * Structure:
 *   Layer 1 (Sources):   Fundamental  |  Technical  |  Alpha (CASE)
 *   Layer 2 (Scores):    Committee    |  Purified   |  CASE Score
 *   Layer 3 (Synthesis): Opportunity Score  ←→  Decision Matrix
 *   Layer 4 (Output):    CIO Decision + Confidence + Position
 */

import { useEffect, useState, useMemo } from "react";
import {
    Shield,
    LineChart,
    Radio,
    Target,
    TrendingUp,
    AlertTriangle,
    CheckCircle2,
    Minus,
    ArrowDown,
    Zap,
    Brain,
} from "lucide-react";
import type { CombinedState, AlphaStackData } from "@/hooks/useCombinedStream";

// ─── Types ────────────────────────────────────────────────────────────────────

interface ConvergenceMapProps {
    combined: CombinedState;
}

type NodeStatus = "idle" | "active" | "complete";

interface FlowNode {
    id: string;
    label: string;
    sublabel?: string;
    value?: string;
    score?: number;
    max?: number;
    signal?: "bullish" | "bearish" | "neutral" | "none";
    status: NodeStatus;
    icon: React.ReactNode;
    layer: number;
    column: number;
    span?: number;
}

// ─── Signal color helpers ────────────────────────────────────────────────────

function signalStyle(signal: "bullish" | "bearish" | "neutral" | "none") {
    switch (signal) {
        case "bullish": return { color: "#22c55e", bg: "rgba(34,197,94,0.08)", border: "rgba(34,197,94,0.25)" };
        case "bearish": return { color: "#ef4444", bg: "rgba(239,68,68,0.08)", border: "rgba(239,68,68,0.25)" };
        case "neutral": return { color: "#eab308", bg: "rgba(234,179,8,0.08)", border: "rgba(234,179,8,0.25)" };
        default: return { color: "#6b7280", bg: "rgba(107,114,128,0.06)", border: "rgba(48,54,61,0.6)" };
    }
}

function scoreToSignal(score: number, max: number): "bullish" | "bearish" | "neutral" {
    const pct = (score / max) * 100;
    if (pct >= 65) return "bullish";
    if (pct <= 35) return "bearish";
    return "neutral";
}

function positionToSignal(pos: string): "bullish" | "bearish" | "neutral" {
    const p = pos?.toUpperCase() ?? "";
    if (p.includes("BUY") || p.includes("STRONG")) return "bullish";
    if (p.includes("SELL") || p.includes("AVOID")) return "bearish";
    return "neutral";
}

// ─── FlowNode Card ──────────────────────────────────────────────────────────

function NodeCard({ node, animDelay }: { node: FlowNode; animDelay: number }) {
    const sig = signalStyle(node.signal ?? "none");
    const isComplete = node.status === "complete";
    const isActive = node.status === "active";

    return (
        <div
            className="relative"
            style={{
                animation: `fadeSlideIn 0.4s ease ${animDelay}s both`,
                gridColumn: node.span ? `span ${node.span}` : undefined,
            }}
        >
            <div
                className="rounded-xl p-4 transition-all duration-500"
                style={{
                    background: isComplete ? sig.bg : "rgba(22,27,34,0.6)",
                    border: `1px solid ${isComplete ? sig.border : "rgba(48,54,61,0.5)"}`,
                    boxShadow: isComplete ? `0 0 20px -6px ${sig.color}20` : undefined,
                    opacity: node.status === "idle" ? 0.4 : 1,
                }}
            >
                {/* Header */}
                <div className="flex items-center gap-2 mb-2">
                    <div
                        className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
                        style={{
                            background: isComplete
                                ? `${sig.color}18`
                                : "rgba(48,54,61,0.4)",
                        }}
                    >
                        <span style={{ color: isComplete ? sig.color : "#6b7280" }}>
                            {node.icon}
                        </span>
                    </div>
                    <div className="flex-1 min-w-0">
                        <span className="text-[9px] font-black uppercase tracking-widest block"
                            style={{ color: isComplete ? sig.color : "#6b7280" }}>
                            {node.label}
                        </span>
                        {node.sublabel && (
                            <span className="text-[8px] text-gray-600 block truncate">
                                {node.sublabel}
                            </span>
                        )}
                    </div>

                    {/* Status indicator */}
                    {isActive && (
                        <div className="w-2 h-2 rounded-full bg-[#d4af37] animate-pulse" />
                    )}
                    {isComplete && (
                        <CheckCircle2 size={12} style={{ color: sig.color }} />
                    )}
                </div>

                {/* Score */}
                {node.value && (
                    <div className="mt-1 flex items-baseline gap-1">
                        <span
                            className="text-xl font-black font-mono tabular-nums"
                            style={{ color: isComplete ? sig.color : "#4b5563" }}
                        >
                            {node.value}
                        </span>
                        {node.max && (
                            <span className="text-[10px] text-gray-600 font-mono">
                                /{node.max}
                            </span>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}

// ─── Connection Lines ───────────────────────────────────────────────────────

function FlowArrow({ delay }: { delay: number }) {
    return (
        <div
            className="flex justify-center py-1"
            style={{ animation: `fadeSlideIn 0.3s ease ${delay}s both` }}
        >
            <div className="flex flex-col items-center gap-0">
                <div className="w-px h-4 bg-gradient-to-b from-transparent to-[#d4af37]/30" />
                <ArrowDown size={10} className="text-[#d4af37]/40" />
            </div>
        </div>
    );
}

function ConvergenceLines({ count, delay }: { count: number; delay: number }) {
    return (
        <div
            className="flex justify-center py-1 relative"
            style={{ animation: `fadeSlideIn 0.3s ease ${delay}s both` }}
        >
            <svg viewBox="0 0 600 30" preserveAspectRatio="none" width="100%" height="30" className="overflow-visible">
                {/* Vertical drops from each column */}
                <line x1="100" y1="0" x2="100" y2="15" stroke="#d4af37" strokeOpacity="0.2" strokeWidth="1" />
                <line x1="300" y1="0" x2="300" y2="15" stroke="#d4af37" strokeOpacity="0.2" strokeWidth="1" />
                <line x1="500" y1="0" x2="500" y2="15" stroke="#d4af37" strokeOpacity="0.2" strokeWidth="1" />
                {/* Horizontal merge */}
                <line x1="100" y1="15" x2="500" y2="15" stroke="#d4af37" strokeOpacity="0.2" strokeWidth="1" />
                {/* Center drop + arrow */}
                <line x1="300" y1="15" x2="300" y2="28" stroke="#d4af37" strokeOpacity="0.3" strokeWidth="1" />
                <polygon points="300,30 295,25 305,25" fill="#d4af37" fillOpacity="0.3" />
            </svg>
        </div>
    );
}

// ─── Main Component ─────────────────────────────────────────────────────────

export default function ConvergenceMap({ combined }: ConvergenceMapProps) {
    const {
        decision, committee, technical, opportunity,
        positionSizing, alphaStack, fundamentalDataReady, status,
    } = combined;

    if (!decision) return null;

    // Derive scores
    const fundScore = committee?.score ?? 0;
    const techScore = (technical as any)?.purified_score
        ?? (technical as any)?.summary?.technical_score
        ?? 0;
    const caseScore = alphaStack?.case_score ?? 0;
    const oppScore = opportunity?.opportunity_score ?? 0;
    const confidence = (decision.confidence_score ?? 0) * 100;
    const position = decision.investment_position ?? "ANALYZING";
    const allocation = positionSizing?.suggested_allocation ?? 0;
    const riskLevel = positionSizing?.risk_level ?? "—";

    // Signals
    const fundSignal = committee?.signal?.toUpperCase() ?? "";
    const techSignal = (technical as any)?.purified_signal
        ?? (technical as any)?.summary?.signal ?? "";

    const isComplete = status === "complete";

    // Build nodes
    const nodes: FlowNode[] = useMemo(() => [
        // Layer 0 — Source engines
        {
            id: "fundamental",
            label: "Fundamental",
            sublabel: "4-Agent Committee",
            value: fundScore.toFixed(1),
            max: 10,
            score: fundScore,
            signal: isComplete ? scoreToSignal(fundScore, 10) : "none",
            status: committee ? "complete" : fundamentalDataReady ? "active" : "idle",
            icon: <Shield size={13} />,
            layer: 0,
            column: 0,
        },
        {
            id: "technical",
            label: "Technical",
            sublabel: "Purified Score",
            value: techScore.toFixed(1),
            max: 10,
            score: techScore,
            signal: isComplete ? scoreToSignal(techScore, 10) : "none",
            status: technical ? "complete" : "idle",
            icon: <LineChart size={13} />,
            layer: 0,
            column: 1,
        },
        {
            id: "alpha",
            label: "Alpha Stack",
            sublabel: `CASE · ${alphaStack?.environment?.replace(" Environment", "") ?? "—"}`,
            value: caseScore.toFixed(0),
            max: 100,
            score: caseScore,
            signal: isComplete ? scoreToSignal(caseScore, 100) : "none",
            status: alphaStack ? "complete" : "idle",
            icon: <Radio size={13} />,
            layer: 0,
            column: 2,
        },
        // Layer 1 — Synthesis
        {
            id: "decision_matrix",
            label: "Decision Matrix",
            sublabel: `Fund(${fundScore.toFixed(1)}) × Tech(${techScore.toFixed(1)}) → ${position}`,
            value: undefined,
            signal: isComplete ? positionToSignal(position) : "none",
            status: decision ? "complete" : "idle",
            icon: <Brain size={13} />,
            layer: 1,
            column: 0,
            span: 2,
        },
        {
            id: "opportunity",
            label: "Opportunity",
            sublabel: "Composite Score (0-10)",
            value: oppScore.toFixed(1),
            max: 10,
            score: oppScore,
            signal: isComplete ? scoreToSignal(oppScore, 10) : "none",
            status: opportunity ? "complete" : "idle",
            icon: <Target size={13} />,
            layer: 1,
            column: 2,
        },
        // Layer 2 — Final Output
        {
            id: "cio_decision",
            label: "CIO Decision",
            sublabel: `Confidence ${confidence.toFixed(0)}% · Alloc ${allocation.toFixed(1)}% · Risk ${riskLevel}`,
            value: position,
            signal: isComplete ? positionToSignal(position) : "none",
            status: decision ? "complete" : "idle",
            icon: <Zap size={13} />,
            layer: 2,
            column: 0,
            span: 3,
        },
    ], [fundScore, techScore, caseScore, oppScore, confidence, position, allocation, riskLevel, isComplete, committee, technical, alphaStack, opportunity, decision, fundamentalDataReady, status]);

    // Group by layer
    const layers = [
        nodes.filter(n => n.layer === 0),
        nodes.filter(n => n.layer === 1),
        nodes.filter(n => n.layer === 2),
    ];

    return (
        <div className="glass-card border-[#30363d] p-5 overflow-hidden">
            {/* Title */}
            <div className="flex items-center gap-2 mb-5">
                <div className="w-6 h-6 rounded-lg flex items-center justify-center"
                    style={{ background: "rgba(212,175,55,0.1)", border: "1px solid rgba(212,175,55,0.2)" }}>
                    <TrendingUp size={12} className="text-[#d4af37]" />
                </div>
                <span className="text-[9px] font-black uppercase tracking-widest text-[#d4af37]">
                    Decision Convergence Map
                </span>
            </div>

            {/* Layer 0: Source Engines */}
            <div className="grid grid-cols-3 gap-3">
                {layers[0].map((node, i) => (
                    <NodeCard key={node.id} node={node} animDelay={0.1 + i * 0.08} />
                ))}
            </div>

            {/* Convergence arrows */}
            <ConvergenceLines count={3} delay={0.4} />

            {/* Layer 1: Synthesis */}
            <div className="grid grid-cols-3 gap-3">
                {layers[1].map((node, i) => (
                    <NodeCard key={node.id} node={node} animDelay={0.5 + i * 0.08} />
                ))}
            </div>

            {/* Arrow to final */}
            <FlowArrow delay={0.65} />

            {/* Layer 2: Final Decision */}
            <div className="grid grid-cols-3 gap-3">
                {layers[2].map((node, i) => (
                    <NodeCard key={node.id} node={node} animDelay={0.7} />
                ))}
            </div>

            {/* Divergence indicator */}
            {isComplete && (
                <div
                    className="mt-4 flex items-center gap-3 px-3 py-2 rounded-lg"
                    style={{
                        background: "rgba(22,27,34,0.5)",
                        border: "1px solid rgba(48,54,61,0.4)",
                        animation: "fadeSlideIn 0.4s ease 0.85s both",
                    }}
                >
                    <div className="flex items-center gap-1.5">
                        <span className="text-[8px] font-black uppercase tracking-widest text-gray-600">
                            Fund-Tech Divergence
                        </span>
                        <span className={`text-[10px] font-mono font-bold ${
                            Math.abs(fundScore - techScore) > 3 ? "text-orange-400" :
                            Math.abs(fundScore - techScore) > 1.5 ? "text-yellow-400" : "text-green-400"
                        }`}>
                            {Math.abs(fundScore - techScore).toFixed(1)} pts
                        </span>
                    </div>
                    <div className="w-px h-3 bg-[#30363d]" />
                    <div className="flex items-center gap-1.5">
                        <span className="text-[8px] font-black uppercase tracking-widest text-gray-600">
                            Signal Alignment
                        </span>
                        {(() => {
                            const signals = [
                                scoreToSignal(fundScore, 10),
                                scoreToSignal(techScore, 10),
                                scoreToSignal(caseScore, 100),
                            ];
                            const allSame = signals.every(s => s === signals[0]);
                            const allDiff = new Set(signals).size === 3;
                            return allSame ? (
                                <span className="text-[10px] font-bold text-green-400 flex items-center gap-1">
                                    <CheckCircle2 size={10} /> Converged
                                </span>
                            ) : allDiff ? (
                                <span className="text-[10px] font-bold text-red-400 flex items-center gap-1">
                                    <AlertTriangle size={10} /> Divergent
                                </span>
                            ) : (
                                <span className="text-[10px] font-bold text-yellow-400 flex items-center gap-1">
                                    <Minus size={10} /> Partial
                                </span>
                            );
                        })()}
                    </div>
                </div>
            )}
        </div>
    );
}
