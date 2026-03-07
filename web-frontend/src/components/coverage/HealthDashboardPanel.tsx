"use client";

/**
 * HealthDashboardPanel.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Enhanced provider health panel for System Intelligence view.
 * Shows provider cards with mini sparklines, avg latency, uptime,
 * and recent failures. Fetches from /providers/health and
 * /providers/health/history/{name}.
 */

import { useState, useEffect, useCallback } from "react";
import {
    Activity,
    AlertTriangle,
    CheckCircle2,
    Globe,
    RefreshCw,
    Wifi,
    WifiOff,
} from "lucide-react";

// ── Types ────────────────────────────────────────────────────────────────

interface HealthSnapshot {
    status: string;
    circuit_breaker_state: string;
    consecutive_failures: number;
    avg_latency_ms: number;
    success_rate_24h: number;
    snapshot_at: string | null;
}

interface ProviderSummary {
    status: string;
    avg_latency_ms: number;
    consecutive_failures: number;
    last_success: string | null;
    last_failure: string | null;
    circuit_breaker_state?: string;
}

interface AggregateHealth {
    overall_status: string;
    active_count: number;
    degraded_count: number;
    disabled_count: number;
    providers: Record<string, ProviderSummary>;
}

// ── Constants ────────────────────────────────────────────────────────────

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const OVERALL_STYLES: Record<string, { color: string; bg: string; label: string }> = {
    healthy: { color: "#22C55E", bg: "rgba(34,197,94,0.1)", label: "All Systems Operational" },
    degraded: { color: "#F59E0B", bg: "rgba(245,158,11,0.1)", label: "Degraded Performance" },
    critical: { color: "#EF4444", bg: "rgba(239,68,68,0.1)", label: "Critical — Multiple Failures" },
};

// ── Component ────────────────────────────────────────────────────────────

export default function HealthDashboardPanel() {
    const [health, setHealth] = useState<AggregateHealth | null>(null);
    const [histories, setHistories] = useState<Record<string, HealthSnapshot[]>>({});
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchHealth = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`${BACKEND}/providers/health`);
            const data = await res.json();
            setHealth(data);

            // Fetch histories for each provider (concurrently)
            const providerNames = Object.keys(data.providers || {});
            const historyResults = await Promise.allSettled(
                providerNames.map(async (name) => {
                    const hRes = await fetch(
                        `${BACKEND}/providers/health/history/${encodeURIComponent(name)}?hours=24`,
                    );
                    const hData = await hRes.json();
                    return { name, snapshots: hData.snapshots || [] };
                }),
            );

            const hMap: Record<string, HealthSnapshot[]> = {};
            for (const result of historyResults) {
                if (result.status === "fulfilled") {
                    hMap[result.value.name] = result.value.snapshots;
                }
            }
            setHistories(hMap);
        } catch (e) {
            setError("Could not reach provider health endpoint");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchHealth();
    }, [fetchHealth]);

    if (!health) {
        return (
            <div
                style={{
                    background: "linear-gradient(135deg, rgba(15,23,42,0.95), rgba(15,23,42,0.85))",
                    border: "1px solid rgba(212,175,55,0.15)",
                    borderRadius: 12,
                    padding: "20px 24px",
                    textAlign: "center" as const,
                    color: "#64748B",
                    fontSize: 13,
                }}
            >
                {loading ? "Loading provider health…" : error || "No data"}
            </div>
        );
    }

    const overall = OVERALL_STYLES[health.overall_status] || OVERALL_STYLES.healthy;
    const providers = Object.entries(health.providers || {});

    return (
        <div
            style={{
                background: "linear-gradient(135deg, rgba(15,23,42,0.95), rgba(15,23,42,0.85))",
                border: "1px solid rgba(212,175,55,0.15)",
                borderRadius: 12,
                padding: "20px 24px",
            }}
        >
            {/* Header */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <Globe size={16} style={{ color: "#D4AF37" }} />
                    <h3
                        style={{
                            fontSize: 13, fontWeight: 900,
                            textTransform: "uppercase" as const,
                            letterSpacing: "0.1em", color: "#E2E8F0", margin: 0,
                        }}
                    >
                        Provider Health Monitor
                    </h3>
                </div>
                <button
                    onClick={fetchHealth}
                    disabled={loading}
                    style={{
                        background: "rgba(212,175,55,0.1)",
                        border: "1px solid rgba(212,175,55,0.2)",
                        borderRadius: 6, padding: "4px 8px",
                        cursor: "pointer", display: "flex",
                        alignItems: "center", gap: 4,
                        color: "#D4AF37", fontSize: 11,
                    }}
                >
                    <RefreshCw size={12} style={{ animation: loading ? "spin 1s linear infinite" : "none" }} />
                    Refresh
                </button>
            </div>

            {/* Overall status banner */}
            <div
                style={{
                    background: overall.bg,
                    border: `1px solid ${overall.color}30`,
                    borderRadius: 8, padding: "10px 14px",
                    marginBottom: 16,
                    display: "flex", alignItems: "center", justifyContent: "space-between",
                }}
            >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span
                        style={{
                            width: 8, height: 8, borderRadius: "50%",
                            background: overall.color,
                            boxShadow: `0 0 8px ${overall.color}60`,
                        }}
                    />
                    <span style={{ fontSize: 12, fontWeight: 700, color: overall.color }}>
                        {overall.label}
                    </span>
                </div>
                <div style={{ display: "flex", gap: 10, fontSize: 11, color: "#94A3B8" }}>
                    <span>
                        <strong style={{ color: "#22C55E" }}>{health.active_count}</strong> active
                    </span>
                    {health.degraded_count > 0 && (
                        <span>
                            <strong style={{ color: "#F59E0B" }}>{health.degraded_count}</strong> degraded
                        </span>
                    )}
                    {health.disabled_count > 0 && (
                        <span>
                            <strong style={{ color: "#EF4444" }}>{health.disabled_count}</strong> disabled
                        </span>
                    )}
                </div>
            </div>

            {/* Provider cards grid */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 10 }}>
                {providers.map(([name, prov]) => {
                    const snapshots = histories[name] || [];
                    const isHealthy = prov.status === "active" && prov.consecutive_failures === 0;
                    const statusColor = isHealthy ? "#22C55E" : prov.status === "degraded" ? "#F59E0B" : "#EF4444";

                    return (
                        <div
                            key={name}
                            style={{
                                background: "rgba(30,41,59,0.6)",
                                border: "1px solid rgba(148,163,184,0.08)",
                                borderRadius: 8, padding: 12,
                            }}
                        >
                            {/* Name + status */}
                            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                                <span style={{ fontSize: 11, fontWeight: 700, color: "#E2E8F0", textTransform: "uppercase" as const }}>
                                    {name}
                                </span>
                                <span
                                    style={{
                                        width: 8, height: 8, borderRadius: "50%",
                                        background: statusColor,
                                        boxShadow: `0 0 6px ${statusColor}50`,
                                    }}
                                />
                            </div>

                            {/* Mini sparkline */}
                            {snapshots.length > 0 && (
                                <MiniSparkline data={snapshots.map((s) => s.avg_latency_ms || 0)} />
                            )}

                            {/* Metrics */}
                            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 4, marginTop: 6 }}>
                                <div style={{ fontSize: 9, color: "#64748B", textTransform: "uppercase" as const }}>
                                    Latency
                                    <div style={{ fontSize: 12, fontWeight: 700, color: "#E2E8F0" }}>
                                        {prov.avg_latency_ms.toFixed(0)}ms
                                    </div>
                                </div>
                                <div style={{ fontSize: 9, color: "#64748B", textTransform: "uppercase" as const }}>
                                    Failures
                                    <div
                                        style={{
                                            fontSize: 12, fontWeight: 700,
                                            color: prov.consecutive_failures === 0 ? "#22C55E" : "#EF4444",
                                        }}
                                    >
                                        {prov.consecutive_failures}
                                    </div>
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>

            {providers.length === 0 && (
                <div style={{ textAlign: "center" as const, padding: "16px 0", color: "#64748B", fontSize: 12 }}>
                    No providers registered
                </div>
            )}
        </div>
    );
}

// ── Mini Sparkline ──────────────────────────────────────────────────────

function MiniSparkline({ data }: { data: number[] }) {
    if (data.length < 2) return null;

    const max = Math.max(...data, 1);
    const width = 180;
    const height = 24;
    const points = data.map((v, i) => {
        const x = (i / (data.length - 1)) * width;
        const y = height - (v / max) * height;
        return `${x},${y}`;
    });

    return (
        <svg width={width} height={height} style={{ display: "block", marginBottom: 4, opacity: 0.7 }}>
            <polyline
                points={points.join(" ")}
                fill="none"
                stroke="#D4AF37"
                strokeWidth={1.5}
                strokeLinejoin="round"
            />
        </svg>
    );
}
