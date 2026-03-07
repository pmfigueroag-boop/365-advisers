"use client";

/**
 * ProviderHealthDashboard.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Real-time dashboard for EDPL provider health, status, and capabilities.
 * Shows each registered provider with circuit breaker state, latency, and
 * enable/disable controls.
 */

import { useState } from "react";
import {
    Activity,
    AlertTriangle,
    CheckCircle2,
    ChevronDown,
    ChevronRight,
    Globe,
    Power,
    RefreshCw,
    Shield,
    Wifi,
    WifiOff,
    Zap,
} from "lucide-react";
import { useProviderHealth, ProviderHealth, RegistryEntry } from "@/hooks/useProviderHealth";

// ── Domain labels & icons ───────────────────────────────────────────────────

const DOMAIN_META: Record<string, { label: string; color: string }> = {
    market_data: { label: "Market Data", color: "#10B981" },
    etf_flows: { label: "ETF Flows", color: "#6366F1" },
    options: { label: "Options Intelligence", color: "#F59E0B" },
    institutional: { label: "Institutional Flow", color: "#8B5CF6" },
    sentiment: { label: "News & Sentiment", color: "#EC4899" },
    macro: { label: "Macro Nowcasting", color: "#14B8A6" },
};

const STATUS_STYLES: Record<string, { bg: string; text: string; icon: any }> = {
    active: { bg: "rgba(16, 185, 129, 0.1)", text: "#10B981", icon: CheckCircle2 },
    degraded: { bg: "rgba(245, 158, 11, 0.1)", text: "#F59E0B", icon: AlertTriangle },
    disabled: { bg: "rgba(239, 68, 68, 0.1)", text: "#EF4444", icon: WifiOff },
    unknown: { bg: "rgba(107, 114, 128, 0.1)", text: "#6B7280", icon: Wifi },
};

// ── Component ───────────────────────────────────────────────────────────────

export default function ProviderHealthDashboard() {
    const { health, registry, loading, error, refresh, toggleProvider } = useProviderHealth();
    const [expandedDomain, setExpandedDomain] = useState<string | null>(null);

    // Count providers by status
    const statusCounts = Object.values(health).reduce(
        (acc, p) => {
            acc[p.status] = (acc[p.status] || 0) + 1;
            return acc;
        },
        {} as Record<string, number>,
    );
    const totalProviders = Object.keys(health).length;
    const activeCount = statusCounts["active"] || 0;

    return (
        <div
            style={{
                background: "linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(15, 23, 42, 0.85))",
                border: "1px solid rgba(212, 175, 55, 0.15)",
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
                            fontSize: 13,
                            fontWeight: 900,
                            textTransform: "uppercase" as const,
                            letterSpacing: "0.1em",
                            color: "#E2E8F0",
                            margin: 0,
                        }}
                    >
                        External Data Providers
                    </h3>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    {/* Status summary pills */}
                    <div style={{ display: "flex", gap: 6 }}>
                        <span
                            style={{
                                fontSize: 11,
                                padding: "2px 8px",
                                borderRadius: 8,
                                background: "rgba(16, 185, 129, 0.15)",
                                color: "#10B981",
                                fontWeight: 700,
                            }}
                        >
                            {activeCount}/{totalProviders} Active
                        </span>
                        {(statusCounts["degraded"] || 0) > 0 && (
                            <span
                                style={{
                                    fontSize: 11,
                                    padding: "2px 8px",
                                    borderRadius: 8,
                                    background: "rgba(245, 158, 11, 0.15)",
                                    color: "#F59E0B",
                                    fontWeight: 700,
                                }}
                            >
                                {statusCounts["degraded"]} Degraded
                            </span>
                        )}
                    </div>

                    {/* Refresh button */}
                    <button
                        onClick={refresh}
                        disabled={loading}
                        style={{
                            background: "rgba(212, 175, 55, 0.1)",
                            border: "1px solid rgba(212, 175, 55, 0.2)",
                            borderRadius: 6,
                            padding: "4px 8px",
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            gap: 4,
                            color: "#D4AF37",
                            fontSize: 11,
                        }}
                    >
                        <RefreshCw size={12} style={{ animation: loading ? "spin 1s linear infinite" : "none" }} />
                        Refresh
                    </button>
                </div>
            </div>

            {error && (
                <div
                    style={{
                        background: "rgba(239, 68, 68, 0.1)",
                        border: "1px solid rgba(239, 68, 68, 0.2)",
                        borderRadius: 8,
                        padding: "8px 12px",
                        fontSize: 12,
                        color: "#EF4444",
                        marginBottom: 12,
                    }}
                >
                    {error}
                </div>
            )}

            {/* Domain Sections */}
            <div style={{ display: "flex", flexDirection: "column" as const, gap: 8 }}>
                {registry?.active_domains?.map((domain) => {
                    const meta = DOMAIN_META[domain] || { label: domain, color: "#6B7280" };
                    const entries: RegistryEntry[] = registry.domains[domain] || [];
                    const isExpanded = expandedDomain === domain;

                    return (
                        <div
                            key={domain}
                            style={{
                                background: "rgba(30, 41, 59, 0.6)",
                                border: "1px solid rgba(148, 163, 184, 0.08)",
                                borderRadius: 8,
                                overflow: "hidden",
                            }}
                        >
                            {/* Domain header row */}
                            <div
                                onClick={() => setExpandedDomain(isExpanded ? null : domain)}
                                style={{
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "space-between",
                                    padding: "10px 14px",
                                    cursor: "pointer",
                                    transition: "background 0.15s ease",
                                }}
                                onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(30, 41, 59, 0.9)")}
                                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                            >
                                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                                    {isExpanded ? (
                                        <ChevronDown size={14} style={{ color: "#94A3B8" }} />
                                    ) : (
                                        <ChevronRight size={14} style={{ color: "#94A3B8" }} />
                                    )}
                                    <div
                                        style={{
                                            width: 8,
                                            height: 8,
                                            borderRadius: "50%",
                                            background: meta.color,
                                            boxShadow: `0 0 6px ${meta.color}40`,
                                        }}
                                    />
                                    <span
                                        style={{
                                            fontSize: 12,
                                            fontWeight: 700,
                                            color: "#E2E8F0",
                                            textTransform: "uppercase" as const,
                                            letterSpacing: "0.05em",
                                        }}
                                    >
                                        {meta.label}
                                    </span>
                                </div>

                                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                    {entries.map((entry) => {
                                        const st = STATUS_STYLES[entry.status] || STATUS_STYLES.unknown;
                                        const StatusIcon = st.icon;
                                        return (
                                            <span
                                                key={entry.name}
                                                style={{
                                                    display: "flex",
                                                    alignItems: "center",
                                                    gap: 4,
                                                    fontSize: 11,
                                                    color: st.text,
                                                    fontWeight: 600,
                                                }}
                                            >
                                                <StatusIcon size={12} />
                                                {entry.name}
                                            </span>
                                        );
                                    })}
                                </div>
                            </div>

                            {/* Expanded detail */}
                            {isExpanded && (
                                <div style={{ padding: "0 14px 14px" }}>
                                    {entries.map((entry) => {
                                        const providerHealth = health[entry.name];
                                        const st = STATUS_STYLES[entry.status] || STATUS_STYLES.unknown;

                                        return (
                                            <div
                                                key={entry.name}
                                                style={{
                                                    background: "rgba(15, 23, 42, 0.5)",
                                                    border: `1px solid ${st.text}20`,
                                                    borderRadius: 8,
                                                    padding: 14,
                                                    marginTop: 8,
                                                }}
                                            >
                                                <div
                                                    style={{
                                                        display: "flex",
                                                        alignItems: "center",
                                                        justifyContent: "space-between",
                                                        marginBottom: 10,
                                                    }}
                                                >
                                                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                                        <Zap size={14} style={{ color: meta.color }} />
                                                        <span style={{ fontSize: 13, fontWeight: 700, color: "#E2E8F0" }}>
                                                            {entry.name}
                                                        </span>
                                                        <span
                                                            style={{
                                                                fontSize: 10,
                                                                padding: "2px 6px",
                                                                borderRadius: 4,
                                                                background: st.bg,
                                                                color: st.text,
                                                                fontWeight: 700,
                                                                textTransform: "uppercase" as const,
                                                            }}
                                                        >
                                                            {entry.status}
                                                        </span>
                                                    </div>

                                                    {/* Toggle button */}
                                                    <button
                                                        onClick={() =>
                                                            toggleProvider(entry.name, entry.status === "disabled")
                                                        }
                                                        style={{
                                                            background:
                                                                entry.status === "disabled"
                                                                    ? "rgba(16, 185, 129, 0.1)"
                                                                    : "rgba(239, 68, 68, 0.1)",
                                                            border: `1px solid ${entry.status === "disabled" ? "#10B98130" : "#EF444430"}`,
                                                            borderRadius: 6,
                                                            padding: "3px 8px",
                                                            cursor: "pointer",
                                                            display: "flex",
                                                            alignItems: "center",
                                                            gap: 4,
                                                            fontSize: 10,
                                                            color:
                                                                entry.status === "disabled" ? "#10B981" : "#EF4444",
                                                            fontWeight: 600,
                                                        }}
                                                    >
                                                        <Power size={10} />
                                                        {entry.status === "disabled" ? "Enable" : "Disable"}
                                                    </button>
                                                </div>

                                                {/* Metrics grid */}
                                                {providerHealth && (
                                                    <div
                                                        style={{
                                                            display: "grid",
                                                            gridTemplateColumns: "repeat(4, 1fr)",
                                                            gap: 8,
                                                            marginBottom: 10,
                                                        }}
                                                    >
                                                        <MetricPill
                                                            label="Latency"
                                                            value={`${providerHealth.avg_latency_ms.toFixed(0)}ms`}
                                                            color={
                                                                providerHealth.avg_latency_ms < 500
                                                                    ? "#10B981"
                                                                    : providerHealth.avg_latency_ms < 2000
                                                                        ? "#F59E0B"
                                                                        : "#EF4444"
                                                            }
                                                        />
                                                        <MetricPill
                                                            label="Failures"
                                                            value={String(providerHealth.consecutive_failures)}
                                                            color={
                                                                providerHealth.consecutive_failures === 0
                                                                    ? "#10B981"
                                                                    : "#EF4444"
                                                            }
                                                        />
                                                        <MetricPill
                                                            label="Last OK"
                                                            value={
                                                                providerHealth.last_success
                                                                    ? formatTimeAgo(providerHealth.last_success)
                                                                    : "never"
                                                            }
                                                            color="#94A3B8"
                                                        />
                                                        <MetricPill
                                                            label="Last Fail"
                                                            value={
                                                                providerHealth.last_failure
                                                                    ? formatTimeAgo(providerHealth.last_failure)
                                                                    : "never"
                                                            }
                                                            color="#94A3B8"
                                                        />
                                                    </div>
                                                )}

                                                {/* Capabilities */}
                                                <div style={{ display: "flex", flexWrap: "wrap" as const, gap: 4 }}>
                                                    {entry.capabilities.map((cap) => (
                                                        <span
                                                            key={cap}
                                                            style={{
                                                                fontSize: 10,
                                                                padding: "2px 6px",
                                                                borderRadius: 4,
                                                                background: "rgba(148, 163, 184, 0.08)",
                                                                color: "#94A3B8",
                                                                fontFamily: "monospace",
                                                            }}
                                                        >
                                                            {cap}
                                                        </span>
                                                    ))}
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Empty state */}
            {(!registry?.active_domains || registry.active_domains.length === 0) && !loading && (
                <div
                    style={{
                        textAlign: "center" as const,
                        padding: "24px 0",
                        color: "#64748B",
                        fontSize: 13,
                    }}
                >
                    <Shield size={24} style={{ margin: "0 auto 8px", opacity: 0.5 }} />
                    <p style={{ margin: 0 }}>No external providers registered</p>
                    <p style={{ margin: "4px 0 0", fontSize: 11 }}>
                        Set API keys in <code style={{ color: "#D4AF37" }}>.env</code> to activate providers
                    </p>
                </div>
            )}
        </div>
    );
}

// ── Helper Components ───────────────────────────────────────────────────────

function MetricPill({ label, value, color }: { label: string; value: string; color: string }) {
    return (
        <div
            style={{
                background: "rgba(30, 41, 59, 0.5)",
                borderRadius: 6,
                padding: "6px 8px",
                textAlign: "center" as const,
            }}
        >
            <div style={{ fontSize: 9, color: "#64748B", textTransform: "uppercase" as const, letterSpacing: "0.05em" }}>
                {label}
            </div>
            <div style={{ fontSize: 13, fontWeight: 700, color, marginTop: 2 }}>{value}</div>
        </div>
    );
}

function formatTimeAgo(isoString: string): string {
    try {
        const then = new Date(isoString).getTime();
        const now = Date.now();
        const diff = Math.floor((now - then) / 1000);

        if (diff < 60) return `${diff}s ago`;
        if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
        return `${Math.floor(diff / 86400)}d ago`;
    } catch {
        return "—";
    }
}
