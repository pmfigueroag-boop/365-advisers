"use client";

import React from "react";
import type { CompositeAlphaResponse } from "@/hooks/useAlphaSignals";

// ── Radar chart configuration ────────────────────────────────────────────────

const CATEGORIES = [
    { key: "value", label: "Value", angle: 0 },
    { key: "quality", label: "Quality", angle: 45 },
    { key: "momentum", label: "Momentum", angle: 90 },
    { key: "growth", label: "Growth", angle: 135 },
    { key: "volatility", label: "Volatility", angle: 180 },
    { key: "flow", label: "Flow", angle: 225 },
    { key: "event", label: "Event", angle: 270 },
    { key: "macro", label: "Macro", angle: 315 },
];

const CX = 150;
const CY = 150;
const MAX_R = 110;
const RINGS = [20, 40, 60, 80, 100];
const LABEL_R = MAX_R + 18;

function polarToXY(angleDeg: number, radius: number): [number, number] {
    const rad = ((angleDeg - 90) * Math.PI) / 180;
    return [CX + radius * Math.cos(rad), CY + radius * Math.sin(rad)];
}

// ── Component ────────────────────────────────────────────────────────────────

interface AlphaRadarChartProps {
    data: CompositeAlphaResponse | null | undefined;
}

export default function AlphaRadarChart({ data }: AlphaRadarChartProps) {
    if (!data) return null;

    // Build polygon points from subscores
    const polygonPoints = CATEGORIES.map(({ key, angle }) => {
        const score = data.subscores[key]?.score ?? 0;
        const r = (score / 100) * MAX_R;
        const [x, y] = polarToXY(angle, r);
        return `${x},${y}`;
    }).join(" ");

    const gradientId = `radar-fill-${Math.random().toString(36).slice(2, 8)}`;

    return (
        <div
            className="glass-card p-5 border border-[#30363d]"
            style={{ animation: "fadeSlideIn 0.5s ease 0.1s both" }}
        >
            <p className="text-[8px] font-black uppercase tracking-[0.2em] text-gray-600 mb-4">
                Signal Radar
            </p>

            <svg viewBox="0 0 300 300" className="w-full max-w-[320px] mx-auto">
                <defs>
                    <radialGradient id={gradientId} cx="50%" cy="50%" r="50%">
                        <stop offset="0%" stopColor="#d4af37" stopOpacity="0.35" />
                        <stop offset="100%" stopColor="#d4af37" stopOpacity="0.05" />
                    </radialGradient>
                </defs>

                {/* Ring guides */}
                {RINGS.map((ring) => {
                    const r = (ring / 100) * MAX_R;
                    return (
                        <circle
                            key={ring}
                            cx={CX}
                            cy={CY}
                            r={r}
                            fill="none"
                            stroke="#21262d"
                            strokeWidth="0.7"
                        />
                    );
                })}

                {/* Axis lines */}
                {CATEGORIES.map(({ key, angle }) => {
                    const [x, y] = polarToXY(angle, MAX_R);
                    return (
                        <line
                            key={key}
                            x1={CX}
                            y1={CY}
                            x2={x}
                            y2={y}
                            stroke="#21262d"
                            strokeWidth="0.5"
                        />
                    );
                })}

                {/* Data polygon */}
                <polygon
                    points={polygonPoints}
                    fill={`url(#${gradientId})`}
                    stroke="#d4af37"
                    strokeWidth="1.5"
                    strokeLinejoin="round"
                    style={{
                        transition: "all 0.8s cubic-bezier(0.34, 1.56, 0.64, 1)",
                    }}
                />

                {/* Data points with glow */}
                {CATEGORIES.map(({ key, angle }) => {
                    const score = data.subscores[key]?.score ?? 0;
                    const r = (score / 100) * MAX_R;
                    const [x, y] = polarToXY(angle, r);
                    const hasConflict = data.subscores[key]?.conflict_detected;
                    return (
                        <g key={key}>
                            <circle
                                cx={x}
                                cy={y}
                                r="4"
                                fill={hasConflict ? "#f97316" : "#d4af37"}
                                stroke={hasConflict ? "#f97316" : "#d4af37"}
                                strokeWidth="1"
                                opacity="0.9"
                            />
                            <circle
                                cx={x}
                                cy={y}
                                r="7"
                                fill="none"
                                stroke={hasConflict ? "#f97316" : "#d4af37"}
                                strokeWidth="0.5"
                                opacity="0.3"
                            />
                        </g>
                    );
                })}

                {/* Axis labels */}
                {CATEGORIES.map(({ key, label, angle }) => {
                    const [x, y] = polarToXY(angle, LABEL_R);
                    const score = data.subscores[key]?.score ?? 0;
                    return (
                        <g key={`label-${key}`}>
                            <text
                                x={x}
                                y={y - 4}
                                textAnchor="middle"
                                dominantBaseline="central"
                                className="fill-gray-400"
                                style={{
                                    fontSize: "8px",
                                    fontWeight: 700,
                                    letterSpacing: "0.05em",
                                    textTransform: "uppercase",
                                }}
                            >
                                {label}
                            </text>
                            <text
                                x={x}
                                y={y + 8}
                                textAnchor="middle"
                                dominantBaseline="central"
                                className="fill-white"
                                style={{
                                    fontSize: "9px",
                                    fontWeight: 900,
                                    fontFamily: "monospace",
                                }}
                            >
                                {score.toFixed(0)}
                            </text>
                        </g>
                    );
                })}
            </svg>
        </div>
    );
}
