/**
 * TechnicalICDashboard.tsx
 * ─────────────────────────────────────────────────────────────────────────────
 * Technical IC "War Room" — 5-round visual panel showing the structured debate
 * between 6 specialist agents interpreting technical data through distinct
 * theoretical frameworks.
 *
 * Follows the established design system:
 *   - Dark theme (#0d1117 / #161b22)
 *   - Glass cards with #30363d borders
 *   - Gold accent (#d4af37) for active states
 */

"use client";

import React, { useState } from "react";
import {
    Swords,
    Play,
    RotateCcw,
    Clock,
    TrendingUp,
    Activity,
    BarChart3,
    Volume2,
    Landmark,
    Layers,
    Target,
    Shield,
    ChevronDown,
    ChevronUp,
    AlertTriangle,
    CheckCircle,
    XCircle,
    Crosshair,
} from "lucide-react";
import {
    useTechnicalICStream,
    type TacticalAssessment,
    type TacticalConflict,
    type TimeframeAssessment,
    type TacticalVote,
    type TechnicalICVerdict,
} from "@/hooks/useTechnicalICStream";

// ─── Types ──────────────────────────────────────────────────────────────────

interface Props {
    ticker: string | null;
}

// ─── Design Helpers ─────────────────────────────────────────────────────────

const signalColor = (signal: string) => {
    const s = signal?.toUpperCase() || "";
    if (s.includes("BUY") || s === "BULLISH") return "#22c55e";
    if (s.includes("SELL") || s === "BEARISH") return "#ef4444";
    return "#a1a1aa";
};

const signalBg = (signal: string) => {
    const s = signal?.toUpperCase() || "";
    if (s.includes("BUY") || s === "BULLISH") return "rgba(34,197,94,0.12)";
    if (s.includes("SELL") || s === "BEARISH") return "rgba(239,68,68,0.12)";
    return "rgba(161,161,170,0.08)";
};

const severityColor = (severity: string) => {
    if (severity === "HIGH") return "#ef4444";
    if (severity === "MEDIUM") return "#f59e0b";
    return "#a1a1aa";
};

const domainIcon = (domain: string) => {
    const props = { size: 14 };
    switch (domain) {
        case "trend": return <TrendingUp {...props} />;
        case "momentum": return <Activity {...props} />;
        case "volatility": return <BarChart3 {...props} />;
        case "volume": return <Volume2 {...props} />;
        case "structure": return <Landmark {...props} />;
        case "mtf": return <Layers {...props} />;
        default: return <Target {...props} />;
    }
};

const ROUND_LABELS = ["Assess", "Conflict", "Timeframe", "Conviction", "Verdict"];
const GOLD = "#d4af37";

// ─── Sub-Components ─────────────────────────────────────────────────────────

function AssessmentCard({ a }: { a: TacticalAssessment }) {
    const [open, setOpen] = useState(false);
    return (
        <div
            style={{
                background: "#161b22",
                border: `1px solid ${signalColor(a.signal)}33`,
                borderRadius: 10,
                padding: "14px 16px",
                display: "flex",
                flexDirection: "column",
                gap: 10,
            }}
        >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ color: signalColor(a.signal) }}>{domainIcon(a.domain)}</span>
                    <span style={{ fontWeight: 600, fontSize: 13, color: "#e6edf3" }}>{a.agent}</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span
                        style={{
                            background: signalBg(a.signal),
                            color: signalColor(a.signal),
                            padding: "2px 10px",
                            borderRadius: 20,
                            fontSize: 11,
                            fontWeight: 600,
                        }}
                    >
                        {a.signal}
                    </span>
                    <span style={{ fontSize: 11, color: "#8b949e" }}>
                        {Math.round(a.conviction * 100)}%
                    </span>
                </div>
            </div>
            <p style={{ fontSize: 12, color: "#c9d1d9", lineHeight: 1.5, margin: 0 }}>
                {a.thesis}
            </p>
            {(a.theoretical_framework || a.cross_module_note) && (
                <button
                    onClick={() => setOpen(!open)}
                    style={{
                        background: "none",
                        border: "none",
                        color: GOLD,
                        fontSize: 11,
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: 4,
                        padding: 0,
                    }}
                >
                    {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                    {open ? "Less" : "Framework & Details"}
                </button>
            )}
            {open && (
                <div style={{ fontSize: 11, color: "#8b949e", display: "flex", flexDirection: "column", gap: 6 }}>
                    {a.theoretical_framework && (
                        <div>
                            <strong style={{ color: "#c9d1d9" }}>Framework:</strong>{" "}
                            {a.theoretical_framework}
                        </div>
                    )}
                    {a.cross_module_note && (
                        <div>
                            <strong style={{ color: "#c9d1d9" }}>Cross-Module:</strong>{" "}
                            {a.cross_module_note}
                        </div>
                    )}
                    {a.supporting_data?.length > 0 && (
                        <div>
                            <strong style={{ color: "#c9d1d9" }}>Data:</strong>
                            <ul style={{ margin: "4px 0 0 16px", padding: 0 }}>
                                {a.supporting_data.map((d, i) => (
                                    <li key={i}>{d}</li>
                                ))}
                            </ul>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

function ConflictCard({ c }: { c: TacticalConflict }) {
    return (
        <div
            style={{
                background: "#161b22",
                border: `1px solid ${severityColor(c.severity)}33`,
                borderRadius: 10,
                padding: "14px 16px",
                display: "flex",
                flexDirection: "column",
                gap: 8,
            }}
        >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: "#e6edf3" }}>
                    <Swords size={12} style={{ marginRight: 6, color: severityColor(c.severity) }} />
                    {c.challenger} → {c.target}
                </span>
                <span
                    style={{
                        fontSize: 10,
                        padding: "2px 8px",
                        borderRadius: 20,
                        background: `${severityColor(c.severity)}20`,
                        color: severityColor(c.severity),
                        fontWeight: 600,
                    }}
                >
                    {c.severity}
                </span>
            </div>
            <p style={{ fontSize: 12, color: "#c9d1d9", margin: 0, lineHeight: 1.5 }}>
                {c.disagreement}
            </p>
            {c.theoretical_basis && (
                <p style={{ fontSize: 11, color: "#8b949e", margin: 0, fontStyle: "italic" }}>
                    Basis: {c.theoretical_basis}
                </p>
            )}
        </div>
    );
}

function TimeframeCard({ t }: { t: TimeframeAssessment }) {
    const alignColor =
        t.timeframe_alignment === "ALIGNED"
            ? "#22c55e"
            : t.timeframe_alignment === "DIVERGENT"
                ? "#ef4444"
                : "#f59e0b";
    return (
        <div
            style={{
                background: "#161b22",
                border: `1px solid ${alignColor}33`,
                borderRadius: 10,
                padding: "14px 16px",
                display: "flex",
                flexDirection: "column",
                gap: 8,
            }}
        >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: "#e6edf3" }}>{t.agent}</span>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span
                        style={{
                            fontSize: 10,
                            padding: "2px 8px",
                            borderRadius: 20,
                            background: `${alignColor}20`,
                            color: alignColor,
                            fontWeight: 600,
                        }}
                    >
                        {t.timeframe_alignment}
                    </span>
                    <span style={{ fontSize: 11, color: "#8b949e" }}>
                        Dom: {t.dominant_timeframe}
                    </span>
                </div>
            </div>
            {t.defense && (
                <p style={{ fontSize: 12, color: "#c9d1d9", margin: 0, lineHeight: 1.5 }}>
                    {t.defense}
                </p>
            )}
            {t.conviction_adjustment !== 0 && (
                <span style={{ fontSize: 11, color: t.conviction_adjustment > 0 ? "#22c55e" : "#ef4444" }}>
                    Conviction: {t.conviction_adjustment > 0 ? "+" : ""}{(t.conviction_adjustment * 100).toFixed(0)}%
                </span>
            )}
            {Object.keys(t.timeframe_readings || {}).length > 0 && (
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    {Object.entries(t.timeframe_readings).map(([tf, sig]) => (
                        <span
                            key={tf}
                            style={{
                                fontSize: 10,
                                padding: "2px 6px",
                                borderRadius: 4,
                                background: signalBg(sig),
                                color: signalColor(sig),
                                fontWeight: 500,
                            }}
                        >
                            {tf}: {sig}
                        </span>
                    ))}
                </div>
            )}
        </div>
    );
}

function VoteCard({ v }: { v: TacticalVote }) {
    return (
        <div
            style={{
                background: "#161b22",
                border: `1px solid ${v.dissents ? "#ef444433" : "#30363d"}`,
                borderRadius: 10,
                padding: "12px 16px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
            }}
        >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: "#e6edf3" }}>{v.agent}</span>
                <span
                    style={{
                        background: signalBg(v.signal),
                        color: signalColor(v.signal),
                        padding: "2px 10px",
                        borderRadius: 20,
                        fontSize: 11,
                        fontWeight: 600,
                    }}
                >
                    {v.signal}
                </span>
                {v.dissents && (
                    <span style={{ fontSize: 10, color: "#ef4444", fontWeight: 600 }}>⚠️ DISSENT</span>
                )}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 11, color: "#8b949e" }}>
                <span>Conv: {Math.round(v.conviction * 100)}%</span>
                {v.conviction_drift !== 0 && (
                    <span style={{ color: v.conviction_drift > 0 ? "#22c55e" : "#ef4444" }}>
                        Drift: {v.conviction_drift > 0 ? "+" : ""}{(v.conviction_drift * 100).toFixed(0)}%
                    </span>
                )}
                <span>Weight: {v.regime_weight.toFixed(1)}×</span>
            </div>
        </div>
    );
}

function VerdictPanel({ v }: { v: TechnicalICVerdict }) {
    const consensusColor =
        v.consensus_strength === "unanimous" || v.consensus_strength === "strong_majority"
            ? "#22c55e"
            : v.consensus_strength === "contested" || v.consensus_strength === "split"
                ? "#ef4444"
                : "#f59e0b";

    return (
        <div
            style={{
                background: "linear-gradient(135deg, #161b22 0%, #0d1117 100%)",
                border: `1px solid ${GOLD}44`,
                borderRadius: 12,
                padding: 20,
                display: "flex",
                flexDirection: "column",
                gap: 16,
            }}
        >
            {/* Hero */}
            <div style={{ textAlign: "center" }}>
                <span
                    style={{
                        fontSize: 48,
                        fontWeight: 900,
                        color: signalColor(v.signal),
                        letterSpacing: -1,
                        fontVariantNumeric: "tabular-nums",
                        filter: "drop-shadow(0 2px 8px rgba(0,0,0,0.5))",
                    }}
                >
                    {(v.score ?? 5).toFixed(1)}
                </span>
                <span style={{ fontSize: 10, color: "#8b949e", fontWeight: 700, marginLeft: 2 }}>/10</span>
                <div
                    style={{
                        fontSize: 28, fontWeight: 700,
                        color: signalColor(v.signal),
                        letterSpacing: 2,
                        marginTop: 4,
                    }}
                >
                    {v.signal}
                </div>
                <div style={{ fontSize: 12, color: "#8b949e", marginTop: 4 }}>
                    Confidence: {Math.round(v.confidence * 100)}% ·{" "}
                    <span style={{ color: consensusColor }}>{v.consensus_strength.replace("_", " ")}</span>
                </div>
            </div>

            {/* Narrative */}
            <div
                style={{
                    background: "#0d111766",
                    borderRadius: 8,
                    padding: "12px 14px",
                    fontSize: 13,
                    color: "#c9d1d9",
                    lineHeight: 1.6,
                    borderLeft: `3px solid ${GOLD}`,
                }}
            >
                {v.narrative}
            </div>

            {/* Action Plan */}
            {v.action_plan && (v.action_plan.entry_zone || v.action_plan.stop_loss) && (
                <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: GOLD, marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
                        <Crosshair size={14} /> ACTION PLAN
                    </div>
                    <div
                        style={{
                            display: "grid",
                            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                            gap: 8,
                        }}
                    >
                        {v.action_plan.entry_zone && (
                            <div style={{ background: "#0d1117", borderRadius: 8, padding: "8px 12px" }}>
                                <div style={{ fontSize: 10, color: "#8b949e" }}>Entry Zone</div>
                                <div style={{ fontSize: 12, color: "#22c55e", fontWeight: 600 }}>{v.action_plan.entry_zone}</div>
                            </div>
                        )}
                        {v.action_plan.stop_loss && (
                            <div style={{ background: "#0d1117", borderRadius: 8, padding: "8px 12px" }}>
                                <div style={{ fontSize: 10, color: "#8b949e" }}>Stop Loss</div>
                                <div style={{ fontSize: 12, color: "#ef4444", fontWeight: 600 }}>{v.action_plan.stop_loss}</div>
                            </div>
                        )}
                        {v.action_plan.take_profit_1 && (
                            <div style={{ background: "#0d1117", borderRadius: 8, padding: "8px 12px" }}>
                                <div style={{ fontSize: 10, color: "#8b949e" }}>Take Profit 1</div>
                                <div style={{ fontSize: 12, color: "#22c55e", fontWeight: 600 }}>{v.action_plan.take_profit_1}</div>
                            </div>
                        )}
                        {v.action_plan.take_profit_2 && (
                            <div style={{ background: "#0d1117", borderRadius: 8, padding: "8px 12px" }}>
                                <div style={{ fontSize: 10, color: "#8b949e" }}>Take Profit 2</div>
                                <div style={{ fontSize: 12, color: "#22c55e" }}>{v.action_plan.take_profit_2}</div>
                            </div>
                        )}
                        {v.action_plan.risk_reward && (
                            <div style={{ background: "#0d1117", borderRadius: 8, padding: "8px 12px" }}>
                                <div style={{ fontSize: 10, color: "#8b949e" }}>R/R Ratio</div>
                                <div style={{ fontSize: 12, color: GOLD, fontWeight: 600 }}>{v.action_plan.risk_reward}</div>
                            </div>
                        )}
                        {v.action_plan.invalidation && (
                            <div style={{ background: "#0d1117", borderRadius: 8, padding: "8px 12px" }}>
                                <div style={{ fontSize: 10, color: "#8b949e" }}>Invalidation</div>
                                <div style={{ fontSize: 12, color: "#ef4444" }}>{v.action_plan.invalidation}</div>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Vote Breakdown + Key Levels + Timing */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                {v.key_levels && (
                    <div style={{ background: "#0d1117", borderRadius: 8, padding: "10px 14px" }}>
                        <div style={{ fontSize: 11, fontWeight: 600, color: "#8b949e", marginBottom: 4 }}>Key Levels</div>
                        <div style={{ fontSize: 12, color: "#c9d1d9" }}>{v.key_levels}</div>
                    </div>
                )}
                {v.timing && (
                    <div style={{ background: "#0d1117", borderRadius: 8, padding: "10px 14px" }}>
                        <div style={{ fontSize: 11, fontWeight: 600, color: "#8b949e", marginBottom: 4 }}>Timing</div>
                        <div style={{ fontSize: 12, color: "#c9d1d9" }}>{v.timing}</div>
                    </div>
                )}
            </div>

            {/* Risk Factors */}
            {v.risk_factors?.length > 0 && (
                <div>
                    <div style={{ fontSize: 11, fontWeight: 600, color: "#ef4444", marginBottom: 6, display: "flex", alignItems: "center", gap: 4 }}>
                        <AlertTriangle size={12} /> RISK FACTORS
                    </div>
                    <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12, color: "#c9d1d9" }}>
                        {v.risk_factors.map((r, i) => (
                            <li key={i} style={{ marginBottom: 4 }}>{r}</li>
                        ))}
                    </ul>
                </div>
            )}

            {/* Dissenting Opinions */}
            {v.dissenting_opinions?.length > 0 && (
                <div>
                    <div style={{ fontSize: 11, fontWeight: 600, color: "#f59e0b", marginBottom: 6, display: "flex", alignItems: "center", gap: 4 }}>
                        <Shield size={12} /> DISSENTING OPINIONS
                    </div>
                    <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12, color: "#c9d1d9" }}>
                        {v.dissenting_opinions.map((d, i) => (
                            <li key={i} style={{ marginBottom: 4 }}>{d}</li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
}

// ─── Main Dashboard ─────────────────────────────────────────────────────────

export default function TechnicalICDashboard({ ticker }: Props) {
    const { state, run, reset } = useTechnicalICStream(ticker);
    const [activeRound, setActiveRound] = useState(0);

    // Auto-advance to latest completed round
    const completedRound =
        state.verdict ? 4
            : state.votes.length > 0 ? 3
                : state.timeframes.length > 0 ? 2
                    : state.conflicts.length > 0 ? 1
                        : state.assessments.length > 0 ? 0
                            : -1;

    const currentRound = Math.min(activeRound, completedRound >= 0 ? completedRound : 0);

    // Auto-track latest round
    React.useEffect(() => {
        if (completedRound >= 0) setActiveRound(completedRound);
    }, [completedRound]);

    // ── Idle State ───────────────────────────────────────────────
    if (state.status === "idle") {
        return (
            <div
                style={{
                    display: "flex", flexDirection: "column",
                    alignItems: "center", justifyContent: "center",
                    gap: 16, padding: 60, color: "#8b949e",
                }}
            >
                <Swords size={40} style={{ color: GOLD, opacity: 0.5 }} />
                <div style={{ fontSize: 16, fontWeight: 600, color: "#e6edf3" }}>
                    No War Room Session Active
                </div>
                <p style={{ fontSize: 13, maxWidth: 420, textAlign: "center", lineHeight: 1.6 }}>
                    The Technical IC assembles 6 specialist analysts — Trend, Momentum, Volatility,
                    Volume, Structure, and Multi-Timeframe — to debate and interpret real engine data
                    through distinct theoretical frameworks.
                </p>
                <button
                    onClick={run}
                    disabled={!ticker}
                    style={{
                        display: "flex", alignItems: "center", gap: 8,
                        padding: "10px 24px", borderRadius: 8,
                        background: GOLD, color: "#0d1117",
                        border: "none", fontWeight: 600, fontSize: 13,
                        cursor: ticker ? "pointer" : "not-allowed",
                        opacity: ticker ? 1 : 0.5,
                    }}
                >
                    <Swords size={14} /> Launch War Room
                </button>
            </div>
        );
    }

    // ── Error State ──────────────────────────────────────────────
    if (state.status === "error") {
        return (
            <div
                style={{
                    display: "flex", flexDirection: "column",
                    alignItems: "center", gap: 12, padding: 40, color: "#ef4444",
                }}
            >
                <XCircle size={32} />
                <span style={{ fontSize: 14, fontWeight: 600 }}>War Room Error</span>
                <span style={{ fontSize: 12, color: "#8b949e" }}>{state.error}</span>
                <button
                    onClick={reset}
                    style={{
                        padding: "8px 20px", borderRadius: 8,
                        background: "#21262d", color: "#c9d1d9",
                        border: "1px solid #30363d", cursor: "pointer",
                        fontSize: 12, fontWeight: 500,
                    }}
                >
                    <RotateCcw size={12} /> Reset
                </button>
            </div>
        );
    }

    // ── Active / Done ────────────────────────────────────────────
    return (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {/* Header */}
            <div
                style={{
                    display: "flex", justifyContent: "space-between",
                    alignItems: "center", padding: "8px 0",
                }}
            >
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <Swords size={18} style={{ color: GOLD }} />
                    <span style={{ fontSize: 15, fontWeight: 700, color: "#e6edf3" }}>
                        Technical War Room
                    </span>
                    {state.status === "running" && (
                        <span
                            style={{
                                fontSize: 10, padding: "2px 10px",
                                borderRadius: 20, background: "#d4af3730",
                                color: GOLD, fontWeight: 600,
                                animation: "pulse 2s infinite",
                            }}
                        >
                            ● LIVE
                        </span>
                    )}
                    {state.status === "done" && (
                        <span style={{ fontSize: 10, padding: "2px 10px", borderRadius: 20, background: "#22c55e20", color: "#22c55e", fontWeight: 600 }}>
                            ✓ COMPLETE
                        </span>
                    )}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    {state.elapsed_ms > 0 && (
                        <span style={{ fontSize: 11, color: "#8b949e", display: "flex", alignItems: "center", gap: 4 }}>
                            <Clock size={12} /> {(state.elapsed_ms / 1000).toFixed(1)}s
                        </span>
                    )}
                    <button
                        onClick={reset}
                        style={{
                            padding: "6px 14px", borderRadius: 6,
                            background: "#21262d", color: "#c9d1d9",
                            border: "1px solid #30363d", cursor: "pointer",
                            fontSize: 11, fontWeight: 500,
                            display: "flex", alignItems: "center", gap: 4,
                        }}
                    >
                        <RotateCcw size={11} /> Reset
                    </button>
                </div>
            </div>

            {/* Round Progress Bar */}
            <div
                style={{
                    display: "flex", gap: 0,
                    background: "#0d1117",
                    borderRadius: 8,
                    overflow: "hidden",
                    border: "1px solid #30363d",
                }}
            >
                {ROUND_LABELS.map((label, i) => {
                    const isComplete = completedRound >= i;
                    const isActive = currentRound === i;
                    return (
                        <button
                            key={label}
                            onClick={() => isComplete && setActiveRound(i)}
                            style={{
                                flex: 1,
                                padding: "8px 0",
                                background: isActive ? `${GOLD}22` : "transparent",
                                borderTop: "none",
                                borderLeft: "none",
                                borderBottom: isActive ? `2px solid ${GOLD}` : "2px solid transparent",
                                borderRight: i < 4 ? "1px solid #21262d" : "none",
                                color: isComplete ? (isActive ? GOLD : "#c9d1d9") : "#484f58",
                                fontSize: 11,
                                fontWeight: isActive ? 700 : 500,
                                cursor: isComplete ? "pointer" : "default",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                gap: 4,
                            }}
                        >
                            {isComplete && !isActive && <CheckCircle size={10} style={{ color: "#22c55e" }} />}
                            R{i + 1}: {label}
                        </button>
                    );
                })}
            </div>

            {/* Round Content */}
            <div style={{ minHeight: 200 }}>
                {/* Round 1: Assessments */}
                {currentRound === 0 && (
                    <div>
                        <div style={{ fontSize: 13, fontWeight: 600, color: "#e6edf3", marginBottom: 12 }}>
                            Round 1 — Initial Assessments
                        </div>
                        {state.assessments.length === 0 && state.status === "running" && (
                            <div style={{ color: "#8b949e", fontSize: 12, textAlign: "center", padding: 30 }}>
                                Agents are analyzing engine data through their theoretical frameworks...
                            </div>
                        )}
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: 10 }}>
                            {state.assessments.map((a, i) => (
                                <AssessmentCard key={i} a={a} />
                            ))}
                        </div>
                    </div>
                )}

                {/* Round 2: Conflicts */}
                {currentRound === 1 && (
                    <div>
                        <div style={{ fontSize: 13, fontWeight: 600, color: "#e6edf3", marginBottom: 12 }}>
                            Round 2 — Conflict Identification
                        </div>
                        {state.conflicts.length === 0 && state.status === "running" && (
                            <div style={{ color: "#8b949e", fontSize: 12, textAlign: "center", padding: 30 }}>
                                Identifying maximum-disagreement conflicts...
                            </div>
                        )}
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: 10 }}>
                            {state.conflicts.map((c, i) => (
                                <ConflictCard key={i} c={c} />
                            ))}
                        </div>
                    </div>
                )}

                {/* Round 3: Timeframe Reconciliation */}
                {currentRound === 2 && (
                    <div>
                        <div style={{ fontSize: 13, fontWeight: 600, color: "#e6edf3", marginBottom: 12 }}>
                            Round 3 — Timeframe Reconciliation
                        </div>
                        {state.timeframes.length === 0 && state.status === "running" && (
                            <div style={{ color: "#8b949e", fontSize: 12, textAlign: "center", padding: 30 }}>
                                Agents are reconciling their readings across 6 timeframes...
                            </div>
                        )}
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: 10 }}>
                            {state.timeframes.map((t, i) => (
                                <TimeframeCard key={i} t={t} />
                            ))}
                        </div>
                    </div>
                )}

                {/* Round 4: Conviction Votes */}
                {currentRound === 3 && (
                    <div>
                        <div style={{ fontSize: 13, fontWeight: 600, color: "#e6edf3", marginBottom: 12 }}>
                            Round 4 — Conviction Votes
                        </div>
                        {state.votes.length === 0 && state.status === "running" && (
                            <div style={{ color: "#8b949e", fontSize: 12, textAlign: "center", padding: 30 }}>
                                Casting final votes with regime-weighted conviction...
                            </div>
                        )}
                        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                            {state.votes.map((v, i) => (
                                <VoteCard key={i} v={v} />
                            ))}
                        </div>
                    </div>
                )}

                {/* Round 5: Verdict */}
                {currentRound === 4 && (
                    <div>
                        <div style={{ fontSize: 13, fontWeight: 600, color: "#e6edf3", marginBottom: 12 }}>
                            Round 5 — Head Technician Verdict
                        </div>
                        {!state.verdict && state.status === "running" && (
                            <div style={{ color: "#8b949e", fontSize: 12, textAlign: "center", padding: 30 }}>
                                Head Technician is synthesizing the debate...
                            </div>
                        )}
                        {state.verdict && <VerdictPanel v={state.verdict} />}
                    </div>
                )}
            </div>
        </div>
    );
}
