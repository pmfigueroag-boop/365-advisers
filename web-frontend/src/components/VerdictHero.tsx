"use client";

/**
 * VerdictHero.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Level 1 — Investment Verdict.
 *
 * Answers the question: "Is this a good opportunity?" in 3 seconds.
 * Shows: score, composite alpha, allocation, risk, confidence, freshness.
 */

import { useEffect, useState } from "react";
import {
    TrendingUp,
    TrendingDown,
    Minus,
    Shield,
    Target,
    Activity,
    Clock,
    Users,
    Zap,
} from "lucide-react";
import type { CombinedState } from "@/hooks/useCombinedStream";
import type { SignalProfileResponse } from "@/hooks/useAlphaSignals";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function verdictColor(position: string) {
    const p = position?.toUpperCase() ?? "";
    if (p.includes("BUY") || p.includes("OVERWEIGHT")) return { text: "text-green-400", bg: "bg-green-500/10", border: "border-green-500/30", glow: "shadow-green-500/20" };
    if (p.includes("SELL") || p.includes("UNDERWEIGHT")) return { text: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/30", glow: "shadow-red-500/20" };
    return { text: "text-yellow-400", bg: "bg-yellow-500/10", border: "border-yellow-500/30", glow: "shadow-yellow-500/20" };
}

function riskColor(risk: string) {
    const r = risk?.toLowerCase() ?? "";
    if (r.includes("low")) return "text-green-400";
    if (r.includes("medium") || r.includes("moderate")) return "text-yellow-400";
    if (r.includes("high")) return "text-orange-400";
    if (r.includes("critical")) return "text-red-400";
    return "text-gray-400";
}

function ScoreRing({ value, max = 10, size = 80, label }: { value: number; max?: number; size?: number; label: string }) {
    const [animatedValue, setAnimatedValue] = useState(0);
    const pct = Math.min(100, (animatedValue / max) * 100);
    const radius = (size - 10) / 2;
    const circumference = 2 * Math.PI * radius;
    const dashOffset = circumference * (1 - pct / 100);

    useEffect(() => {
        const timer = setTimeout(() => setAnimatedValue(value), 100);
        return () => clearTimeout(timer);
    }, [value]);

    const hue = pct > 66 ? 120 : pct > 33 ? 45 : 0;
    const color = `hsl(${hue}, 80%, 55%)`;

    return (
        <div className="flex flex-col items-center gap-1.5">
            <svg width={size} height={size} className="drop-shadow-lg">
                <circle cx={size / 2} cy={size / 2} r={radius} stroke="#1c2128" strokeWidth="5" fill="none" />
                <circle
                    cx={size / 2} cy={size / 2} r={radius}
                    stroke={color} strokeWidth="5" fill="none"
                    strokeDasharray={circumference} strokeDashoffset={dashOffset}
                    strokeLinecap="round"
                    transform={`rotate(-90 ${size / 2} ${size / 2})`}
                    style={{ transition: "stroke-dashoffset 1.2s ease-out" }}
                />
                <text x="50%" y="50%" textAnchor="middle" dominantBaseline="central"
                    fill={color} fontSize={size * 0.28} fontWeight="900" fontFamily="monospace">
                    {animatedValue.toFixed(1)}
                </text>
            </svg>
            <span className="text-[9px] font-black uppercase tracking-widest text-gray-500">{label}</span>
        </div>
    );
}

function MetricPill({ icon, label, value, color = "text-gray-300" }: { icon: React.ReactNode; label: string; value: string; color?: string }) {
    return (
        <div className="flex flex-col items-center gap-1 px-3 py-2.5 rounded-xl bg-[#161b22] border border-[#30363d]">
            <div className="text-gray-600">{icon}</div>
            <span className={`text-lg font-black font-mono ${color}`}>{value}</span>
            <span className="text-[8px] font-black uppercase tracking-widest text-gray-600">{label}</span>
        </div>
    );
}

function ConfidenceBar({ value }: { value: number }) {
    const pct = Math.min(100, Math.max(0, value));
    const color = pct > 70 ? "bg-green-500" : pct > 40 ? "bg-yellow-500" : "bg-red-500";
    return (
        <div className="flex items-center gap-2">
            <span className="text-[9px] font-black uppercase tracking-widest text-gray-600">Confidence</span>
            <div className="flex-1 h-1.5 bg-[#1c2128] rounded-full overflow-hidden max-w-[120px]">
                <div className={`h-full rounded-full ${color} transition-all duration-1000`} style={{ width: `${pct}%` }} />
            </div>
            <span className="text-[10px] font-mono font-bold text-gray-400">{pct}%</span>
        </div>
    );
}

function HealthDots({ count, total = 4 }: { count: number; total?: number }) {
    return (
        <div className="flex items-center gap-2">
            <span className="text-[9px] font-black uppercase tracking-widest text-gray-600">System</span>
            <div className="flex gap-1">
                {Array.from({ length: total }).map((_, i) => (
                    <div
                        key={i}
                        className={`w-2 h-2 rounded-full ${i < count ? "bg-green-500" : "bg-[#30363d]"}`}
                    />
                ))}
            </div>
        </div>
    );
}

// ─── Component ────────────────────────────────────────────────────────────────

interface VerdictHeroProps {
    combined: CombinedState;
    alphaProfile: SignalProfileResponse | null;
}

export default function VerdictHero({ combined, alphaProfile }: VerdictHeroProps) {
    const { decision, opportunity, positionSizing, committee, fundamentalDataReady, agentMemos, technical } = combined;

    const ticker = combined.ticker ?? "";
    const name = fundamentalDataReady?.name ?? ticker;
    const price = fundamentalDataReady?.ratios?.valuation?.price != null
        ? Number(fundamentalDataReady.ratios.valuation.price) : null;

    // Investment position
    const position = decision?.investment_position ?? "ANALYZING";
    const vc = verdictColor(position);

    // Key metrics
    const oppScore = opportunity?.opportunity_score ?? 0;
    const compositeAlpha = alphaProfile?.composite_alpha?.score ?? 0;
    const allocation = positionSizing?.suggested_allocation ?? 0;
    const risk = positionSizing?.risk_level ?? "—";
    const confidence = decision?.confidence_score ?? 0;
    const agentVotes = agentMemos.length;
    const totalAgents = 4;

    // System health: count of subsystems reporting
    const healthCount = [
        fundamentalDataReady !== null,
        technical !== null,
        decision !== null,
        alphaProfile !== null,
    ].filter(Boolean).length;

    // Freshness
    const decay = alphaProfile?.composite_alpha?.decay;
    const freshnessLabel = decay?.freshness_level ?? "—";

    // One-liner thesis
    const thesis = decision?.cio_memo?.thesis_summary ?? "";

    const isComplete = combined.status === "complete";

    return (
        <div
            className={`relative overflow-hidden rounded-2xl border ${vc.border} ${vc.bg} p-6 md:p-8 transition-all duration-500`}
            style={{ animation: "verdictReveal 0.6s ease both", boxShadow: isComplete ? `0 0 40px -10px ${vc.glow}` : undefined }}
        >
            {/* Subtle gradient overlay */}
            <div className="absolute inset-0 bg-gradient-to-br from-transparent via-transparent to-black/20 pointer-events-none" />

            <div className="relative z-10">
                {/* Header */}
                <div className="flex items-start justify-between mb-6">
                    <div>
                        <div className="flex items-center gap-3 mb-1">
                            <h2 className="text-2xl md:text-3xl font-black tracking-tight text-white">{ticker}</h2>
                            {price !== null && (
                                <span className="text-sm font-mono text-gray-400">${price.toFixed(2)}</span>
                            )}
                        </div>
                        <p className="text-xs text-gray-500">{name}</p>
                    </div>

                    {/* Verdict badge */}
                    <div className={`px-4 py-2 rounded-xl border ${vc.border} ${vc.bg}`} style={{ animation: isComplete ? "badgePop 0.5s ease 0.3s both" : undefined }}>
                        <span className={`text-xs md:text-sm font-black uppercase tracking-widest ${vc.text}`}>
                            {position === "ANALYZING" ? "Analyzing..." : position}
                        </span>
                    </div>
                </div>

                {/* Metric cards */}
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3 mb-6">
                    <div className="col-span-2 sm:col-span-1 flex justify-center">
                        <ScoreRing value={oppScore} label="Score" />
                    </div>
                    <MetricPill
                        icon={<Activity size={14} />}
                        label="Alpha"
                        value={compositeAlpha.toFixed(0)}
                        color={compositeAlpha > 60 ? "text-green-400" : compositeAlpha > 40 ? "text-yellow-400" : "text-red-400"}
                    />
                    <MetricPill
                        icon={<Target size={14} />}
                        label="Allocation"
                        value={`${(allocation * 100).toFixed(1)}%`}
                        color="text-[#d4af37]"
                    />
                    <MetricPill
                        icon={<Shield size={14} />}
                        label="Risk"
                        value={risk}
                        color={riskColor(risk)}
                    />
                    <MetricPill
                        icon={<Users size={14} />}
                        label="Vote"
                        value={`${agentVotes}/${totalAgents}`}
                        color="text-gray-300"
                    />
                </div>

                {/* Thesis one-liner */}
                {thesis && (
                    <p className="text-sm text-gray-300 italic leading-relaxed mb-4 pl-3 border-l-2 border-[#d4af37]/40">
                        &ldquo;{thesis}&rdquo;
                    </p>
                )}

                {/* Bottom bar: confidence + freshness + system health */}
                <div className="flex flex-wrap items-center justify-between gap-4 pt-4 border-t border-white/5">
                    <ConfidenceBar value={confidence} />
                    <div className="flex items-center gap-2">
                        <Clock size={10} className="text-gray-600" />
                        <span className="text-[9px] font-black uppercase tracking-widest text-gray-600">Freshness</span>
                        <span className={`text-[10px] font-mono font-bold ${freshnessLabel === "fresh" ? "text-green-400" : freshnessLabel === "aging" ? "text-yellow-400" : "text-red-400"}`}>
                            {freshnessLabel}
                        </span>
                    </div>
                    <HealthDots count={healthCount} />
                </div>
            </div>
        </div>
    );
}
